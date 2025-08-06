param()

Write-Host "=== RESTARTING GRAPHRAG WITH FIXED CONFIGURATION ===" -ForegroundColor Yellow

# Stop the current API server on 8082
Write-Host "Stopping current API server..." -ForegroundColor Cyan
$processes = Get-Process python -ErrorAction SilentlyContinue
foreach ($proc in $processes) {
    $cmdline = ""
    $cmdlineObj = Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.Id)" -ErrorAction SilentlyContinue
    if ($cmdlineObj) {
        $cmdline = $cmdlineObj.CommandLine
    }
    
    if ($cmdline -and ($cmdline -like "*uvicorn*" -or $cmdline -like "*src.main*")) {
        Write-Host "Killing API server process (PID: $($proc.Id))" -ForegroundColor Red
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
}

Start-Sleep -Seconds 3

# Ensure the .env file is loaded by starting fresh
Write-Host "Starting API server with updated configuration..." -ForegroundColor Green
Write-Host "The .env file now has:" -ForegroundColor Gray
Write-Host "  - API_PORT=8082" -ForegroundColor Gray
Write-Host "  - All database connections configured" -ForegroundColor Gray
Write-Host "  - CORS updated for port 8082" -ForegroundColor Gray

# Start API server
$apiProcess = Start-Process -FilePath "python" -ArgumentList "-m", "src.main" -PassThru -NoNewWindow
Write-Host "API server restarted (PID: $($apiProcess.Id))" -ForegroundColor Green

Start-Sleep -Seconds 5

# Check if it's running
$listening = netstat -ano | findstr ":8082.*LISTENING"
if ($listening) {
    Write-Host "✓ API server is now running on port 8082" -ForegroundColor Green
    Write-Host "✓ Frontend proxy updated to use port 8082" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "1. Restart your frontend (Ctrl+C in the frontend terminal, then 'npm start')" -ForegroundColor White
    Write-Host "2. The frontend will now connect to the API on port 8082" -ForegroundColor White
    Write-Host "3. Check: http://localhost:8082/api/v1/health/readiness" -ForegroundColor White
} else {
    Write-Host "✗ API server failed to start on port 8082" -ForegroundColor Red
}

Write-Host "=== RESTART COMPLETED ===" -ForegroundColor Yellow