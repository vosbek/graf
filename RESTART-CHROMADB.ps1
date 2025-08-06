param()

Write-Host "=== RESTARTING CHROMADB PROPERLY ===" -ForegroundColor Yellow

# Check current container status
Write-Host "1. Current container status..." -ForegroundColor Cyan
podman ps -a | findstr chromadb

# Start all containers to ensure ChromaDB comes back up
Write-Host "2. Starting all containers..." -ForegroundColor Cyan
podman-compose -f podman-compose.dev.yml up -d

# Wait for containers to start
Write-Host "3. Waiting for ChromaDB to start..." -ForegroundColor Cyan
Start-Sleep -Seconds 15

# Check container status again
Write-Host "4. Container status after restart..." -ForegroundColor Cyan
podman ps | findstr chromadb

# Test ChromaDB connection
Write-Host "5. Testing ChromaDB..." -ForegroundColor Cyan
$attempts = 0
$maxAttempts = 6
$chromaWorking = $false

while ($attempts -lt $maxAttempts -and -not $chromaWorking) {
    $attempts++
    Write-Host "Attempt $attempts/$maxAttempts..."
    
    $test = Invoke-WebRequest -Uri "http://localhost:8000/api/v2/heartbeat" -UseBasicParsing -TimeoutSec 5 -ErrorAction SilentlyContinue
    if ($test) {
        Write-Host "ChromaDB heartbeat: SUCCESS" -ForegroundColor Green
        $chromaWorking = $true
    } else {
        Write-Host "ChromaDB not ready yet, waiting..." -ForegroundColor Yellow
        Start-Sleep -Seconds 5
    }
}

if ($chromaWorking) {
    # Test collections endpoint
    Write-Host "6. Testing collections endpoint..." -ForegroundColor Cyan
    $collections = Invoke-WebRequest -Uri "http://localhost:8000/api/v2/collections" -UseBasicParsing -TimeoutSec 5 -ErrorAction SilentlyContinue
    if ($collections) {
        Write-Host "Collections endpoint: SUCCESS ($($collections.StatusCode))" -ForegroundColor Green
        Write-Host "ChromaDB is now working!" -ForegroundColor Green
        
        Write-Host "7. Testing API health..." -ForegroundColor Cyan
        Start-Sleep -Seconds 5
        $apiHealth = Invoke-WebRequest -Uri "http://localhost:8082/api/v1/health/readiness" -UseBasicParsing -TimeoutSec 10 -ErrorAction SilentlyContinue
        if ($apiHealth) {
            $response = $apiHealth.Content | ConvertFrom-Json
            Write-Host "API Status: $($response.status)" -ForegroundColor $(if($response.status -eq "ready") {"Green"} else {"Yellow"})
        }
    } else {
        Write-Host "Collections endpoint still failing" -ForegroundColor Red
    }
} else {
    Write-Host "ChromaDB failed to start properly" -ForegroundColor Red
    Write-Host "Checking logs..." -ForegroundColor Cyan
    podman logs --tail 20 codebase-rag-chromadb
}

Write-Host "=== CHROMADB RESTART COMPLETED ===" -ForegroundColor Yellow