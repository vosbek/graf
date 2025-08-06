param()

Write-Host "=== FIXING CHROMADB COLLECTIONS API ===" -ForegroundColor Yellow

# Test the specific failing endpoint
Write-Host "1. Testing the failing collections endpoint..." -ForegroundColor Cyan
$collectionsTest = Invoke-WebRequest -Uri "http://localhost:8000/api/v2/collections" -UseBasicParsing -TimeoutSec 5 -ErrorAction SilentlyContinue
if ($collectionsTest) {
    Write-Host "Collections endpoint works: $($collectionsTest.StatusCode)" -ForegroundColor Green
    Write-Host "Response: $($collectionsTest.Content)" -ForegroundColor Gray
} else {
    Write-Host "Collections endpoint returns 404 - this is the problem!" -ForegroundColor Red
}

Write-Host ""

# Try alternative v2 endpoints that might work
Write-Host "2. Testing alternative ChromaDB v2 endpoints..." -ForegroundColor Cyan
$endpoints = @(
    "http://localhost:8000/api/v2/heartbeat",
    "http://localhost:8000/api/v2/version", 
    "http://localhost:8000/api/v2/pre-flight-checks"
)

foreach ($endpoint in $endpoints) {
    $test = Invoke-WebRequest -Uri $endpoint -UseBasicParsing -TimeoutSec 5 -ErrorAction SilentlyContinue
    if ($test) {
        Write-Host "$endpoint : $($test.StatusCode)" -ForegroundColor Green
    } else {
        Write-Host "$endpoint : FAILED" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "3. Restarting ChromaDB container..." -ForegroundColor Cyan
podman restart codebase-rag-chromadb
Start-Sleep -Seconds 10

Write-Host "4. Testing collections endpoint after restart..." -ForegroundColor Cyan
$collectionsTest2 = Invoke-WebRequest -Uri "http://localhost:8000/api/v2/collections" -UseBasicParsing -TimeoutSec 10 -ErrorAction SilentlyContinue
if ($collectionsTest2) {
    Write-Host "Collections endpoint now works: $($collectionsTest2.StatusCode)" -ForegroundColor Green
    Write-Host "Response: $($collectionsTest2.Content)" -ForegroundColor Gray
} else {
    Write-Host "Collections endpoint still fails - trying alternative fix..." -ForegroundColor Yellow
    
    Write-Host "5. Checking ChromaDB container logs..." -ForegroundColor Cyan
    podman logs --tail 10 codebase-rag-chromadb
    
    Write-Host ""
    Write-Host "6. Trying to recreate ChromaDB container..." -ForegroundColor Cyan
    podman stop codebase-rag-chromadb
    podman rm codebase-rag-chromadb
    podman-compose -f podman-compose.dev.yml up -d codebase-rag-chromadb
    
    Start-Sleep -Seconds 15
    Write-Host "Testing after container recreation..." -ForegroundColor Cyan
    $collectionsTest3 = Invoke-WebRequest -Uri "http://localhost:8000/api/v2/collections" -UseBasicParsing -TimeoutSec 10 -ErrorAction SilentlyContinue
    if ($collectionsTest3) {
        Write-Host "SUCCESS: Collections endpoint now works!" -ForegroundColor Green
    } else {
        Write-Host "FAILED: Collections endpoint still broken" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "=== CHROMADB FIX COMPLETED ===" -ForegroundColor Yellow