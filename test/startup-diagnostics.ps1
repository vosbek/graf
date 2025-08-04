#!/usr/bin/env pwsh
<#
.SYNOPSIS
  End-to-end diagnostics for local GraphRAG stack (Chroma, Neo4j, API) and frontend proxy.

.DESCRIPTION
  - Collects environment and Podman status
  - Verifies Chroma v2 health endpoint
  - Verifies Neo4j via cypher-shell inside container
  - Probes API liveness (/docs) and readiness (/api/v1/health/ready)
  - Optionally starts API in foreground (to surface logs) if not reachable
  - Optionally checks frontend -> backend connectivity
  - Summarizes pass/fail with actionable hints

.PARAMETER CheckFrontend
  Also test frontend dev server proxy to API (default: false)

.PARAMETER StartApiIfMissing
  If API is not reachable on port 8080, run uvicorn in foreground (default: false)
#>

param(
  [switch]$CheckFrontend = $false,
  [switch]$StartApiIfMissing = $false
)

$ErrorActionPreference = "Stop"

function Section {
  param([string]$Title)
  Write-Host ""
  Write-Host "=== $Title ===" -ForegroundColor Cyan
}

function Try-InvokeHttp {
  param(
    [string]$Url,
    [int]$TimeoutSec = 5
  )
  try {
    $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec
    return @{ ok = $true; code = $resp.StatusCode; body = $resp.Content }
  } catch {
    return @{ ok = $false; error = $_.Exception.Message }
  }
}

function Podman-Check {
  try {
    $ver = podman --version
    return @{ ok = $true; msg = $ver }
  } catch {
    return @{ ok = $false; msg = "Podman not available. On Windows, run 'podman machine init' then 'podman machine start' if needed." }
  }
}

function Check-Chroma {
  $r = Try-InvokeHttp "http://localhost:8000/api/v2/healthcheck" 5
  if ($r.ok) {
    Write-Host "Chroma v2 health: HTTP $($r.code)" -ForegroundColor Green
    return $true
  } else {
    Write-Warning "Chroma v2 health failed: $($r.error)"
    return $false
  }
}

function Check-Neo4j {
  try {
    podman exec codebase-rag-neo4j cypher-shell -u neo4j -p codebase-rag-2024 "RETURN 1" | Out-Null
    Write-Host "Neo4j cypher-shell: OK (RETURN 1 succeeded)" -ForegroundColor Green
    return $true
  } catch {
    Write-Warning "Neo4j cypher-shell failed: $($_.Exception.Message)"
    return $false
  }
}

function Check-Api {
  $docs = Try-InvokeHttp "http://localhost:8080/docs" 3
  $ready = Try-InvokeHttp "http://localhost:8080/api/v1/health/ready" 3

  $reachable = $false
  if ($docs.ok) {
    Write-Host "API /docs: HTTP $($docs.code)" -ForegroundColor Green
    $reachable = $true
  } else {
    Write-Warning "API /docs failed: $($docs.error)"
  }

  if ($ready.ok) {
    Write-Host "API readiness: HTTP $($ready.code)" -ForegroundColor Green
  } else {
    Write-Warning "API readiness failed: $($ready.error)"
  }

  return @{ reachable = $reachable; docs = $docs; ready = $ready }
}

function Start-Api-Foreground {
  Write-Host "`nStarting API in foreground to surface errors..." -ForegroundColor Yellow
  $env:APP_ENV = "development"
  $env:API_HOST = "0.0.0.0"
  $env:API_PORT = "8080"
  $env:NEO4J_URI = "bolt://localhost:7687"
  $env:NEO4J_USERNAME = "neo4j"
  $env:NEO4J_PASSWORD = "codebase-rag-2024"
  $env:NEO4J_DATABASE = "neo4j"
  $env:CHROMA_HOST = "localhost"
  $env:CHROMA_PORT = "8000"
  $env:LOG_LEVEL = "INFO"
  $env:EMBEDDING_MODEL = "microsoft/codebert-base"
  $env:AUTH_ENABLED = "false"

  python -m uvicorn src.main:app --host 0.0.0.0 --port 8080 --log-level info
}

function Check-Frontend-Proxy {
  $health = Try-InvokeHttp "http://localhost:3001/api/v1/health/" 5
  $repos = Try-InvokeHttp "http://localhost:3001/api/v1/index/repositories" 5

  if ($health.ok) {
    Write-Host "Frontend proxy -> API health: HTTP $($health.code)" -ForegroundColor Green
  } else {
    Write-Warning "Frontend proxy -> API health failed: $($health.error)"
  }

  if ($repos.ok) {
    Write-Host "Frontend proxy -> API repositories: HTTP $($repos.code)" -ForegroundColor Green
  } else {
    Write-Warning "Frontend proxy -> API repositories failed: $($repos.error)"
  }

  return @{ health = $health; repos = $repos }
}

# 1) Environment snapshot
Section "Environment"
Write-Host "PWD: $(Get-Location)" -ForegroundColor Gray
$pod = Podman-Check
if ($pod.ok) {
  Write-Host "Podman: $($pod.msg)" -ForegroundColor Green
} else {
  Write-Warning $pod.msg
}

# 2) Containers status
Section "Containers"
try {
  podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
} catch {
  Write-Warning "podman ps failed: $($_.Exception.Message)"
}

# 3) Service checks
Section "Chroma v2"
$chromaOk = Check-Chroma

Section "Neo4j"
$neo4jOk = Check-Neo4j

Section "API"
$api = Check-Api
$apiOk = $api.reachable -and $api.ready.ok

# 4) Optional: start API if missing and recheck
if (-not $api.reachable -and $StartApiIfMissing) {
  Section "API Autostart (foreground)"
  Start-Api-Foreground
  # After user exits the foreground server, re-check quickly
  Section "API (post-start) quick check"
  $api = Check-Api
  $apiOk = $api.reachable -and $api.ready.ok
}

# 5) Optional: Frontend proxy checks
$feOk = $true
if ($CheckFrontend) {
  Section "Frontend -> Backend proxy"
  $fe = Check-Frontend-Proxy
  $feOk = $fe.health.ok -and $fe.repos.ok
}

# 6) Summary
Section "Summary"
$summary = [PSCustomObject]@{
  ChromaV2_OK      = $chromaOk
  Neo4j_OK         = $neo4jOk
  Api_Docs_OK      = $api.docs.ok
  Api_Ready_OK     = $api.ready.ok
  Frontend_Proxy   = $(if ($CheckFrontend) { if ($feOk) { "OK" } else { "FAILED" } } else { "SKIPPED" })
}

$summary | Format-Table | Out-String | Write-Host

Write-Host ""
if (-not $chromaOk) {
  Write-Host "- Chroma v2 not healthy: inspect logs with 'podman logs -f codebase-rag-chromadb'" -ForegroundColor Yellow
}
if (-not $neo4jOk) {
  Write-Host "- Neo4j not ready: run 'podman logs -f codebase-rag-neo4j' and recheck cypher-shell RETURN 1" -ForegroundColor Yellow
}
if (-not $api.docs.ok) {
  Write-Host "- API /docs not reachable: run API in foreground: 'python -m uvicorn src.main:app --host 0.0.0.0 --port 8080 --log-level debug'" -ForegroundColor Yellow
}
if ($api.docs.ok -and -not $api.ready.ok) {
  Write-Host "- API reachable but not ready: background initialization (Chroma/Neo4j/CodeBERT) may still be running." -ForegroundColor Yellow
}
if ($CheckFrontend -and -not $feOk) {
  Write-Host "- Frontend proxy failing: ensure API is reachable on 8080 and frontend dev server is on 3001." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Diagnostics complete." -ForegroundColor Green