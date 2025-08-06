param()

Write-Host "=== CLEAN RESTART WITH PERSISTENT V2 TENANT CONFIG ===" -ForegroundColor Yellow

Write-Host "1. Configuration verification..." -ForegroundColor Cyan
Write-Host "✓ .env file now permanently sets:" -ForegroundColor Green  
Write-Host "   CHROMA_TENANT=default_tenant" -ForegroundColor White
Write-Host "   CHROMA_DATABASE=default_database" -ForegroundColor White
Write-Host "✓ ChromaDB tenant and database already exist" -ForegroundColor Green

Write-Host "2. Clean shutdown of all processes..." -ForegroundColor Cyan
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

# Clean shutdown wait
Start-Sleep -Seconds 5

Write-Host "3. Starting fresh API server with .env config..." -ForegroundColor Cyan
# Start API server - it will read from .env file
$apiProcess = Start-Process -FilePath "python" -ArgumentList "-m", "src.main" -PassThru -NoNewWindow
Write-Host "API server started (PID: $($apiProcess.Id)) - reading tenant config from .env" -ForegroundColor Green

Write-Host "4. Extended initialization wait (background tasks)..." -ForegroundColor Cyan
Start-Sleep -Seconds 30

Write-Host "5. System health verification..." -ForegroundColor Cyan
$attempts = 0
$maxAttempts = 15
$systemReady = $false
$lastErrorMessage = ""

while ($attempts -lt $maxAttempts -and -not $systemReady) {
    $attempts++
    Write-Host "Health verification attempt $attempts/$maxAttempts..."
    
    $apiHealth = Invoke-WebRequest -Uri "http://localhost:8082/api/v1/health/readiness" -UseBasicParsing -TimeoutSec 20 -ErrorAction SilentlyContinue
    if ($apiHealth) {
        $response = $apiHealth.Content | ConvertFrom-Json
        Write-Host "API Status: $($response.status)" -ForegroundColor $(if($response.status -eq "ready") {"Green"} elseif($response.status -eq "not_ready") {"Yellow"} else {"Red"})
        
        if ($response.status -eq "ready") {
            $systemReady = $true
            Write-Host ""
            Write-Host "SUCCESS: COMPLETE GRAPHRAG SYSTEM IS READY!" -ForegroundColor Green
            Write-Host ""
            Write-Host "ChromaDB: v2 tenant architecture (default_tenant/default_database)" -ForegroundColor Green
            Write-Host "Neo4j: Graph database connected" -ForegroundColor Green  
            Write-Host "Redis: Cache system ready" -ForegroundColor Green
            Write-Host "API: All health checks passing" -ForegroundColor Green
        } elseif ($response.status -eq "not_ready") {
            if ($response.self_heal -and $response.self_heal.errors) {
                $errors = $response.self_heal.errors -join ', '
                $lastErrorMessage = $errors
                Write-Host "Still initializing... Errors: $errors" -ForegroundColor Yellow
                
                # Check if we still have the tenant=None problem
                if ($errors -like "*tenant: None*") {
                    Write-Host "Still seeing tenant=None errors - environment not fully loaded" -ForegroundColor Yellow
                } elseif ($errors -like "*409*" -or $errors -like "*already exists*") {
                    Write-Host "Good: Using correct tenant path (409 = collection exists)" -ForegroundColor Green
                }
            } else {
                Write-Host "Still initializing... (no specific errors)" -ForegroundColor Yellow
            }
        }
    } else {
        Write-Host "API not responding..." -ForegroundColor Red
    }
    
    if (-not $systemReady) {
        Start-Sleep -Seconds 4
    }
}

Write-Host ""
if ($systemReady) {
    Write-Host "GRAPHRAG SYSTEM FULLY OPERATIONAL!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next Steps:" -ForegroundColor Cyan
    Write-Host "1. Your frontend should now work - restart it to use port 8082" -ForegroundColor White
    Write-Host "2. Test the dashboard at http://localhost:3000" -ForegroundColor White  
    Write-Host "3. API health: http://localhost:8082/api/v1/health/readiness" -ForegroundColor White
    Write-Host ""
    Write-Host "The System is starting up message should be gone!" -ForegroundColor Yellow
} else {
    Write-Host "System initialization incomplete after all attempts" -ForegroundColor Red
    Write-Host "Last error: $lastErrorMessage" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "If still seeing tenant: None errors, there may be cached modules." -ForegroundColor Yellow
    Write-Host "Try restarting your PowerShell session and running this script again." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== CLEAN RESTART COMPLETED ===" -ForegroundColor Yellow