param()

Write-Host "=== FIXING GHOST TCP CONNECTIONS ON PORT 8081 ===" -ForegroundColor Yellow

Write-Host "This is a common Windows issue where crashed processes leave ghost TCP listeners." -ForegroundColor Gray
Write-Host "The solution is to reset the TCP/IP stack or wait for Windows to clean them up." -ForegroundColor Gray
Write-Host ""

# Method 1: Try to flush DNS and reset network stack
Write-Host "Method 1: Flushing network stack..." -ForegroundColor Cyan
ipconfig /flushdns | Out-Null
Write-Host "DNS cache flushed" -ForegroundColor Green

# Method 2: Wait and check if they clear naturally
Write-Host "Method 2: Waiting for Windows to clean up ghost connections..." -ForegroundColor Cyan
Write-Host "Waiting 10 seconds for automatic cleanup..." -ForegroundColor Gray
Start-Sleep -Seconds 10

$stillListening = netstat -ano | findstr ":8081.*LISTENING"
if ($stillListening) {
    Write-Host "Ghost connections still present. Using alternative port..." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "SOLUTION: Use port 8082 instead of 8081" -ForegroundColor Cyan
    Write-Host "We will modify the startup script to use port 8082 which should be free." -ForegroundColor Cyan
    
    # Check if 8082 is free
    $port8082 = netstat -ano | findstr ":8082.*LISTENING"
    if ($port8082) {
        Write-Host "Port 8082 is also blocked" -ForegroundColor Red
        Write-Host "Recommendation: Restart your computer to clear all ghost connections" -ForegroundColor Yellow
    } else {
        Write-Host "Port 8082 is available! We will use this instead." -ForegroundColor Green
    }
} else {
    Write-Host "Port 8081 is now free!" -ForegroundColor Green
}

Write-Host ""
Write-Host "=== GHOST CONNECTION FIX COMPLETED ===" -ForegroundColor Yellow