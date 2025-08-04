#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Start/Restart local GraphRAG stack (ChromaDB, Neo4j) and run API with CodeBERT-only
.DESCRIPTION
    - Brings down any previous stacks
    - Starts podman-compose.dev.yml (Chroma, Neo4j, Redis, Postgres)
    - Waits for health (with extended warmup on Windows)
    - Exports API environment and starts FastAPI locally (uvicorn)
#>

param(
    [switch]$RebuildImages = $false,
    [switch]$UseComposeApi = $false,   # if set, expects a prebuilt image and enabled api service in compose
    [int]$ApiPort = 8080
)

$ErrorActionPreference = "Stop"

function Wait-For-Http200 {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 240,
        [int]$IntervalSeconds = 5
    )
    $elapsed = 0
    while ($elapsed -lt $TimeoutSeconds) {
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
            if ($resp.StatusCode -eq 200) { return $true }
        } catch {
            # ignore
        }
        Start-Sleep -Seconds $IntervalSeconds
        $elapsed += $IntervalSeconds
    }
    return $false
}

function Wait-For-ProcessHealthy {
    param(
        [string]$ContainerName,
        [string]$Cmd,
        [int]$TimeoutSeconds = 240,
        [int]$IntervalSeconds = 5
    )
    $elapsed = 0
    while ($elapsed -lt $TimeoutSeconds) {
        try {
            podman exec $ContainerName $Cmd | Out-Null
            return $true
        } catch {
            # ignore
        }
        Start-Sleep -Seconds $IntervalSeconds
        $elapsed += $IntervalSeconds
    }
    return $false
}

Write-Host "=== GraphRAG Local Startup ===" -ForegroundColor Green
Write-Host "Using podman-compose.dev.yml for services" -ForegroundColor Cyan

# Optional: rebuild api image if requested
if ($RebuildImages) {
    Write-Host "Rebuilding API image (docker/Dockerfile.api)..." -ForegroundColor Yellow
    podman build -t codebase-rag-api -f docker/Dockerfile.api .
}

# Bring down any previous stacks (suppress benign errors)
Write-Host "Stopping any previous compose stacks..." -ForegroundColor Yellow
try { podman-compose -f podman-compose.dev.yml down 2>$null } catch {}
try { podman-compose -f podman-compose-services-only.yml down 2>$null } catch {}
try { podman-compose -f docker-compose.yml down 2>$null } catch {}

# Start dev services
Write-Host "Starting podman-compose.dev.yml..." -ForegroundColor Green
podman-compose -f podman-compose.dev.yml up -d

# Wait for Chroma heartbeat (v2 healthcheck; old v1 is deprecated)
Write-Host "Waiting for ChromaDB to become ready (http://localhost:8000/api/v2/healthcheck)..." -ForegroundColor Yellow
$chromaReady = Wait-For-Http200 -Url "http://localhost:8000/api/v2/healthcheck" -TimeoutSeconds 300 -IntervalSeconds 5
if (-not $chromaReady) {
    Write-Warning "ChromaDB did not reach 200 within timeout. Check logs: podman logs -f codebase-rag-chromadb"
}

# Wait for Neo4j to become ready using proper exec arguments (avoid shell parsing issues)
Write-Host "Waiting for Neo4j to become ready..." -ForegroundColor Yellow
$neo4jElapsed = 0
$neo4jTimeout = 300
while ($neo4jElapsed -lt $neo4jTimeout) {
    try {
        podman exec codebase-rag-neo4j cypher-shell -u neo4j -p codebase-rag-2024 "RETURN 1" | Out-Null
        break
    } catch {
        Start-Sleep -Seconds 5
        $neo4jElapsed += 5
    }
}
if ($neo4jElapsed -ge $neo4jTimeout) {
    Write-Warning "Neo4j did not become ready within timeout. Check logs: podman logs -f codebase-rag-neo4j"
}

if ($UseComposeApi) {
    Write-Host "Starting API via compose (expects api service enabled and image prebuilt)..." -ForegroundColor Green
    podman-compose -f podman-compose.dev.yml up -d
    Write-Host "API will self-healthcheck on /api/v1/health/ready" -ForegroundColor Cyan
    Write-Host "To view logs: podman logs -f codebase-rag-api" -ForegroundColor DarkGray
    exit 0
}

# Kill any existing Python processes (local run mode)
Write-Host "Cleaning up existing local python API processes..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force

# Export environment for local API run
$env:APP_ENV = "development"
$env:API_HOST = "0.0.0.0"
$env:API_PORT = "$ApiPort"
$env:NEO4J_URI = "bolt://localhost:7687"
$env:NEO4J_USERNAME = "neo4j"
$env:NEO4J_PASSWORD = "codebase-rag-2024"
$env:NEO4J_DATABASE = "neo4j"
$env:CHROMA_HOST = "localhost"
$env:CHROMA_PORT = "8000"
$env:LOG_LEVEL = "INFO"
$env:EMBEDDING_MODEL = "microsoft/codebert-base"
$env:AUTH_ENABLED = "false"

Write-Host "`nStarting API locally on port $ApiPort..." -ForegroundColor Green
Write-Host "  Neo4j: bolt://localhost:7687" -ForegroundColor White
Write-Host "  ChromaDB: localhost:8000" -ForegroundColor White
Write-Host "  API Port: $ApiPort" -ForegroundColor White
Write-Host "  CodeBERT: microsoft/codebert-base (768-d, no fallbacks)" -ForegroundColor Cyan

# Run Uvicorn in foreground to surface startup errors clearly and ensure process is actually running
Write-Host "`nStarting API (foreground) to surface logs..." -ForegroundColor Yellow
python -m uvicorn src.main:app --host 0.0.0.0 --port $ApiPort --log-level info

# If you prefer background execution, comment the line above and uncomment the block below:
# Start-Process -FilePath "python" -ArgumentList "-m uvicorn src.main:app --host 0.0.0.0 --port $ApiPort --log-level info" -NoNewWindow
# Write-Host "`nPolling API readiness at http://localhost:$ApiPort/api/v1/health/ready ..." -ForegroundColor Yellow
# $apiReady = Wait-For-Http200 -Url "http://localhost:$ApiPort/api/v1/health/ready" -TimeoutSeconds 600 -IntervalSeconds 5
# if ($apiReady) {
#     Write-Host "API is ready." -ForegroundColor Green
# } else {
#     Write-Warning "API did not become ready in time. Check: python logs or http://localhost:$ApiPort/docs"
# }

Write-Host "Done." -ForegroundColor Green