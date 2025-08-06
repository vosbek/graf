param()

Write-Host "=== DEFINITIVE CHROMADB V2 ARCHITECTURE FIX ===" -ForegroundColor Yellow

Write-Host "ANALYSIS COMPLETE: ChromaDB requires tenant/database structure:" -ForegroundColor Cyan
Write-Host "- Collections: /api/v2/tenants/{tenant}/databases/{database}/collections" -ForegroundColor White
Write-Host "- Health: /api/v2/heartbeat (works)" -ForegroundColor White
Write-Host "- Tenant: /api/v2/tenants" -ForegroundColor White
Write-Host "- Database: /api/v2/tenants/{tenant}/databases" -ForegroundColor White

Write-Host "1. Creating default tenant 'default_tenant'..." -ForegroundColor Cyan
$createTenant = @{
    name = "default_tenant"
} | ConvertTo-Json

$tenantResponse = Invoke-WebRequest -Uri "http://localhost:8000/api/v2/tenants" -Method POST -Body $createTenant -ContentType "application/json" -UseBasicParsing -ErrorAction SilentlyContinue
if ($tenantResponse) {
    Write-Host "Tenant created: $($tenantResponse.StatusCode)" -ForegroundColor Green
} else {
    # Tenant might already exist, check if it exists
    $checkTenant = Invoke-WebRequest -Uri "http://localhost:8000/api/v2/tenants/default_tenant" -UseBasicParsing -ErrorAction SilentlyContinue
    if ($checkTenant) {
        Write-Host "Tenant already exists: $($checkTenant.StatusCode)" -ForegroundColor Green
    } else {
        Write-Host "Failed to create or find tenant" -ForegroundColor Red
    }
}

Write-Host "2. Creating default database 'default_database'..." -ForegroundColor Cyan
$createDatabase = @{
    name = "default_database"
} | ConvertTo-Json

$dbResponse = Invoke-WebRequest -Uri "http://localhost:8000/api/v2/tenants/default_tenant/databases" -Method POST -Body $createDatabase -ContentType "application/json" -UseBasicParsing -ErrorAction SilentlyContinue
if ($dbResponse) {
    Write-Host "Database created: $($dbResponse.StatusCode)" -ForegroundColor Green
} else {
    # Database might already exist, check if it exists
    $checkDb = Invoke-WebRequest -Uri "http://localhost:8000/api/v2/tenants/default_tenant/databases/default_database" -UseBasicParsing -ErrorAction SilentlyContinue
    if ($checkDb) {
        Write-Host "Database already exists: $($checkDb.StatusCode)" -ForegroundColor Green
    } else {
        Write-Host "Failed to create or find database" -ForegroundColor Red
    }
}

Write-Host "3. Testing collections endpoint with proper tenant structure..." -ForegroundColor Cyan
$collectionsTest = Invoke-WebRequest -Uri "http://localhost:8000/api/v2/tenants/default_tenant/databases/default_database/collections" -UseBasicParsing -ErrorAction SilentlyContinue
if ($collectionsTest) {
    Write-Host "Collections endpoint now works: $($collectionsTest.StatusCode)" -ForegroundColor Green
    Write-Host "Response: $($collectionsTest.Content)" -ForegroundColor Gray
} else {
    Write-Host "Collections endpoint still fails" -ForegroundColor Red
}

Write-Host "4. Stopping current API server..." -ForegroundColor Cyan
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

Write-Host "5. Starting API with correct v2 tenant configuration..." -ForegroundColor Cyan
# Set environment variables for v2 tenant mode
$env:CHROMA_TENANT = "default_tenant"
$env:CHROMA_DATABASE = "default_database"
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
Write-Host "API server started (PID: $($apiProcess.Id)) with proper v2 tenant config" -ForegroundColor Green

Write-Host "6. Waiting for full initialization..." -ForegroundColor Cyan
Start-Sleep -Seconds 25

Write-Host "7. Testing complete system health..." -ForegroundColor Cyan
$attempts = 0
$maxAttempts = 12
$systemReady = $false

while ($attempts -lt $maxAttempts -and -not $systemReady) {
    $attempts++
    Write-Host "System health check attempt $attempts/$maxAttempts..."
    
    $apiHealth = Invoke-WebRequest -Uri "http://localhost:8082/api/v1/health/readiness" -UseBasicParsing -TimeoutSec 15 -ErrorAction SilentlyContinue
    if ($apiHealth) {
        $response = $apiHealth.Content | ConvertFrom-Json
        Write-Host "API Status: $($response.status)" -ForegroundColor $(if($response.status -eq "ready") {"Green"} elseif($response.status -eq "not_ready") {"Yellow"} else {"Red"})
        
        if ($response.status -eq "ready") {
            $systemReady = $true
            Write-Host "COMPLETE SYSTEM SUCCESS!" -ForegroundColor Green
            Write-Host "Vector Database: ChromaDB (v2 tenant architecture)" -ForegroundColor Green
            Write-Host "Graph Database: Neo4j" -ForegroundColor Green
            Write-Host "Cache: Redis" -ForegroundColor Green
        } elseif ($response.status -eq "not_ready") {
            if ($response.self_heal -and $response.self_heal.errors) {
                Write-Host "Still initializing... Errors: $($response.self_heal.errors -join ', ')" -ForegroundColor Yellow
            } else {
                Write-Host "Still initializing..." -ForegroundColor Yellow
            }
        }
    } else {
        Write-Host "API not responding yet..." -ForegroundColor Red
    }
    
    if (-not $systemReady) {
        Start-Sleep -Seconds 3
    }
}

if ($systemReady) {
    Write-Host ""
    Write-Host "GRAPHRAG SYSTEM IS FULLY OPERATIONAL!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Your frontend will now show the complete dashboard!" -ForegroundColor Yellow
    Write-Host "- API Health: http://localhost:8082/api/v1/health/readiness" -ForegroundColor White
    Write-Host "- Frontend: http://localhost:3000 (restart to use port 8082)" -ForegroundColor White
    Write-Host ""
    Write-Host "Architecture Summary:" -ForegroundColor Cyan
    Write-Host "ChromaDB v2 with tenant default_tenant and database default_database" -ForegroundColor White
    Write-Host "Neo4j graph database for relationships" -ForegroundColor White
    Write-Host "Redis for caching and task management" -ForegroundColor White
    Write-Host "Complete RAG pipeline ready for indexing and querying" -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "System not fully ready after maximum attempts" -ForegroundColor Red
    if ($apiHealth) {
        Write-Host "Final health response:" -ForegroundColor Yellow
        Write-Host $apiHealth.Content -ForegroundColor Gray
    }
    Write-Host "Check logs for detailed error information" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== DEFINITIVE V2 ARCHITECTURE FIX COMPLETED ===" -ForegroundColor Yellow