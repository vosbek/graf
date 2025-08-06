param()

$ErrorActionPreference = 'Continue'
$LogFile = "logs\safe-stop-$(Get-Date -Format 'yyyy-MM-dd-HH-mm-ss').log"

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

Write-Log "=== SAFE GRAPHRAG SHUTDOWN STARTING ===" "INFO"

# Step 1: Kill ONLY GraphRAG API processes (port 8081)
Write-Log "Checking for GraphRAG API processes on port 8081..." "INFO"
$lines = netstat -ano | findstr ":8081.*LISTENING"
if ($lines) {
    foreach ($line in $lines) {
        if ($line -match "LISTENING\s+(\d+)$") {
            $processId = [int]$Matches[1]
            $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
            if ($process) {
                # Double-check it's actually a Python/uvicorn process
                $cmdline = ""
                $cmdlineObj = Get-CimInstance Win32_Process -Filter "ProcessId=$processId" -ErrorAction SilentlyContinue
                if ($cmdlineObj) {
                    $cmdline = $cmdlineObj.CommandLine
                }
                
                if ($cmdline -and ($cmdline -like "*python*" -and ($cmdline -like "*uvicorn*" -or $cmdline -like "*src.main*"))) {
                    Write-Log "Killing GraphRAG API process (PID: $processId)" "INFO"
                    Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
                    Write-Log "Killed GraphRAG API (PID: $processId)" "SUCCESS"
                } else {
                    Write-Log "Skipping non-GraphRAG process on port 8081 (PID: $processId)" "INFO"
                }
            }
        }
    }
} else {
    Write-Log "No processes found on port 8081" "INFO"
}

# Step 2: Kill React frontend (port 3000) - safer approach
Write-Log "Checking for React frontend on port 3000..." "INFO"
$lines = netstat -ano | findstr ":3000.*LISTENING"
if ($lines) {
    foreach ($line in $lines) {
        if ($line -match "LISTENING\s+(\d+)$") {
            $processId = [int]$Matches[1]
            $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
            if ($process -and $process.ProcessName -eq "node") {
                Write-Log "Killing React frontend (PID: $processId)" "INFO"
                Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
                Write-Log "Killed React frontend (PID: $processId)" "SUCCESS"
            }
        }
    }
} else {
    Write-Log "No React frontend found on port 3000" "INFO"
}

# Step 3: Stop containers safely
Write-Log "Stopping containers..." "INFO"
$composeFiles = @("podman-compose.dev.yml", "docker-compose.dev.yml")
foreach ($file in $composeFiles) {
    if (Test-Path $file) {
        Write-Log "Stopping containers from $file" "INFO"
        podman-compose -f $file down --remove-orphans 2>$null
    }
}

# Step 4: Verify GraphRAG ports are free
Write-Log "Verifying GraphRAG ports are free..." "INFO"
$graphragPorts = @(3000, 8081)
foreach ($port in $graphragPorts) {
    $listening = netstat -ano | findstr ":$port.*LISTENING"
    if (-not $listening) {
        Write-Log "Port $port is free" "SUCCESS"
    } else {
        Write-Log "Port $port still has listeners (non-GraphRAG process)" "INFO"
    }
}

Write-Log "=== SAFE SHUTDOWN COMPLETED ===" "SUCCESS"
Write-Log "GraphRAG services stopped. PowerShell and other system processes preserved." "SUCCESS"