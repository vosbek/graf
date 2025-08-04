param(
  [string]$ApiBase = "http://localhost:8080",
  [string]$Repository = "jmeter-ai",
  [int]$Depth = 2,
  [int]$LimitNodes = 300,
  [int]$LimitEdges = 800,
  [switch]$VerboseLogs
)

$ErrorActionPreference = 'Stop'

function Info([string]$msg) {
  $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  Write-Host ("[{0}] [INFO] {1}" -f $ts, $msg)
}
function Warn([string]$msg) {
  $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  Write-Host ("[{0}] [WARN] {1}" -f $ts, $msg) -ForegroundColor Yellow
}
function Err([string]$msg) {
  $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  Write-Host ("[{0}] [ERROR] {1}" -f $ts, $msg) -ForegroundColor Red
}
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

# Utility: POST /api/v1/query/graph
function Invoke-GraphQuery {
  param(
    [string]$Cypher,
    [hashtable]$Parameters
  )
  $body = @{
    cypher = $Cypher
    parameters = $Parameters
    read_only = $true
  } | ConvertTo-Json -Depth 6
  try {
    $resp = Invoke-WebRequest -UseBasicParsing -Method Post -Uri "$ApiBase/api/v1/query/graph" -ContentType "application/json" -Body $body
    return $resp.Content
  } catch {
    Show-ErrorBody -Err $_
    return $null
  }
}

# Utility: GET
function Invoke-GetJson {
  param([string]$Url)
  try {
    $resp = Invoke-WebRequest -UseBasicParsing -Method Get -Uri $Url
    return $resp.Content
  } catch {
    Show-ErrorBody -Err $_
    return $null
  }
}

# 1) API health checks
Show-Section "API Health"
$health = Invoke-GetJson -Url "$ApiBase/api/v1/health/"
if ($health) { Write-Host $health } else { Warn "Health check failed" }
$ready = Invoke-GetJson -Url "$ApiBase/api/v1/health/ready"
if ($ready) { Write-Host $ready } else { Warn "Readiness check failed" }

# 2) Graph router reachability
Show-Section "Graph Router Ping/Diag"
$ping = Invoke-GetJson -Url "$ApiBase/api/v1/graph/ping"
if ($ping) { Write-Host ("Ping: " + $ping) } else { Warn "Ping failed" }
$diag = Invoke-GetJson -Url "$ApiBase/api/v1/graph/diag"
if ($diag) { Write-Host ("Diag: " + $diag) } else { Warn "Diag failed" }

# 3) Visualization sample
Show-Section "Graph Visualization (sanity)"
$vizUrl = "$ApiBase/api/v1/graph/visualization?repository=$Repository&depth=$Depth&limit_nodes=$LimitNodes&limit_edges=$LimitEdges&trace=false"
Write-Host "GET $vizUrl"
$viz = Invoke-GetJson -Url $vizUrl
if ($viz) { Write-Host $viz } else { Warn "Visualization call failed" }

# 4) Neo4j directional checks via /query/graph
Show-Section "Neo4j: Repository existence"
$cy1 = 'MATCH (r:Repository {name: $repository}) RETURN count(r) as repo_count'
$content1 = Invoke-GraphQuery -Cypher $cy1 -Parameters @{ repository = $Repository }
if ($content1) { Write-Host $content1 }

Show-Section "Neo4j: Adjacent nodes by label counts"
$cy2 = @'
MATCH (r:Repository {name: $repository})-[]-(n)
RETURN labels(n) as labels, count(*) as cnt
ORDER BY cnt DESC
LIMIT 10
'@
$content2 = Invoke-GraphQuery -Cypher $cy2 -Parameters @{ repository = $Repository }
if ($content2) { Write-Host $content2 }

Show-Section "Neo4j: Edge existence and sample"
$cy3 = @'
MATCH (r:Repository {name: $repository})-[e]-(n)
RETURN type(e) as rel_type, count(*) as cnt
ORDER BY cnt DESC
LIMIT 10
'@
$content3 = Invoke-GraphQuery -Cypher $cy3 -Parameters @{ repository = $Repository }
if ($content3) { Write-Host $content3 }

Show-Section "Neo4j: Sample contents (first 10 nodes/edges)"
$cy4 = @'
MATCH (r:Repository {name: $repository})- [e] - (n)
RETURN r.name as repository, labels(n) as labels, n.path as path, n.name as name, type(e) as rel
LIMIT 10
'@
$content4 = Invoke-GraphQuery -Cypher $cy4 -Parameters @{ repository = $Repository }
if ($content4) { Write-Host $content4 }

Show-Section "Neo4j: Repository metadata fields"
$cy5 = @'
MATCH (r:Repository {name: $repository})
RETURN r.size_loc as size_loc, r.complexity_score as complexity, r.provides_services as provides, r.consumes_services as consumes
'@
$content5 = Invoke-GraphQuery -Cypher $cy5 -Parameters @{ repository = $Repository }
if ($content5) { Write-Host $content5 }

# 5) ChromaDB health and directional checks via API endpoints
Show-Section "ChromaDB: API Search sanity (uses /api/v1/query/semantic)"
# Build a low-impact search: query by repository name
$searchBody = @{
  query = "repo:$Repository"
  limit = 3
  min_score = 0.0
  include_metadata = $true
} | ConvertTo-Json -Depth 6
try {
  $sresp = Invoke-WebRequest -UseBasicParsing -Method Post -Uri "$ApiBase/api/v1/query/semantic" -ContentType "application/json" -Body $searchBody
  Write-Host $sresp.Content
} catch {
  Show-ErrorBody -Err $_
}

Show-Section "Summary (Human-Readable)"
try {
  # Parse some numbers to provide a short conclusion
  $repoCountJson = ($content1 | ConvertFrom-Json -ErrorAction SilentlyContinue)
  $repoCount = 0
  if ($repoCountJson -and $repoCountJson.records -and $repoCountJson.records.Count -gt 0) {
    if ($repoCountJson.records[0].repo_count -ne $null) {
      $repoCount = [int]$repoCountJson.records[0].repo_count
    }
  }
  $edgeCountJson = ($content3 | ConvertFrom-Json -ErrorAction SilentlyContinue)
  $edgeCount = 0
  if ($edgeCountJson -and $edgeCountJson.records -and $edgeCountJson.records.Count -gt 0) {
    # Sum cnt if multiple rows
    foreach ($rec in $edgeCountJson.records) {
      if ($rec.cnt -ne $null) { $edgeCount += [int]$rec.cnt }
    }
  }
  $searchJson = ($sresp.Content | ConvertFrom-Json -ErrorAction SilentlyContinue)
  $searchResults = 0
  if ($searchJson -and $searchJson.total_results -ne $null) { $searchResults = [int]$searchJson.total_results }

  Info ("Repository exists: {0}" -f ($repoCount -gt 0))
  Info ("Edges touching repository: {0}" -f $edgeCount)
  Info ("Semantic search results (directional): {0}" -f $searchResults)

  if ($repoCount -gt 0 -and $edgeCount -eq 0) {
    Warn "Graph appears to have the Repository node but no adjacent nodes/relationships. Indexing may not have created nodes/edges in Neo4j."
  }
  if ($searchResults -eq 0) {
    Warn "ChromaDB returned zero results. Ensure collection is initialized and embeddings indexed for this repo."
  }
} catch {
  Warn "Could not compute summary: $($_.Exception.Message)"
}

if ($VerboseLogs) {
  Show-Section "Raw Diagnostics Echo"
  Write-Host "RepoCount JSON:"
  Write-Host ($content1)
  Write-Host "EdgeType JSON:"
  Write-Host ($content3)
}