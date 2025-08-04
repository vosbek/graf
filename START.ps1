#!/usr/bin/env pwsh
<#
.SYNOPSIS
    GraphRAG Unified Startup Script - One Command to Rule Them All
    
.DESCRIPTION
    Simplified, unified startup for the GraphRAG Codebase Analysis Platform.
    Automatically detects environment, manages dependencies, and starts services.
    
.PARAMETER Mode
    Startup mode: 'full' (default), 'backend', 'frontend', 'mvp'
    
.PARAMETER SkipDeps
    Skip dependency checking for faster startup
    
.PARAMETER Clean
    Clean startup - remove old logs and containers
    
.PARAMETER Status
    Show system status instead of starting
    
.EXAMPLE
    .\START.ps1                    # Full system (recommended)
    .\START.ps1 -Mode backend      # Backend services only  
    .\START.ps1 -Mode api          # API server only
    .\START.ps1 -Mode frontend     # Frontend only
    .\START.ps1 -Mode mvp          # Minimal viable product
    .\START.ps1 -Status            # Check system health
    .\START.ps1 -Clean             # Clean startup
    
.NOTES
    GraphRAG - AI-Powered Codebase Analysis Platform
    For Struts/CORBA/Java Migration and 50-100 Codebase Analysis
#>

param(
    [ValidateSet('full', 'backend', 'frontend', 'api', 'mvp', 'api-debug')]
    [string]$Mode = 'full',
    
    [switch]$SkipDeps,
    [switch]$Clean,
    [switch]$Status,
    [switch]$Quiet,
    [ValidateSet('DEBUG', 'INFO', 'WARNING', 'ERROR')]
    [string]$LogLevel = 'INFO'
)

# === CONFIGURATION ===
$ErrorActionPreference = "Stop"
$StartTime = Get-Date
$LogFile = "logs\start-$(Get-Date -Format 'yyyy-MM-dd-HH-mm-ss').log"

# Version marker (increment on each run)
$VersionFile = "VERSION"
function Get-And-Increment-Version {
    try {
        if (-not (Test-Path $VersionFile)) {
            "1" | Out-File -FilePath $VersionFile -Encoding ascii -Force
            return 1
        }
        $raw = Get-Content -Path $VersionFile -ErrorAction Stop | Select-Object -First 1
        $v = 0
        if ([int]::TryParse(($raw -replace '[^\d]', ''), [ref]$v)) {
            $v = $v + 1
        } else {
            $v = 1
        }
        Set-Content -Path $VersionFile -Value "$v" -NoNewline -Encoding ascii
        return $v
    } catch {
        return 0
    }
}

# === FUNCTIONS ===
function Write-Log {
    param(
        [string]$Message, 
        [ValidateSet("DEBUG", "INFO", "WARN", "ERROR")]
        [string]$Level = "INFO",
        [string]$Component = "MAIN"
    )
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"
    $processId = $PID
    $logEntry = "[$timestamp] [$processId] [$Component] [$Level] $Message"
    
    # Only show DEBUG messages if LogLevel is DEBUG
    if ($Level -eq "DEBUG" -and $LogLevel -ne "DEBUG") {
        # Still write to file but don't display
        if (-not (Test-Path "logs")) { New-Item -ItemType Directory -Path "logs" -Force | Out-Null }
        Add-Content -Path $LogFile -Value $logEntry
        return
    }
    
    if (-not $Quiet) {
        switch ($Level) {
            "ERROR" { Write-Host $logEntry -ForegroundColor Red }
            "WARN"  { Write-Host $logEntry -ForegroundColor Yellow }
            "INFO"  { Write-Host $logEntry -ForegroundColor Green }
            "DEBUG" { Write-Host $logEntry -ForegroundColor Cyan }
            default { Write-Host $logEntry }
        }
    }
    
    # Ensure logs directory exists
    if (-not (Test-Path "logs")) { New-Item -ItemType Directory -Path "logs" -Force | Out-Null }
    Add-Content -Path $LogFile -Value $logEntry
}

function Test-ServiceHealth {
    param(
        [string]$ServiceName,
        [string]$Url,
        [int]$TimeoutSeconds = 60,
        [int]$RetryIntervalSeconds = 3,
        [string]$ExpectedContent = $null,
        [hashtable]$Headers = @{},
        [int]$Port = 0
    )
    
    Write-Log "Starting health check for $ServiceName at $Url (timeout: ${TimeoutSeconds}s)" "INFO"
    $startTime = Get-Date
    $timeout = $startTime.AddSeconds($TimeoutSeconds)
    $attemptCount = 0
    
    while ((Get-Date) -lt $timeout) {
        $attemptCount++
        $currentTime = Get-Date
        $elapsed = ($currentTime - $startTime).TotalSeconds
        
        try {
            Write-Log "Health check attempt $attemptCount for $ServiceName (elapsed: ${elapsed}s)" "DEBUG"

            # Optional TCP pre-check for faster feedback on Windows/Podman
            if ($Port -gt 0) {
                $tcpOk = Test-NetConnection -ComputerName "localhost" -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue
                if (-not $tcpOk) {
                    Write-Log "$ServiceName TCP not open on port $Port yet" "DEBUG"
                    Start-Sleep -Seconds $RetryIntervalSeconds
                    continue
                }
            }
            
            $requestParams = @{
                Uri = $Url
                Method = 'GET'
                TimeoutSec = 5
                UseBasicParsing = $true
                Headers = $Headers
                ErrorAction = 'Stop'
            }
            
            $response = Invoke-WebRequest @requestParams
            
            if ($response.StatusCode -eq 200) {
                # Check for expected content if specified
                if ($ExpectedContent -and $response.Content -notmatch $ExpectedContent) {
                    $snippet = $response.Content.Substring(0, [Math]::Min(120, $response.Content.Length))
                    Write-Log "$ServiceName returned 200 but content validation failed. Expected snippet: $ExpectedContent | Body: $snippet" "WARN"
                    Start-Sleep -Seconds $RetryIntervalSeconds
                    continue
                }
                
                $totalElapsed = ((Get-Date) - $startTime).TotalSeconds
                $snippetOk = $response.Content.Substring(0, [Math]::Min(120, $response.Content.Length))
                Write-Log "$ServiceName is healthy (HTTP $($response.StatusCode), total elapsed: ${totalElapsed}s) | Body: $snippetOk" "INFO"
                return @{
                    Success = $true
                    ResponseTime = $totalElapsed
                    StatusCode = $response.StatusCode
                    AttemptCount = $attemptCount
                    Content = $response.Content
                }
            }
            else {
                Write-Log "$ServiceName returned status code $($response.StatusCode)" "WARN"
            }
        }
        catch {
            $errorMessage = $_.Exception.Message
            if ($_.Exception.InnerException) {
                $errorMessage += " (Inner: $($_.Exception.InnerException.Message))"
            }
            Write-Log "$ServiceName health check attempt $attemptCount failed: $errorMessage" "DEBUG"
        }
        
        if ((Get-Date) -lt $timeout) {
            Write-Log "Waiting ${RetryIntervalSeconds}s before next health check attempt for $ServiceName" "DEBUG"
            Start-Sleep -Seconds $RetryIntervalSeconds
        }
    }
    
    $totalElapsed = ((Get-Date) - $startTime).TotalSeconds
    Write-Log "$ServiceName health check failed after $attemptCount attempts in ${totalElapsed}s" "ERROR"
    return @{
        Success = $false
        ResponseTime = $totalElapsed
        StatusCode = $null
        AttemptCount = $attemptCount
        Error = "Health check timeout after $TimeoutSeconds seconds"
    }
}

function Test-DatabaseConnectivity {
    param(
        [string]$ServiceName,
        [string]$DbHost = "localhost",
        [int]$Port,
        [int]$TimeoutSeconds = 30
    )
    
    Write-Log "Testing database connectivity for $ServiceName at ${DbHost}:${Port}" "INFO"
    $startTime = Get-Date
    
    try {
        # Test TCP connection first
        $tcpTest = Test-NetConnection -ComputerName $DbHost -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue
        
        if (-not $tcpTest) {
            Write-Log "$ServiceName TCP connection failed to ${DbHost}:${Port}" "ERROR"
            return @{
                Success = $false
                Error = "TCP connection failed"
                ResponseTime = ((Get-Date) - $startTime).TotalSeconds
            }
        }
        
        Write-Log "$ServiceName TCP connection successful to ${DbHost}:${Port}" "INFO"
        
        # Service-specific connectivity tests
        switch ($ServiceName) {
            "Neo4j" {
                return Test-Neo4jConnectivity -Neo4jHost $DbHost -Port $Port -TimeoutSeconds $TimeoutSeconds
            }
            "ChromaDB" {
                return Test-ChromaDBConnectivity -ChromaHost $DbHost -Port $Port -TimeoutSeconds $TimeoutSeconds
            }
            "PostgreSQL" {
                return Test-PostgreSQLConnectivity -PgHost $DbHost -Port $Port -TimeoutSeconds $TimeoutSeconds
            }
            default {
                $responseTime = ((Get-Date) - $startTime).TotalSeconds
                Write-Log "$ServiceName basic connectivity test passed (${responseTime}s)" "INFO"
                return @{
                    Success = $true
                    ResponseTime = $responseTime
                }
            }
        }
    }
    catch {
        $responseTime = ((Get-Date) - $startTime).TotalSeconds
        Write-Log "$ServiceName connectivity test failed: $($_.Exception.Message)" "ERROR"
        return @{
            Success = $false
            Error = $_.Exception.Message
            ResponseTime = $responseTime
        }
    }
}

function Test-Neo4jConnectivity {
    param(
        [string]$Neo4jHost = "localhost",
        [int]$Port = 7474,
        [int]$TimeoutSeconds = 30
    )
    
    Write-Log "Testing Neo4j connectivity (bolt and http)" "INFO" "NEO4J"
    $startTime = Get-Date
    
    try {
        # 1) Bolt/ cypher-shell (most authoritative for readiness)
        $boltOpen = Test-NetConnection -ComputerName "localhost" -Port 7687 -InformationLevel Quiet -WarningAction SilentlyContinue
        if (-not $boltOpen) {
            Write-Log "Neo4j bolt port 7687 not open yet" "WARN" "NEO4J"
        } else {
            $shell = podman exec codebase-rag-neo4j cypher-shell -u neo4j -p codebase-rag-2024 "RETURN 1 as test" 2>$null
            if ($LASTEXITCODE -eq 0 -and ($shell -match '1')) {
                $responseTime = ((Get-Date) - $startTime).TotalSeconds
                Write-Log "Neo4j bolt/cypher-shell OK (${responseTime}s)" "INFO" "NEO4J"
                return @{
                    Success = $true
                    ResponseTime = $responseTime
                    AuthenticationTest = $true
                    Method = "cypher-shell"
                }
            }
        }

        # 2) Fallback to HTTP check if cypher-shell path didn’t succeed but port is open
        $healthUrl = "http://${Neo4jHost}:${Port}/"
        $response = Invoke-WebRequest -Uri $healthUrl -Method GET -TimeoutSec $TimeoutSeconds -UseBasicParsing -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            $responseTime = ((Get-Date) - $startTime).TotalSeconds
            Write-Log "Neo4j HTTP landing page reachable (${responseTime}s)" "INFO" "NEO4J"
            return @{
                Success = $true
                ResponseTime = $responseTime
                AuthenticationTest = $false
                Method = "http"
            }
        }
    }
    catch {
        $responseTime = ((Get-Date) - $startTime).TotalSeconds
        Write-Log "Neo4j connectivity test failed: $($_.Exception.Message)" "ERROR" "NEO4J"
        return @{
            Success = $false
            Error = $_.Exception.Message
            ResponseTime = $responseTime
            AuthenticationTest = $false
        }
    }
}

function Test-ChromaDBConnectivity {
    param(
        [string]$ChromaHost = "localhost",
        [int]$Port = 8000,
        [int]$TimeoutSeconds = 30
    )
    
    Write-Log "Testing ChromaDB connectivity and API functionality" "INFO" "CHROMADB"
    $startTime = Get-Date

    try {
        # Chroma v2 health endpoint (standardized)
        $healthUrl = "http://${ChromaHost}:${Port}/api/v2/healthcheck"
        $resp = Invoke-WebRequest -Uri $healthUrl -Method GET -TimeoutSec $TimeoutSeconds -UseBasicParsing -ErrorAction Stop

        if ($resp.StatusCode -eq 200) {
            $responseTime = ((Get-Date) - $startTime).TotalSeconds
            Write-Log ("ChromaDB health OK (HTTP {0}) in {1}s | Body: {2}" -f $resp.StatusCode, ([math]::Round($responseTime,2)), ($resp.Content.Substring(0, [Math]::Min(120, $resp.Content.Length)))) "INFO" "CHROMADB"
            return @{
                Success = $true
                ResponseTime = $responseTime
                ApiTest = $true
                StatusCode = $resp.StatusCode
                Content = $resp.Content
            }
        } else {
            Write-Log ("ChromaDB health returned HTTP {0}" -f $resp.StatusCode) "WARN" "CHROMADB"
        }
    }
    catch {
        $responseTime = ((Get-Date) - $startTime).TotalSeconds
        Write-Log "ChromaDB connectivity test failed: $($_.Exception.Message)" "ERROR" "CHROMADB"
        return @{
            Success = $false
            Error = $_.Exception.Message
            ResponseTime = $responseTime
            ApiTest = $false
        }
    }
}

function Test-PostgreSQLConnectivity {
    param(
        [string]$PgHost = "localhost",
        [int]$Port = 5432,
        [int]$TimeoutSeconds = 30
    )
    
    Write-Log "Testing PostgreSQL connectivity" "INFO" "POSTGRES"
    $startTime = Get-Date
    
    try {
        # For PostgreSQL, we'll just test the TCP connection since we don't have psql available
        # In a full implementation, you would use a PostgreSQL .NET driver
        $tcpTest = Test-NetConnection -ComputerName $PgHost -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue
        
        if ($tcpTest) {
            $responseTime = ((Get-Date) - $startTime).TotalSeconds
            Write-Log "PostgreSQL TCP connectivity successful (${responseTime}s)" "INFO" "POSTGRES"
            return @{
                Success = $true
                ResponseTime = $responseTime
                TcpTest = $true
            }
        }
        else {
            Write-Log "PostgreSQL TCP connectivity failed" "ERROR" "POSTGRES"
            return @{
                Success = $false
                Error = "TCP connection failed"
                ResponseTime = ((Get-Date) - $startTime).TotalSeconds
                TcpTest = $false
            }
        }
    }
    catch {
        $responseTime = ((Get-Date) - $startTime).TotalSeconds
        Write-Log "PostgreSQL connectivity test failed: $($_.Exception.Message)" "ERROR" "POSTGRES"
        return @{
            Success = $false
            Error = $_.Exception.Message
            ResponseTime = $responseTime
            TcpTest = $false
        }
    }
}

function Invoke-ComprehensiveSystemValidation {
    param(
        [int]$TimeoutSeconds = 120
    )
    
    Write-Log "Starting comprehensive system validation" "INFO" "VALIDATION"
    $validationStart = Get-Date
    $validationResults = @{}
    $overallSuccess = $true
    
    # Phase 0: Configuration validation
    Write-Log "Phase 0: Configuration and environment validation" "INFO" "VALIDATION"
    try {
        Write-Log "Running Python configuration validator" "INFO" "VALIDATION"
        $configValidation = python -c "
import asyncio
import sys
import os
sys.path.append('src')
from services.config_validator import validate_configuration

async def main():
    try:
        summary = await validate_configuration()
        print(f'CONFIG_VALIDATION_SUCCESS={summary.overall_success}')
        print(f'CONFIG_VALIDATION_CRITICAL={summary.critical_failures}')
        print(f'CONFIG_VALIDATION_ERRORS={summary.error_failures}')
        print(f'CONFIG_VALIDATION_WARNINGS={summary.warning_failures}')
        print(f'CONFIG_VALIDATION_TIME={summary.validation_time:.2f}')
        return 0 if summary.overall_success else 1
    except Exception as e:
        print(f'CONFIG_VALIDATION_ERROR={str(e)}')
        return 1

sys.exit(asyncio.run(main()))
" 2>&1
        
        $configExitCode = $LASTEXITCODE
        
        if ($configExitCode -eq 0) {
            Write-Log "Configuration validation passed" "INFO" "VALIDATION"
            $validationResults["Configuration"] = @{
                Success = $true
                Message = "Configuration validation successful"
                Details = $configValidation
            }
        } else {
            Write-Log "Configuration validation failed" "ERROR" "VALIDATION"
            Write-Log "Configuration validation output: $configValidation" "ERROR" "VALIDATION"
            $validationResults["Configuration"] = @{
                Success = $false
                Message = "Configuration validation failed"
                Details = $configValidation
                Error = "Critical configuration issues detected"
            }
            $overallSuccess = $false
            
            # Parse validation output for specific issues
            if ($configValidation -match "CONFIG_VALIDATION_CRITICAL=(\d+)") {
                $criticalCount = $matches[1]
                if ([int]$criticalCount -gt 0) {
                    Write-Log "Found $criticalCount critical configuration issues - system cannot start safely" "ERROR" "VALIDATION"
                    Write-Log "Please fix configuration issues before proceeding" "ERROR" "VALIDATION"
                    Write-Log "Run 'python -m src.services.config_validator' for detailed report" "INFO" "VALIDATION"
                }
            }
        }
    } catch {
        Write-Log "Configuration validation error: $($_.Exception.Message)" "ERROR" "VALIDATION"
        $validationResults["Configuration"] = @{
            Success = $false
            Message = "Configuration validation error"
            Error = $_.Exception.Message
        }
        $overallSuccess = $false
    }
    
    # Define services to validate
    $services = @(
        @{
            Name = "ChromaDB"
            HealthUrl = "http://localhost:8000/api/v2/healthcheck"
            DatabasePort = 8000
            ExpectedContent = $null
            Critical = $true
        },
        @{
            Name = "Neo4j"
            HealthUrl = "http://localhost:7474/"
            DatabasePort = 7474
            ExpectedContent = $null
            Critical = $true
        },
        @{
            Name = "API Server"
            HealthUrl = "http://localhost:8080/api/v1/health/"
            DatabasePort = 8080
            ExpectedContent = $null
            Critical = $true
        }
    )
    
    # Add PostgreSQL if it's expected to be running
    if ($Mode -eq 'full') {
        $services += @{
            Name = "PostgreSQL"
            HealthUrl = $null
            DatabasePort = 5432
            ExpectedContent = $null
            Critical = $false
        }
    }
    
    Write-Log "Validating $($services.Count) services with ${TimeoutSeconds}s timeout" "INFO" "VALIDATION"
    # Hint: Using Chroma v2 health; Neo4j via /; API via /api/v1/health/
    
    # Phase 1: Basic service health checks
    Write-Log "Phase 1: Basic service health validation" "INFO" "VALIDATION"
    foreach ($service in $services) {
        Write-Log "Validating service: $($service.Name)" "INFO" "VALIDATION"
        
        if ($service.HealthUrl) {
            # Provide Port for TCP pre-checks when known
            $portHint = if ($service.Name -eq "ChromaDB") { 8000 } elseif ($service.Name -eq "Neo4j") { 7474 } elseif ($service.Name -eq "API Server") { 8080 } else { 0 }
            $timeoutHint = if ($service.Name -eq "ChromaDB" -or $service.Name -eq "Neo4j") { 120 } else { 90 }
            $healthResult = Test-ServiceHealth -ServiceName $service.Name -Url $service.HealthUrl -TimeoutSeconds $timeoutHint -RetryIntervalSeconds 3 -ExpectedContent $service.ExpectedContent -Port $portHint
            $validationResults[$service.Name] = $healthResult
            
            if (-not $healthResult.Success) {
                Write-Log "$($service.Name) health check failed: $($healthResult.Error)" "ERROR" "VALIDATION"
                if ($service.Critical) {
                    $overallSuccess = $false
                }
            }
        }
        else {
            # For services without HTTP endpoints, test database connectivity
            $dbResult = Test-DatabaseConnectivity -ServiceName $service.Name -Port $service.DatabasePort
            $validationResults[$service.Name] = $dbResult
            
            if (-not $dbResult.Success) {
                Write-Log "$($service.Name) connectivity failed: $($dbResult.Error)" "ERROR" "VALIDATION"
                if ($service.Critical) {
                    $overallSuccess = $false
                }
            }
        }
    }
    
    # Phase 2: Inter-service communication validation
    Write-Log "Phase 2: Inter-service communication validation" "INFO" "VALIDATION"
    
    # Test API to database connections
    if ($validationResults["API Server"].Success) {
        Write-Log "Testing API server database connections" "INFO" "VALIDATION"
        
        # Test API readiness endpoint (includes database connectivity)
        $readinessResult = Test-ServiceHealth -ServiceName "API Readiness" -Url "http://localhost:8080/api/v1/health/ready" -TimeoutSeconds 60
        $validationResults["API Readiness"] = $readinessResult
        
        if (-not $readinessResult.Success) {
            Write-Log "API readiness check failed - database connections may be broken" "ERROR" "VALIDATION"
            $overallSuccess = $false
        }
        else {
            Write-Log "API readiness check passed - database connections verified" "INFO" "VALIDATION"
        }
    }
    else {
        Write-Log "Skipping inter-service validation - API server not healthy" "WARN" "VALIDATION"
        $overallSuccess = $false
    }
    
    # Phase 3: System integration validation
    Write-Log "Phase 3: System integration validation" "INFO" "VALIDATION"
    
    if ($overallSuccess) {
        # Test a simple end-to-end operation if possible
        try {
            Write-Log "Testing system integration with health summary endpoint" "INFO" "VALIDATION"
            $integrationResult = Test-ServiceHealth -ServiceName "System Integration" -Url "http://localhost:8080/api/v1/health/" -TimeoutSeconds 15
            $validationResults["System Integration"] = $integrationResult
            
            if (-not $integrationResult.Success) {
                Write-Log "System integration test failed" "WARN" "VALIDATION"
            }
            else {
                Write-Log "System integration test passed" "INFO" "VALIDATION"
            }
        }
        catch {
            Write-Log "System integration test error: $($_.Exception.Message)" "WARN" "VALIDATION"
        }
    }
    
    # Generate validation summary
    $validationEnd = Get-Date
    $totalValidationTime = ($validationEnd - $validationStart).TotalSeconds
    
    Write-Log "=== SYSTEM VALIDATION SUMMARY ===" "INFO" "VALIDATION"
    Write-Log "Total validation time: ${totalValidationTime}s" "INFO" "VALIDATION"
    Write-Log "Overall result: $(if ($overallSuccess) { 'SUCCESS' } else { 'FAILED' })" $(if ($overallSuccess) { "INFO" } else { "ERROR" }) "VALIDATION"
    
    foreach ($serviceName in $validationResults.Keys) {
        $result = $validationResults[$serviceName]
        $status = if ($result.Success) { "[PASS]" } else { "[FAIL]" }
        $responseTime = if ($result.ResponseTime) { "$([math]::Round($result.ResponseTime, 2))s" } else { "N/A" }
        
        Write-Log "$status $serviceName (${responseTime})" $(if ($result.Success) { "INFO" } else { "ERROR" }) "VALIDATION"
        
        if (-not $result.Success -and $result.Error) {
            Write-Log "  Error: $($result.Error)" "ERROR" "VALIDATION"
            
            # Provide troubleshooting guidance
            switch ($serviceName) {
                "ChromaDB" {
                    Write-Log "  Troubleshooting: Check if ChromaDB container is running: podman ps | grep chromadb" "INFO" "VALIDATION"
                    Write-Log "  Troubleshooting: Restart ChromaDB: podman-compose -f podman-compose.dev.yml restart chromadb" "INFO" "VALIDATION"
                }
                "Neo4j" {
                    Write-Log "  Troubleshooting: Check if Neo4j container is running: podman ps | grep neo4j" "INFO" "VALIDATION"
                    Write-Log "  Troubleshooting: Check Neo4j logs: podman logs neo4j" "INFO" "VALIDATION"
                    Write-Log "  Troubleshooting: Verify credentials: neo4j/codebase-rag-2024" "INFO" "VALIDATION"
                }
                "API Server" {
                    Write-Log "  Troubleshooting: Check if API process is running: Get-Process | Where-Object {$_.ProcessName -match 'python|uvicorn'}" "INFO" "VALIDATION"
                    Write-Log "  Troubleshooting: Check API logs in the console or logs directory" "INFO" "VALIDATION"
                    Write-Log "  Troubleshooting: Verify Python dependencies: pip list | grep fastapi" "INFO" "VALIDATION"
                }
                "PostgreSQL" {
                    Write-Log "  Troubleshooting: Check if PostgreSQL container is running: podman ps | grep postgres" "INFO" "VALIDATION"
                    Write-Log "  Troubleshooting: Check PostgreSQL logs: podman logs postgres" "INFO" "VALIDATION"
                }
            }
        }
    }
    
    return @{
        Success = $overallSuccess
        Results = $validationResults
        ValidationTime = $totalValidationTime
        Summary = "Validated $($validationResults.Count) services in ${totalValidationTime}s"
    }
}

function Wait-ForServiceInitialization {
    param(
        [string]$ServiceName,
        [scriptblock]$TestCondition,
        [int]$TimeoutSeconds = 120,
        [int]$CheckIntervalSeconds = 5,
        [string]$InitializationMessage = "Waiting for service initialization"
    )
    
    Write-Log "$InitializationMessage for $ServiceName (timeout: ${TimeoutSeconds}s)" "INFO" "INIT"
    $startTime = Get-Date
    $timeout = $startTime.AddSeconds($TimeoutSeconds)
    $attemptCount = 0
    
    while ((Get-Date) -lt $timeout) {
        $attemptCount++
        $elapsed = ((Get-Date) - $startTime).TotalSeconds
        
        Write-Log "Initialization check $attemptCount for $ServiceName (elapsed: ${elapsed}s)" "DEBUG" "INIT"
        
        try {
            $result = & $TestCondition
            if ($result) {
                $totalElapsed = ((Get-Date) - $startTime).TotalSeconds
                Write-Log "$ServiceName initialization completed successfully ($([math]::Round($totalElapsed, 1))s, $attemptCount attempts)" "INFO" "INIT"
                return @{
                    Success = $true
                    ElapsedTime = $totalElapsed
                    AttemptCount = $attemptCount
                }
            }
        }
        catch {
            Write-Log "$ServiceName initialization check failed: $($_.Exception.Message)" "DEBUG" "INIT"
        }
        
        if ((Get-Date) -lt $timeout) {
            Write-Log "Waiting ${CheckIntervalSeconds}s before next initialization check for $ServiceName" "DEBUG" "INIT"
            Start-Sleep -Seconds $CheckIntervalSeconds
        }
    }
    
    $totalElapsed = ((Get-Date) - $startTime).TotalSeconds
    Write-Log "$ServiceName initialization timeout after $([math]::Round($totalElapsed, 1))s ($attemptCount attempts)" "ERROR" "INIT"
    return @{
        Success = $false
        ElapsedTime = $totalElapsed
        AttemptCount = $attemptCount
        Error = "Initialization timeout"
    }
}

function Show-SystemStatus {
    Write-Log "=== GraphRAG System Status ===" "INFO" "STATUS"
    
    # Check container status
    try {
        Write-Log "Container Status:" "INFO" "STATUS"
        $containers = podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>$null
        if ($containers) {
            Write-Host $containers
            
            # Get detailed container info
            $containerCount = (podman ps --format "{{.Names}}" 2>$null | Measure-Object).Count
            Write-Log "Total running containers: $containerCount" "INFO" "STATUS"
        }
        else {
            Write-Log "No containers currently running" "WARN" "STATUS"
        }
    }
    catch {
        Write-Log "Podman not available or error checking containers: $($_.Exception.Message)" "WARN" "STATUS"
    }
    
    # Comprehensive service health checks
    Write-Log "Service Health Status:" "INFO" "STATUS"
    $services = @(
        @{
            Name = "ChromaDB"
            Port = 8000
            HealthUrl = "http://localhost:8000/api/v2/healthcheck"
            ExpectedContent = $null
        },
        @{
            Name = "Neo4j"
            Port = 7474
            HealthUrl = "http://localhost:7474/"
            ExpectedContent = $null
        },
        @{
            Name = "API Server"
            Port = 8080
            HealthUrl = "http://localhost:8080/api/v1/health/"
            ExpectedContent = $null
        },
        @{
            Name = "Frontend"
            Port = 3000
            HealthUrl = "http://localhost:3000"
            ExpectedContent = $null
        }
    )
    
    $healthyServices = 0
    $totalServices = $services.Count
    
    foreach ($service in $services) {
        try {
            # Test port connectivity first
            $portOpen = Test-NetConnection -ComputerName localhost -Port $service.Port -InformationLevel Quiet -WarningAction SilentlyContinue
            
            if ($portOpen) {
                # Test HTTP endpoint if available
                if ($service.HealthUrl) {
                    try {
                        $response = Invoke-WebRequest -Uri $service.HealthUrl -Method GET -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
                        if ($response.StatusCode -eq 200) {
                            Write-Log "[OK] $($service.Name) (port $($service.Port)): Healthy" "INFO" "STATUS"
                            $healthyServices++
                        }
                        else {
                            Write-Log "[!] $($service.Name) (port $($service.Port)): HTTP $($response.StatusCode)" "WARN" "STATUS"
                        }
                    }
                    catch {
                        Write-Log "[!] $($service.Name) (port $($service.Port)): Port open, HTTP failed" "WARN" "STATUS"
                    }
                }
                else {
                    Write-Log "[OK] $($service.Name) (port $($service.Port)): Port open" "INFO" "STATUS"
                    $healthyServices++
                }
            }
            else {
                Write-Log "[X] $($service.Name) (port $($service.Port)): Not running" "WARN" "STATUS"
            }
        }
        catch {
            Write-Log "[?] $($service.Name) (port $($service.Port)): Status check failed" "WARN" "STATUS"
        }
    }
    
    # Overall system health summary
    $healthPercentage = [math]::Round(($healthyServices / $totalServices) * 100, 1)
    $healthStatus = if ($healthPercentage -eq 100) { "EXCELLENT" } 
                   elseif ($healthPercentage -ge 75) { "GOOD" }
                   elseif ($healthPercentage -ge 50) { "DEGRADED" }
                   else { "CRITICAL" }
    
    Write-Log "=== System Health Summary ===" "INFO" "STATUS"
    Write-Log "Healthy Services: $healthyServices/$totalServices ($healthPercentage%)" "INFO" "STATUS"
    Write-Log "Overall Status: $healthStatus" $(if ($healthPercentage -ge 75) { "INFO" } else { "WARN" }) "STATUS"
    
    # Performance information
    try {
        $uptime = (Get-Date) - $StartTime
        Write-Log "Session Uptime: $([math]::Round($uptime.TotalMinutes, 1)) minutes" "INFO" "STATUS"
    }
    catch {
        Write-Log "Uptime calculation failed" "DEBUG" "STATUS"
    }
    
    Write-Log "=== Access URLs ===" "INFO" "STATUS"
    Write-Host "ChromaDB API:   http://localhost:8000/api/v2/healthcheck" -ForegroundColor Cyan
    Write-Host "Neo4j Browser:  http://localhost:7474 (neo4j / codebase-rag-2024)" -ForegroundColor Cyan
    Write-Host "API Server:     http://localhost:8080/api/v1/health/" -ForegroundColor Cyan
    Write-Host "Frontend App:   http://localhost:3000" -ForegroundColor Cyan
    
    Write-Log "=== Troubleshooting ===" "INFO" "STATUS"
    Write-Host "View logs:      Get-Content $LogFile -Wait" -ForegroundColor Yellow
    Write-Host "Check status:   .\START.ps1 -Status" -ForegroundColor Yellow
    Write-Host "Clean restart:  .\START.ps1 -Clean" -ForegroundColor Yellow
}

# Ensure fresh startup helpers exist before use in 'full' mode
function Write-LogWrapper { param([string]$msg,[string]$lvl='INFO'); Write-Log $msg $lvl }

function Stop-ProcessIfRunning {
    param([string]$Name)
    try {
        $procs = Get-Process -Name $Name -ErrorAction SilentlyContinue
        if ($procs) {
            Write-Log "Stopping process: $Name (count=$($procs.Count))" "INFO"
            $procs | Stop-Process -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 300
        }
    } catch {
        $errMsg = $_.Exception.Message
        Write-Log ("Unable to stop process {0}: {1}" -f $Name, $errMsg) "WARN"
    }
}

function Stop-FrontendIfRunning {
    # Safer: only stop Node/NPM processes started from this workspace's frontend dir or bound to PORT=3000
    try {
        $workspace = (Get-Location).Path
        $frontendPath = Join-Path $workspace "frontend"

        # Match node-based frontend dev servers by command line containing our frontend path
        $nodeProcs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
            ($_.Name -match 'node' -or $_.Name -match 'npm' -or $_.Name -match 'yarn' -or $_.Name -match 'pnpm') -and
            ($_.CommandLine -match [regex]::Escape($frontendPath))
        }

        # Fallback: match by typical dev server port marker (PORT=3000) if path match fails
        if (-not $nodeProcs -or $nodeProcs.Count -eq 0) {
            $nodeProcs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
                ($_.Name -match 'node' -or $_.Name -match 'npm' -or $_.Name -match 'yarn' -or $_.Name -match 'pnpm') -and
                ($_.CommandLine -match 'PORT\s*=\s*3000' -or $_.CommandLine -match '--port\s+3000')
            }
        }

        foreach ($p in ($nodeProcs | Where-Object { $_ })) {
            Write-Log ("Stopping Frontend proc PID {0}: {1}" -f $p.ProcessId, $p.CommandLine) "INFO"
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 200
        }
    } catch {
        Write-Log ("Scoped frontend stop failed: {0}" -f $_.Exception.Message) "WARN"
    }
}

function Stop-ApiIfRunning {
    # Safer: only stop uvicorn/python serving our API on this workspace/path or port 8080
    try {
        $workspace = (Get-Location).Path

        # Match uvicorn command launched for this app
        $apiProcs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
            ($_.CommandLine -match 'uvicorn') -and
            ($_.CommandLine -match 'src\.main:app' -or $_.CommandLine -match [regex]::Escape($workspace)) -and
            ($_.CommandLine -match '--port\s+8080' -or $_.CommandLine -match '0\.0\.0\.0:8080')
        }

        # Fallback: any python process running uvicorn on 8080 when above filter fails
        if (-not $apiProcs -or $apiProcs.Count -eq 0) {
            $apiProcs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
                ($_.Name -match 'python' -or $_.Name -match 'uvicorn') -and
                ($_.CommandLine -match 'uvicorn') -and
                ($_.CommandLine -match '--port\s+8080' -or $_.CommandLine -match '0\.0\.0\.0:8080')
            }
        }

        foreach ($p in ($apiProcs | Where-Object { $_ })) {
            Write-Log ("Stopping API proc PID {0}: {1}" -f $p.ProcessId, $p.CommandLine) "INFO"
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 200
        }
    } catch {
        Write-Log ("Scoped API stop failed: {0}" -f $_.Exception.Message) "WARN"
    }
}

function Stop-ComposeStack {
    param([string[]]$ComposeFiles = @("podman-compose.dev.yml"))
    foreach ($f in $ComposeFiles) {
        if (Test-Path $f) {
            try {
                Write-Log "Bringing down compose stack: $f" "INFO"
                podman-compose -f $f down --remove-orphans 2>$null | Out-Null
            } catch {
                $errMsg = $_.Exception.Message
                Write-Log ("Compose down failed for {0}: {1}" -f $f, $errMsg) "WARN"
            }
        }
    }
}

function Start-BackendServices {
    Write-Log "Starting backend infrastructure services (fresh)..." "INFO" "BACKEND"

    # If Clean or as part of 'full', ensure old stack is stopped
    if ($Clean) {
        Write-Log "Cleaning up existing backend services..." "INFO" "BACKEND"
        Stop-ComposeStack -ComposeFiles @("podman-compose.dev.yml")
        try { 
            Write-Log "Pruning unused containers and images..." "INFO" "BACKEND"
            podman system prune -f 2>$null | Out-Null 
        } catch {
            Write-Log "Container pruning failed: $($_.Exception.Message)" "WARN" "BACKEND"
        }
    }

    # Start only required services for MVP: chromadb and neo4j
    Write-Log "Launching ChromaDB and Neo4j using podman-compose.dev.yml..." "INFO" "BACKEND"
    try {
        $composeResult = podman-compose -f podman-compose.dev.yml up -d chromadb neo4j 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Log "Failed to start backend services (exit code: $LASTEXITCODE)" "ERROR" "BACKEND"
            Write-Log "Compose output: $composeResult" "ERROR" "BACKEND"
            return $false
        }
        Write-Log "Backend containers started, waiting for service initialization..." "INFO" "BACKEND"
    }
    catch {
        Write-Log "Exception starting backend services: $($_.Exception.Message)" "ERROR" "BACKEND"
        return $false
    }
    
    # Wait for ChromaDB to be ready
    Write-Log "Waiting for ChromaDB initialization..." "INFO" "BACKEND"
    $chromaResult = Wait-ForServiceInitialization -ServiceName "ChromaDB" -TimeoutSeconds 240 -CheckIntervalSeconds 3 -TestCondition {
        try {
            # Prefer TCP test first to avoid long HTTP timeouts
            $tcpOk = Test-NetConnection -ComputerName "localhost" -Port 8000 -InformationLevel Quiet -WarningAction SilentlyContinue
            if (-not $tcpOk) { return $false }
            $response = Invoke-WebRequest -Uri "http://localhost:8000/api/v2/healthcheck" -Method GET -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
            return $response.StatusCode -eq 200
        }
        catch {
            return $false
        }
    } -InitializationMessage "Waiting for ChromaDB API to become available"
    
    if (-not $chromaResult.Success) {
        Write-Log "ChromaDB failed to initialize within timeout period" "ERROR" "BACKEND"
        return $false
    }
    
    # Wait for Neo4j to be ready
    Write-Log "Waiting for Neo4j initialization..." "INFO" "BACKEND"
    $neo4jResult = Wait-ForServiceInitialization -ServiceName "Neo4j" -TimeoutSeconds 180 -CheckIntervalSeconds 3 -TestCondition {
        try {
            # Prefer bolt readiness via cypher-shell which is more reliable than HTTP landing page
            $tcpOk = Test-NetConnection -ComputerName "localhost" -Port 7687 -InformationLevel Quiet -WarningAction SilentlyContinue
            if (-not $tcpOk) { return $false }
            $shell = podman exec codebase-rag-neo4j cypher-shell -u neo4j -p codebase-rag-2024 "RETURN 1 as test" 2>$null
            if ($LASTEXITCODE -ne 0) { return $false }
            return ($shell -match '1')
        }
        catch {
            return $false
        }
    } -InitializationMessage "Waiting for Neo4j to accept cypher-shell connections"
    
    if (-not $neo4jResult.Success) {
        Write-Log "Neo4j failed to initialize within timeout period" "ERROR" "BACKEND"
        return $false
    }
    
    # Validate database connectivity
    Write-Log "Validating backend service connectivity..." "INFO" "BACKEND"
    $chromaConnectivity = Test-DatabaseConnectivity -ServiceName "ChromaDB" -Port 8000
    $neo4jConnectivity = Test-DatabaseConnectivity -ServiceName "Neo4j" -Port 7474
    
    if (-not $chromaConnectivity.Success) {
        Write-Log "ChromaDB connectivity validation failed: $($chromaConnectivity.Error)" "ERROR" "BACKEND"
        return $false
    }
    
    if (-not $neo4jConnectivity.Success) {
        Write-Log "Neo4j connectivity validation failed: $($neo4jConnectivity.Error)" "ERROR" "BACKEND"
        return $false
    }
    
    $totalBackendTime = $chromaResult.ElapsedTime + $neo4jResult.ElapsedTime
    Write-Log "Backend services started and validated successfully (total time: ${totalBackendTime}s)" "INFO" "BACKEND"
    return $true
}


function Start-ApiServer {
    Write-Log "Starting GraphRAG API server (fresh)..." "INFO" "API"

    # Always stop previous API processes
    Write-Log "Stopping any existing API server processes..." "INFO" "API"
    Stop-ApiIfRunning

    try {
        if (Test-Path "src\main.py") {
            Write-Log "Starting FastAPI server with log level: $LogLevel" "INFO" "API"
            $env:LOG_LEVEL = $LogLevel
            # If caller forces a host API port, honor it (used to avoid 8080 collisions)
            if (-not $env:GRAFRAG_HOST_API_PORT -and $Mode -eq 'api') {
                # In api mode, prefer 8081 by default to avoid container 8080
                $env:GRAFRAG_HOST_API_PORT = "8081"
                Write-Log ("GRAFRAG_HOST_API_PORT not set; defaulting to {0} for api mode" -f $env:GRAFRAG_HOST_API_PORT) "WARN" "API"
            }
            
            # Validate Python and dependencies before starting
            Write-Log "Validating Python environment..." "INFO" "API"
            $pythonVersion = python --version 2>&1
            Write-Log "Python version: $pythonVersion" "INFO" "API"
            
            # Check for required packages
            $requiredPackages = @("fastapi", "uvicorn")
            foreach ($package in $requiredPackages) {
                try {
                    $packageCheck = python -c "import $package; print('${package}: OK')" 2>&1
                    Write-Log "Package check: $packageCheck" "DEBUG" "API"
                }
                catch {
                    Write-Log "Warning: Package $package may not be installed" "WARN" "API"
                }
            }
            
            Write-Log "Launching uvicorn server..." "INFO" "API"
            # Force local workspace source to be used by uvicorn by setting PYTHONPATH to the cwd
            try {
                $cwd = (Get-Location).Path
                $env:PYTHONPATH = $cwd
                Write-Log ("PYTHONPATH set to: {0}" -f $env:PYTHONPATH) "INFO" "API"
            } catch {
                Write-Log ("Failed to set PYTHONPATH: {0}" -f $_.Exception.Message) "WARN" "API"
            }

            # Select host port for uvicorn. If GRAFRAG_HOST_API_PORT is set, honor it; otherwise default to 8080.
            $hostPort = 8080
            if ($env:GRAFRAG_HOST_API_PORT) {
                try {
                    $hp = [int]$env:GRAFRAG_HOST_API_PORT
                    if ($hp -ge 1024 -and $hp -le 65535) {
                        $hostPort = $hp
                        Write-Log ("Using forced host uvicorn port: {0}" -f $hostPort) "INFO" "API"
                    } else {
                        Write-Log ("Invalid GRAFRAG_HOST_API_PORT '{0}', falling back to 8080" -f $env:GRAFRAG_HOST_API_PORT) "WARN" "API"
                    }
                } catch {
                    Write-Log ("Failed to parse GRAFRAG_HOST_API_PORT '{0}', falling back to 8080" -f $env:GRAFRAG_HOST_API_PORT) "WARN" "API"
                }
            }

            $cmd = "python -m uvicorn src.main:app --host 0.0.0.0 --port $hostPort --reload --log-level $($LogLevel.ToLower())"
            Write-Log ("Launching Command: {0}" -f $cmd) "INFO" "API"
            Start-Process -FilePath "python" -ArgumentList "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "$hostPort", "--reload", "--log-level", $LogLevel.ToLower() -WorkingDirectory (Get-Location) -WindowStyle Hidden
        }
        elseif (Test-Path "mvp\main.py") {
            Write-Log "Starting MVP API server..." "INFO" "API"
            Start-Process -FilePath "python" -ArgumentList "mvp\main.py" -WorkingDirectory (Get-Location) -WindowStyle Hidden
        }
        else {
            Write-Log "No API server found (src\main.py or mvp\main.py)" "ERROR" "API"
            return $false
        }
        
        # Wait for API server initialization with proper validation (respect chosen port)
        Write-Log "Waiting for API server initialization..." "INFO" "API"
        $apiBase = ("http://localhost:{0}" -f $hostPort)
        $apiResult = Wait-ForServiceInitialization -ServiceName "API Server" -TimeoutSeconds 60 -CheckIntervalSeconds 2 -TestCondition {
            try {
                $response = Invoke-WebRequest -Uri ($apiBase + "/api/v1/health/") -Method GET -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
                return $response.StatusCode -eq 200
            }
            catch {
                return $false
            }
        } -InitializationMessage "Waiting for API server to become responsive"
        
        if (-not $apiResult.Success) {
            Write-Log "API server failed to initialize within timeout period" "ERROR" "API"
            return $false
        }
        
        # Comprehensive API health validation
        Write-Log "Performing comprehensive API health validation..." "INFO" "API"
        # Query runtime-info to ensure the running server instance is the edited codebase
        try {
            $rt = Invoke-WebRequest -Uri ($apiBase + "/api/v1/health/runtime-info") -Method GET -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
            if ($rt.StatusCode -eq 200 -and $rt.Content) {
                $rtJson = $null
                try { $rtJson = $rt.Content | ConvertFrom-Json } catch {}
                if ($rtJson) {
                    $modFile = $rtJson.module_main_file
                    $cwdSrv  = $rtJson.cwd
                    Write-Log ("RuntimeInfo: module_main_file={0} | cwd={1}" -f $modFile, $cwdSrv) "INFO" "API"
                } else {
                    Write-Log "RuntimeInfo: JSON parse failed" "WARN" "API"
                }
            } else {
                Write-Log ("RuntimeInfo endpoint returned HTTP {0}" -f $rt.StatusCode) "WARN" "API"
            }
        } catch {
            # If runtime-info is missing, log a strong hint about wrong code instance and abort early
            Write-Log ("RuntimeInfo endpoint not reachable or missing: {0}" -f $_.Exception.Message) "ERROR" "API"
            Write-Log "The API instance on :8080 does not include new diagnostics. Likely a different source tree or container is serving." "ERROR" "API"
            Write-Log "Ensure no containerized API is bound to 8080 or change host uvicorn port, then re-run START.ps1 -Mode api" "ERROR" "API"
        }

        $healthResult = Test-ServiceHealth -ServiceName "API Server" -Url ($apiBase + "/api/v1/health/") -TimeoutSeconds 30
        
        if (-not $healthResult.Success) {
            Write-Log "API server health validation failed: $($healthResult.Error)" "ERROR" "API"
            return $false
        }
        
        # Test API readiness (includes database connectivity)
        Write-Log "Testing API readiness and database connectivity..." "INFO" "API"
        $readinessResult = Test-ServiceHealth -ServiceName "API Readiness" -Url ($apiBase + "/api/v1/health/ready") -TimeoutSeconds 60
        
        if (-not $readinessResult.Success) {
            Write-Log "API readiness check failed - may indicate database connectivity issues" "WARN" "API"
            Write-Log "API server started but may not be fully functional" "WARN" "API"
        }
        else {
            # Parse JSON to reflect actual readiness status
            try {
                $readyJson = $null
                if ($readinessResult.Content) {
                    $readyJson = $readinessResult.Content | ConvertFrom-Json
                }
                if ($readyJson -and $readyJson.status) {
                    Write-Log ("API readiness status: {0}" -f $readyJson.status) "INFO" "API"
                } else {
                    Write-Log "API readiness endpoint returned 200 but status field missing" "WARN" "API"
                }
            } catch {
                Write-Log ("API readiness JSON parse failed: {0}" -f $_.Exception.Message) "WARN" "API"
            }
        }
        
        Write-Log "API server started successfully (initialization time: $($apiResult.ElapsedTime)s)" "INFO" "API"
        return $true
    }
    catch {
        Write-Log "Failed to start API server: $($_.Exception.Message)" "ERROR" "API"
        return $false
    }
}

function Start-Frontend {
    Write-Log "Starting React frontend (fresh)..." "INFO"

    # Always stop previous dev servers
    Stop-FrontendIfRunning

    if (-not (Test-Path "frontend\package.json")) {
        Write-Log "Frontend not found (frontend\package.json missing)" "ERROR"
        return $false
    }
    
    if (-not (Test-Path "frontend\node_modules")) {
        Write-Log "Installing frontend dependencies..." "INFO"
        Push-Location frontend
        npm install
        Pop-Location
    }
    
    # Start frontend dev server in FOREGROUND (do not background)
    Write-Log "Launching React development server in foreground..." "INFO"
    Push-Location frontend
    try {
        # Force PowerShell to invoke npm.cmd to avoid opening npm.ps1 in an editor
        $env:PORT = 3000
        & "$env:ProgramFiles\nodejs\npm.cmd" start
        $npmExit = $LASTEXITCODE
    } catch {
        Pop-Location
        Write-Log ("Failed to start React dev server: {0}" -f $_.Exception.Message) "ERROR"
        return $false
    } finally {
        if ((Get-Location).Path -like "*frontend") { Pop-Location }
    }

    if ($npmExit -ne 0) {
        Write-Log "React dev server exited with code $npmExit" "ERROR"
        return $false
    }
    return $true
}

function Start-MvpMode {
    Write-Log "Starting MVP mode (minimal viable product)..." "INFO"
    
    if (-not (Test-Path "mvp\main.py")) {
        Write-Log "MVP version not found (mvp\main.py missing)" "ERROR"
        return $false
    }
    
    # Start MVP with its own compose file
    if ($Clean) {
        podman-compose -f mvp-compose.yml down --remove-orphans 2>$null | Out-Null
    }
    
    podman-compose -f mvp-compose.yml up -d
    
    if ($LASTEXITCODE -ne 0) {
        Write-Log "Failed to start MVP services" "ERROR"
        return $false
    }
    
    Write-Log "MVP started successfully" "INFO"
    return $true
}

function Install-Dependencies {
    if ($SkipDeps) {
        Write-Log "Skipping dependency check (--SkipDeps specified)" "INFO" "DEPS"
        return $true
    }
    
    Write-Log "Checking system dependencies..." "INFO" "DEPS"
    $dependencyIssues = @()
    
    # Check Podman
    if (-not (Get-Command podman -ErrorAction SilentlyContinue)) {
        Write-Log "Podman not found. Please install Podman Desktop or Podman CLI" "ERROR" "DEPS"
        $dependencyIssues += "Podman CLI not available"
        return $false
    }
    else {
        $podmanVersion = podman --version 2>$null
        Write-Log "Podman available: $podmanVersion" "INFO" "DEPS"
    }
    
    # Check podman-compose
    if (-not (Get-Command podman-compose -ErrorAction SilentlyContinue)) {
        Write-Log "podman-compose not found, attempting to install..." "INFO" "DEPS"
        try {
            pip install podman-compose
            Write-Log "podman-compose installed successfully" "INFO" "DEPS"
        }
        catch {
            Write-Log "Failed to install podman-compose: $($_.Exception.Message)" "ERROR" "DEPS"
            $dependencyIssues += "podman-compose installation failed"
            return $false
        }
    }
    else {
        $composeVersion = podman-compose --version 2>$null
        Write-Log "podman-compose available: $composeVersion" "INFO" "DEPS"
    }
    
    # Check Python
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Log "Python not found. Please install Python 3.8+" "ERROR" "DEPS"
        $dependencyIssues += "Python not available"
        return $false
    }
    else {
        $pythonVersion = python --version 2>&1
        Write-Log "Python available: $pythonVersion" "INFO" "DEPS"
        
        # Check pip
        if (-not (Get-Command pip -ErrorAction SilentlyContinue)) {
            Write-Log "pip not found - may cause issues with Python dependencies" "WARN" "DEPS"
            $dependencyIssues += "pip not available"
        }
    }
    
    # Check Node.js (for frontend)
    if ($Mode -eq 'full' -or $Mode -eq 'frontend') {
        if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
            Write-Log "Node.js not found. Please install Node.js 16+" "WARN" "DEPS"
            $dependencyIssues += "Node.js not available (frontend will not work)"
        }
        else {
            $nodeVersion = node --version 2>$null
            Write-Log "Node.js available: $nodeVersion" "INFO" "DEPS"
            
            # Check npm
            if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
                Write-Log "npm not found - frontend dependencies cannot be managed" "WARN" "DEPS"
                $dependencyIssues += "npm not available"
            }
        }
    }
    
    # Summary
    if ($dependencyIssues.Count -eq 0) {
        Write-Log "All required dependencies are available" "INFO" "DEPS"
    }
    else {
        Write-Log "Dependency issues found: $($dependencyIssues.Count)" "WARN" "DEPS"
        foreach ($issue in $dependencyIssues) {
            Write-Log "  - $issue" "WARN" "DEPS"
        }
    }
    
    Write-Log "Dependencies check completed" "INFO" "DEPS"
    return $true
}

# === MAIN EXECUTION ===
function Main {
    Write-Log "GraphRAG Unified Startup Script v2.0 - Enhanced Validation" "INFO" "MAIN"
    $codeVersion = Get-And-Increment-Version
    if ($codeVersion -gt 0) {
        Write-Log ("Code Version: {0}" -f $codeVersion) "INFO" "MAIN"
    } else {
        Write-Log "Code Version: unavailable (VERSION file error)" "WARN" "MAIN"
    }
    # Print working dir and Python resolution upfront to detect path drift
    try {
        $cwd = (Get-Location).Path
        Write-Log ("Working Directory: {0}" -f $cwd) "INFO" "MAIN"
        $py = (Get-Command python -ErrorAction SilentlyContinue).Source
        if ($py) { Write-Log ("Python Executable: {0}" -f $py) "INFO" "MAIN" }
    } catch {}
    Write-Log "Mode: $Mode | Clean: $Clean | SkipDeps: $SkipDeps | LogLevel: $LogLevel" "INFO" "MAIN"
    Write-Log "Session ID: $PID | Log file: $LogFile" "INFO" "MAIN"
    
    # Show status and exit if requested
    if ($Status) {
        Write-Log "Displaying system status..." "INFO" "MAIN"
        Show-SystemStatus
        return
    }
    
    # Clean logs if requested
    if ($Clean) {
        Write-Log "Performing cleanup operations..." "INFO" "MAIN"
        try {
            $oldLogs = Get-ChildItem -Path "logs" -Filter "*.log" -ErrorAction SilentlyContinue | Where-Object {$_.LastWriteTime -lt (Get-Date).AddDays(-7)}
            if ($oldLogs) {
                $oldLogs | Remove-Item -Force
                Write-Log "Cleaned $($oldLogs.Count) old log files" "INFO" "MAIN"
            }
            
            $startupLogs = Get-ChildItem -Path "." -Filter "*startup*.log" -ErrorAction SilentlyContinue
            if ($startupLogs) {
                $startupLogs | Remove-Item -Force
                Write-Log "Cleaned $($startupLogs.Count) startup log files" "INFO" "MAIN"
            }
            
            $frontendLogs = Get-ChildItem -Path "frontend" -Filter "*startup*.log" -ErrorAction SilentlyContinue
            if ($frontendLogs) {
                $frontendLogs | Remove-Item -Force
                Write-Log "Cleaned $($frontendLogs.Count) frontend log files" "INFO" "MAIN"
            }
        }
        catch {
            Write-Log "Could not clean all logs: $($_.Exception.Message)" "WARN" "MAIN"
        }
    }
    
    # Install dependencies
    Write-Log "Validating system dependencies..." "INFO" "MAIN"
    if (-not (Install-Dependencies)) {
        Write-Log "Dependency validation failed - cannot proceed with startup" "ERROR" "MAIN"
        exit 1
    }
    
    # Execute based on mode
    Write-Log "Starting services in mode: $Mode" "INFO" "MAIN"
    $success = $true
    $startupStartTime = Get-Date
    
    switch ($Mode) {
        'backend' {
            Write-Log "Starting backend services only..." "INFO" "MAIN"
            $success = Start-BackendServices
        }
        'frontend' {
            Write-Log "Starting frontend only..." "INFO" "MAIN"
            $success = Start-Frontend
        }
        'api' {
            Write-Log "Starting API server only..." "INFO" "MAIN"
            # Force host uvicorn to use 8081 unconditionally in api mode to avoid collisions with containers or other processes on 8080
            try {
                $env:GRAFRAG_HOST_API_PORT = "8081"
                Write-Log ("Forcing host uvicorn port to {0} in api mode" -f $env:GRAFRAG_HOST_API_PORT) "WARN" "MAIN"
            } catch {}
            $success = Start-ApiServer
        }
        'api-debug' {
            Write-Log "Starting API server in FOREGROUND DEBUG mode..." "WARN" "MAIN"
            try {
                if (-not (Test-Path "src\main.py")) {
                    Write-Log "No API server found (src\main.py missing)" "ERROR" "API"
                    $success = $false
                } else {
                    if (-not $env:GRAFRAG_HOST_API_PORT) { $env:GRAFRAG_HOST_API_PORT = "8081" }
                    $hostPort = [int]$env:GRAFRAG_HOST_API_PORT
                    try {
                        $cwd = (Get-Location).Path
                        $env:PYTHONPATH = $cwd
                        Write-Log ("PYTHONPATH set to: {0}" -f $env:PYTHONPATH) "INFO" "API"
                    } catch {}
                    $cmd = "python -m uvicorn src.main:app --host 0.0.0.0 --port $hostPort --reload --log-level $($LogLevel.ToLower())"
                    Write-Log ("Foreground DEBUG command: {0}" -f $cmd) "WARN" "API"
                    Write-Log "Streaming uvicorn output below. Press Ctrl+C to stop." "WARN" "API"
                    python -m uvicorn src.main:app --host 0.0.0.0 --port $hostPort --reload --log-level $($LogLevel.ToLower())
                    $success = ($LASTEXITCODE -eq 0)
                }
            } catch {
                Write-Log ("Foreground uvicorn failed: {0}" -f $_.Exception.Message) "ERROR" "API"
                $success = $false
            }
        }
        'api-debug' {
            Write-Log "Starting API server in FOREGROUND DEBUG mode..." "WARN" "MAIN"
            try {
                if (-not (Test-Path "src\main.py")) {
                    Write-Log "No API server found (src\main.py missing)" "ERROR" "API"
                    $success = $false
                } else {
                    if (-not $env:GRAFRAG_HOST_API_PORT) { $env:GRAFRAG_HOST_API_PORT = "8081" }
                    $hostPort = [int]$env:GRAFRAG_HOST_API_PORT
                    try {
                        $cwd = (Get-Location).Path
                        $env:PYTHONPATH = $cwd
                        Write-Log ("PYTHONPATH set to: {0}" -f $env:PYTHONPATH) "INFO" "API"
                    } catch {}
                    $cmd = "python -m uvicorn src.main:app --host 0.0.0.0 --port $hostPort --reload --log-level $($LogLevel.ToLower())"
                    Write-Log ("Foreground DEBUG command: {0}" -f $cmd) "WARN" "API"
                    Write-Log "Streaming uvicorn output below. Press Ctrl+C to stop." "WARN" "API"
                    python -m uvicorn src.main:app --host 0.0.0.0 --port $hostPort --reload --log-level $($LogLevel.ToLower())
                    $success = ($LASTEXITCODE -eq 0)
                }
            } catch {
                Write-Log ("Foreground uvicorn failed: {0}" -f $_.Exception.Message) "ERROR" "API"
                $success = $false
            }
        }
        'mvp' {
            Write-Log "Starting MVP mode..." "INFO" "MAIN"
            $success = Start-MvpMode
        }
        'full' {
            Write-Log "Starting full system with comprehensive validation..." "INFO" "MAIN"
            
            # Enforce clean restart of everything (scoped stops only; do not kill unrelated tools)
            Write-Log "Stopping existing services for clean restart..." "INFO" "MAIN"
            Stop-FrontendIfRunning
            Stop-ApiIfRunning
            Stop-ComposeStack -ComposeFiles @("podman-compose.dev.yml")
            
            # Start services in dependency order
            Write-Log "Starting services in dependency order..." "INFO" "MAIN"
            $success = Start-BackendServices
            if ($success) {
                Write-Log "Backend services started, proceeding to API server..." "INFO" "MAIN"
                # Force 8081 for host uvicorn to avoid 8080 collision with containers; frontend will proxy or use REACT_APP_API_URL
                try {
                    $env:GRAFRAG_HOST_API_PORT = "8081"
                    Write-Log "Using host API port 8081 for full mode" "INFO" "MAIN"
                } catch {}
                $success = Start-ApiServer
            }
            if ($success) {
                Write-Log "API server started, proceeding to frontend..." "INFO" "MAIN"
                # Ensure frontend can reach API on the chosen port:
                #  - If package.json proxy is present, relative paths will proxy to :8080 by default; override via env
                try {
                    $env:REACT_APP_API_URL = ("http://localhost:{0}" -f $env:GRAFRAG_HOST_API_PORT)
                    if (-not $env:REACT_APP_API_URL) { $env:REACT_APP_API_URL = "http://localhost:8081" }
                    Write-Log ("REACT_APP_API_URL set to {0}" -f $env:REACT_APP_API_URL) "INFO" "MAIN"
                } catch {}
                $success = Start-Frontend
            }
        }
    }
    
    $startupElapsed = ((Get-Date) - $startupStartTime).TotalSeconds
    Write-Log "Service startup phase completed in ${startupElapsed}s" "INFO" "MAIN"
    
    # Comprehensive system validation
    if ($success) {
        Write-Log "Performing comprehensive system validation..." "INFO" "MAIN"
        $validationResult = Invoke-ComprehensiveSystemValidation -TimeoutSeconds 120
        
        if (-not $validationResult.Success) {
            Write-Log "System validation failed - some services may not be functioning correctly" "ERROR" "MAIN"
            Write-Log "Validation summary: $($validationResult.Summary)" "ERROR" "MAIN"
            
            # Don't fail the startup completely, but warn the user
            Write-Log "System started with validation warnings - check the logs above for details" "WARN" "MAIN"
            Write-Log "You may need to restart failed services or check their configuration" "WARN" "MAIN"
        }
        else {
            Write-Log "System validation passed successfully" "INFO" "MAIN"
            Write-Log "Validation summary: $($validationResult.Summary)" "INFO" "MAIN"
        }
    }

    # Show results
    if ($success) {
        $totalElapsed = (Get-Date) - $StartTime
        Write-Log "=== STARTUP COMPLETED SUCCESSFULLY ===" "INFO" "MAIN"
        Write-Log "Total startup time: $([math]::Round($totalElapsed.TotalSeconds, 1))s" "INFO" "MAIN"
        Write-Log "Service startup: $([math]::Round($startupElapsed, 1))s" "INFO" "MAIN"
        if ($validationResult) {
            Write-Log "System validation: $([math]::Round($validationResult.ValidationTime, 1))s" "INFO" "MAIN"
        }
        Write-Log "" "INFO" "MAIN"
        Show-SystemStatus
        Write-Log "" "INFO" "MAIN"
        Write-Log "Your GraphRAG system is ready for use!" "INFO" "MAIN"
        Write-Log "View real-time logs: Get-Content $LogFile -Wait" "INFO" "MAIN"
        Write-Log "Check status anytime: .\START.ps1 -Status" "INFO" "MAIN"
    }
    else {
        Write-Log "=== STARTUP FAILED ===" "ERROR" "MAIN"
        Write-Log "GraphRAG startup failed after $([math]::Round(((Get-Date) - $StartTime).TotalSeconds, 1))s" "ERROR" "MAIN"
        Write-Log "Check the detailed logs above for specific error information" "ERROR" "MAIN"
        Write-Log "Common solutions:" "INFO" "MAIN"
        Write-Log "  1. Try a clean restart: .\START.ps1 -Clean" "INFO" "MAIN"
        Write-Log "  2. Check system status: .\START.ps1 -Status" "INFO" "MAIN"
        Write-Log "  3. Review logs: Get-Content $LogFile" "INFO" "MAIN"
        exit 1
    }
}

# Run main function
Main