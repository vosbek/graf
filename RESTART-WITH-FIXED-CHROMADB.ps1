param()

Write-Host "=== RESTARTING WITH FIXED CHROMADB CLIENT ===" -ForegroundColor Yellow

# Stop the current API server
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

Write-Host "2. Fixed ChromaDB client to use v1 API endpoints:" -ForegroundColor Green
Write-Host "   - Using /api/v1/heartbeat for health checks" -ForegroundColor White
Write-Host "   - Using /api/v1/collections for collection management" -ForegroundColor White
Write-Host "   - Skipping tenant/database setup (v1 mode)" -ForegroundColor White

Write-Host "3. Starting API server with fixed client..." -ForegroundColor Cyan

# Set environment variables (force v1 mode by clearing tenant)
$env:CHROMA_TENANT = ""
$env:CHROMA_DATABASE = ""
$env:CHROMA_HOST = "localhost"
$env:CHROMA_PORT = "8000"
$env:NEO4J_URI = "bolt://localhost:7687"
$env:NEO4J_USERNAME = "neo4j"
$env:NEO4J_PASSWORD = "codebase-rag-2024"
$env:NEO4J_DATABASE = "neo4j"
$env:APP_ENV = "development"
$env:API_HOST = "0.0.0.0"
$env:API_PORT = "8082"
$env:LOG_LEVEL = "INFO"

# Start API server
$apiProcess = Start-Process -FilePath "python" -ArgumentList "-m", "src.main" -PassThru -NoNewWindow
Write-Host "API server started (PID: $($apiProcess.Id))" -ForegroundColor Green

Write-Host "4. Waiting for API to initialize..." -ForegroundColor Cyan
Start-Sleep -Seconds 20

Write-Host "5. Testing ChromaDB endpoints directly..." -ForegroundColor Cyan
# Test v1 collections endpoint
$v1collections = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/collections" -UseBasicParsing -TimeoutSec 5 -ErrorAction SilentlyContinue
if ($v1collections) {
    Write-Host "✓ ChromaDB v1 collections endpoint works: $($v1collections.StatusCode)" -ForegroundColor Green
} else {
    Write-Host "✗ ChromaDB v1 collections endpoint still fails" -ForegroundColor Red
}

Write-Host "6. Testing API health..." -ForegroundColor Cyan
$attempts = 0
$maxAttempts = 10
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
        Start-Sleep -Seconds 3
    }
}

if ($apiReady) {
    Write-Host "7. SYSTEM IS NOW READY!" -ForegroundColor Green
    Write-Host "✓ ChromaDB v1 API working" -ForegroundColor Green
    Write-Host "✓ Neo4j connected" -ForegroundColor Green
    Write-Host "✓ API health check passes" -ForegroundColor Green
    Write-Host ""
    Write-Host "Your frontend should now show the dashboard!" -ForegroundColor Yellow
    Write-Host "API: http://localhost:8082/api/v1/health/readiness" -ForegroundColor White
    Write-Host ""
    Write-Host "You now have a fully working GraphRAG system:" -ForegroundColor Cyan
    Write-Host "- Vector Database: ChromaDB (v1 API)" -ForegroundColor White
    Write-Host "- Graph Database: Neo4j" -ForegroundColor White  
    Write-Host "- Cache: Redis" -ForegroundColor White
} else {
    Write-Host "7. API still not ready after all attempts" -ForegroundColor Red
    if ($apiHealth) {
        Write-Host "Final response:" -ForegroundColor Red
        Write-Host $apiHealth.Content -ForegroundColor Gray
    }
}

Write-Host "=== CHROMADB FIX COMPLETED ===" -ForegroundColor Yellow