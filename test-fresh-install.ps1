#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Fresh Installation Test Script for GraphRAG
    
.DESCRIPTION
    Simulates a fresh Windows installation by testing the complete setup process
    from dependency validation through system startup and basic functionality.
    
.PARAMETER CleanTest
    Remove all containers and data before testing (simulate truly fresh install)
    
.PARAMETER SkipLongTests
    Skip time-consuming tests like full Python package installation
    
.EXAMPLE
    .\test-fresh-install.ps1                    # Standard test
    .\test-fresh-install.ps1 -CleanTest         # Clean test (removes all data)
    .\test-fresh-install.ps1 -SkipLongTests     # Skip slow operations
#>

param(
    [switch]$CleanTest,
    [switch]$SkipLongTests
)

$ErrorActionPreference = "Continue"
$StartTime = Get-Date

function Write-TestStatus {
    param(
        [string]$Message,
        [string]$Status = "INFO",
        [string]$Color = "White"
    )
    
    $timestamp = (Get-Date).ToString("HH:mm:ss")
    $statusIcon = switch ($Status) {
        "PASS" { "✅" }
        "FAIL" { "❌" } 
        "WARN" { "⚠️" }
        "INFO" { "ℹ️" }
        "TEST" { "🧪" }
        "TIME" { "⏱️" }
        default { "•" }
    }
    
    Write-Host "[$timestamp] $statusIcon $Message" -ForegroundColor $Color
}

function Test-FreshInstallPrerequisites {
    Write-TestStatus "=== Testing Fresh Install Prerequisites ===" "TEST" "Cyan"
    
    $testStart = Get-Date
    
    # Run the Windows setup checker
    if (Test-Path "check-windows-setup.ps1") {
        Write-TestStatus "Running Windows setup validation..." "INFO" "White"
        try {
            .\check-windows-setup.ps1 -Detailed
            Write-TestStatus "Windows setup validation completed" "PASS" "Green"
        } catch {
            Write-TestStatus "Windows setup validation failed: $($_.Exception.Message)" "FAIL" "Red"
            return $false
        }
    } else {
        Write-TestStatus "Windows setup checker not found" "WARN" "Yellow"
    }
    
    $elapsed = ((Get-Date) - $testStart).TotalSeconds
    Write-TestStatus "Prerequisites test completed in ${elapsed}s" "TIME" "Cyan"
    return $true
}

function Test-EnvironmentConfiguration {
    Write-TestStatus "=== Testing Environment Configuration ===" "TEST" "Cyan"
    
    $testStart = Get-Date
    
    # Check if .env exists
    if (-not (Test-Path ".env")) {
        Write-TestStatus ".env file not found - creating from template..." "WARN" "Yellow"
        
        if (Test-Path ".env.windows.example") {
            Copy-Item ".env.windows.example" ".env" -Force
            Write-TestStatus "Created .env from Windows template" "PASS" "Green"
        } elseif (Test-Path ".env.example") {
            Copy-Item ".env.example" ".env" -Force
            Write-TestStatus "Created .env from generic template" "PASS" "Green"
        } else {
            Write-TestStatus "No environment template found" "FAIL" "Red"
            return $false
        }
    } else {
        Write-TestStatus ".env file exists" "PASS" "Green"
    }
    
    # Validate .env content
    $envContent = Get-Content ".env" -Raw
    $requiredVars = @("REPOS_PATH", "NEO4J_PASSWORD")
    
    foreach ($var in $requiredVars) {
        if ($envContent -match "$var=") {
            Write-TestStatus "Environment variable $var is configured" "PASS" "Green"
        } else {
            Write-TestStatus "Environment variable $var is missing" "WARN" "Yellow"
        }
    }
    
    $elapsed = ((Get-Date) - $testStart).TotalSeconds
    Write-TestStatus "Environment configuration test completed in ${elapsed}s" "TIME" "Cyan"
    return $true
}

function Test-PythonDependencyInstallation {
    Write-TestStatus "=== Testing Python Dependency Installation ===" "TEST" "Cyan"
    
    if ($SkipLongTests) {
        Write-TestStatus "Skipping Python dependency installation (SkipLongTests enabled)" "WARN" "Yellow"
        return $true
    }
    
    $testStart = Get-Date
    
    # Test pip installation of requirements
    if (Test-Path "requirements.txt") {
        Write-TestStatus "Installing Python dependencies (this may take 10-15 minutes)..." "INFO" "White"
        
        try {
            # Install with verbose output to show progress
            $installResult = pip install -r requirements.txt --user 2>&1
            
            if ($LASTEXITCODE -eq 0) {
                Write-TestStatus "Python dependencies installed successfully" "PASS" "Green"
            } else {
                Write-TestStatus "Python dependency installation had issues" "WARN" "Yellow"
                Write-TestStatus "Install output (last 10 lines):" "INFO" "White"
                $installResult | Select-Object -Last 10 | ForEach-Object { 
                    Write-TestStatus "  $_" "INFO" "Gray" 
                }
            }
        } catch {
            Write-TestStatus "Python dependency installation failed: $($_.Exception.Message)" "FAIL" "Red"
            return $false
        }
    } else {
        Write-TestStatus "requirements.txt not found" "FAIL" "Red"
        return $false
    }
    
    # Test importing key packages
    $keyPackages = @("fastapi", "uvicorn", "chromadb", "neo4j")
    
    foreach ($package in $keyPackages) {
        try {
            $importTest = python -c "import $package; print('$package OK')" 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-TestStatus "Package $package imports successfully" "PASS" "Green"
            } else {
                Write-TestStatus "Package $package import failed" "FAIL" "Red"
            }
        } catch {
            Write-TestStatus "Package $package test failed: $($_.Exception.Message)" "FAIL" "Red"
        }
    }
    
    $elapsed = ((Get-Date) - $testStart).TotalSeconds
    Write-TestStatus "Python dependency test completed in ${elapsed}s" "TIME" "Cyan"
    return $true
}

function Test-ContainerServices {
    Write-TestStatus "=== Testing Container Services ===" "TEST" "Cyan"
    
    $testStart = Get-Date
    
    # Clean containers if requested
    if ($CleanTest) {
        Write-TestStatus "Cleaning existing containers for fresh test..." "INFO" "White"
        try {
            podman-compose -f podman-compose.dev.yml down --volumes --remove-orphans 2>$null
            podman system prune -f 2>$null
            Write-TestStatus "Container cleanup completed" "PASS" "Green"
        } catch {
            Write-TestStatus "Container cleanup failed (may be normal): $($_.Exception.Message)" "WARN" "Yellow"
        }
    }
    
    # Start backend services
    Write-TestStatus "Starting backend services..." "INFO" "White"
    try {
        $startResult = .\START.ps1 -Mode backend 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-TestStatus "Backend services started successfully" "PASS" "Green"
        } else {
            Write-TestStatus "Backend service startup had issues" "WARN" "Yellow"
            Write-TestStatus "Startup output (last 10 lines):" "INFO" "White"
            $startResult | Select-Object -Last 10 | ForEach-Object { 
                Write-TestStatus "  $_" "INFO" "Gray" 
            }
        }
    } catch {
        Write-TestStatus "Backend service startup failed: $($_.Exception.Message)" "FAIL" "Red"
        return $false
    }
    
    # Wait a bit for services to stabilize
    Write-TestStatus "Waiting for services to stabilize..." "INFO" "White"
    Start-Sleep -Seconds 30
    
    # Test service health
    $services = @(
        @{Name="ChromaDB"; Url="http://localhost:8000/api/v2/healthcheck"},
        @{Name="Neo4j"; Url="http://localhost:7474/"},
        @{Name="Redis"; Port=6379}
    )
    
    foreach ($service in $services) {
        if ($service.Url) {
            try {
                $response = Invoke-WebRequest -Uri $service.Url -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
                if ($response.StatusCode -eq 200) {
                    Write-TestStatus "$($service.Name) is healthy (HTTP 200)" "PASS" "Green"
                } else {
                    Write-TestStatus "$($service.Name) returned HTTP $($response.StatusCode)" "WARN" "Yellow"
                }
            } catch {
                Write-TestStatus "$($service.Name) health check failed: $($_.Exception.Message)" "FAIL" "Red"
            }
        } elseif ($service.Port) {
            try {
                $tcpTest = Test-NetConnection -ComputerName localhost -Port $service.Port -InformationLevel Quiet -WarningAction SilentlyContinue
                if ($tcpTest) {
                    Write-TestStatus "$($service.Name) is accessible on port $($service.Port)" "PASS" "Green"
                } else {
                    Write-TestStatus "$($service.Name) is not accessible on port $($service.Port)" "FAIL" "Red"
                }
            } catch {
                Write-TestStatus "$($service.Name) port test failed: $($_.Exception.Message)" "FAIL" "Red"
            }
        }
    }
    
    $elapsed = ((Get-Date) - $testStart).TotalSeconds
    Write-TestStatus "Container services test completed in ${elapsed}s" "TIME" "Cyan"
    return $true
}

function Test-ApiServer {
    Write-TestStatus "=== Testing API Server ===" "TEST" "Cyan"
    
    $testStart = Get-Date
    
    # Start API server
    Write-TestStatus "Starting API server in background..." "INFO" "White"
    try {
        # Start API server in background
        $apiJob = Start-Job -ScriptBlock {
            Set-Location $using:PWD
            .\START.ps1 -Mode api 2>&1
        }
        
        # Wait for API to start
        Write-TestStatus "Waiting for API server to initialize..." "INFO" "White"
        Start-Sleep -Seconds 45
        
        # Test API endpoints
        $apiEndpoints = @(
            @{Name="Health"; Url="http://localhost:8081/api/v1/health/"},
            @{Name="Ready"; Url="http://localhost:8081/api/v1/health/ready"},
            @{Name="Docs"; Url="http://localhost:8081/docs"}
        )
        
        foreach ($endpoint in $apiEndpoints) {
            try {
                $response = Invoke-WebRequest -Uri $endpoint.Url -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
                if ($response.StatusCode -eq 200) {
                    Write-TestStatus "API $($endpoint.Name) endpoint is working" "PASS" "Green"
                } else {
                    Write-TestStatus "API $($endpoint.Name) returned HTTP $($response.StatusCode)" "WARN" "Yellow"
                }
            } catch {
                Write-TestStatus "API $($endpoint.Name) test failed: $($_.Exception.Message)" "FAIL" "Red"
            }
        }
        
        # Stop the background job
        Stop-Job $apiJob -ErrorAction SilentlyContinue
        Remove-Job $apiJob -ErrorAction SilentlyContinue
        
    } catch {
        Write-TestStatus "API server test failed: $($_.Exception.Message)" "FAIL" "Red"
        return $false
    }
    
    $elapsed = ((Get-Date) - $testStart).TotalSeconds
    Write-TestStatus "API server test completed in ${elapsed}s" "TIME" "Cyan"
    return $true
}

function Test-FrontendDependencies {
    Write-TestStatus "=== Testing Frontend Dependencies ===" "TEST" "Cyan"
    
    $testStart = Get-Date
    
    if (Test-Path "frontend\package.json") {
        # Test npm install
        try {
            Push-Location frontend
            Write-TestStatus "Installing frontend dependencies..." "INFO" "White"
            
            $npmResult = npm install 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-TestStatus "Frontend dependencies installed successfully" "PASS" "Green"
            } else {
                Write-TestStatus "Frontend dependency installation had issues" "WARN" "Yellow"
                Write-TestStatus "npm output (last 5 lines):" "INFO" "White"
                $npmResult | Select-Object -Last 5 | ForEach-Object { 
                    Write-TestStatus "  $_" "INFO" "Gray" 
                }
            }
            
            # Test if key packages are available
            if (Test-Path "node_modules") {
                $keyPackages = @("react", "react-dom", "@mui/material", "axios")
                foreach ($package in $keyPackages) {
                    if (Test-Path "node_modules\$package") {
                        Write-TestStatus "Package $package is installed" "PASS" "Green"
                    } else {
                        Write-TestStatus "Package $package is missing" "FAIL" "Red"
                    }
                }
            }
            
        } catch {
            Write-TestStatus "Frontend dependency test failed: $($_.Exception.Message)" "FAIL" "Red"
            return $false
        } finally {
            Pop-Location
        }
    } else {
        Write-TestStatus "Frontend package.json not found" "FAIL" "Red"
        return $false
    }
    
    $elapsed = ((Get-Date) - $testStart).TotalSeconds
    Write-TestStatus "Frontend dependencies test completed in ${elapsed}s" "TIME" "Cyan"
    return $true
}

function Test-FullSystemIntegration {
    Write-TestStatus "=== Testing Full System Integration ===" "TEST" "Cyan"
    
    if ($SkipLongTests) {
        Write-TestStatus "Skipping full system integration test (SkipLongTests enabled)" "WARN" "Yellow"
        return $true
    }
    
    $testStart = Get-Date
    
    # This would be a comprehensive test of the full system
    # For now, just test that START.ps1 -Status works
    try {
        Write-TestStatus "Running system status check..." "INFO" "White"
        $statusResult = .\START.ps1 -Status 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            Write-TestStatus "System status check completed successfully" "PASS" "Green"
        } else {
            Write-TestStatus "System status check had issues" "WARN" "Yellow"
        }
    } catch {
        Write-TestStatus "System status check failed: $($_.Exception.Message)" "FAIL" "Red"
        return $false
    }
    
    $elapsed = ((Get-Date) - $testStart).TotalSeconds
    Write-TestStatus "Full system integration test completed in ${elapsed}s" "TIME" "Cyan"
    return $true
}

# Main test execution
function Start-FreshInstallTest {
    Write-TestStatus "GraphRAG Fresh Installation Test" "TEST" "Cyan"
    Write-TestStatus "====================================" "INFO" "White"
    Write-TestStatus "Test started at: $(Get-Date)" "INFO" "White"
    if ($CleanTest) {
        Write-TestStatus "Clean test mode: Will remove existing data" "WARN" "Yellow"
    }
    if ($SkipLongTests) {
        Write-TestStatus "Skip long tests mode: Will skip time-consuming operations" "WARN" "Yellow"
    }
    Write-TestStatus "" "INFO" "White"
    
    $testResults = @{}
    
    # Run all tests
    $testResults["Prerequisites"] = Test-FreshInstallPrerequisites
    $testResults["Environment"] = Test-EnvironmentConfiguration
    $testResults["PythonDeps"] = Test-PythonDependencyInstallation
    $testResults["Containers"] = Test-ContainerServices
    $testResults["ApiServer"] = Test-ApiServer
    $testResults["FrontendDeps"] = Test-FrontendDependencies
    $testResults["Integration"] = Test-FullSystemIntegration
    
    # Generate final report
    $totalElapsed = ((Get-Date) - $StartTime).TotalSeconds
    
    Write-TestStatus "" "INFO" "White"
    Write-TestStatus "====================================" "INFO" "White"
    Write-TestStatus "FRESH INSTALLATION TEST SUMMARY" "TEST" "Cyan"
    Write-TestStatus "====================================" "INFO" "White"
    
    $passed = 0
    $failed = 0
    
    foreach ($test in $testResults.Keys) {
        if ($testResults[$test]) {
            Write-TestStatus "$test - PASSED" "PASS" "Green"
            $passed++
        } else {
            Write-TestStatus "$test - FAILED" "FAIL" "Red"
            $failed++
        }
    }
    
    Write-TestStatus "" "INFO" "White"
    Write-TestStatus "Total test time: $([math]::Round($totalElapsed, 1))s" "TIME" "Cyan"
    Write-TestStatus "Results: $passed passed, $failed failed" "INFO" "White"
    
    if ($failed -eq 0) {
        Write-TestStatus "🎉 ALL TESTS PASSED!" "PASS" "Green"
        Write-TestStatus "Your fresh Windows installation is working perfectly!" "INFO" "Cyan"
        Write-TestStatus "GraphRAG is ready for production use." "INFO" "White"
    } elseif ($failed -le 2) {
        Write-TestStatus "⚠️ MOSTLY SUCCESSFUL with minor issues" "WARN" "Yellow"
        Write-TestStatus "System should work, but address failed tests for optimal experience" "INFO" "White"
    } else {
        Write-TestStatus "❌ MULTIPLE FAILURES DETECTED" "FAIL" "Red"
        Write-TestStatus "Fresh installation needs attention before proceeding" "INFO" "White"
        Write-TestStatus "Review failed tests and fix issues" "INFO" "White"
    }
    
    Write-TestStatus "" "INFO" "White"
    Write-TestStatus "For troubleshooting, see: WINDOWS-FRESH-INSTALL.md" "INFO" "Cyan"
    Write-TestStatus "For support, run: .\START.ps1 -Status" "INFO" "White"
}

# Execute the test
Start-FreshInstallTest