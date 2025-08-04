param(
  [ValidateSet("health","dry-run","live","e2e")]
  [string]$Mode = "e2e",
  [string]$Repository = "jmeter-ai",
  [string]$LocalPath = "C:\devl\workspaces\jmeter-ai",
  [string]$ApiBase = "http://localhost:8080",
  [switch]$Restart,
  [int]$TimeoutSec = 900,
  [int]$PollIntervalSec = 3,
  [switch]$VerboseLogs
)

# Fail fast on non-200/JSON issues
$ErrorActionPreference = "Stop"

$ErrorActionPreference = "Stop"

function Info($msg){ Write-Host "[INFO]  $msg" -ForegroundColor Green }
function Warn($msg){ Write-Host "[WARN]  $msg" -ForegroundColor Yellow }
function Err($msg){ Write-Host "[ERROR] $msg" -ForegroundColor Red }

function Try-InvokeJson([string]$Method, [string]$Url, [string]$BodyJson = $null, [int]$Retries = 5, [int]$BackoffMs = 500) {
  for ($i = 0; $i -lt $Retries; $i++) {
    try {
      if ($VerboseLogs) { Write-Host "HTTP $Method $Url (attempt $($i+1)/$Retries)" -ForegroundColor DarkGray }
      if ($Method -eq "GET") {
        return Invoke-RestMethod -Method GET -Uri $Url -TimeoutSec 25 -ErrorAction Stop
      } elseif ($Method -eq "POST") {
        if ($null -ne $BodyJson) {
          return Invoke-RestMethod -Method POST -Uri $Url -ContentType "application/json" -Body $BodyJson -TimeoutSec 60 -ErrorAction Stop
        } else {
          return Invoke-RestMethod -Method POST -Uri $Url -TimeoutSec 60 -ErrorAction Stop
        }
      } elseif ($Method -eq "DELETE") {
        return Invoke-RestMethod -Method DELETE -Uri $Url -TimeoutSec 25 -ErrorAction Stop
      } else {
        throw "Unsupported method: $Method"
      }
    } catch {
      $msg = $_.Exception.Message
      # Retry on transient 503/502/connection resets during app initialization
      if ($msg -match "503|502|timed out|connection.*reset|refused") {
        if ($i -lt ($Retries - 1)) {
          if ($VerboseLogs) { Write-Host "Transient error, backing off: $msg" -ForegroundColor DarkYellow }
          Start-Sleep -Milliseconds ($BackoffMs * [math]::Pow(2, $i))
          continue
        }
      }
      Warn "HTTP call failed: $Method $Url :: $msg"
      return $null
    }
  }
}

function Wait-For-Status([string]$TaskId, [int]$Timeout, [int]$Interval) {
  $deadline = (Get-Date).AddSeconds($Timeout)
  while ((Get-Date) -lt $deadline) {
    $statusUrl = "$ApiBase/api/v1/index/status/$TaskId"
    $status = Try-InvokeJson -Method "GET" -Url $statusUrl
    if ($status -ne $null) {
      if ($VerboseLogs) {
        Write-Host ("Status: " + ($status | ConvertTo-Json -Depth 8)) -ForegroundColor DarkGray
      }
      $st = $status.status
      if ($st -eq "completed" -or $st -eq "COMPLETED") {
        return @{ result = $status; success = $true }
      }
      if ($st -eq "failed" -or $st -eq "FAILED") {
        return @{ result = $status; success = $false }
      }
    }
    Start-Sleep -Seconds $Interval
  }
  return @{ result = $null; success = $false }
}

function Health-Probe() {
  Info "==== API Health ===="
  # Wait for /health/live to become available
  $deadline = (Get-Date).AddSeconds(60)
  $live = $null
  while ((Get-Date) -lt $deadline) {
    $live = Try-InvokeJson -Method "GET" -Url "$ApiBase/api/v1/health/live"
    if ($live -and $live.status) { break }
    Start-Sleep -Seconds 1
  }
  if ($live) { Write-Host ($live | ConvertTo-Json -Depth 8) } else { Warn "Live check failed" }

  # Readiness often lags — poll for a short window before proceeding
  $ready = $null
  $deadline2 = (Get-Date).AddSeconds(120)
  while ((Get-Date) -lt $deadline2) {
    $ready = Try-InvokeJson -Method "GET" -Url "$ApiBase/api/v1/health/ready"
    if ($ready -and ($ready.status -eq "ready" -or $ready.status -eq "healthy" -or $ready.status -eq "degraded")) { break }
    Start-Sleep -Seconds 2
  }
  if ($ready) { Write-Host ($ready | ConvertTo-Json -Depth 8) } else { Warn "Readiness check failed" }

  Info "==== Component Diagnostics ===="
  # Prefer comprehensive diag if available
  $comp = Try-InvokeJson -Method "GET" -Url "$ApiBase/api/v1/health/enhanced/comprehensive"
  if ($comp) {
    Write-Host ($comp | ConvertTo-Json -Depth 8)
  } else {
    # fallbacks
    $diagNeo = Try-InvokeJson -Method "GET" -Url "$ApiBase/api/v1/health/enhanced/neo4j"
    if ($diagNeo) { Write-Host ($diagNeo | ConvertTo-Json -Depth 8) }
    $diagChroma = Try-InvokeJson -Method "GET" -Url "$ApiBase/api/v1/health/enhanced/chroma"
    if ($diagChroma) { Write-Host ($diagChroma | ConvertTo-Json -Depth 8) }
    $diagEmbed = Try-InvokeJson -Method "GET" -Url "$ApiBase/api/v1/health/enhanced/embedding"
    if ($diagEmbed) { Write-Host ($diagEmbed | ConvertTo-Json -Depth 8) }
  }
}

function Start-Ingestion([switch]$Local, [switch]$DryRun) {
  if ($Local) {
    $url = "$ApiBase/api/v1/index/repository/local"
    if ($DryRun) { $url += "?dry_run=true" }
    $body = @{ name = $Repository; local_path = $LocalPath } | ConvertTo-Json -Depth 8
    # POST can still race while API initializes; give it some retries explicitly
    $resp = Try-InvokeJson -Method "POST" -Url $url -BodyJson $body -Retries 8 -BackoffMs 750
    return $resp
  } else {
    $url = "$ApiBase/api/v1/index/repository"
    if ($DryRun) { $url += "?dry_run=true" }
    $body = @{
      name = $Repository
      url  = "https://github.com/dummy/$Repository"
      branch = "main"
      maven_enabled = $true
    } | ConvertTo-Json -Depth 8
    $resp = Try-InvokeJson -Method "POST" -Url $url -BodyJson $body -Retries 8 -BackoffMs 750
    return $resp
  }
}

function Post-Validation([switch]$LiveMode) {
  Info "==== Post-Ingestion Validation ===="
  # Neo4j: basic repo existence
  $repoNameParam = [uri]::EscapeDataString($Repository)
  $viz = Try-InvokeJson -Method "GET" -Url "$ApiBase/api/v1/graph/visualization?repository=$repoNameParam&depth=2&limit_nodes=300&limit_edges=800"
  if ($viz) {
    $nodesCount = 0; $edgesCount = 0
    if ($viz.nodes) { $nodesCount = ($viz.nodes | Measure-Object).Count }
    if ($viz.edges) { $edgesCount = ($viz.edges | Measure-Object).Count }
    Write-Host ("Visualization nodes=$nodesCount edges=$edgesCount") -ForegroundColor Cyan
  } else {
    Warn "Visualization call failed or returned null"
  }

  # Semantic search sanity if live mode: expects some results
  if ($LiveMode) {
    $semanticUrl = "$ApiBase/api/v1/query/semantic"
    $payload = @{ query = "repo:$Repository"; limit = 3; min_score = 0.1 } | ConvertTo-Json -Depth 8
    $sem = Try-InvokeJson -Method "POST" -Url $semanticUrl -BodyJson $payload
    if ($sem) {
      $total = 0
      if ($sem.total_results) { $total = [int]$sem.total_results }
      elseif ($sem.results) { $total = ($sem.results | Measure-Object).Count }
      Write-Host ("Semantic results total=$total") -ForegroundColor Cyan
    } else {
      Warn "Semantic search failed or returned empty"
    }
  }
}

# Main
try {
  if ($Restart) {
    Info "Restart requested; invoking stop.ps1 then START.ps1"
    if (Test-Path ".\stop.ps1") { & .\stop.ps1 } else { Warn "stop.ps1 not found in workspace" }
    if (Test-Path ".\START.ps1") { & .\START.ps1 } else { Warn "START.ps1 not found in workspace" }
    # Allow initialization window for services to bind (Neo4j, Chroma, API)
    Start-Sleep -Seconds 8
  }

  switch ($Mode) {
    "health" {
      Health-Probe
      break
    }
    "dry-run" {
      Health-Probe
      $isLocal = $true
      if (!(Test-Path $LocalPath)) { Warn "LocalPath not found: $LocalPath; using remote indexing payload"; $isLocal = $false }
      Info "==== Starting DRY-RUN ingestion ===="
      $resp = Start-Ingestion -Local:$isLocal -DryRun:$true
      if (-not $resp) { throw "Dry-run start failed" }
      # Poll final state
      $deadline = (Get-Date).AddSeconds($TimeoutSec)
      $finalStatus = $null
      while ((Get-Date) -lt $deadline) {
        $all = Try-InvokeJson -Method "GET" -Url "$ApiBase/api/v1/index/status"
        if ($all -and $all.task_statuses) {
          $matches = @()
          foreach ($k in $all.task_statuses.Keys) {
            $st = $all.task_statuses[$k]
            if ($st.repository_name -eq $Repository) { $matches += @{key=$k; st=$st} }
          }
          if ($matches.Count -gt 0) {
            $sorted = $matches | Sort-Object { $_.st.started_at } -Descending
            $candidate = $sorted[0].st
            if ($VerboseLogs) { Write-Host ("Polling: " + ($candidate | ConvertTo-Json -Depth 8)) -ForegroundColor DarkGray }
            if ($candidate.status -match "completed|COMPLETED|failed|FAILED") { $finalStatus = $candidate; break }
          }
        }
        Start-Sleep -Seconds $PollIntervalSec
      }
      if (-not $finalStatus) { Err "Timed out waiting for dry-run status"; exit 2 }
      Info ("Final status: " + ($finalStatus | ConvertTo-Json -Depth 8))
      if (-not ($finalStatus.status -match "completed|COMPLETED")) { Err "Dry-run ended with failure"; exit 3 }
      Post-Validation -LiveMode:$false
      break
    }
    "live" {
      Health-Probe
      $isLocal = $true
      if (!(Test-Path $LocalPath)) { Warn "LocalPath not found: $LocalPath; using remote indexing payload"; $isLocal = $false }
      Info "==== Starting LIVE ingestion ===="
      $resp = Start-Ingestion -Local:$isLocal -DryRun:$false
      if (-not $resp) { throw "Live ingestion start failed" }
      # Poll final state
      $deadline = (Get-Date).AddSeconds($TimeoutSec)
      $finalStatus = $null
      while ((Get-Date) -lt $deadline) {
        $all = Try-InvokeJson -Method "GET" -Url "$ApiBase/api/v1/index/status"
        if ($all -and $all.task_statuses) {
          $matches = @()
          foreach ($k in $all.task_statuses.Keys) {
            $st = $all.task_statuses[$k]
            if ($st.repository_name -eq $Repository) { $matches += @{key=$k; st=$st} }
          }
          if ($matches.Count -gt 0) {
            $sorted = $matches | Sort-Object { $_.st.started_at } -Descending
            $candidate = $sorted[0].st
            if ($VerboseLogs) { Write-Host ("Polling: " + ($candidate | ConvertTo-Json -Depth 8)) -ForegroundColor DarkGray }
            if ($candidate.status -match "completed|COMPLETED|failed|FAILED") { $finalStatus = $candidate; break }
          }
        }
        Start-Sleep -Seconds $PollIntervalSec
      }
      if (-not $finalStatus) { Err "Timed out waiting for live status"; exit 2 }
      Info ("Final status: " + ($finalStatus | ConvertTo-Json -Depth 8))
      if (-not ($finalStatus.status -match "completed|COMPLETED")) { Err "Live ingestion ended with failure"; exit 4 }
      Post-Validation -LiveMode:$true
      break
    }
    "e2e" {
      # Run health -> dry-run -> live (if dry-run passes)
      Health-Probe
      $isLocal = $true
      if (!(Test-Path $LocalPath)) { Warn "LocalPath not found: $LocalPath; using remote indexing payload"; $isLocal = $false }

      Info "==== DRY-RUN stage ===="
      $resp1 = Start-Ingestion -Local:$isLocal -DryRun:$true
      if (-not $resp1) { throw "Dry-run start failed" }

      # Poll dry-run
      $deadline1 = (Get-Date).AddSeconds($TimeoutSec)
      $dryFinal = $null
      while ((Get-Date) -lt $deadline1) {
        $all1 = Try-InvokeJson -Method "GET" -Url "$ApiBase/api/v1/index/status"
        if ($all1 -and $all1.task_statuses) {
          $matches1 = @()
          foreach ($k in $all1.task_statuses.Keys) {
            $st1 = $all1.task_statuses[$k]
            if ($st1.repository_name -eq $Repository) { $matches1 += @{key=$k; st=$st1} }
          }
          if ($matches1.Count -gt 0) {
            $sorted1 = $matches1 | Sort-Object { $_.st.started_at } -Descending
            $cand1 = $sorted1[0].st
            if ($VerboseLogs) { Write-Host ("Polling: " + ($cand1 | ConvertTo-Json -Depth 8)) -ForegroundColor DarkGray }
            if ($cand1.status -match "completed|COMPLETED|failed|FAILED") { $dryFinal = $cand1; break }
          }
        }
        Start-Sleep -Seconds $PollIntervalSec
      }
      if (-not $dryFinal) { Err "Timed out waiting for dry-run status"; exit 2 }
      if (-not ($dryFinal.status -match "completed|COMPLETED")) { Err "Dry-run ended with failure"; exit 3 }
      Info "Dry-run completed; proceeding to LIVE ingestion"

      Info "==== LIVE stage ===="
      $resp2 = Start-Ingestion -Local:$isLocal -DryRun:$false
      if (-not $resp2) { throw "Live ingestion start failed" }

      # Poll live
      $deadline2 = (Get-Date).AddSeconds($TimeoutSec)
      $liveFinal = $null
      while ((Get-Date) -lt $deadline2) {
        $all2 = Try-InvokeJson -Method "GET" -Url "$ApiBase/api/v1/index/status"
        if ($all2 -and $all2.task_statuses) {
          $matches2 = @()
          foreach ($k in $all2.task_statuses.Keys) {
            $st2 = $all2.task_statuses[$k]
            if ($st2.repository_name -eq $Repository) { $matches2 += @{key=$k; st=$st2} }
          }
          if ($matches2.Count -gt 0) {
            $sorted2 = $matches2 | Sort-Object { $_.st.started_at } -Descending
            $cand2 = $sorted2[0].st
            if ($VerboseLogs) { Write-Host ("Polling: " + ($cand2 | ConvertTo-Json -Depth 8)) -ForegroundColor DarkGray }
            if ($cand2.status -match "completed|COMPLETED|failed|FAILED") { $liveFinal = $cand2; break }
          }
        }
        Start-Sleep -Seconds $PollIntervalSec
      }
      if (-not $liveFinal) { Err "Timed out waiting for live status"; exit 2 }
      if (-not ($liveFinal.status -match "completed|COMPLETED")) { Err "Live ingestion ended with failure"; exit 4 }
      Post-Validation -LiveMode:$true
      break
    }
  }

  exit 0
} catch {
  Err $_.Exception.Message
  if ($VerboseLogs) { Write-Host $_.ScriptStackTrace -ForegroundColor DarkGray }
  exit 1
}