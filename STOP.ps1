#!/usr/bin/env pwsh
<#
.SYNOPSIS
    GraphRAG System Shutdown Script - Enhanced Version
    
.DESCRIPTION
    Safe and comprehensive shutdown script for GraphRAG services.
    Uses PID tracking and graceful shutdown processes to avoid interfering with other system processes.
    
.PARAMETER Force
    Force stop all tracked processes immediately without graceful shutdown attempts
    
.PARAMETER VerboseLogs
    Enable detailed logging and diagnostics during shutdown
    
.EXAMPLE
    .\STOP.ps1                 # Normal graceful shutdown
    .\STOP.ps1 -Force          # Force stop all services
    .\STOP.ps1 -VerboseLogs    # Detailed logging during shutdown
    
.NOTES
    This script safely stops only GraphRAG-related processes using PID tracking and process filtering.
#>

param(
    [switch]$Force,
    [switch]$VerboseLogs
)

# Configuration
$ErrorActionPreference = 'SilentlyContinue'
$StartTime = Get-Date
$LogFile = "logs\stop-$(Get-Date -Format 'yyyy-MM-dd-HH-mm-ss').log"
$PidTrackingFile = "logs\running-pids.json"
$ComposeFile = "podman-compose.dev.yml"

# Ensure logs directory exists
if (-not (Test-Path "logs")) { 
    New-Item -ItemType Directory -Path "logs" -Force | Out-Null 
}

# Enhanced logging function
function Write-Log {
    param(
        [string]$Message, 
        [ValidateSet("INFO", "WARN", "ERROR", "DEBUG", "SUCCESS")]
        [string]$Level = "INFO",
        [string]$Component = "STOP"
    )
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"
    $processId = $PID
    $logEntry = "[$timestamp] [$processId] [$Component] [$Level] $Message"
    
    # Console output with colors
    switch ($Level) {
        "ERROR" { Write-Host $logEntry -ForegroundColor Red }
        "WARN"  { Write-Host $logEntry -ForegroundColor Yellow }
        "SUCCESS" { Write-Host $logEntry -ForegroundColor Green }
        "DEBUG" { if ($VerboseLogs) { Write-Host $logEntry -ForegroundColor Cyan } }
        default { Write-Host $logEntry }
    }
    
    # Always log to file
    Add-Content -Path $LogFile -Value $logEntry -ErrorAction SilentlyContinue
}

function Stop-TrackedProcesses {
    Write-Log "Checking for tracked processes in PID file..." "INFO" "PID"
    
    if (-not (Test-Path $PidTrackingFile)) {
        Write-Log "No PID tracking file found at: $PidTrackingFile" "DEBUG" "PID"
        return @()
    }
    
    try {
        $pidData = Get-Content $PidTrackingFile -Raw | ConvertFrom-Json
        $stoppedProcesses = @()
        
        # Get all properties of the JSON object
        $properties = $pidData.PSObject.Properties.Name
        
        foreach ($key in $properties) {
            $processPid = $pidData.$key
            try {
                $process = Get-Process -Id $processPid -ErrorAction SilentlyContinue
                if ($process) {
                    Write-Log "Stopping tracked process: $key (PID: $processPid)" "INFO" "PID"
                    if ($VerboseLogs) {
                        Write-Log "Process details: $($process.ProcessName) - $($process.StartTime)" "DEBUG" "PID"
                    }
                    
                    if ($Force) {
                        Stop-Process -Id $processPid -Force -ErrorAction SilentlyContinue
                        Write-Log "Force stopped process $key (PID: $processPid)" "SUCCESS" "PID"
                    } else {
                        # Try graceful shutdown first
                        try {
                            $process.CloseMainWindow()
                            Start-Sleep -Milliseconds 2000
                            
                            # Check if process has exited
                            $checkProcess = Get-Process -Id $processPid -ErrorAction SilentlyContinue
                            if ($checkProcess -and -not $checkProcess.HasExited) {
                                Write-Log "Graceful shutdown failed for $key, using force stop..." "WARN" "PID"
                                Stop-Process -Id $processPid -Force -ErrorAction SilentlyContinue
                            }
                            Write-Log "Gracefully stopped process $key (PID: $processPid)" "SUCCESS" "PID"
                        } catch {
                            Write-Log "Failed to gracefully stop $key, using force stop..." "WARN" "PID"
                            Stop-Process -Id $processPid -Force -ErrorAction SilentlyContinue
                        }
                    }
                    
                    $stoppedProcesses += @{
                        Name = $key
                        PID = $processPid
                        Status = "Stopped"
                    }
                } else {
                    Write-Log "Tracked process $key (PID: $processPid) was not running" "DEBUG" "PID"
                    $stoppedProcesses += @{
                        Name = $key
                        PID = $processPid
                        Status = "NotRunning"
                    }
                }
            } catch {
                Write-Log "Failed to stop tracked process $key (PID: $processPid): $($_.Exception.Message)" "ERROR" "PID"
                $stoppedProcesses += @{
                    Name = $key
                    PID = $processPid
                    Status = "Error"
                    Error = $_.Exception.Message
                }
            }
        }
        
        # Clear the tracking file after processing
        "{}" | Set-Content $PidTrackingFile
        Write-Log "Processed $($stoppedProcesses.Count) tracked processes" "SUCCESS" "PID"
        return $stoppedProcesses
        
    } catch {
        Write-Log "Failed to process PID tracking file: $($_.Exception.Message)" "ERROR" "PID"
        return @()
    }
}

function Stop-ProcessesByName {
    param(
        [string]$ProcessName,
        [string]$ComponentName = $ProcessName
    )
    
    Write-Log "Stopping $ProcessName processes..." "INFO" $ComponentName.ToUpper()
    $stoppedCount = 0
    
    try {
        $workspace = (Get-Location).Path
        $processes = Get-Process -Name $ProcessName -ErrorAction SilentlyContinue
        
        if ($processes) {
            foreach ($process in $processes) {
                # Attempt to scope by command line when available
                $shouldStop = $false
                $cmdline = ""
                
                try {
                    $wmi = Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $process.Id) -ErrorAction SilentlyContinue
                    if ($wmi) {
                        $cmdline = $wmi.CommandLine
                        
                        # Immediately exclude Claude Code and VS Code processes
                        if ($cmdline -like "*claude*" -or $cmdline -like "*vscode*" -or $cmdline -like "*code.exe*" -or $cmdline -like "*Code.exe*") {
                            Write-Log "Skipping Claude Code/VS Code process (PID: $($process.Id))" "INFO" $ComponentName.ToUpper()
                            continue
                        }
                    }
                    
                    # Check if process is related to our workspace (more restrictive to avoid Claude Code)
                    if ($cmdline -and (
                        ($cmdline -like "*$workspace*" -and (
                            $cmdline -like "*src.main:app*" -or 
                            $cmdline -like "*uvicorn*" -or 
                            $cmdline -like "*npm start*" -or 
                            $cmdline -like "*frontend*" -or
                            $cmdline -like "*codebase-rag*"
                        )) -or
                        ($cmdline -like "*src.main:app*") -or
                        ($cmdline -like "*uvicorn*" -and $cmdline -like "*8080*")
                    ) -and $cmdline -notlike "*claude*" -and $cmdline -notlike "*vscode*" -and $cmdline -notlike "*code.exe*") {
                        $shouldStop = $true
                        Write-Log "Found workspace-related $ProcessName process (PID: $($process.Id))" "INFO" $ComponentName.ToUpper()
                    } elseif ($Force) {
                        $shouldStop = $true
                        Write-Log "Force mode: stopping $ProcessName process (PID: $($process.Id))" "WARN" $ComponentName.ToUpper()
                    } elseif (-not $cmdline) {
                        # If we can't get command line and it's not a force stop, be cautious
                        Write-Log "Cannot determine command line for $ProcessName PID $($process.Id) - skipping (use -Force to override)" "WARN" $ComponentName.ToUpper()
                    } else {
                        Write-Log "Skipping non-workspace $ProcessName process (PID: $($process.Id))" "DEBUG" $ComponentName.ToUpper()
                    }
                } catch {
                    if ($Force) {
                        $shouldStop = $true
                        Write-Log "Cannot check process details, but Force mode is on - stopping PID $($process.Id)" "WARN" $ComponentName.ToUpper()
                    }
                }
                
                if ($shouldStop) {
                    # Always log command line for Node/Python processes to help with debugging
                    if ($cmdline) {
                        Write-Log "Process PID $($process.Id) command line: $cmdline" "DEBUG" $ComponentName.ToUpper()
                    } else {
                        Write-Log "Process PID $($process.Id) has no accessible command line" "DEBUG" $ComponentName.ToUpper()
                    }
                    
                    try {
                        if ($Force) {
                            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
                            Write-Log "Force stopped $ProcessName (PID: $($process.Id))" "SUCCESS" $ComponentName.ToUpper()
                        } else {
                            # Try graceful shutdown first
                            $process.CloseMainWindow()
                            Start-Sleep -Milliseconds 1500
                            
                            $checkProcess = Get-Process -Id $process.Id -ErrorAction SilentlyContinue
                            if ($checkProcess -and -not $checkProcess.HasExited) {
                                Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
                                Write-Log "Graceful shutdown failed, force stopped $ProcessName (PID: $($process.Id))" "WARN" $ComponentName.ToUpper()
                            } else {
                                Write-Log "Gracefully stopped $ProcessName (PID: $($process.Id))" "SUCCESS" $ComponentName.ToUpper()
                            }
                        }
                        $stoppedCount++
                    } catch {
                        Write-Log "Failed to stop $ProcessName PID $($process.Id): $($_.Exception.Message)" "ERROR" $ComponentName.ToUpper()
                    }
                }
            }
        }
        
        if ($stoppedCount -gt 0) {
            Write-Log "Stopped $stoppedCount $ProcessName process(es)" "SUCCESS" $ComponentName.ToUpper()
        } else {
            Write-Log "No $ProcessName processes found to stop" "DEBUG" $ComponentName.ToUpper()
        }
        
        return $stoppedCount
    } catch {
        Write-Log "Failed to enumerate/stop $ProcessName processes: $($_.Exception.Message)" "ERROR" $ComponentName.ToUpper()
        return 0
    }
}

function Stop-ComposeServices {
    Write-Log "Stopping container services..." "INFO" "COMPOSE"
    
    $stoppedServices = @()
    
    if (Test-Path $ComposeFile) {
        try {
            Write-Log "Bringing down compose stack: $ComposeFile" "INFO" "COMPOSE"
            
            $output = podman-compose -f $ComposeFile down --remove-orphans 2>&1
            
            if ($LASTEXITCODE -eq 0) {
                Write-Log "Successfully brought down: $ComposeFile" "SUCCESS" "COMPOSE"
                $stoppedServices += $ComposeFile
            } else {
                Write-Log "Compose down had issues for $ComposeFile (exit code: $LASTEXITCODE)" "WARN" "COMPOSE"
                if ($VerboseLogs) {
                    Write-Log "Output: $output" "DEBUG" "COMPOSE"
                }
                # Still consider it stopped if containers are down
                $stoppedServices += $ComposeFile
            }
        } catch {
            Write-Log "Compose down failed for ${ComposeFile}: $($_.Exception.Message)" "ERROR" "COMPOSE"
        }
    } else {
        Write-Log "Compose file not found: $ComposeFile" "DEBUG" "COMPOSE"
    }
    
    # Additional cleanup: stop any remaining GraphRAG containers
    try {
        $containers = podman ps -a --filter "name=codebase-rag" --format "{{.Names}}" 2>$null
        if ($containers) {
            Write-Log "Found remaining GraphRAG containers, stopping them..." "INFO" "COMPOSE"
            foreach ($container in $containers) {
                if ($container) {
                    podman stop $container 2>$null
                    podman rm $container 2>$null
                    Write-Log "Stopped and removed container: $container" "SUCCESS" "COMPOSE"
                }
            }
        }
    } catch {
        Write-Log "Failed to cleanup remaining containers: $($_.Exception.Message)" "WARN" "COMPOSE"
    }
    
    return $stoppedServices
}

function Clear-PortListeners {
    Write-Log "Checking port listeners for cleanup..." "INFO" "PORTS"
    
    # Common GraphRAG ports
    $ports = @(3000, 8080, 8081, 8082)
    $clearedPorts = @()
    
    foreach ($port in $ports) {
        try {
            $listeners = netstat -ano | Select-String "LISTENING" | Select-String ":$port "
            if ($listeners) {
                foreach ($line in $listeners) {
                    $parts = $line -split "\s+"
                    $processPid = $parts[-1]
                    
                    if ($processPid -match "^\d+$") {
                        try {
                            $process = Get-Process -Id ([int]$processPid) -ErrorAction SilentlyContinue
                            if ($process) {
                                Write-Log "Port $port is in use by PID $processPid ($($process.ProcessName))" "INFO" "PORTS"
                                if ($Force -or $process.ProcessName -in @("python", "node", "uvicorn", "npm")) {
                                    Stop-Process -Id ([int]$processPid) -Force -ErrorAction SilentlyContinue
                                    Write-Log "Stopped process on port $port (PID: $processPid)" "SUCCESS" "PORTS"
                                    $clearedPorts += $port
                                } else {
                                    Write-Log "Skipping port $port cleanup (use -Force to override)" "WARN" "PORTS"
                                }
                            }
                        } catch {
                            Write-Log "Failed to stop process on port $port (PID: $processPid): $($_.Exception.Message)" "ERROR" "PORTS"
                        }
                    }
                }
            } else {
                Write-Log "Port $port is not in use" "DEBUG" "PORTS"
            }
        } catch {
            Write-Log "Failed to check port ${port}: $($_.Exception.Message)" "ERROR" "PORTS"
        }
    }
    
    return $clearedPorts
}

function Test-ServicesShutdown {
    Write-Log "Validating services shutdown..." "INFO" "VALIDATE"
    
    $services = @(
        @{ Name = "API Server (8080)"; Port = 8080; ProcessName = "python" },
        @{ Name = "API Server (8082)"; Port = 8082; ProcessName = "python" },
        @{ Name = "Frontend"; Port = 3000; ProcessName = "node" }
    )
    
    $runningServices = @()
    $allStopped = $true
    
    foreach ($service in $services) {
        # Check port
        $portOpen = $false
        try {
            $tcpClient = New-Object System.Net.Sockets.TcpClient
            $tcpClient.Connect("localhost", $service.Port)
            $tcpClient.Close()
            $portOpen = $true
        } catch {
            # Port is not open, which is what we want
        }
        
        # Check processes
        $processes = Get-Process -Name $service.ProcessName -ErrorAction SilentlyContinue
        $workspaceProcesses = 0
        if ($processes) {
            $workspace = (Get-Location).Path
            foreach ($proc in $processes) {
                try {
                    $wmi = Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $proc.Id) -ErrorAction SilentlyContinue
                    if ($wmi -and $wmi.CommandLine -and $wmi.CommandLine -like "*$workspace*") {
                        $workspaceProcesses++
                    }
                } catch {
                    # Ignore errors checking command line
                }
            }
        }
        
        if ($portOpen -or $workspaceProcesses -gt 0) {
            $runningServices += $service.Name
            $allStopped = $false
            Write-Log "$($service.Name) is still running (Port: $portOpen, Workspace Processes: $workspaceProcesses)" "WARN" "VALIDATE"
        } else {
            Write-Log "$($service.Name) is stopped" "SUCCESS" "VALIDATE"
        }
    }
    
    # Check containers
    try {
        $containers = podman ps --filter "name=codebase-rag" --format "{{.Names}}" 2>$null
        if ($containers -and $containers.Trim()) {
            $runningServices += "Containers"
            $allStopped = $false
            Write-Log "GraphRAG containers are still running: $containers" "WARN" "VALIDATE"
        } else {
            Write-Log "No GraphRAG containers running" "SUCCESS" "VALIDATE"
        }
    } catch {
        Write-Log "Failed to check containers: $($_.Exception.Message)" "WARN" "VALIDATE"
    }
    
    return @{
        AllStopped = $allStopped
        RunningServices = $runningServices
        ValidationPassed = $allStopped
    }
}

function Show-ShutdownSummary {
    param([hashtable]$Results)
    
    $totalElapsed = ((Get-Date) - $StartTime).TotalSeconds
    
    Write-Log "=== SHUTDOWN SUMMARY ===" "INFO" "SUMMARY"
    Write-Log "Total shutdown time: $([math]::Round($totalElapsed, 1))s" "INFO" "SUMMARY"
    
    if ($Results.TrackedProcesses) {
        $tracked = $Results.TrackedProcesses
        Write-Log "Tracked processes: $($tracked.Count) processed" "INFO" "SUMMARY"
    }
    
    if ($Results.ProcessesStopped) {
        Write-Log "Processes stopped by name: $($Results.ProcessesStopped)" "INFO" "SUMMARY"
    }
    
    if ($Results.ComposeServices) {
        Write-Log "Compose services: $($Results.ComposeServices.Count) stopped" "INFO" "SUMMARY"
    }
    
    if ($Results.PortsCleared -and $Results.PortsCleared.Count -gt 0) {
        Write-Log "Ports cleared: $($Results.PortsCleared -join ', ')" "INFO" "SUMMARY"
    }
    
    if ($Results.ValidationResult) {
        $validation = $Results.ValidationResult
        if ($validation.AllStopped) {
            Write-Log "Validation: All services successfully stopped" "SUCCESS" "SUMMARY"
        } else {
            Write-Log "Validation: Some services still running: $($validation.RunningServices -join ', ')" "WARN" "SUMMARY"
        }
    }
    
    Write-Log "Shutdown log: $LogFile" "INFO" "SUMMARY"
}

# === MAIN EXECUTION ===
function Main {
    Write-Log "GraphRAG System Shutdown - Enhanced Version" "INFO" "MAIN"
    Write-Log "Working Directory: $(Get-Location)" "INFO" "MAIN"
    Write-Log "Shutdown mode: $(if ($Force) { 'FORCE' } else { 'GRACEFUL' }) | Verbose: $VerboseLogs" "INFO" "MAIN"
    Write-Log "Session ID: $PID | Log file: $LogFile" "INFO" "MAIN"
    
    $results = @{}
    
    try {
        # Step 1: Stop tracked processes from PID file
        Write-Log "=== PHASE 1: Stopping Tracked Processes ===" "INFO" "MAIN"
        $results.TrackedProcesses = Stop-TrackedProcesses
        
        # Step 2: Stop processes by name (scoped to workspace)
        Write-Log "=== PHASE 2: Stopping Processes by Name ===" "INFO" "MAIN"
        $nodeCount = Stop-ProcessesByName -ProcessName "node" -ComponentName "Frontend"
        $pythonCount = Stop-ProcessesByName -ProcessName "python" -ComponentName "API"
        $results.ProcessesStopped = $nodeCount + $pythonCount
        
        # Step 3: Stop container services
        Write-Log "=== PHASE 3: Stopping Container Services ===" "INFO" "MAIN"
        $results.ComposeServices = Stop-ComposeServices
        
        # Step 4: Clear port listeners (optional)
        if ($Force) {
            Write-Log "=== PHASE 4: Clearing Port Listeners (Force Mode) ===" "INFO" "MAIN"
            $results.PortsCleared = Clear-PortListeners
        } else {
            Write-Log "=== PHASE 4: Skipping Port Cleanup (use -Force to enable) ===" "INFO" "MAIN"
            $results.PortsCleared = @()
        }
        
        # Step 5: Validate shutdown
        Write-Log "=== PHASE 5: Validating Shutdown ===" "INFO" "MAIN"
        Start-Sleep -Seconds 3  # Give processes time to fully terminate
        $results.ValidationResult = Test-ServicesShutdown
        
        # Show summary
        Show-ShutdownSummary -Results $results
        
        # Final status
        if ($results.ValidationResult -and -not $results.ValidationResult.AllStopped) {
            Write-Log "=== SHUTDOWN COMPLETED WITH WARNINGS ===" "WARN" "MAIN"
            Write-Log "Some services may still be running - check the summary above" "WARN" "MAIN"
            Write-Log "You may need to run with -Force flag for complete cleanup" "INFO" "MAIN"
            exit 1
        } else {
            Write-Log "=== SHUTDOWN COMPLETED SUCCESSFULLY ===" "SUCCESS" "MAIN"
            Write-Log "All GraphRAG services have been stopped" "SUCCESS" "MAIN"
        }
        
    } catch {
        Write-Log "Critical error during shutdown: $($_.Exception.Message)" "ERROR" "MAIN"
        Write-Log "Stack trace: $($_.ScriptStackTrace)" "ERROR" "MAIN"
        exit 1
    }
}

# Verbose diagnostics if requested
if ($VerboseLogs) {
    Write-Log "=== SYSTEM DIAGNOSTICS ===" "DEBUG" "DIAG"
    try {
        $runningProcesses = Get-Process node, python -ErrorAction SilentlyContinue
        if ($runningProcesses) {
            Write-Log "Current Node/Python processes:" "DEBUG" "DIAG"
            $runningProcesses | ForEach-Object { 
                Write-Log "  PID: $($_.Id) - $($_.ProcessName) - Started: $($_.StartTime)" "DEBUG" "DIAG"
            }
        }
        
        $openPorts = netstat -ano | Select-String "LISTENING" | Select-String ":3000|:8080|:8081|:8082"
        if ($openPorts) {
            Write-Log "Listening ports:" "DEBUG" "DIAG"
            $openPorts | ForEach-Object { Write-Log "  $_" "DEBUG" "DIAG" }
        }
        
        $containers = podman ps --filter "name=codebase-rag" 2>$null
        if ($containers) {
            Write-Log "GraphRAG containers:" "DEBUG" "DIAG"
            Write-Log "$containers" "DEBUG" "DIAG"
        }
    } catch {
        Write-Log "Failed to gather diagnostics: $($_.Exception.Message)" "DEBUG" "DIAG"
    }
}

# Run main function
Main