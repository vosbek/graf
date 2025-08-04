Param(
  [string]$BaseUrl = "http://localhost:8001",
  [int]$MaxAttempts = 60,
  [int]$DelaySeconds = 2
)

Write-Host "Polling $BaseUrl/api/v1/health/ready (max $MaxAttempts attempts, $DelaySeconds sec delay)..."

$attempt = 0
$ready = $false
$lastError = $null

while ($attempt -lt $MaxAttempts -and -not $ready) {
  $attempt++
  try {
    $resp = Invoke-RestMethod -Uri "$BaseUrl/api/v1/health/ready" -TimeoutSec 8 -Method GET
    $status = $resp.status
    $score = if ($resp.PSObject.Properties.Name -contains "health_score") { $resp.health_score } else { $null }
    Write-Host ("Attempt {0}: status={1} health_score={2}" -f $attempt, $status, $score)

    if ($status -eq "ready") {
      $ready = $true
      break
    }
  }
  catch {
    $lastError = $_.Exception.Message
    Write-Host ("Attempt {0}: error {1}" -f $attempt, $lastError)
  }

  Start-Sleep -Seconds $DelaySeconds
}

if (-not $ready) {
  Write-Host "Service did not become ready within $MaxAttempts attempts."
  if ($lastError) { Write-Host ("Last error: {0}" -f $lastError) }
  exit 2
}

Write-Host "READY reached. Fetching detailed health..."
try {
  $detailed = Invoke-RestMethod -Uri "$BaseUrl/api/v1/health/detailed" -TimeoutSec 15 -Method GET
  # Summarize components keys safely
  $componentNames = @()
  if ($detailed -and $detailed.components) {
    $componentNames = ($detailed.components | Get-Member -MemberType NoteProperty | Select-Object -ExpandProperty Name)
  }
  $summary = [PSCustomObject]@{
    overall    = $detailed.status
    components = ($componentNames -join ",")
    timestamp  = $detailed.timestamp
  }
  $summary | ConvertTo-Json -Depth 6
  # Also output full JSON for debugging
  "`nFull detailed payload:" | Out-Host
  ($detailed | ConvertTo-Json -Depth 8)
  exit 0
}
catch {
  Write-Host ("Error fetching detailed health: {0}" -f $_.Exception.Message)
  exit 3
}