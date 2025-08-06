#!/usr/bin/env pwsh
<#
.SYNOPSIS
    GraphRAG Simplified Startup Script
.DESCRIPTION
    A streamlined script to start the GraphRAG platform. It ensures all dependencies are met,
    loads environment configurations, and launches the required services with robust error handling.
.PARAMETER Mode
    Specifies which part of the application to start.
    'full'    - (Default) Starts all backend and frontend services.
    'backend' - Starts only the backend containers (Neo4j, ChromaDB, Redis).
    'api'     - Starts only the Python FastAPI server.
    'frontend'- Starts only the React frontend development server.
.PARAMETER Clean
    Performs a clean startup by stopping and removing existing containers and volumes
    before starting the services.
.EXAMPLE
    # Start the entire application stack
    .\START.ps1 -Mode full

.EXAMPLE
    # Start the full stack with a clean slate
    .\START.ps1 -Mode full -Clean

.EXAMPLE
    # Start only the backend services
    .\START.ps1 -Mode backend

.NOTES
    This script must be run from the project's root directory.
    It requires Podman, Podman-Compose, Python 3.8+, and Node.js to be installed and available in the system's PATH.
#>
param(
    [ValidateSet('full', 'backend', 'api', 'frontend')]
    [string]$Mode = 'full',
    [switch]$Clean
)

# --- Script Configuration ---
$ErrorActionPreference = "Stop"
$LogFile = "logs\startup-$(Get-Date -Format 'yyyy-MM-dd_HH-mm-ss').log"
$ComposeFile = "podman-compose.dev.yml"
$PidTrackingFile = "logs\running-pids.json"

# --- Logging Function ---
function Write-Log {
    param(
        [string]$Message,
        [ValidateSet("INFO", "WARN", "ERROR")]
        [string]$Level = "INFO",
        [string]$Component = "MAIN"
    )
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] [$Component] $Message"

    # Write to console with color
    switch ($Level) {
        "ERROR" { Write-Host $logEntry -ForegroundColor Red }
        "WARN"  { Write-Host $logEntry -ForegroundColor Yellow }
        default { Write-Host $logEntry -ForegroundColor Green }
    }
    # Write to log file
    if (-not (Test-Path "logs")) { New-Item -ItemType Directory -Path "logs" -Force | Out-Null }
    Add-Content -Path $LogFile -Value $logEntry
}

# --- Environment File Loader ---
function Load-EnvFile {
    param([string]$FilePath = ".env")
    if (-not (Test-Path $FilePath)) {
        Write-Log ".env file not found at '$FilePath'. Using default environment variables." "WARN" "ENV"
        return
    }
    try {
        Get-Content $FilePath | ForEach-Object {
            $line = $_.Trim()
            if ($line -and $line -notmatch '^\s*#') {
                $parts = $line -split '=', 2
                if ($parts.Length -eq 2) {
                    $key = $parts[0].Trim()
                    $value = $parts[1].Trim()
                    # Remove quotes if present
                    if ($value.StartsWith('"') -and $value.EndsWith('"')) {
                        $value = $value.Substring(1, $value.Length - 2)
                    }
                    # Set environment variable for the current process
                    [System.Environment]::SetEnvironmentVariable($key, $value, 'Process')
                    Write-Log "Loaded '$key' from .env file." "INFO" "ENV"
                }
            }
        }
    } catch {
        Write-Log "Failed to read or parse the .env file: $($_.Exception.Message)" "ERROR" "ENV"
        throw "Could not load environment from .env file. Halting."
    }
}

# --- Dependency and Service Functions ---

function Check-Dependencies {
    Write-Log "Checking for required dependencies..." "INFO" "DEPS"
    $dependencies = @{
        "podman"         = { podman --version }
        "podman-compose" = { podman-compose --version }
        "python"         = { python --version }
    }
    
    # Only check node/npm if we're starting frontend
    if ($Mode -eq 'full' -or $Mode -eq 'frontend') {
        $dependencies["node"] = { node --version }
        $dependencies["npm"] = { npm --version }
    }
    
    $missing = @()

    foreach ($dep in $dependencies.Keys) {
        try {
            $null = & $dependencies[$dep] 2>$null
            Write-Log "- Found '$dep'." "INFO" "DEPS"
        } catch {
            Write-Log "- Dependency '$dep' is missing or not in PATH." "ERROR" "DEPS"
            $missing += $dep
        }
    }

    if ($missing.Count -gt 0) {
        throw "Please install the following missing dependencies: $($missing -join ', ')"
    }
    Write-Log "All required dependencies are installed." "INFO" "DEPS"
}

function Wait-ForServiceHealth {
    param(
        [string]$ServiceName,
        [string]$Url,
        [int]$TimeoutSeconds = 120,
        [int]$CheckIntervalSeconds = 5
    )
    
    Write-Log "Waiting for '$ServiceName' to be healthy at $Url..." "INFO" "HEALTH"
    $timeout = (Get-Date).AddSeconds($TimeoutSeconds)
    $attemptCount = 0
    
    while ((Get-Date) -lt $timeout) {
        $attemptCount++
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
            if ($response.StatusCode -eq 200) {
                $elapsed = $TimeoutSeconds - (($timeout - (Get-Date)).TotalSeconds)
                Write-Log "'$ServiceName' is healthy (attempt $attemptCount, ${elapsed}s elapsed)." "INFO" "HEALTH"
                return $true
            }
        } catch {
            Write-Log "Health check attempt $attemptCount for '$ServiceName' failed: $($_.Exception.Message)" "WARN" "HEALTH"
        }
        Start-Sleep -Seconds $CheckIntervalSeconds
    }
    
    throw "'$ServiceName' failed to become healthy within the $TimeoutSeconds-second timeout (attempted $attemptCount times)."
}

function Start-BackendServices {
    $Component = "BACKEND"
    Write-Log "Starting backend services..." "INFO" $Component

    if ($Clean) {
        Write-Log "Performing clean stop of backend services..." "WARN" $Component
        try {
            podman-compose -f $ComposeFile down --volumes --remove-orphans 2>$null
            Write-Log "Backend services and volumes removed successfully." "INFO" $Component
        } catch {
            Write-Log "Failed to run 'podman-compose down'. It might be the first run." "WARN" $Component
        }
    }

    try {
        Write-Log "Bringing up backend services with podman-compose..." "INFO" $Component
        $composeOutput = podman-compose -f $ComposeFile up -d chromadb neo4j redis 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Log "Podman-compose failed with exit code $LASTEXITCODE" "ERROR" $Component
            Write-Log "Output: $composeOutput" "ERROR" $Component
            throw "Failed to start backend services"
        }
        Write-Log "Backend services started. Waiting for health checks..." "INFO" $Component
    } catch {
        throw "Failed to start backend services with podman-compose. Error: $($_.Exception.Message)"
    }

    # Wait for services to be healthy with proper endpoints
    $services = @{
        "ChromaDB" = "http://localhost:8000/api/v2/healthcheck"
        "Neo4j"    = "http://localhost:7474"
        "Redis"    = "http://localhost:6379"  # Redis doesn't have HTTP, but we'll check the port
    }
    
    foreach ($name in $services.Keys) {
        $url = $services[$name]
        if ($name -eq "Redis") {
            # Special handling for Redis - just check if port is open
            Write-Log "Checking Redis connectivity on port 6379..." "INFO" $Component
            $timeout = (Get-Date).AddSeconds(60)
            $connected = $false
            while ((Get-Date) -lt $timeout -and -not $connected) {
                try {
                    $tcpClient = New-Object System.Net.Sockets.TcpClient
                    $tcpClient.Connect("localhost", 6379)
                    $tcpClient.Close()
                    $connected = $true
                    Write-Log "Redis is accepting connections on port 6379." "INFO" $Component
                } catch {
                    Start-Sleep -Seconds 3
                }
            }
            if (-not $connected) {
                throw "Redis failed to become available on port 6379"
            }
        } else {
            Wait-ForServiceHealth -ServiceName $name -Url $url -TimeoutSeconds 180 -CheckIntervalSeconds 5
        }
    }
    Write-Log "All backend services are healthy and ready." "INFO" $Component
}

function Start-ApiServer {
    $Component = "API"
    Write-Log "Starting API server..." "INFO" $Component
    
    # Get API port from environment or use default
    $apiPort = $env:API_PORT
    if (-not $apiPort) { $apiPort = 8082 }
    
    try {
        # Ensure Python dependencies are installed
        if (Test-Path "requirements.txt") {
            Write-Log "Installing/verifying Python dependencies from requirements.txt..." "INFO" $Component
            pip install -r requirements.txt 2>$null | Out-Null
        }
        
        Write-Log "Launching Uvicorn for src.main:app on port $apiPort..." "INFO" $Component
        $process = Start-Process python -ArgumentList "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "$apiPort", "--reload" -PassThru -WindowStyle Hidden
        
        if (-not $process -or -not $process.Id) {
            throw "Failed to start API server process"
        }
        
        Write-Log "API server process started with PID: $($process.Id)." "INFO" $Component
        
        # Save PID to tracking file for cleanup
        try {
            $pidData = @{}
            if (Test-Path $PidTrackingFile) {
                $existing = Get-Content $PidTrackingFile -Raw | ConvertFrom-Json
                $existing.PSObject.Properties | ForEach-Object { $pidData[$_.Name] = $_.Value }
            }
            $pidData["api_server"] = $process.Id
            $pidData | ConvertTo-Json | Set-Content $PidTrackingFile
            Write-Log "API server PID saved to tracking file." "INFO" $Component
        } catch {
            Write-Log "Failed to save PID to tracking file: $($_.Exception.Message)" "WARN" $Component
        }
        
        # Health check
        $healthUrl = "http://localhost:$apiPort/api/v1/health/"
        Wait-ForServiceHealth -ServiceName "API Server" -Url $healthUrl -TimeoutSeconds 90 -CheckIntervalSeconds 3
        
        Write-Log "API server is healthy and ready at http://localhost:$apiPort" "INFO" $Component
        
    } catch {
        throw "Failed to start the API server. Error: $($_.Exception.Message)"
    }
}

function Start-Frontend {
    $Component = "FRONTEND"
    Write-Log "Starting frontend..." "INFO" $Component
    try {
        if (-not (Test-Path "frontend")) {
            Write-Log "Frontend directory not found. Skipping frontend startup." "WARN" $Component
            return
        }
        
        Push-Location -Path "frontend"
        
        # Ensure Node.js dependencies are installed
        if (-not (Test-Path "node_modules")) {
            Write-Log "Installing Node.js dependencies with npm..." "INFO" $Component
            npm install 2>$null
            if ($LASTEXITCODE -ne 0) {
                throw "npm install failed"
            }
        }
        
        Write-Log "Launching frontend development server with 'npm start'..." "INFO" $Component
        # Start in a new window so the user can see the output and stop it easily.
        $frontendProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", "npm start" -PassThru -WindowStyle Normal
        
        if ($frontendProcess -and $frontendProcess.Id) {
            Write-Log "Frontend server started with PID: $($frontendProcess.Id)" "INFO" $Component
            
            # Save PID to tracking file
            try {
                $pidData = @{}
                if (Test-Path $PidTrackingFile) {
                    $existing = Get-Content $PidTrackingFile -Raw | ConvertFrom-Json
                    $existing.PSObject.Properties | ForEach-Object { $pidData[$_.Name] = $_.Value }
                }
                $pidData["frontend"] = $frontendProcess.Id
                $pidData | ConvertTo-Json | Set-Content $PidTrackingFile
                Write-Log "Frontend PID saved to tracking file." "INFO" $Component
            } catch {
                Write-Log "Failed to save frontend PID: $($_.Exception.Message)" "WARN" $Component
            }
        }
        
        Write-Log "Frontend server is starting in a new window. Monitor that window for status." "INFO" $Component
        Write-Log "Access the UI at http://localhost:3000 once it's compiled." "INFO" $Component
        
        Pop-Location
    } catch {
        if ((Get-Location).Path -like "*frontend*") { Pop-Location }
        throw "Failed to start the frontend. Error: $($_.Exception.Message)"
    }
}

# --- Main Execution Logic ---

Write-Log "--- GraphRAG Startup Initialized (Mode: $Mode, Clean: $Clean) ---"

try {
    # 1. Load Environment Variables FIRST
    Write-Log "=== PHASE 1: Loading Environment Configuration ===" "INFO"
    Load-EnvFile

    # 2. Check Dependencies
    Write-Log "=== PHASE 2: Dependency Validation ===" "INFO"
    Check-Dependencies

    # 3. Execute Startup Mode with Dependencies-First Approach
    switch ($Mode) {
        'backend' {
            Write-Log "=== PHASE 3: Starting Backend Services Only ===" "INFO"
            Start-BackendServices
        }
        'api' {
            Write-Log "=== PHASE 3: Starting API Server Only ===" "INFO"
            Start-ApiServer
        }
        'frontend' {
            Write-Log "=== PHASE 3: Starting Frontend Only ===" "INFO"
            Start-Frontend
        }
        'full' {
            Write-Log "=== PHASE 3: Starting Full Stack (Dependencies-First) ===" "INFO"
            Write-Log "Step 1: Backend Services (ChromaDB, Neo4j, Redis)" "INFO"
            Start-BackendServices
            Write-Log "Step 2: API Server (after backend is healthy)" "INFO"
            Start-ApiServer
            Write-Log "Step 3: Frontend (after API is healthy)" "INFO"
            Start-Frontend
        }
    }

    $apiPort = $env:API_PORT
    if (-not $apiPort) { $apiPort = 8082 }
    
    $successMessage = @"
=== SYSTEM STARTUP COMPLETE ===
Mode: '$Mode'
$(if ($Mode -eq 'backend' -or $Mode -eq 'full') { "✅ Backend services running (ChromaDB, Neo4j, Redis)" })
$(if ($Mode -eq 'api' -or $Mode -eq 'full') { "✅ API Server running at http://localhost:$apiPort" })
$(if ($Mode -eq 'frontend' -or $Mode -eq 'full') { "✅ Frontend available at http://localhost:3000" })

Access Points:
- ChromaDB: http://localhost:8000/api/v2/healthcheck
- Neo4j Browser: http://localhost:7474 (neo4j / codebase-rag-2024)
- API Health: http://localhost:${apiPort}/api/v1/health/
- Frontend: http://localhost:3000

To stop the system: .\STOP.ps1
"@
    Write-Log $successMessage "INFO"

} catch {
    Write-Log "!!! CRITICAL ERROR DURING STARTUP !!!" "ERROR"
    Write-Log $_.Exception.Message "ERROR"
    Write-Log "Please check the logs at '$LogFile' for more details." "ERROR"
    Write-Log "For troubleshooting guidance, see troubleshoot8625.md" "INFO"
    exit 1
}