#!/usr/bin/env pwsh
<#
.SYNOPSIS
    GraphRAG System Health Validation Script
    
.DESCRIPTION
    Comprehensive health check and validation script for GraphRAG system.
    Provides detailed status, version information, connectivity tests, and recommendations.
    
.PARAMETER Quick
    Perform only essential health checks (faster)
    
.PARAMETER Detailed
    Include detailed diagnostics and performance metrics
    
.PARAMETER Export
    Export results to JSON file for automation
    
.PARAMETER Fix
    Attempt to fix common issues automatically
    
.EXAMPLE
    .\HEALTH-CHECK.ps1                      # Standard health check
    .\HEALTH-CHECK.ps1 -Quick               # Fast essential checks
    .\HEALTH-CHECK.ps1 -Detailed            # Comprehensive diagnostics
    .\HEALTH-CHECK.ps1 -Export results.json # Export to file
    .\HEALTH-CHECK.ps1 -Fix                 # Try to fix issues
    
.NOTES
    GraphRAG - Comprehensive System Health Validation
    Provides actionable insights for system troubleshooting
#>

param(
    [switch]$Quick,
    [switch]$Detailed,
    [string]$Export,
    [switch]$Fix
)

# Configuration
$ErrorActionPreference = 'SilentlyContinue'
$StartTime = Get-Date
$LogFile = "logs\health-$(Get-Date -Format 'yyyy-MM-dd-HH-mm-ss').log"

# Ensure logs directory exists
if (-not (Test-Path "logs")) { 
    New-Item -ItemType Directory -Path "logs" -Force | Out-Null 
}

# Results structure
$HealthResults = @{
    Timestamp = $StartTime
    SystemInfo = @{}
    Services = @{}
    Versions = @{}
    Environment = @{}
    Connectivity = @{}
    Performance = @{}
    Issues = @()
    Recommendations = @()
    OverallStatus = "Unknown"
    HealthScore = 0
}

# Logging function
function Write-HealthLog {
    param(
        [string]$Message, 
        [ValidateSet("INFO", "WARN", "ERROR", "SUCCESS", "DEBUG")]
        [string]$Level = "INFO",
        [string]$Component = "HEALTH"
    )
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"
    $logEntry = "[$timestamp] [$Component] [$Level] $Message"
    
    # Console output with colors
    switch ($Level) {
        "ERROR" { Write-Host $logEntry -ForegroundColor Red }
        "WARN"  { Write-Host $logEntry -ForegroundColor Yellow }
        "SUCCESS" { Write-Host $logEntry -ForegroundColor Green }
        "DEBUG" { if ($Detailed) { Write-Host $logEntry -ForegroundColor Cyan } }
        default { Write-Host $logEntry -ForegroundColor White }
    }
    
    # Log to file
    Add-Content -Path $LogFile -Value $logEntry -ErrorAction SilentlyContinue
}

function Get-SystemInformation {
    Write-HealthLog "Gathering system information..." "INFO" "SYSTEM"
    
    try {
        $HealthResults.SystemInfo = @{
            OS = (Get-CimInstance Win32_OperatingSystem).Caption
            Version = (Get-CimInstance Win32_OperatingSystem).Version
            Architecture = $env:PROCESSOR_ARCHITECTURE
            PowerShellVersion = $PSVersionTable.PSVersion.ToString()
            WorkingDirectory = (Get-Location).Path
            CurrentUser = $env:USERNAME
            Hostname = $env:COMPUTERNAME
            TotalMemoryGB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 2)
            AvailableMemoryGB = [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB / 1024, 2)
            CPUCores = (Get-CimInstance Win32_ComputerSystem).NumberOfProcessors
            DiskSpaceGB = [math]::Round((Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'").FreeSpace / 1GB, 2)
        }
        
        Write-HealthLog "System: $($HealthResults.SystemInfo.OS) ($($HealthResults.SystemInfo.Architecture))" "SUCCESS" "SYSTEM"
        Write-HealthLog "Memory: $($HealthResults.SystemInfo.AvailableMemoryGB)GB / $($HealthResults.SystemInfo.TotalMemoryGB)GB available" "INFO" "SYSTEM"
        return $true
    } catch {
        Write-HealthLog "Failed to gather system information: $($_.Exception.Message)" "ERROR" "SYSTEM"
        return $false
    }
}

function Get-VersionInformation {
    Write-HealthLog "Checking version information..." "INFO" "VERSIONS"
    
    $HealthResults.Versions = @{}
    $versionChecks = @(
        @{ Name = "Python"; Command = "python --version"; Parser = { $args[0] -replace "Python ", "" } },
        @{ Name = "Node.js"; Command = "node --version"; Parser = { $args[0] -replace "v", "" } },
        @{ Name = "npm"; Command = "npm --version"; Parser = { $args[0] } },
        @{ Name = "Podman"; Command = "podman --version"; Parser = { ($args[0] -split " ")[2] } },
        @{ Name = "PodmanCompose"; Command = "podman-compose --version"; Parser = { ($args[0] -split " ")[-1] } },
        @{ Name = "pip"; Command = "pip --version"; Parser = { ($args[0] -split " ")[1] } },
        @{ Name = "Git"; Command = "git --version"; Parser = { ($args[0] -split " ")[-1] } }
    )
    
    foreach ($check in $versionChecks) {
        try {
            $output = Invoke-Expression $check.Command 2>&1
            if ($LASTEXITCODE -eq 0 -and $output) {
                $version = & $check.Parser $output.ToString()
                $HealthResults.Versions[$check.Name] = @{
                    Version = $version.Trim()
                    Available = $true
                    Raw = $output.ToString().Trim()
                }
                Write-HealthLog "$($check.Name): $($version.Trim())" "SUCCESS" "VERSIONS"
            } else {
                $HealthResults.Versions[$check.Name] = @{
                    Available = $false
                    Error = "Command failed or not found"
                }
                Write-HealthLog "$($check.Name): Not available" "WARN" "VERSIONS"
            }
        } catch {
            $HealthResults.Versions[$check.Name] = @{
                Available = $false
                Error = $_.Exception.Message
            }
            Write-HealthLog "$($check.Name): Error - $($_.Exception.Message)" "ERROR" "VERSIONS"
        }
    }
    
    # Check Python packages
    if ($HealthResults.Versions.Python.Available) {
        Write-HealthLog "Checking Python packages..." "INFO" "VERSIONS"
        $pythonPackages = @("fastapi", "uvicorn", "neo4j", "chromadb", "redis")
        $HealthResults.Versions.PythonPackages = @{}
        
        foreach ($package in $pythonPackages) {
            try {
                $packageInfo = python -c "import $package; print($package.__version__)" 2>&1
                if ($LASTEXITCODE -eq 0) {
                    $HealthResults.Versions.PythonPackages[$package] = $packageInfo.Trim()
                    Write-HealthLog "Python ${package}: $($packageInfo.Trim())" "SUCCESS" "VERSIONS"
                } else {
                    $HealthResults.Versions.PythonPackages[$package] = "Not installed"
                    Write-HealthLog "Python ${package}: Not installed" "WARN" "VERSIONS"
                }
            } catch {
                $HealthResults.Versions.PythonPackages[$package] = "Error: $($_.Exception.Message)"
                Write-HealthLog "Python ${package}: Error checking version" "ERROR" "VERSIONS"
            }
        }
    }
    
    return $true
}

function Test-ServiceHealth {
    Write-HealthLog "Testing service health..." "INFO" "SERVICES"
    
    $services = @(
        @{
            Name = "ChromaDB"
            Port = 8000
            HealthUrl = "http://localhost:8000/api/v2/healthcheck"
            ProcessName = $null
            Container = "codebase-rag-chromadb"
            Critical = $true
        },
        @{
            Name = "Neo4j"
            Port = 7474
            HealthUrl = "http://localhost:7474/"
            BoltPort = 7687
            ProcessName = $null
            Container = "codebase-rag-neo4j"
            Critical = $true
        },
        @{
            Name = "Redis"
            Port = 6379
            HealthUrl = $null
            ProcessName = $null
            Container = "codebase-rag-redis"
            Critical = $true
        },
        @{
            Name = "API Server"
            Port = 8080
            AlternatePort = 8081
            HealthUrl = "http://localhost:8080/api/v1/health/"
            ProcessName = "python"
            Container = $null
            Critical = $true
        },
        @{
            Name = "Frontend"
            Port = 3000
            HealthUrl = "http://localhost:3000/"
            ProcessName = "node"
            Container = $null
            Critical = $false
        }
    )
    
    $HealthResults.Services = @{}
    $healthyCount = 0
    
    foreach ($service in $services) {
        $serviceResult = @{
            Name = $service.Name
            Status = "Unknown"
            Port = $service.Port
            PortOpen = $false
            HttpHealthy = $false
            ProcessRunning = $false
            ContainerRunning = $false
            ResponseTime = $null
            Details = @{}
            Issues = @()
        }
        
        try {
            # Test primary port
            $portTest = Test-NetConnection -ComputerName localhost -Port $service.Port -InformationLevel Quiet -WarningAction SilentlyContinue
            $serviceResult.PortOpen = $portTest
            
            # Test alternate port for API server
            if (-not $portTest -and $service.AlternatePort) {
                $altPortTest = Test-NetConnection -ComputerName localhost -Port $service.AlternatePort -InformationLevel Quiet -WarningAction SilentlyContinue
                if ($altPortTest) {
                    $serviceResult.Port = $service.AlternatePort
                    $serviceResult.PortOpen = $true
                    $service.HealthUrl = $service.HealthUrl -replace ":$($service.Port)/", ":$($service.AlternatePort)/"
                }
            }
            
            # Test HTTP endpoint if available
            if ($service.HealthUrl -and $serviceResult.PortOpen) {
                try {
                    $startTime = Get-Date
                    $response = Invoke-WebRequest -Uri $service.HealthUrl -Method GET -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
                    $responseTime = ((Get-Date) - $startTime).TotalMilliseconds
                    
                    if ($response.StatusCode -eq 200) {
                        $serviceResult.HttpHealthy = $true
                        $serviceResult.ResponseTime = [math]::Round($responseTime, 2)
                        $serviceResult.Details.StatusCode = $response.StatusCode
                        $serviceResult.Details.ContentLength = $response.Content.Length
                    }
                } catch {
                    $serviceResult.Issues += "HTTP health check failed: $($_.Exception.Message)"
                }
            }
            
            # Check for running processes
            if ($service.ProcessName) {
                $processes = Get-Process -Name $service.ProcessName -ErrorAction SilentlyContinue
                $serviceResult.ProcessRunning = ($processes.Count -gt 0)
                $serviceResult.Details.ProcessCount = $processes.Count
                if ($processes) {
                    $serviceResult.Details.ProcessPIDs = $processes.Id
                }
            }
            
            # Check container status
            if ($service.Container) {
                try {
                    $containerStatus = podman ps --filter "name=$($service.Container)" --format "{{.Status}}" 2>$null
                    $serviceResult.ContainerRunning = (-not [string]::IsNullOrEmpty($containerStatus) -and $containerStatus -like "*Up*")
                    $serviceResult.Details.ContainerStatus = $containerStatus
                } catch {
                    $serviceResult.Issues += "Container status check failed"
                }
            }
            
            # Determine overall status
            if ($service.Container) {
                # Container-based service
                $serviceResult.Status = if ($serviceResult.ContainerRunning -and $serviceResult.PortOpen) {
                    if ($serviceResult.HttpHealthy -or -not $service.HealthUrl) { "Healthy" } else { "Degraded" }
                } else { "Unhealthy" }
            } else {
                # Process-based service
                $serviceResult.Status = if ($serviceResult.ProcessRunning -and $serviceResult.PortOpen) {
                    if ($serviceResult.HttpHealthy -or -not $service.HealthUrl) { "Healthy" } else { "Degraded" }
                } else { "Unhealthy" }
            }
            
            if ($serviceResult.Status -eq "Healthy") {
                $healthyCount++
                Write-HealthLog "$($service.Name): Healthy (Port: $($serviceResult.Port), Response: $($serviceResult.ResponseTime)ms)" "SUCCESS" "SERVICES"
            } elseif ($serviceResult.Status -eq "Degraded") {
                Write-HealthLog "$($service.Name): Degraded - $($serviceResult.Issues -join ', ')" "WARN" "SERVICES"
            } else {
                Write-HealthLog "$($service.Name): Unhealthy - $($serviceResult.Issues -join ', ')" "ERROR" "SERVICES"
                if ($service.Critical) {
                    $HealthResults.Issues += "Critical service $($service.Name) is unhealthy"
                }
            }
            
        } catch {
            $serviceResult.Status = "Error"
            $serviceResult.Issues += "Health check exception: $($_.Exception.Message)"
            Write-HealthLog "$($service.Name): Error during health check - $($_.Exception.Message)" "ERROR" "SERVICES"
        }
        
        $HealthResults.Services[$service.Name] = $serviceResult
    }
    
    # Calculate service health percentage
    $totalServices = $services.Count
    $healthPercentage = [math]::Round(($healthyCount / $totalServices) * 100, 1)
    $HealthResults.Services.Summary = @{
        Total = $totalServices
        Healthy = $healthyCount
        HealthPercentage = $healthPercentage
    }
    
    Write-HealthLog "Service Summary: $healthyCount/$totalServices healthy ($healthPercentage%)" "INFO" "SERVICES"
    return $healthyCount -eq $totalServices
}

function Test-EnvironmentConfiguration {
    Write-HealthLog "Validating environment configuration..." "INFO" "ENVIRONMENT"
    
    $requiredEnvVars = @(
        "NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "NEO4J_DATABASE",
        "CHROMA_HOST", "CHROMA_PORT", "REDIS_URL"
    )
    
    $optionalEnvVars = @(
        "GRAFRAG_HOST_API_PORT", "REACT_APP_API_URL", "LOG_LEVEL", "PYTHONPATH"
    )
    
    $HealthResults.Environment = @{
        Required = @{}
        Optional = @{}
        Missing = @()
        Present = @()
    }
    
    # Check required environment variables
    foreach ($var in $requiredEnvVars) {
        $value = [Environment]::GetEnvironmentVariable($var)
        $HealthResults.Environment.Required[$var] = @{
            Present = (-not [string]::IsNullOrEmpty($value))
            Value = if ($value) { $value } else { $null }
        }
        
        if ($value) {
            $HealthResults.Environment.Present += $var
            Write-HealthLog "Environment ${var}: Set" "SUCCESS" "ENVIRONMENT"
        } else {
            $HealthResults.Environment.Missing += $var
            Write-HealthLog "Environment ${var}: Missing" "WARN" "ENVIRONMENT"
            $HealthResults.Issues += "Required environment variable $var is not set"
        }
    }
    
    # Check optional environment variables
    foreach ($var in $optionalEnvVars) {
        $value = [Environment]::GetEnvironmentVariable($var)
        $HealthResults.Environment.Optional[$var] = @{
            Present = (-not [string]::IsNullOrEmpty($value))
            Value = if ($value) { $value } else { $null }
        }
        
        if ($value) {
            Write-HealthLog "Environment ${var}: $value" "INFO" "ENVIRONMENT"
        } else {
            Write-HealthLog "Environment ${var}: Not set" "DEBUG" "ENVIRONMENT"
        }
    }
    
    return $HealthResults.Environment.Missing.Count -eq 0
}

function Test-ConnectivityAndIntegration {
    Write-HealthLog "Testing service connectivity and integration..." "INFO" "CONNECTIVITY"
    
    $HealthResults.Connectivity = @{
        DatabaseConnections = @{}
        ApiIntegration = @{}
        CrossServiceTests = @{}
    }
    
    # Test database connections
    if ($HealthResults.Services.Neo4j.Status -eq "Healthy") {
        try {
            $neo4jTest = podman exec codebase-rag-neo4j cypher-shell -u neo4j -p codebase-rag-2024 "RETURN 1 as test" 2>$null
            $HealthResults.Connectivity.DatabaseConnections.Neo4j = @{
                Connected = ($LASTEXITCODE -eq 0)
                Response = $neo4jTest
            }
            if ($LASTEXITCODE -eq 0) {
                Write-HealthLog "Neo4j Connectivity: Database connection successful" "SUCCESS" "CONNECTIVITY"
            } else {
                Write-HealthLog "Neo4j Connectivity: Database connection failed" "ERROR" "CONNECTIVITY"
            }
        } catch {
            Write-HealthLog "Neo4j Connectivity: Test failed - $($_.Exception.Message)" "ERROR" "CONNECTIVITY"
        }
    }
    
    # Test API integration
    if ($HealthResults.Services."API Server".Status -in @("Healthy", "Degraded")) {
        $apiPort = $HealthResults.Services."API Server".Port
        try {
            # Test API readiness
            $readinessUrl = "http://localhost:$apiPort/api/v1/health/ready"
            $readinessResponse = Invoke-WebRequest -Uri $readinessUrl -Method GET -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
            $readinessData = $readinessResponse.Content | ConvertFrom-Json
            
            $HealthResults.Connectivity.ApiIntegration.Readiness = @{
                Status = $readinessData.status
                Ready = ($readinessData.status -eq "ready")
                Response = $readinessData
            }
            
            Write-HealthLog "API Readiness: $($readinessData.status)" $(if ($readinessData.status -eq "ready") { "SUCCESS" } else { "WARN" }) "CONNECTIVITY"
            
        } catch {
            Write-HealthLog "API Integration: Readiness test failed - $($_.Exception.Message)" "ERROR" "CONNECTIVITY"
        }
    }
    
    return $true
}

function Get-PerformanceMetrics {
    if (-not $Detailed) { return $true }
    
    Write-HealthLog "Collecting performance metrics..." "INFO" "PERFORMANCE"
    
    try {
        $HealthResults.Performance = @{
            CPU = @{
                Usage = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
                ProcessorCount = (Get-CimInstance Win32_ComputerSystem).NumberOfProcessors
            }
            Memory = @{
                TotalGB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 2)
                AvailableGB = [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB / 1024, 2)
                UsagePercent = [math]::Round(((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory - (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory * 1024) / (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory * 100, 1)
            }
            Disk = @{
                FreeSpaceGB = [math]::Round((Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'").FreeSpace / 1GB, 2)
                TotalSizeGB = [math]::Round((Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'").Size / 1GB, 2)
                UsagePercent = [math]::Round(((Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'").Size - (Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'").FreeSpace) / (Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'").Size * 100, 1)
            }
        }
        
        Write-HealthLog "CPU Usage: $($HealthResults.Performance.CPU.Usage)%" "INFO" "PERFORMANCE"
        Write-HealthLog "Memory Usage: $($HealthResults.Performance.Memory.UsagePercent)% ($($HealthResults.Performance.Memory.AvailableGB)GB available)" "INFO" "PERFORMANCE"
        Write-HealthLog "Disk Usage: $($HealthResults.Performance.Disk.UsagePercent)% ($($HealthResults.Performance.Disk.FreeSpaceGB)GB free)" "INFO" "PERFORMANCE"
        
        return $true
    } catch {
        Write-HealthLog "Failed to collect performance metrics: $($_.Exception.Message)" "ERROR" "PERFORMANCE"
        return $false
    }
}

function Generate-Recommendations {
    Write-HealthLog "Generating recommendations..." "INFO" "RECOMMENDATIONS"
    
    $HealthResults.Recommendations = @()
    
    # Service-specific recommendations
    foreach ($serviceName in $HealthResults.Services.Keys) {
        if ($serviceName -eq "Summary") { continue }
        
        $service = $HealthResults.Services[$serviceName]
        if ($service.Status -ne "Healthy") {
            switch ($serviceName) {
                "ChromaDB" {
                    $HealthResults.Recommendations += @{
                        Category = "Service"
                        Service = $serviceName
                        Issue = "ChromaDB is not healthy"
                        Recommendation = "Check container status: podman ps | grep chromadb"
                        Action = "podman-compose -f podman-compose.dev.yml restart chromadb"
                        Priority = "High"
                    }
                }
                "Neo4j" {
                    $HealthResults.Recommendations += @{
                        Category = "Service"
                        Service = $serviceName
                        Issue = "Neo4j is not healthy"
                        Recommendation = "Verify credentials and container status"
                        Action = "podman logs codebase-rag-neo4j"
                        Priority = "High"
                    }
                }
                "API Server" {
                    $HealthResults.Recommendations += @{
                        Category = "Service"
                        Service = $serviceName
                        Issue = "API Server is not healthy"
                        Recommendation = "Check if API server process is running"
                        Action = ".\START.ps1 -Mode api"
                        Priority = "Critical"
                    }
                }
            }
        }
    }
    
    # Environment variable recommendations
    if ($HealthResults.Environment.Missing.Count -gt 0) {
        $HealthResults.Recommendations += @{
            Category = "Configuration"
            Issue = "Missing required environment variables: $($HealthResults.Environment.Missing -join ', ')"
            Recommendation = "Set missing environment variables for database connections"
            Action = "Use the SET-ENVIRONMENT.ps1 script or set manually"
            Priority = "High"
        }
    }
    
    # Performance recommendations
    if ($HealthResults.Performance) {
        if ($HealthResults.Performance.Memory.UsagePercent -gt 85) {
            $HealthResults.Recommendations += @{
                Category = "Performance"
                Issue = "High memory usage: $($HealthResults.Performance.Memory.UsagePercent)%"
                Recommendation = "Monitor memory usage and consider increasing system memory"
                Action = "Close unnecessary applications or increase system RAM"
                Priority = "Medium"
            }
        }
        
        if ($HealthResults.Performance.Disk.UsagePercent -gt 90) {
            $HealthResults.Recommendations += @{
                Category = "Performance"
                Issue = "Low disk space: $($HealthResults.Performance.Disk.FreeSpaceGB)GB free"
                Recommendation = "Clean up disk space or expand storage"
                Action = "Delete old logs, containers, or temporary files"
                Priority = "High"
            }
        }
    }
    
    # Version recommendations
    foreach ($component in $HealthResults.Versions.Keys) {
        if (-not $HealthResults.Versions[$component].Available) {
            $priority = switch ($component) {
                "Python" { "Critical" }
                "Podman" { "Critical" }
                "Node.js" { "Medium" }
                default { "Low" }
            }
            
            $HealthResults.Recommendations += @{
                Category = "Dependencies"
                Issue = "$component is not available"
                Recommendation = "Install $component to ensure full functionality"
                Action = "Download and install $component from official website"
                Priority = $priority
            }
        }
    }
    
    Write-HealthLog "Generated $($HealthResults.Recommendations.Count) recommendations" "INFO" "RECOMMENDATIONS"
}

function Calculate-OverallHealth {
    Write-HealthLog "Calculating overall health score..." "INFO" "SCORE"
    
    $scores = @{
        Services = 0
        Environment = 0
        Versions = 0
        Connectivity = 0
    }
    
    # Service health score (40% weight)
    if ($HealthResults.Services.Summary) {
        $scores.Services = $HealthResults.Services.Summary.HealthPercentage * 0.4
    }
    
    # Environment score (20% weight)
    $requiredVarsSet = $HealthResults.Environment.Present.Count
    $totalRequiredVars = $HealthResults.Environment.Required.Keys.Count
    $scores.Environment = if ($totalRequiredVars -gt 0) { ($requiredVarsSet / $totalRequiredVars) * 100 * 0.2 } else { 0 }
    
    # Version availability score (20% weight)
    $criticalTools = @("Python", "Podman")
    $availableTools = $criticalTools | Where-Object { $HealthResults.Versions[$_].Available }
    $scores.Versions = if ($criticalTools.Count -gt 0) { ($availableTools.Count / $criticalTools.Count) * 100 * 0.2 } else { 0 }
    
    # Connectivity score (20% weight)
    $connectivityScore = 100 # Default to full score if no specific tests fail
    if ($HealthResults.Connectivity.ApiIntegration.Readiness -and -not $HealthResults.Connectivity.ApiIntegration.Readiness.Ready) {
        $connectivityScore = 50
    }
    $scores.Connectivity = $connectivityScore * 0.2
    
    $HealthResults.HealthScore = [math]::Round($scores.Services + $scores.Environment + $scores.Versions + $scores.Connectivity, 1)
    
    # Determine overall status
    $HealthResults.OverallStatus = switch ($HealthResults.HealthScore) {
        { $_ -ge 90 } { "Excellent" }
        { $_ -ge 75 } { "Good" }
        { $_ -ge 50 } { "Fair" }
        { $_ -ge 25 } { "Poor" }
        default { "Critical" }
    }
    
    Write-HealthLog "Overall Health Score: $($HealthResults.HealthScore)% ($($HealthResults.OverallStatus))" $(if ($HealthResults.HealthScore -ge 75) { "SUCCESS" } else { "WARN" }) "SCORE"
}

function Show-HealthReport {
    $totalElapsed = ((Get-Date) - $StartTime).TotalSeconds
    
    Write-Host "`n" -NoNewline
    Write-Host "╔══════════════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║                      GraphRAG System Health Report                          ║" -ForegroundColor Cyan
    Write-Host "╠══════════════════════════════════════════════════════════════════════════════╣" -ForegroundColor Cyan
    Write-Host "║ Timestamp: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')                                            ║" -ForegroundColor White
    Write-Host "║ Duration:  $([math]::Round($totalElapsed, 2))s                                                      ║" -ForegroundColor White
    Write-Host "║ Health Score: $($HealthResults.HealthScore)% ($($HealthResults.OverallStatus))                                    ║" -ForegroundColor $(if ($HealthResults.HealthScore -ge 75) { "Green" } else { "Yellow" })
    Write-Host "╚══════════════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    
    # System Information
    Write-Host "`n📊 SYSTEM INFORMATION" -ForegroundColor Blue
    Write-Host "OS: $($HealthResults.SystemInfo.OS)" -ForegroundColor White
    Write-Host "Memory: $($HealthResults.SystemInfo.AvailableMemoryGB)GB / $($HealthResults.SystemInfo.TotalMemoryGB)GB available" -ForegroundColor White
    Write-Host "Disk Space: $($HealthResults.SystemInfo.DiskSpaceGB)GB free" -ForegroundColor White
    
    # Service Status
    Write-Host "`n🔧 SERVICE STATUS" -ForegroundColor Blue
    foreach ($serviceName in $HealthResults.Services.Keys) {
        if ($serviceName -eq "Summary") { continue }
        
        $service = $HealthResults.Services[$serviceName]
        $statusIcon = switch ($service.Status) {
            "Healthy" { "✅" }
            "Degraded" { "⚠️" }
            "Unhealthy" { "❌" }
            default { "❓" }
        }
        
        $color = switch ($service.Status) {
            "Healthy" { "Green" }
            "Degraded" { "Yellow" }
            "Unhealthy" { "Red" }
            default { "Gray" }
        }
        
        $portInfo = if ($service.ResponseTime) { " (Port: $($service.Port), $($service.ResponseTime)ms)" } else { " (Port: $($service.Port))" }
        Write-Host "$statusIcon $($serviceName): $($service.Status)$portInfo" -ForegroundColor $color
        
        if ($service.Issues.Count -gt 0) {
            foreach ($issue in $service.Issues) {
                Write-Host "   └─ $issue" -ForegroundColor Red
            }
        }
    }
    
    # Version Information
    Write-Host "`n📦 VERSION INFORMATION" -ForegroundColor Blue
    foreach ($component in $HealthResults.Versions.Keys) {
        if ($component -eq "PythonPackages") { continue }
        
        $version = $HealthResults.Versions[$component]
        if ($version.Available) {
            Write-Host "✅ ${component}: $($version.Version)" -ForegroundColor Green
        } else {
            Write-Host "❌ ${component}: Not available" -ForegroundColor Red
        }
    }
    
    # Python Packages
    if ($HealthResults.Versions.PythonPackages) {
        Write-Host "`n🐍 PYTHON PACKAGES" -ForegroundColor Blue
        foreach ($package in $HealthResults.Versions.PythonPackages.Keys) {
            $version = $HealthResults.Versions.PythonPackages[$package]
            if ($version -ne "Not installed" -and -not $version.StartsWith("Error")) {
                Write-Host "✅ ${package}: $version" -ForegroundColor Green
            } else {
                Write-Host "❌ ${package}: $version" -ForegroundColor Red
            }
        }
    }
    
    # Environment Variables
    Write-Host "`n🌐 ENVIRONMENT CONFIGURATION" -ForegroundColor Blue
    Write-Host "Required Variables: $($HealthResults.Environment.Present.Count)/$($HealthResults.Environment.Required.Keys.Count) set" -ForegroundColor $(if ($HealthResults.Environment.Missing.Count -eq 0) { "Green" } else { "Yellow" })
    
    if ($HealthResults.Environment.Missing.Count -gt 0) {
        Write-Host "Missing: $($HealthResults.Environment.Missing -join ', ')" -ForegroundColor Red
    }
    
    # Issues and Recommendations
    if ($HealthResults.Issues.Count -gt 0) {
        Write-Host "`n⚠️  ISSUES DETECTED" -ForegroundColor Red
        foreach ($issue in $HealthResults.Issues) {
            Write-Host "• $issue" -ForegroundColor Red
        }
    }
    
    if ($HealthResults.Recommendations.Count -gt 0) {
        Write-Host "`n💡 RECOMMENDATIONS" -ForegroundColor Yellow
        $criticalRecs = $HealthResults.Recommendations | Where-Object { $_.Priority -eq "Critical" }
        $highRecs = $HealthResults.Recommendations | Where-Object { $_.Priority -eq "High" }
        
        if ($criticalRecs) {
            Write-Host "🚨 Critical:" -ForegroundColor Red
            foreach ($rec in $criticalRecs) {
                Write-Host "   • $($rec.Issue)" -ForegroundColor Red
                Write-Host "     Action: $($rec.Action)" -ForegroundColor White
            }
        }
        
        if ($highRecs) {
            Write-Host "⚠️  High Priority:" -ForegroundColor Yellow
            foreach ($rec in $highRecs) {
                Write-Host "   • $($rec.Issue)" -ForegroundColor Yellow
                Write-Host "     Action: $($rec.Action)" -ForegroundColor White
            }
        }
    }
    
    # Access URLs
    Write-Host "`n🌐 ACCESS URLS" -ForegroundColor Blue
    if ($HealthResults.Services."API Server".Status -eq "Healthy") {
        $apiPort = $HealthResults.Services."API Server".Port
        Write-Host "API Server:   http://localhost:$apiPort/api/v1/health/" -ForegroundColor Cyan
    }
    if ($HealthResults.Services.ChromaDB.Status -eq "Healthy") {
        Write-Host "ChromaDB API: http://localhost:8000/api/v2/healthcheck" -ForegroundColor Cyan
    }
    if ($HealthResults.Services.Neo4j.Status -eq "Healthy") {
        Write-Host "Neo4j Browser: http://localhost:7474 (neo4j / codebase-rag-2024)" -ForegroundColor Cyan
    }
    if ($HealthResults.Services.Frontend.Status -eq "Healthy") {
        Write-Host "Frontend App: http://localhost:3000" -ForegroundColor Cyan
    }
    
    Write-Host "`n📝 NEXT STEPS" -ForegroundColor Green
    if ($HealthResults.HealthScore -ge 90) {
        Write-Host "✅ System is running optimally!" -ForegroundColor Green
        Write-Host "   • All services are healthy and ready for use" -ForegroundColor White
    } elseif ($HealthResults.HealthScore -ge 75) {
        Write-Host "✅ System is running well with minor issues" -ForegroundColor Green
        Write-Host "   • Review recommendations above to optimize performance" -ForegroundColor White
    } else {
        Write-Host "⚠️  System needs attention" -ForegroundColor Yellow
        Write-Host "   • Address critical and high priority recommendations" -ForegroundColor White
        Write-Host "   • Consider running: .\START.ps1 -Clean" -ForegroundColor White
    }
    
    Write-Host "`nHealth check log: $LogFile" -ForegroundColor Gray
}

# === MAIN EXECUTION ===
function Main {
    Write-HealthLog "Starting GraphRAG System Health Check..." "SUCCESS" "MAIN"
    Write-HealthLog "Mode: $(if ($Quick) { 'Quick' } elseif ($Detailed) { 'Detailed' } else { 'Standard' })" "INFO" "MAIN"
    
    try {
        # Core health checks
        Get-SystemInformation
        Get-VersionInformation
        Test-ServiceHealth
        Test-EnvironmentConfiguration
        
        if (-not $Quick) {
            Test-ConnectivityAndIntegration
            if ($Detailed) {
                Get-PerformanceMetrics
            }
        }
        
        Generate-Recommendations
        Calculate-OverallHealth
        
        # Show results
        Show-HealthReport
        
        # Export if requested
        if ($Export) {
            $HealthResults | ConvertTo-Json -Depth 5 | Set-Content $Export
            Write-HealthLog "Results exported to: $Export" "SUCCESS" "MAIN"
        }
        
        # Auto-fix if requested
        if ($Fix) {
            Write-HealthLog "Auto-fix not yet implemented" "WARN" "MAIN"
        }
        
        Write-HealthLog "Health check completed successfully" "SUCCESS" "MAIN"
        
        # Return appropriate exit code
        if ($HealthResults.OverallStatus -in @("Critical", "Poor")) {
            exit 1
        }
        
    } catch {
        Write-HealthLog "Critical error during health check: $($_.Exception.Message)" "ERROR" "MAIN"
        Write-HealthLog "Stack trace: $($_.ScriptStackTrace)" "ERROR" "MAIN"
        exit 1
    }
}

# Run main function
Main