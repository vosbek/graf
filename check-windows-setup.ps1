#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Windows Setup Validation Script for GraphRAG
    
.DESCRIPTION
    Validates that a fresh Windows machine has all required dependencies
    for running GraphRAG. Provides detailed diagnostics and installation guidance.
    
.PARAMETER Fix
    Attempt to automatically fix common issues
    
.PARAMETER Detailed
    Show detailed information about each component
    
.EXAMPLE
    .\check-windows-setup.ps1              # Basic validation
    .\check-windows-setup.ps1 -Detailed    # Detailed validation  
    .\check-windows-setup.ps1 -Fix         # Auto-fix issues
#>

param(
    [switch]$Fix,
    [switch]$Detailed
)

$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"

# Colors for output
$Red = "Red"
$Green = "Green"
$Yellow = "Yellow"  
$Cyan = "Cyan"
$White = "White"

function Write-Status {
    param(
        [string]$Message,
        [string]$Status = "INFO",
        [string]$Color = $White
    )
    
    $timestamp = Get-Date -Format "HH:mm:ss"
    $statusIcon = switch ($Status) {
        "PASS" { "✅" }
        "FAIL" { "❌" }
        "WARN" { "⚠️" }
        "INFO" { "ℹ️" }
        "FIX"  { "🔧" }
        default { "•" }
    }
    
    Write-Host "[$timestamp] $statusIcon $Message" -ForegroundColor $Color
}

function Test-CommandExists {
    param([string]$Command)
    
    try {
        $null = Get-Command $Command -ErrorAction Stop
        return $true
    }
    catch {
        return $false
    }
}

function Test-WindowsVersion {
    Write-Status "Checking Windows version..." "INFO" $Cyan
    
    $os = Get-CimInstance Win32_OperatingSystem
    $version = [System.Version]$os.Version
    $buildNumber = $os.BuildNumber
    $productName = $os.Caption
    
    if ($Detailed) {
        Write-Status "OS: $productName" "INFO" $White
        Write-Status "Version: $($version.ToString())" "INFO" $White  
        Write-Status "Build: $buildNumber" "INFO" $White
    }
    
    # Check for Windows 10/11
    if ($version.Major -eq 10) {
        if ($buildNumber -ge 22000) {
            Write-Status "Windows 11 detected - Excellent!" "PASS" $Green
        } elseif ($buildNumber -ge 19041) {
            Write-Status "Windows 10 (recent build) - Good!" "PASS" $Green
        } else {
            Write-Status "Windows 10 (older build) - May have compatibility issues" "WARN" $Yellow
        }
        return $true
    } else {
        Write-Status "Unsupported Windows version - Requires Windows 10/11" "FAIL" $Red
        return $false
    }
}

function Test-PowerShellVersion {
    Write-Status "Checking PowerShell version..." "INFO" $Cyan
    
    $psVersion = $PSVersionTable.PSVersion
    if ($Detailed) {
        Write-Status "PowerShell Version: $($psVersion.ToString())" "INFO" $White
        Write-Status "Edition: $($PSVersionTable.PSEdition)" "INFO" $White
    }
    
    if ($psVersion.Major -ge 5) {
        Write-Status "PowerShell $($psVersion.ToString()) - Compatible!" "PASS" $Green
        return $true
    } else {
        Write-Status "PowerShell $($psVersion.ToString()) - Too old, need 5.1+" "FAIL" $Red
        return $false
    }
}

function Test-ContainerRuntime {
    Write-Status "Checking container runtime..." "INFO" $Cyan
    
    $hasPodman = Test-CommandExists "podman"
    $hasDocker = Test-CommandExists "docker"
    $hasPodmanCompose = Test-CommandExists "podman-compose"
    $hasDockerCompose = Test-CommandExists "docker-compose"
    
    if ($hasPodman) {
        try {
            $podmanVersion = podman --version 2>$null
            Write-Status "Podman found: $podmanVersion" "PASS" $Green
            
            if ($hasPodmanCompose) {
                $composeVersion = podman-compose --version 2>$null
                Write-Status "podman-compose found: $composeVersion" "PASS" $Green
            } else {
                Write-Status "podman-compose not found - will be installed via pip" "WARN" $Yellow
                if ($Fix) {
                    Write-Status "Installing podman-compose..." "FIX" $Cyan
                    try {
                        pip install podman-compose
                        Write-Status "podman-compose installed successfully!" "PASS" $Green
                    } catch {
                        Write-Status "Failed to install podman-compose: $($_.Exception.Message)" "FAIL" $Red
                    }
                }
            }
            return $true
        } catch {
            Write-Status "Podman found but not working: $($_.Exception.Message)" "FAIL" $Red
        }
    } elseif ($hasDocker) {
        try {
            $dockerVersion = docker --version 2>$null
            Write-Status "Docker found: $dockerVersion" "PASS" $Green
            
            if ($hasDockerCompose) {
                $composeVersion = docker-compose --version 2>$null
                Write-Status "docker-compose found: $composeVersion" "PASS" $Green
            } else {
                Write-Status "docker-compose not found - may cause issues" "WARN" $Yellow
            }
            Write-Status "Note: Scripts use podman commands, you may need to adjust" "WARN" $Yellow
            return $true
        } catch {
            Write-Status "Docker found but not working: $($_.Exception.Message)" "FAIL" $Red
        }
    }
    
    Write-Status "No container runtime found - install Podman Desktop or Docker Desktop" "FAIL" $Red
    if ($Fix) {
        Write-Status "Auto-fix not available for container runtime - manual installation required" "WARN" $Yellow
        Write-Status "Install from: https://podman-desktop.io/ or https://www.docker.com/products/docker-desktop/" "INFO" $White
    }
    return $false
}

function Test-Python {
    Write-Status "Checking Python installation..." "INFO" $Cyan
    
    $pythonCommands = @("python", "py", "python3")
    $pythonFound = $false
    
    foreach ($cmd in $pythonCommands) {
        if (Test-CommandExists $cmd) {
            try {
                $pythonVersion = & $cmd --version 2>$null
                $versionNumber = ($pythonVersion -split " ")[1]
                $version = [Version]$versionNumber
                
                if ($Detailed) {
                    Write-Status "Found: $cmd -> $pythonVersion" "INFO" $White
                }
                
                if ($version.Major -eq 3 -and $version.Minor -ge 8) {
                    Write-Status "Python $versionNumber found - Compatible!" "PASS" $Green
                    $pythonFound = $true
                    
                    # Check pip
                    try {
                        $pipVersion = pip --version 2>$null
                        Write-Status "pip found: $($pipVersion.Split(' ')[1])" "PASS" $Green
                    } catch {
                        Write-Status "pip not found - may cause package installation issues" "WARN" $Yellow
                    }
                    break
                } else {
                    Write-Status "Python $versionNumber - Too old, need 3.8+" "WARN" $Yellow
                }
            } catch {
                if ($Detailed) {
                    Write-Status "Command '$cmd' failed: $($_.Exception.Message)" "INFO" $White
                }
            }
        }
    }
    
    if (-not $pythonFound) {
        Write-Status "No compatible Python found - install Python 3.8+" "FAIL" $Red
        if ($Fix) {
            Write-Status "Attempting to install Python 3.11..." "FIX" $Cyan
            try {
                winget install Python.Python.3.11 --accept-source-agreements --accept-package-agreements
                Write-Status "Python 3.11 installation initiated - restart PowerShell to use" "PASS" $Green
            } catch {
                Write-Status "Failed to install Python: $($_.Exception.Message)" "FAIL" $Red
            }
        }
        return $false
    }
    
    return $true
}

function Test-NodeJS {
    Write-Status "Checking Node.js installation..." "INFO" $Cyan
    
    $hasNode = Test-CommandExists "node"
    $hasNpm = Test-CommandExists "npm"
    
    if ($hasNode) {
        try {
            $nodeVersion = node --version 2>$null
            $versionNumber = $nodeVersion -replace "v", ""
            $version = [Version]$versionNumber
            
            if ($Detailed) {
                Write-Status "Node.js version: $nodeVersion" "INFO" $White
            }
            
            if ($version.Major -ge 16) {
                Write-Status "Node.js $nodeVersion - Compatible!" "PASS" $Green
                
                if ($hasNpm) {
                    $npmVersion = npm --version 2>$null
                    Write-Status "npm found: v$npmVersion" "PASS" $Green
                } else {
                    Write-Status "npm not found - frontend will not work" "FAIL" $Red
                    return $false
                }
                return $true
            } else {
                Write-Status "Node.js $nodeVersion - Too old, need 16+" "WARN" $Yellow
            }
        } catch {
            Write-Status "Node.js found but not working: $($_.Exception.Message)" "FAIL" $Red
        }
    }
    
    Write-Status "No compatible Node.js found - install Node.js 16+" "FAIL" $Red
    if ($Fix) {
        Write-Status "Attempting to install Node.js LTS..." "FIX" $Cyan
        try {
            winget install OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements
            Write-Status "Node.js LTS installation initiated - restart PowerShell to use" "PASS" $Green
        } catch {
            Write-Status "Failed to install Node.js: $($_.Exception.Message)" "FAIL" $Red
        }
    }
    return $false
}

function Test-Git {
    Write-Status "Checking Git installation..." "INFO" $Cyan
    
    if (Test-CommandExists "git") {
        try {
            $gitVersion = git --version 2>$null
            Write-Status "Git found: $gitVersion" "PASS" $Green
            return $true
        } catch {
            Write-Status "Git found but not working: $($_.Exception.Message)" "FAIL" $Red
        }
    }
    
    Write-Status "Git not found - needed for repository operations" "FAIL" $Red
    if ($Fix) {
        Write-Status "Attempting to install Git..." "FIX" $Cyan
        try {
            winget install Git.Git --accept-source-agreements --accept-package-agreements
            Write-Status "Git installation initiated - restart PowerShell to use" "PASS" $Green
        } catch {
            Write-Status "Failed to install Git: $($_.Exception.Message)" "FAIL" $Red
        }
    }
    return $false
}

function Test-SystemResources {
    Write-Status "Checking system resources..." "INFO" $Cyan
    
    $memory = Get-CimInstance Win32_ComputerSystem
    $totalMemoryGB = [math]::Round($memory.TotalPhysicalMemory / 1GB, 1)
    
    $disk = Get-CimInstance Win32_LogicalDisk | Where-Object DeviceID -eq "C:"
    $freeSpaceGB = [math]::Round($disk.FreeSpace / 1GB, 1)
    
    if ($Detailed) {
        Write-Status "Total RAM: ${totalMemoryGB}GB" "INFO" $White
        Write-Status "Free disk space (C:): ${freeSpaceGB}GB" "INFO" $White
    }
    
    $resourcesOk = $true
    
    if ($totalMemoryGB -ge 16) {
        Write-Status "RAM: ${totalMemoryGB}GB - Excellent!" "PASS" $Green
    } elseif ($totalMemoryGB -ge 8) {
        Write-Status "RAM: ${totalMemoryGB}GB - Adequate (16GB+ recommended)" "WARN" $Yellow
    } else {
        Write-Status "RAM: ${totalMemoryGB}GB - Insufficient (8GB minimum)" "FAIL" $Red
        $resourcesOk = $false
    }
    
    if ($freeSpaceGB -ge 50) {
        Write-Status "Disk space: ${freeSpaceGB}GB free - Excellent!" "PASS" $Green
    } elseif ($freeSpaceGB -ge 20) {
        Write-Status "Disk space: ${freeSpaceGB}GB free - Adequate" "WARN" $Yellow
    } else {
        Write-Status "Disk space: ${freeSpaceGB}GB free - Insufficient (20GB minimum)" "FAIL" $Red
        $resourcesOk = $false
    }
    
    return $resourcesOk
}

function Test-NetworkPorts {
    Write-Status "Checking network port availability..." "INFO" $Cyan
    
    $requiredPorts = @(3000, 8080, 8081, 8000, 7474, 7687, 6379, 5432)
    $portsOk = $true
    
    foreach ($port in $requiredPorts) {
        try {
            $listener = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Where-Object State -eq "Listen"
            if ($listener) {
                Write-Status "Port $port is in use - may cause conflicts" "WARN" $Yellow
                if ($Detailed) {
                    $process = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
                    if ($process) {
                        Write-Status "  Used by: $($process.ProcessName) (PID: $($process.Id))" "INFO" $White
                    }
                }
            } else {
                if ($Detailed) {
                    Write-Status "Port $port is available" "PASS" $Green
                }
            }
        } catch {
            # Port check failed, assume available
            if ($Detailed) {
                Write-Status "Port $port check failed (assuming available)" "INFO" $White
            }
        }
    }
    
    return $portsOk
}

function Test-PythonPackages {
    Write-Status "Checking Python package prerequisites..." "INFO" $Cyan
    
    # Test if pip can install packages
    try {
        $pipList = pip list --format=json 2>$null | ConvertFrom-Json
        Write-Status "pip is working - found $($pipList.Count) packages" "INFO" $White
    } catch {
        Write-Status "pip not working correctly" "FAIL" $Red
        return $false
    }
    
    # Check for C++ build tools (needed for some packages)
    $vcTools = Get-ChildItem "HKLM:\SOFTWARE\Microsoft\VisualStudio\*\VC\*" -ErrorAction SilentlyContinue
    if ($vcTools) {
        Write-Status "Visual C++ build tools detected" "PASS" $Green
    } else {
        Write-Status "Visual C++ build tools not found - some packages may fail to install" "WARN" $Yellow
        Write-Status "Install from: https://visualstudio.microsoft.com/visual-cpp-build-tools/" "INFO" $White
    }
    
    return $true
}

function Test-ProjectFiles {
    Write-Status "Checking project structure..." "INFO" $Cyan
    
    $requiredFiles = @(
        "START.ps1",
        "requirements.txt", 
        "podman-compose.dev.yml",
        "frontend\package.json",
        "src\main.py"
    )
    
    $filesOk = $true
    
    foreach ($file in $requiredFiles) {
        if (Test-Path $file) {
            if ($Detailed) {
                Write-Status "Found: $file" "PASS" $Green
            }
        } else {
            Write-Status "Missing: $file" "FAIL" $Red
            $filesOk = $false
        }
    }
    
    if ($filesOk) {
        Write-Status "All required project files present" "PASS" $Green
    } else {
        Write-Status "Some project files are missing - check repository" "FAIL" $Red
    }
    
    return $filesOk
}

# Main validation function
function Start-Validation {
    Write-Status "GraphRAG Windows Setup Validation" "INFO" $Cyan
    Write-Status "======================================" "INFO" $White
    
    $results = @{}
    
    # Run all tests
    $results["Windows"] = Test-WindowsVersion
    $results["PowerShell"] = Test-PowerShellVersion  
    $results["Container"] = Test-ContainerRuntime
    $results["Python"] = Test-Python
    $results["NodeJS"] = Test-NodeJS
    $results["Git"] = Test-Git
    $results["Resources"] = Test-SystemResources
    $results["Ports"] = Test-NetworkPorts
    $results["PythonPackages"] = Test-PythonPackages
    $results["ProjectFiles"] = Test-ProjectFiles
    
    # Summary
    Write-Status "" "INFO" $White
    Write-Status "======================================" "INFO" $White
    Write-Status "VALIDATION SUMMARY" "INFO" $Cyan
    Write-Status "======================================" "INFO" $White
    
    $passed = 0
    $failed = 0
    
    foreach ($test in $results.Keys) {
        if ($results[$test]) {
            Write-Status "$test - PASSED" "PASS" $Green
            $passed++
        } else {
            Write-Status "$test - FAILED" "FAIL" $Red
            $failed++
        }
    }
    
    Write-Status "" "INFO" $White
    Write-Status "Results: $passed passed, $failed failed" "INFO" $White
    
    if ($failed -eq 0) {
        Write-Status "🎉 All validation checks passed!" "PASS" $Green
        Write-Status "Your Windows machine is ready for GraphRAG!" "INFO" $Cyan
        Write-Status "Next steps:" "INFO" $White
        Write-Status "  1. Configure .env file with your repository paths" "INFO" $White
        Write-Status "  2. Run: pip install -r requirements.txt" "INFO" $White
        Write-Status "  3. Run: .\START.ps1" "INFO" $White
    } elseif ($failed -le 2) {
        Write-Status "⚠️ Minor issues detected" "WARN" $Yellow
        Write-Status "You may be able to proceed, but fix issues for best experience" "INFO" $White
        if (-not $Fix) {
            Write-Status "Run with -Fix flag to attempt automatic fixes" "INFO" $White
        }
    } else {
        Write-Status "❌ Multiple issues detected" "FAIL" $Red
        Write-Status "Please fix the failed checks before proceeding" "INFO" $White
        if (-not $Fix) {
            Write-Status "Run with -Fix flag to attempt automatic fixes" "INFO" $White
        }
    }
    
    Write-Status "" "INFO" $White
    Write-Status "For detailed installation guide, see: WINDOWS-FRESH-INSTALL.md" "INFO" $Cyan
}

# Run the validation
Start-Validation