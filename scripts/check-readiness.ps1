param(
    [string]$BaseUrl = "http://localhost:8080"
)

Write-Host "Checking GraphRAG readiness endpoints..." -ForegroundColor Cyan
Write-Host "Base URL: $BaseUrl" -ForegroundColor Cyan
Write-Host ""

function Invoke-And-Print {
    param(
        [string]$Url,
        [string]$Label
    )
    Write-Host "==== $Label ====" -ForegroundColor Yellow
    try {
        # Use curl.exe explicitly to avoid PowerShell alias behavior
        $out = & curl.exe -s -i $Url
        if (-not $out) {
            Write-Host "(no output)" -ForegroundColor DarkYellow
        } else {
            $out | Out-String | Write-Host
        }
    } catch {
        Write-Host "Request failed: $($_.Exception.Message)" -ForegroundColor Red
    }
    Write-Host ""
}

function Invoke-And-ParseJson {
    param(
        [string]$Url,
        [string]$Label
    )
    Write-Host "==== $Label (parsed) ====" -ForegroundColor Yellow
    try {
        $raw = & curl.exe -s $Url
        if (-not $raw) {
            Write-Host "(no output)" -ForegroundColor DarkYellow
        } else {
            try {
                $j = $raw | ConvertFrom-Json
                $j | ConvertTo-Json -Depth 6
            } catch {
                Write-Host $raw
            }
        }
    } catch {
        Write-Host "Request failed: $($_.Exception.Message)" -ForegroundColor Red
    }
    Write-Host ""
}

function Test-Tcp {
    param(
        [string]$TargetHost,
        [int]$Port,
        [string]$Name
    )
    try {
        $ok = Test-NetConnection -ComputerName $TargetHost -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue
        $emoji = if ($ok) { "✅" } else { "❌" }
        Write-Host ("$emoji TCP {0}:{1} ({2})" -f $TargetHost, $Port, $Name) -ForegroundColor $(if ($ok) { "Green" } else { "Red" })
    } catch {
        Write-Host ("❌ TCP {0}:{1} ({2}) - {3}" -f $TargetHost, $Port, $Name, $_.Exception.Message) -ForegroundColor Red
    }
}

# Canonical endpoints
$readyUrl = "$BaseUrl/api/v1/health/ready"
$diagUrl  = "$BaseUrl/api/v1/diagnostics/system"

# New diagnostics endpoints (may 404 if old server instance)
$echoUrl  = "$BaseUrl/api/v1/health/echo-revision"
$rtUrl    = "$BaseUrl/api/v1/health/runtime-info"
$ready2   = "$BaseUrl/api/v1/health/ready2"

# 1) Quick TCP connectivity for core services
Write-Host "==== TCP Connectivity ====" -ForegroundColor Yellow
Test-Tcp -TargetHost "localhost" -Port 8000 -Name "ChromaDB"
Test-Tcp -TargetHost "localhost" -Port 7474 -Name "Neo4j HTTP"
Test-Tcp -TargetHost "localhost" -Port 7687 -Name "Neo4j Bolt"
Test-Tcp -TargetHost "localhost" -Port 8080 -Name "API"
Write-Host ""

# 2) API health and diagnostics (raw)
Invoke-And-Print -Url $readyUrl -Label "GET /api/v1/health/ready"
Start-Sleep -Milliseconds 200
Invoke-And-Print -Url $diagUrl -Label "GET /api/v1/diagnostics/system"

# 3) API self-heal/alt readiness and revision markers
Invoke-And-Print -Url $ready2 -Label "GET /api/v1/health/ready2"
Invoke-And-Print -Url $echoUrl -Label "GET /api/v1/health/echo-revision"
Invoke-And-Print -Url $rtUrl   -Label "GET /api/v1/health/runtime-info"

# 4) Parsed summaries (if JSON available)
Invoke-And-ParseJson -Url $readyUrl -Label "Summary /health/ready"
Invoke-And-ParseJson -Url $ready2   -Label "Summary /health/ready2"
Invoke-And-ParseJson -Url $diagUrl  -Label "Summary /diagnostics/system"

# 5) Derived readiness summary
Write-Host "==== Readiness Summary ====" -ForegroundColor Yellow
try {
    $rJson = (& curl.exe -s $readyUrl) | ConvertFrom-Json
} catch { $rJson = $null }
try {
    $r2Json = (& curl.exe -s $ready2) | ConvertFrom-Json
} catch { $r2Json = $null }
try {
    $dJson = (& curl.exe -s $diagUrl) | ConvertFrom-Json
} catch { $dJson = $null }

$readyStatus = if ($rJson -and $rJson.status) { $rJson.status } else { "(n/a)" }
$ready2Status = if ($r2Json -and $r2Json.status) { $r2Json.status } else { "(n/a)" }
$chromaFlag = $false
$neo4jFlag = $false
if ($rJson -and $rJson.state_flags) {
    $chromaFlag = [bool]$rJson.state_flags.chroma_attached
    $neo4jFlag  = [bool]$rJson.state_flags.neo4j_attached
} elseif ($r2Json) {
    $chromaFlag = [bool]$r2Json.chroma_attached
    $neo4jFlag  = [bool]$r2Json.neo4j_attached
}
$errors = @()
if ($r2Json -and $r2Json.errors) { $errors += $r2Json.errors }
if ($rJson -and $rJson.self_heal -and $rJson.self_heal.errors) { $errors += $rJson.self_heal.errors }

Write-Host ("Ready: {0} | Ready2: {1} | ChromaAttached: {2} | Neo4jAttached: {3}" -f $readyStatus, $ready2Status, $chromaFlag, $neo4jFlag) -ForegroundColor Cyan
if ($errors.Count -gt 0) {
    Write-Host "Self-heal errors:" -ForegroundColor Yellow
    $errors | ForEach-Object { Write-Host (" - {0}" -f $_) -ForegroundColor Yellow }
}

Write-Host ""
Write-Host "Done. Copy the outputs above and paste them back here." -ForegroundColor Green