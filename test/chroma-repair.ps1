#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Chroma v2 quick diagnostics and repair: verify health, collection, and round-trip.

.DESCRIPTION
  - GET /api/v2/healthcheck
  - GET /api/v2/info (if available)
  - Ensure collection 'codebase_chunks' exists (create if missing)
  - Add and query a diagnostic document to validate tenant/collection path
#>

$ErrorActionPreference = "Stop"

function Section { param([string]$Title) Write-Host "`n=== $Title ===" -ForegroundColor Cyan }
function TryHttp {
  param([string]$Url, [string]$Method = "GET", [object]$Body = $null, [int]$TimeoutSec = 10)
  try {
    if ($Body -ne $null) {
      $json = $Body | ConvertTo-Json -Depth 5
      $resp = Invoke-WebRequest -Uri $Url -Method $Method -ContentType "application/json" -Body $json -UseBasicParsing -TimeoutSec $TimeoutSec
    } else {
      $resp = Invoke-WebRequest -Uri $Url -Method $Method -UseBasicParsing -TimeoutSec $TimeoutSec
    }
    return @{ ok=$true; code=$resp.StatusCode; body=$resp.Content }
  } catch {
    return @{ ok=$false; error=$_.Exception.Message; code=($_.Exception.Response.StatusCode.value__ 2>$null) }
  }
}

Section "Chroma v2 Health"
$r = TryHttp "http://localhost:8000/api/v2/healthcheck"
if ($r.ok) {
  Write-Host "Health: HTTP $($r.code) $($r.body)" -ForegroundColor Green
} else {
  Write-Warning "Health failed: $($r.error)"
}

Section "Chroma Info"
$info = TryHttp "http://localhost:8000/api/v2/info"
if ($info.ok) {
  Write-Host "Info: HTTP $($info.code) $($info.body)" -ForegroundColor Green
} else {
  Write-Host "Info endpoint failed or not available: $($info.error)" -ForegroundColor Yellow
}

$collection = "codebase_chunks"

Section "Ensure collection '$collection'"
$create = TryHttp "http://localhost:8000/api/v2/collections" "POST" @{ name = $collection }
if ($create.ok -and ($create.code -eq 201 -or $create.code -eq 200)) {
  Write-Host "Collection ensured/created: $collection (HTTP $($create.code))" -ForegroundColor Green
} elseif ($create.code -eq 409) {
  Write-Host "Collection already exists: $collection" -ForegroundColor Yellow
} else {
  Write-Warning "Collection create failed: $($create.error)"
}

Section "Round-trip add/query"
$add = TryHttp "http://localhost:8000/api/v2/collections/$collection/add" "POST" @{
  ids = @("diag_1")
  documents = @("diagnostic document for collection validation")
}
if ($add.ok) {
  Write-Host "Add doc: HTTP $($add.code)" -ForegroundColor Green
} else {
  Write-Warning "Add failed: $($add.error)"
}

$query = TryHttp "http://localhost:8000/api/v2/collections/$collection/query" "POST" @{
  query_texts = @("diagnostic")
  n_results = 1
}
if ($query.ok) {
  Write-Host "Query: HTTP $($query.code) $($query.body)" -ForegroundColor Green
} else {
  Write-Warning "Query failed: $($query.error)"
}

Write-Host "`nChroma repair diagnostics complete." -ForegroundColor Cyan