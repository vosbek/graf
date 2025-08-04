#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Neo4j readiness diagnostics and quick repair hints.

.DESCRIPTION
  - Tails recent container logs
  - Checks HTTP UI (7474) and Bolt via cypher-shell (7687)
  - Prints memory/plugin config hints if container is flapping
#>

$ErrorActionPreference = "Stop"

function Section { param([string]$Title) Write-Host "`n=== $Title ===" -ForegroundColor Cyan }
function Wait-Http200 {
  param([string]$Url, [int]$TimeoutSec = 180)
  $elapsed = 0
  while ($elapsed -lt $TimeoutSec) {
    try {
      $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
      if ($r.StatusCode -eq 200) { return $true }
    } catch { }
    Start-Sleep -Seconds 3
    $elapsed += 3
  }
  return $false
}

Section "Container status"
try {
  podman ps --filter "name=codebase-rag-neo4j" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
} catch {
  Write-Warning "podman ps failed: $($_.Exception.Message)"
}

Section "Recent logs (last 80 lines)"
try {
  podman logs --tail 80 codebase-rag-neo4j
} catch {
  Write-Warning "logs read failed: $($_.Exception.Message)"
}

Section "HTTP UI (7474) check"
$httpOk = Wait-Http200 "http://localhost:7474" 180
if ($httpOk) {
  Write-Host "HTTP UI reachable on http://localhost:7474" -ForegroundColor Green
} else {
  Write-Warning "HTTP UI not reachable yet (may still be starting)"
}

Section "Bolt (7687) via cypher-shell"
try {
  podman exec codebase-rag-neo4j cypher-shell -u neo4j -p codebase-rag-2024 "RETURN 1" | Out-Null
  Write-Host "Bolt responds (cypher-shell RETURN 1 succeeded)" -ForegroundColor Green
  $boltOk = $true
} catch {
  Write-Warning "Bolt not responding: $($_.Exception.Message)"
  $boltOk = $false
}

Section "Hints"
if (-not $httpOk -or -not $boltOk) {
  Write-Host "- If container is restarting, check memory settings in podman-compose.dev.yml:" -ForegroundColor Yellow
  Write-Host "    NEO4J_server_memory_heap_initial__size / max__size / pagecache_size" -ForegroundColor Gray
  Write-Host "- Ensure image is enterprise and license accepted:" -ForegroundColor Yellow
  Write-Host "    image: neo4j:5.15-enterprise" -ForegroundColor Gray
  Write-Host "    NEO4J_ACCEPT_LICENSE_AGREEMENT=yes" -ForegroundColor Gray
  Write-Host "- Validate plugins setting syntax; APOC only is safest for dev:" -ForegroundColor Yellow
  Write-Host "    NEO4J_PLUGINS=[`"apoc`"]" -ForegroundColor Gray
  Write-Host "- Tail logs continuously while it warms up:" -ForegroundColor Yellow
  Write-Host "    podman logs -f codebase-rag-neo4j" -ForegroundColor Gray
} else {
  Write-Host "Neo4j appears ready." -ForegroundColor Green
}

Write-Host "`nNeo4j repair diagnostics complete." -ForegroundColor Cyan