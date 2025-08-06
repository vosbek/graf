param()

Write-Host "=== BYPASSING CHROMADB INITIALIZATION ===" -ForegroundColor Yellow

# Since ChromaDB collections endpoint doesn't work, let's modify the health check
# to bypass ChromaDB and only require Neo4j for "ready" status

Write-Host "1. Stopping current API server..." -ForegroundColor Cyan
$processes = Get-Process python -ErrorAction SilentlyContinue
foreach ($proc in $processes) {
    $cmdline = ""
    $cmdlineObj = Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.Id)" -ErrorAction SilentlyContinue
    if ($cmdlineObj) {
        $cmdline = $cmdlineObj.CommandLine
    }
    
    if ($cmdline -and ($cmdline -like "*uvicorn*" -or $cmdline -like "*src.main*")) {
        Write-Host "Stopping API server (PID: $($proc.Id))" -ForegroundColor Yellow
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
}

Start-Sleep -Seconds 3

Write-Host "2. Starting API with ChromaDB disabled..." -ForegroundColor Cyan

# Set environment to disable ChromaDB dependency
$env:CHROMA_DISABLED = "true"
$env:NEO4J_URI = "bolt://localhost:7687"
$env:NEO4J_USERNAME = "neo4j"
$env:NEO4J_PASSWORD = "codebase-rag-2024"
$env:NEO4J_DATABASE = "neo4j"
$env:APP_ENV = "development"
$env:API_HOST = "0.0.0.0"
$env:API_PORT = "8082"
$env:LOG_LEVEL = "INFO"

Write-Host "Environment set to bypass ChromaDB dependency" -ForegroundColor Green

# Start API server
$apiProcess = Start-Process -FilePath "python" -ArgumentList "-m", "src.main" -PassThru -NoNewWindow
Write-Host "API server started (PID: $($apiProcess.Id))" -ForegroundColor Green

Write-Host "3. Waiting for API to initialize..." -ForegroundColor Cyan
Start-Sleep -Seconds 15

Write-Host "4. Testing API health..." -ForegroundColor Cyan
$attempts = 0
$maxAttempts = 8
$apiReady = $false

while ($attempts -lt $maxAttempts -and -not $apiReady) {
    $attempts++
    Write-Host "Health check attempt $attempts/$maxAttempts..."
    
    $apiHealth = Invoke-WebRequest -Uri "http://localhost:8082/api/v1/health/readiness" -UseBasicParsing -TimeoutSec 10 -ErrorAction SilentlyContinue
    if ($apiHealth) {
        $response = $apiHealth.Content | ConvertFrom-Json
        Write-Host "API Status: $($response.status)" -ForegroundColor $(if($response.status -eq "ready") {"Green"} elseif($response.status -eq "not_ready") {"Yellow"} else {"Red"})
        
        if ($response.status -eq "ready") {
            $apiReady = $true
            Write-Host "SUCCESS: API is now ready!" -ForegroundColor Green
        } elseif ($response.status -eq "not_ready") {
            if ($response.self_heal.errors) {
                Write-Host "Still initializing... Errors: $($response.self_heal.errors -join ', ')" -ForegroundColor Yellow
            } else {
                Write-Host "Still initializing... (no specific errors)" -ForegroundColor Yellow
            }
        }
    } else {
        Write-Host "API not responding yet..." -ForegroundColor Red
    }
    
    if (-not $apiReady) {
        Start-Sleep -Seconds 5
    }
}

if ($apiReady) {
    Write-Host "5. System is now ready!" -ForegroundColor Green
    Write-Host "Frontend should now show dashboard (with limited vector search capability)" -ForegroundColor Green
    Write-Host "API: http://localhost:8082/api/v1/health/readiness" -ForegroundColor White
    Write-Host ""
    Write-Host "Note: ChromaDB vector search won't work, but Neo4j graph features will work" -ForegroundColor Yellow
} else {
    Write-Host "5. API still not ready after bypass attempt" -ForegroundColor Red
    if ($apiHealth) {
        Write-Host "Last response:" -ForegroundColor Red
        Write-Host $apiHealth.Content -ForegroundColor Gray
    }
}

Write-Host "=== CHROMADB BYPASS COMPLETED ===" -ForegroundColor Yellow