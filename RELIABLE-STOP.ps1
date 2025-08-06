param()

$ErrorActionPreference = 'Continue'
$PidFile = "logs\system-pids.json"
$LogFile = "logs\reliable-stop-$(Get-Date -Format 'yyyy-MM-dd-HH-mm-ss').log"

# Ensure logs directory exists
if (-not (Test-Path "logs")) { 
    New-Item -ItemType Directory -Path "logs" -Force | Out-Null 
}

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] $Message"
    Write-Host $logEntry
    Add-Content -Path $LogFile -Value $logEntry -ErrorAction SilentlyContinue
}

Write-Log "=== RELIABLE GRAPHRAG SHUTDOWN STARTING ===" "INFO"
Write-Log "Log file: $LogFile" "INFO"

# Step 1: Kill tracked processes from PID file
if (Test-Path $PidFile) {
    Write-Log "Found PID file with tracked processes" "INFO"
    $pids = Get-Content $PidFile | ConvertFrom-Json -ErrorAction SilentlyContinue
    
    if ($pids) {
        foreach ($service in $pids.PSObject.Properties) {
            $serviceName = $service.Name
            $pid = $service.Value
            
            if ($pid -and $pid -ne 0) {
                $process = Get-Process -Id $pid -ErrorAction SilentlyContinue
                if ($process) {
                    Write-Log "Killing tracked $serviceName (PID: $pid)" "INFO"
                    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
                    Start-Sleep -Seconds 1
                    
                    # Verify it's dead
                    $stillRunning = Get-Process -Id $pid -ErrorAction SilentlyContinue
                    if ($stillRunning) {
                        Write-Log "Process $pid still alive, using taskkill /F" "WARN"
                        taskkill /PID $pid /F /T 2>$null
                    }
                    Write-Log "Stopped $serviceName (PID: $pid)" "SUCCESS"
                }
                else {
                    Write-Log "Process $serviceName (PID: $pid) was not running" "INFO"
                }
            }
        }
    }
    
    # Clear PID file
    "{}" | Set-Content $PidFile
    Write-Log "Cleared PID tracking file" "INFO"
}

# Step 2: Kill all processes on critical ports
$criticalPorts = @(3000, 8080, 8081)
foreach ($port in $criticalPorts) {
    Write-Log "Checking port $port for processes..." "INFO"
    
    $lines = netstat -ano | findstr ":$port.*LISTENING"
    if ($lines) {
        foreach ($line in $lines) {
            if ($line -match "LISTENING\s+(\d+)$") {
                $pid = [int]$Matches[1]
                $process = Get-Process -Id $pid -ErrorAction SilentlyContinue
                if ($process) {
                    Write-Log "Killing process on port $port (PID: $pid, Name: $($process.ProcessName))" "INFO"
                    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
                    taskkill /PID $pid /F /T 2>$null
                    Write-Log "Killed port $port process (PID: $pid)" "SUCCESS"
                }
            }
        }
    }
}

# Step 3: Kill uvicorn processes (but preserve Claude Code)
Write-Log "Cleaning up uvicorn processes..." "INFO"
$pythonProcesses = Get-Process python -ErrorAction SilentlyContinue

foreach ($proc in $pythonProcesses) {
    $cmdline = ""
    $cmdlineObj = Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.Id)" -ErrorAction SilentlyContinue
    if ($cmdlineObj) {
        $cmdline = $cmdlineObj.CommandLine
    }
    
    if ($cmdline -and ($cmdline -like "*uvicorn*" -or $cmdline -like "*src.main:app*")) {
        Write-Log "Killing uvicorn process (PID: $($proc.Id))" "INFO"
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        taskkill /PID $($proc.Id) /F /T 2>$null
        Write-Log "Killed uvicorn (PID: $($proc.Id))" "SUCCESS"
    }
}

# Step 4: Stop containers
Write-Log "Stopping containers..." "INFO"
$composeFiles = @("podman-compose.dev.yml", "docker-compose.dev.yml", "docker-compose.yml")
foreach ($file in $composeFiles) {
    if (Test-Path $file) {
        Write-Log "Stopping containers from $file" "INFO"
        if ($file -like "podman-*") {
            podman-compose -f $file down --remove-orphans 2>$null
        }
        else {
            podman-compose -f $file down --remove-orphans 2>$null
        }
    }
}

# Step 5: Verify critical ports are free
Write-Log "Verifying ports are free..." "INFO"
foreach ($port in $criticalPorts) {
    $listening = netstat -ano | findstr ":$port.*LISTENING"
    if (-not $listening) {
        Write-Log "Port $port is free" "SUCCESS"
    }
    else {
        Write-Log "Port $port still has listeners: $listening" "WARN"
    }
}

Write-Log "=== RELIABLE SHUTDOWN COMPLETED ===" "SUCCESS"
Write-Log "All GraphRAG services have been stopped" "SUCCESS"
Write-Log "System is ready for clean restart" "INFO"