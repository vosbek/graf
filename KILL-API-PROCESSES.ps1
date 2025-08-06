Write-Host "=== KILLING API PROCESSES ===" -ForegroundColor Yellow

# Get processes using port 8081
$lines = netstat -ano | findstr ":8081.*LISTENING"
Write-Host "Port 8081 processes found: $($lines.Count)" -ForegroundColor Gray

# Extract PIDs and kill them
$processIds = @()
foreach ($line in $lines) {
    $parts = $line -split "\s+"
    $processId = $parts[-1]
    if ($processId -match "^\d+$") {
        $processIds += [int]$processId
    }
}

Write-Host "Killing processes: $($processIds -join ', ')" -ForegroundColor Red
foreach ($processId in $processIds) {
    Write-Host "Killing PID $processId" -ForegroundColor Red
    taskkill /PID $processId /F
}

# Kill any uvicorn processes
Write-Host "Killing uvicorn processes..." -ForegroundColor Gray
tasklist | findstr python | foreach {
    $parts = $_ -split "\s+"
    $processId = $parts[1]
    if ($processId -match "^\d+$") {
        $cmdline = (Get-CimInstance Win32_Process -Filter "ProcessId=$processId" -ErrorAction SilentlyContinue).CommandLine
        if ($cmdline -like "*uvicorn*" -or $cmdline -like "*src.main:app*") {
            Write-Host "Killing uvicorn PID $processId" -ForegroundColor Red
            taskkill /PID $processId /F
        }
    }
}

Write-Host "=== CLEANUP DONE ===" -ForegroundColor Green