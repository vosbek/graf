param()

$ErrorActionPreference = 'Continue'
$PidFile = "logs\system-pids.json"
$LogFile = "logs\safe-start-$(Get-Date -Format 'yyyy-MM-dd-HH-mm-ss').log"

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

function Test-ServiceHealth {
    param([string]$Url, [int]$TimeoutSeconds = 10)
    $response = Invoke-WebRequest -Uri $Url -TimeoutSec $TimeoutSeconds -UseBasicParsing -ErrorAction SilentlyContinue
    if ($response -and $response.StatusCode -eq 200) {
        return $true
    }
    return $false
}

Write-Log "=== SAFE GRAPHRAG STARTUP STARTING ===" "INFO"
Write-Log "Log file: $LogFile" "INFO"

# Step 1: Pre-flight checks - ensure system is clean
Write-Log "Running pre-flight checks..." "INFO"

# Check if critical ports are free
$criticalPorts = @(3000, 8081, 8000, 7687)
$blockedPorts = @()
foreach ($port in $criticalPorts) {
    $listening = netstat -ano | findstr ":$port.*LISTENING"
    if ($listening) {
        $blockedPorts += $port
        Write-Log "Port $port is already in use" "WARN"
    }
}

if ($blockedPorts.Count -gt 0) {
    Write-Log "Blocked ports detected: $($blockedPorts -join ', ')" "ERROR"
    Write-Log "Run SAFE-STOP.ps1 first to clean up existing processes" "ERROR"
    exit 1
}

Write-Log "All critical ports are free" "SUCCESS"

# Step 2: Initialize PID tracking
Write-Log "Initializing PID tracking system..." "INFO"
$pids = @{
    "containers" = 0
    "api_server" = 0
    "frontend" = 0
}
$pids | ConvertTo-Json | Set-Content $PidFile
Write-Log "PID tracking initialized" "SUCCESS"

# Step 3: Start containers
Write-Log "Starting containers..." "INFO"
$containerStarted = $false
$composeFiles = @("podman-compose.dev.yml", "docker-compose.dev.yml")

foreach ($file in $composeFiles) {
    if (Test-Path $file) {
        Write-Log "Starting containers from $file" "INFO"
        
        $process = Start-Process -FilePath "podman-compose" -ArgumentList "-f", $file, "up", "-d" -PassThru -NoNewWindow -Wait
        
        if ($process.ExitCode -eq 0) {
            $pids["containers"] = $process.Id
            $containerStarted = $true
            Write-Log "Containers started successfully from $file" "SUCCESS"
            break
        } else {
            Write-Log "Container startup failed with exit code: $($process.ExitCode)" "ERROR"
        }
    }
}

if (-not $containerStarted) {
    Write-Log "No containers started - continuing with local services only" "WARN"
}

# Wait for container services to be ready
if ($containerStarted) {
    Write-Log "Waiting for container services to be ready..." "INFO"
    
    # Wait for ChromaDB (port 8000)
    Write-Log "Waiting for ChromaDB on port 8000..." "INFO"
    if (Wait-ForPort -Port 8000 -TimeoutSeconds 30) {
        Write-Log "ChromaDB is listening on port 8000" "SUCCESS"
    } else {
        Write-Log "ChromaDB not responding on port 8000" "WARN"
    }
    
    # Wait for Neo4j (port 7687)
    Write-Log "Waiting for Neo4j on port 7687..." "INFO"
    if (Wait-ForPort -Port 7687 -TimeoutSeconds 30) {
        Write-Log "Neo4j is listening on port 7687" "SUCCESS"
    } else {
        Write-Log "Neo4j not responding on port 7687" "WARN"
    }
    
    Start-Sleep -Seconds 5  # Additional grace period
}

# Step 4: Start API server
Write-Log "Starting API server..." "INFO"

# Set environment variables for v2-only ChromaDB
$env:CHROMA_TENANT = ""
$env:CHROMA_DATABASE = ""
$env:APP_ENV = "development"
$env:API_HOST = "0.0.0.0"
$env:API_PORT = "8081"
$env:LOG_LEVEL = "INFO"

Write-Log "Environment configured for v2-only ChromaDB" "INFO"

$apiProcess = Start-Process -FilePath "python" -ArgumentList "-m", "src.main" -PassThru -NoNewWindow
$pids["api_server"] = $apiProcess.Id
Write-Log "API server started (PID: $($apiProcess.Id))" "SUCCESS"

# Wait for API server to be ready
Write-Log "Waiting for API server on port 8081..." "INFO"
if (Wait-ForPort -Port 8081 -TimeoutSeconds 45) {
    Write-Log "API server is listening on port 8081" "SUCCESS"
    
    # Test health endpoint
    Start-Sleep -Seconds 5  # Grace period for full initialization
    Write-Log "Testing API health endpoint..." "INFO"
    if (Test-ServiceHealth -Url "http://localhost:8081/api/v1/health/readiness") {
        Write-Log "API server health check passed" "SUCCESS"
    } else {
        Write-Log "API server health check failed - may still be initializing" "WARN"
    }
} else {
    Write-Log "API server not responding on port 8081" "ERROR"
    exit 1
}

# Step 5: Start frontend (optional)
Write-Log "Starting frontend..." "INFO"
if (Test-Path "frontend\package.json") {
    Set-Location "frontend"
    $frontendProcess = Start-Process -FilePath "npm" -ArgumentList "start" -PassThru -NoNewWindow
    $pids["frontend"] = $frontendProcess.Id
    Set-Location ".."
    Write-Log "Frontend started (PID: $($frontendProcess.Id))" "SUCCESS"
    
    # Wait for frontend to be ready
    Write-Log "Waiting for frontend on port 3000..." "INFO"
    if (Wait-ForPort -Port 3000 -TimeoutSeconds 60) {
        Write-Log "Frontend is listening on port 3000" "SUCCESS"
    } else {
        Write-Log "Frontend not responding on port 3000" "WARN"
    }
} else {
    Write-Log "Frontend not available (no package.json found)" "INFO"
}

# Step 6: Update PID file and verify all services
Write-Log "Updating PID tracking..." "INFO"
$pids | ConvertTo-Json | Set-Content $PidFile
Write-Log "PID tracking updated" "SUCCESS"

# Final verification
Write-Log "Running final service verification..." "INFO"
$servicesRunning = 0
$totalServices = 0

# Check API server
$totalServices++
if (Wait-ForPort -Port 8081 -TimeoutSeconds 5) {
    $servicesRunning++
    Write-Log "API server verified (port 8081)" "SUCCESS"
} else {
    Write-Log "API server not responding (port 8081)" "ERROR"
}

# Check frontend
if (Test-Path "frontend\package.json") {
    $totalServices++
    if (Wait-ForPort -Port 3000 -TimeoutSeconds 5) {
        $servicesRunning++
        Write-Log "Frontend verified (port 3000)" "SUCCESS"
    } else {
        Write-Log "Frontend not responding (port 3000)" "ERROR"
    }
}

Write-Log "=== SAFE STARTUP COMPLETED ===" "SUCCESS"
Write-Log "Services running: $servicesRunning/$totalServices" "INFO"

if ($servicesRunning -eq $totalServices) {
    Write-Log "All services are running successfully!" "SUCCESS"
    Write-Log "Dashboard: http://localhost:3000" "INFO"
    Write-Log "API: http://localhost:8081/api/v1/health/readiness" "INFO"
    Write-Log "Logs: $LogFile" "INFO"
    exit 0
} else {
    Write-Log "Some services failed to start properly" "WARN"
    Write-Log "Check the logs for details: $LogFile" "INFO"
    exit 1
}