param()

Write-Host "=== DIAGNOSING HEALTH CHECK FAILURES ===" -ForegroundColor Yellow

# Test 1: Check if containers are actually running
Write-Host "1. Checking container status..." -ForegroundColor Cyan
podman ps --format "table {{.Names}} {{.Status}} {{.Ports}}"
Write-Host ""

# Test 2: Test ChromaDB directly
Write-Host "2. Testing ChromaDB connection..." -ForegroundColor Cyan
$chromatest1 = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/heartbeat" -UseBasicParsing -TimeoutSec 5 -ErrorAction SilentlyContinue
if ($chromatest1) {
    Write-Host "ChromaDB v1 heartbeat: $($chromatest1.StatusCode)" -ForegroundColor Green
} else {
    Write-Host "ChromaDB v1 heartbeat failed" -ForegroundColor Red
}

$chromatest2 = Invoke-WebRequest -Uri "http://localhost:8000/api/v2/heartbeat" -UseBasicParsing -TimeoutSec 5 -ErrorAction SilentlyContinue
if ($chromatest2) {
    Write-Host "ChromaDB v2 heartbeat: $($chromatest2.StatusCode)" -ForegroundColor Green
} else {
    Write-Host "ChromaDB v2 heartbeat failed" -ForegroundColor Red
}

Write-Host ""

# Test 3: Test Neo4j connection
Write-Host "3. Testing Neo4j connection..." -ForegroundColor Cyan
$neo4jUp = netstat -ano | findstr ":7687.*LISTENING"
if ($neo4jUp) {
    Write-Host "Neo4j is listening on port 7687" -ForegroundColor Green
} else {
    Write-Host "Neo4j is not listening on port 7687" -ForegroundColor Red
}

Write-Host ""

# Test 4: Check actual API health endpoint
Write-Host "4. Testing API health endpoint..." -ForegroundColor Cyan
$apiHealth = Invoke-WebRequest -Uri "http://localhost:8082/api/v1/health/readiness" -UseBasicParsing -TimeoutSec 10 -ErrorAction SilentlyContinue
if ($apiHealth) {
    Write-Host "API Health Status: $($apiHealth.StatusCode)" -ForegroundColor Green
    Write-Host "Response: $($apiHealth.Content)" -ForegroundColor Gray
} else {
    Write-Host "API health check failed" -ForegroundColor Red
}

Write-Host ""

# Test 5: Check environment file
Write-Host "5. Checking .env file..." -ForegroundColor Cyan
if (Test-Path ".env") {
    Write-Host ".env file exists" -ForegroundColor Green
    $envContent = Get-Content ".env"
    $requiredVars = @("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "CHROMA_HOST", "CHROMA_PORT")
    foreach ($var in $requiredVars) {
        $found = $envContent | Where-Object { $_ -like "$var=*" }
        if ($found) {
            Write-Host "$var is set" -ForegroundColor Green
        } else {
            Write-Host "$var is missing" -ForegroundColor Red
        }
    }
} else {
    Write-Host ".env file not found" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== DIAGNOSIS COMPLETED ===" -ForegroundColor Yellow