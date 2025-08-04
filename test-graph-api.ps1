# Robust graph API test with both GET (visualization) and direct POST (parameter echo)
# Ensures repository parameter binding all the way through driver regardless of client path.
# Compatible with Windows PowerShell 5.x (no ternary operator) and prints full error bodies.

param(
  [string]$Repository = "jmeter-ai",
  [int]$Depth = 2,
  [int]$LimitNodes = 300,
  [int]$LimitEdges = 800,
  [switch]$Trace
)

$ErrorActionPreference = 'Stop'

function Show-Section([string]$title) {
  Write-Host ""
  Write-Host ("==== {0} ====" -f $title) -ForegroundColor Cyan
}

function Show-ErrorBody {
  param([System.Management.Automation.ErrorRecord]$Err)
  if ($Err -and $Err.Exception -and $Err.Exception.Response) {
    try {
      $reader = New-Object System.IO.StreamReader($Err.Exception.Response.GetResponseStream())
      $text = $reader.ReadToEnd()
      if ($text) { Write-Host $text } else { Write-Host "(empty error response)" }
    } catch {
      Write-Host $Err.Exception.Message
    }
  } else {
    if ($Err -and $Err.Exception) { Write-Host $Err.Exception.Message } else { Write-Host "(no exception body)" }
  }
}

# Compute trace string for PS5 (no ternary)
$traceVal = "false"
if ($Trace.IsPresent) { $traceVal = "true" }

# 0) Graph router reachability probes
Show-Section "GET /api/v1/graph/ping (router reachability)"
try {
  $respP = Invoke-WebRequest -UseBasicParsing -Method Get -Uri "http://localhost:8080/api/v1/graph/ping"
  Write-Host ("Status Code: {0}" -f $respP.StatusCode)
  Write-Host ($respP.Content)
} catch {
  Write-Host "ERROR"
  if ($_.Exception.Response) { Write-Host ("HTTP Status: {0}" -f $_.Exception.Response.StatusCode) }
  Show-ErrorBody -Err $_
}

Show-Section "GET /api/v1/graph/diag (app readiness)"
try {
  $respD = Invoke-WebRequest -UseBasicParsing -Method Get -Uri "http://localhost:8080/api/v1/graph/diag"
  Write-Host ("Status Code: {0}" -f $respD.StatusCode)
  Write-Host ($respD.Content)
} catch {
  Write-Host "ERROR"
  if ($_.Exception.Response) { Write-Host ("HTTP Status: {0}" -f $_.Exception.Response.StatusCode) }
  Show-ErrorBody -Err $_
}

# 1) GET visualization (server builds Cypher and binds params internally)
Show-Section "GET /api/v1/graph/visualization"
$u = "http://localhost:8080/api/v1/graph/visualization?repository=$Repository&depth=$Depth&limit_nodes=$LimitNodes&limit_edges=$LimitEdges&trace=$traceVal"
Write-Host "URL: $u"
try {
  $resp = Invoke-WebRequest -UseBasicParsing -Method Get -Uri $u
  Write-Host ("Status Code: {0}" -f $resp.StatusCode)
  if ($resp.Content) {
    Write-Host $resp.Content
  } else {
    Write-Host "(empty body)"
  }
} catch {
  Write-Host "ERROR"
  if ($_.Exception.Response) {
    Write-Host ("HTTP Status: {0}" -f $_.Exception.Response.StatusCode)
  }
  Show-ErrorBody -Err $_
}

# 2) POST direct graph ping using explicit parameters (verifies driver binding end-to-end)
Show-Section "POST /api/v1/query/graph (parameter binding check)"
$cypher = 'MATCH (r:Repository {name: $repository}) RETURN count(r) AS repo_count'
$bodyObj = @{
  cypher = $cypher
  parameters = @{ repository = $Repository }
  read_only = $true
}
$bodyJson = $bodyObj | ConvertTo-Json -Depth 5
try {
  $resp2 = Invoke-WebRequest -UseBasicParsing -Method Post -Uri 'http://localhost:8080/api/v1/query/graph' -ContentType 'application/json' -Body $bodyJson
  Write-Host ("Status Code: {0}" -f $resp2.StatusCode)
  if ($resp2.Content) {
    Write-Host $resp2.Content
  } else {
    Write-Host "(empty body)"
  }
} catch {
  Write-Host "ERROR"
  if ($_.Exception.Response) {
    Write-Host ("HTTP Status: {0}" -f $_.Exception.Response.StatusCode)
  }
  Show-ErrorBody -Err $_
}

# 3) POST full visualization cypher equivalent (optional deeper check)
Show-Section "POST /api/v1/query/graph (visualization cypher equivalent)"
$vizCypher = @"
MATCH (r:Repository {name: $repository})
WITH r
OPTIONAL MATCH (r)-[e]-(n)
WITH r, e, n
RETURN
  [ { id: coalesce(r.id, toString(id(r))), labels: labels(r), name: coalesce(r.name, toString(id(r))), path: coalesce(r.path,''), size: coalesce(r.size,0) } ] AS nodes,
  collect(DISTINCT { source: coalesce(startNode(e).id, toString(id(startNode(e)))), target: coalesce(endNode(e).id, toString(id(endNode(e)))), type: type(e) }) AS edges
"@
$vizParams = @{
  repository = $Repository
}
$vizBodyObj = @{
  cypher = $vizCypher
  parameters = $vizParams
  read_only = $true
}
$vizBodyJson = $vizBodyObj | ConvertTo-Json -Depth 6

function Invoke-GraphPost {
  param([string]$BodyJson)
  try {
    $resp3 = Invoke-WebRequest -UseBasicParsing -Method Post -Uri 'http://localhost:8080/api/v1/query/graph' -ContentType 'application/json' -Body $BodyJson
    Write-Host ("Status Code: {0}" -f $resp3.StatusCode)
    if ($resp3.Content) { Write-Host $resp3.Content } else { Write-Host "(empty body)" }
    return $true
  } catch {
    Write-Host "ERROR"
    if ($_.Exception.Response) {
      Write-Host ("HTTP Status: {0}" -f $_.Exception.Response.StatusCode)
      Show-ErrorBody -Err $_
    } else {
      Write-Host $_.Exception.Message
    }
    return $false
  }
}

# Primary attempt
$ok = Invoke-GraphPost -BodyJson $vizBodyJson

# Fallback: try a simplified echo cypher to force diagnostics through the same endpoint
if (-not $ok) {
  Show-Section "POST /api/v1/query/graph (fallback diagnostics echo)"
  $echoCypher = 'RETURN $params AS params'
  $echoBody = @{
    cypher = $echoCypher
    parameters = @{ note = 'echo parameters for diagnostics'; repository = $Repository }
    read_only = $true
  } | ConvertTo-Json -Depth 6
  [void](Invoke-GraphPost -BodyJson $echoBody)
}