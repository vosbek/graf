param()

$ErrorActionPreference = 'Continue'
$LogFile = "logs\start-8082-$(Get-Date -Format 'yyyy-MM-dd-HH-mm-ss').log"

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

function Wait-ForPort {
    param([int]$Port, [int]$TimeoutSeconds = 30)
    $elapsed = 0
    while ($elapsed -lt $TimeoutSeconds) {
        $listening = netstat -ano | findstr ":$Port.*LISTENING"
        if ($listening) {
            return $true
        }
        Start-Sleep -Seconds 1
        $elapsed++
    }
    return $false
}

Write-Log "=== STARTING GRAPHRAG ON PORT 8082 (AVOIDING GHOST CONNECTIONS) ===" "INFO"

# Check if port 8082 is free
$port8082 = netstat -ano | findstr ":8082.*LISTENING"
if ($port8082) {
    Write-Log "Port 8082 is also blocked. You may need to restart your computer." "ERROR"
    exit 1
}

Write-Log "Port 8082 is free. Starting services..." "SUCCESS"

# Start containers first
Write-Log "Starting containers..." "INFO"
if (Test-Path "podman-compose.dev.yml") {
    podman-compose -f podman-compose.dev.yml up -d
    Start-Sleep -Seconds 10
    Write-Log "Containers started" "SUCCESS"
}

# Set environment for port 8082
$env:CHROMA_TENANT = ""
$env:CHROMA_DATABASE = ""
$env:APP_ENV = "development"
$env:API_HOST = "0.0.0.0"
$env:API_PORT = "8082"
$env:LOG_LEVEL = "INFO"

Write-Log "Environment configured for port 8082" "INFO"

# Start API server on 8082
Write-Log "Starting API server on port 8082..." "INFO"
$apiProcess = Start-Process -FilePath "python" -ArgumentList "-m", "src.main" -PassThru -NoNewWindow
Write-Log "API server started (PID: $($apiProcess.Id)) on port 8082" "SUCCESS"

# Wait for API to be ready
if (Wait-ForPort -Port 8082 -TimeoutSeconds 45) {
    Write-Log "API server is running on port 8082" "SUCCESS"
    Write-Log "GraphRAG is now accessible at:" "INFO"
    Write-Log "   API: http://localhost:8082/api/v1/health/readiness" "INFO"
    Write-Log "   You can access all endpoints by using port 8082 instead of 8081" "INFO"
}
else {
    Write-Log "API server failed to start on port 8082" "ERROR"
    exit 1
}

Write-Log "=== STARTUP ON PORT 8082 COMPLETED ===" "SUCCESS"