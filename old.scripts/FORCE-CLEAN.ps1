param()

Write-Host "=== FORCE CLEANING PORT 8081 ===" -ForegroundColor Yellow

# Kill everything on port 8081 - no questions asked
$lines = netstat -ano | findstr ":8081.*LISTENING"
if ($lines) {
    Write-Host "Found processes on port 8081:" -ForegroundColor Red
    
    foreach ($line in $lines) {
        Write-Host "  $line" -ForegroundColor Gray
        if ($line -match "LISTENING\s+(\d+)$") {
            $processId = [int]$Matches[1]
            Write-Host "Killing PID $processId with extreme prejudice..." -ForegroundColor Red
            taskkill /PID $processId /F /T
            Start-Sleep -Seconds 1
        }
    }
}
else {
    Write-Host "No processes found on port 8081" -ForegroundColor Green
}

# Verify port is now free
Start-Sleep -Seconds 2
$stillListening = netstat -ano | findstr ":8081.*LISTENING"
if ($stillListening) {
    Write-Host "PORT 8081 STILL BLOCKED!" -ForegroundColor Red
    foreach ($line in $stillListening) {
        Write-Host "  $line" -ForegroundColor Red
    }
}
else {
    Write-Host "PORT 8081 IS NOW FREE!" -ForegroundColor Green
}

Write-Host "=== FORCE CLEAN COMPLETED ===" -ForegroundColor Yellow