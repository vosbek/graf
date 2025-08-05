#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Oracle Database Integration Setup Helper

.DESCRIPTION
    Helps configure Oracle database integration for the GraphRAG system.
    This script assists with setting up environment variables and testing 
    Oracle connectivity for legacy system analysis.

.PARAMETER ConnectionString
    Oracle connection string (format: host:port/service_name)

.PARAMETER Username
    Oracle database username (read-only recommended)

.PARAMETER Password
    Oracle database password

.PARAMETER Schemas
    Comma-separated list of Oracle schemas to analyze

.PARAMETER TestConnection
    Test Oracle connection without enabling integration

.PARAMETER Enable
    Enable Oracle integration by updating .env file

.PARAMETER Disable
    Disable Oracle integration

.EXAMPLE
    .\setup-oracle.ps1 -TestConnection -ConnectionString "localhost:1521/XE" -Username "readonly_user" -Password "password"
    
.EXAMPLE
    .\setup-oracle.ps1 -Enable -ConnectionString "oracledb:1521/ORCL" -Username "app_reader" -Password "secret" -Schemas "INSURANCE,CONTRACTS"

.NOTES
    Oracle Database Integration for Legacy System Migration Analysis
    Enables answering "golden questions" about data sources and business rules
#>

param(
    [string]$ConnectionString,
    [string]$Username,
    [string]$Password,
    [string]$Schemas = "USER",
    [switch]$TestConnection,
    [switch]$Enable,
    [switch]$Disable,
    [switch]$Status
)

$ErrorActionPreference = "Stop"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    switch ($Level) {
        "ERROR" { Write-Host "[$timestamp] [ERROR] $Message" -ForegroundColor Red }
        "WARN"  { Write-Host "[$timestamp] [WARN]  $Message" -ForegroundColor Yellow }
        "INFO"  { Write-Host "[$timestamp] [INFO]  $Message" -ForegroundColor Green }
        default { Write-Host "[$timestamp] [INFO]  $Message" }
    }
}

function Test-OracleConnection {
    param(
        [string]$ConnString,
        [string]$User,
        [string]$Pass
    )
    
    Write-Log "Testing Oracle database connection..."
    Write-Log "Connection String: $ConnString"
    Write-Log "Username: $User"
    
    try {
        # Test using Python oracledb module
        $testScript = @"
import oracledb
import sys

try:
    # Parse connection string
    conn_parts = '$ConnString'.split('/')
    if ':' in conn_parts[0]:
        host_port = conn_parts[0].split(':')
        host = host_port[0]
        port = int(host_port[1])
    else:
        host = conn_parts[0]
        port = 1521
    
    service_name = conn_parts[1] if len(conn_parts) > 1 else 'XE'
    
    # Create connection
    dsn = oracledb.makedsn(host, port, service_name=service_name)
    connection = oracledb.connect(user='$User', password='$Pass', dsn=dsn)
    
    # Test query
    cursor = connection.cursor()
    cursor.execute("SELECT 1 FROM DUAL")
    result = cursor.fetchone()
    
    if result and result[0] == 1:
        print('CONNECTION_SUCCESS=True')
        
        # Get Oracle version
        cursor.execute("SELECT BANNER FROM V$VERSION WHERE ROWNUM = 1")
        version = cursor.fetchone()
        if version:
            print(f'ORACLE_VERSION={version[0]}')
        
        # Get accessible schemas
        cursor.execute("SELECT DISTINCT OWNER FROM ALL_TABLES WHERE ROWNUM <= 10 ORDER BY OWNER")
        schemas = cursor.fetchall()
        schema_list = [row[0] for row in schemas]
        print(f'AVAILABLE_SCHEMAS={",".join(schema_list[:5])}')
        
    cursor.close()
    connection.close()
    print('CONNECTION_TEST=PASSED')
    
except Exception as e:
    print(f'CONNECTION_ERROR={str(e)}')
    print('CONNECTION_TEST=FAILED')
    sys.exit(1)
"@

        $testResult = python -c $testScript 2>&1
        $exitCode = $LASTEXITCODE
        
        if ($exitCode -eq 0) {
            Write-Log "Oracle connection test PASSED" "INFO"
            
            # Parse results
            foreach ($line in $testResult) {
                if ($line -match "ORACLE_VERSION=(.+)") {
                    Write-Log "Oracle Version: $($matches[1])" "INFO"
                }
                elseif ($line -match "AVAILABLE_SCHEMAS=(.+)") {
                    Write-Log "Available Schemas: $($matches[1])" "INFO"
                }
            }
            return $true
        }
        else {
            Write-Log "Oracle connection test FAILED" "ERROR"
            Write-Log "Error details: $testResult" "ERROR"
            return $false
        }
    }
    catch {
        Write-Log "Oracle connection test failed: $($_.Exception.Message)" "ERROR"
        return $false
    }
}

function Update-EnvFile {
    param(
        [string]$ConnString,
        [string]$User,
        [string]$Pass,
        [string]$SchemaList,
        [bool]$EnableOracle
    )
    
    $envFile = ".env"
    
    if (-not (Test-Path $envFile)) {
        Write-Log "Creating new .env file..." "INFO"
        New-Item -Path $envFile -ItemType File -Force | Out-Null
    }
    
    # Read existing content
    $envContent = Get-Content $envFile -ErrorAction SilentlyContinue
    $newContent = @()
    $oracleSection = $false
    $addedOracleConfig = $false
    
    # Process existing lines
    foreach ($line in $envContent) {
        if ($line -match "^# Oracle Database Integration") {
            $oracleSection = $true
        }
        elseif ($line -match "^# " -and $oracleSection) {
            $oracleSection = $false
        }
        
        # Skip existing Oracle configuration lines
        if ($oracleSection -or $line -match "^ORACLE_") {
            continue
        }
        
        $newContent += $line
    }
    
    # Add Oracle configuration
    if ($EnableOracle) {
        $newContent += ""
        $newContent += "# Oracle Database Integration (Updated by setup-oracle.ps1)"
        $newContent += "ORACLE_ENABLED=true"
        $newContent += "ORACLE_CONNECTION_STRING=$ConnString"
        $newContent += "ORACLE_USERNAME=$User"
        $newContent += "ORACLE_PASSWORD=$Pass"
        $newContent += "ORACLE_SCHEMAS=$SchemaList"
        $newContent += "ORACLE_MAX_CONNECTIONS=5"
        $newContent += "ORACLE_SCHEMA_CACHE_TTL=3600"
        
        Write-Log "Oracle integration ENABLED in .env file" "INFO"
    }
    else {
        $newContent += ""
        $newContent += "# Oracle Database Integration (Disabled)"
        $newContent += "ORACLE_ENABLED=false"
        
        Write-Log "Oracle integration DISABLED in .env file" "INFO"
    }
    
    # Write updated content
    $newContent | Set-Content $envFile -Encoding UTF8
    Write-Log "Updated .env file successfully" "INFO"
}

function Show-OracleStatus {
    $envFile = ".env"
    
    Write-Log "=== Oracle Integration Status ===" "INFO"
    
    if (Test-Path $envFile) {
        $envContent = Get-Content $envFile
        $oracleEnabled = $false
        $oracleConfig = @{}
        
        foreach ($line in $envContent) {
            if ($line -match "^ORACLE_ENABLED=(.+)") {
                $oracleEnabled = ($matches[1] -eq "true")
            }
            elseif ($line -match "^ORACLE_CONNECTION_STRING=(.+)") {
                $oracleConfig["ConnectionString"] = $matches[1]
            }
            elseif ($line -match "^ORACLE_USERNAME=(.+)") {
                $oracleConfig["Username"] = $matches[1]
            }
            elseif ($line -match "^ORACLE_SCHEMAS=(.+)") {
                $oracleConfig["Schemas"] = $matches[1]
            }
        }
        
        Write-Log "Oracle Integration: $(if ($oracleEnabled) { 'ENABLED' } else { 'DISABLED' })" "INFO"
        
        if ($oracleEnabled) {
            Write-Log "Connection String: $($oracleConfig.ConnectionString)" "INFO"
            Write-Log "Username: $($oracleConfig.Username)" "INFO" 
            Write-Log "Schemas: $($oracleConfig.Schemas)" "INFO"
            
            Write-Log "" "INFO"
            Write-Log "Oracle API Endpoints:" "INFO"
            Write-Host "  Health Check:    http://localhost:8080/api/v1/oracle/health" -ForegroundColor Cyan
            Write-Host "  Configuration:   http://localhost:8080/api/v1/oracle/config" -ForegroundColor Cyan
            Write-Host "  Data Source:     http://localhost:8080/api/v1/oracle/data-source" -ForegroundColor Cyan
            Write-Host "  Schema Analysis: http://localhost:8080/api/v1/oracle/analyze-schemas" -ForegroundColor Cyan
        }
    }
    else {
        Write-Log ".env file not found - Oracle integration not configured" "WARN"
    }
}

# Main execution
Write-Log "Oracle Database Integration Setup Helper" "INFO"

if ($Status) {
    Show-OracleStatus
    exit 0
}

if ($Disable) {
    Update-EnvFile -ConnString "" -User "" -Pass "" -SchemaList "" -EnableOracle $false
    Write-Log "Oracle integration has been disabled" "INFO"
    Write-Log "Restart the GraphRAG system for changes to take effect" "WARN"
    exit 0
}

# Validate required parameters for other operations
if (-not $ConnectionString -or -not $Username -or -not $Password) {
    Write-Log "Missing required parameters" "ERROR"
    Write-Log "Usage: .\setup-oracle.ps1 -ConnectionString 'host:port/service' -Username 'user' -Password 'pass'" "ERROR"
    Write-Log "Example: .\setup-oracle.ps1 -TestConnection -ConnectionString 'localhost:1521/XE' -Username 'hr' -Password 'password'" "ERROR"
    exit 1
}

# Check Python oracledb dependency
try {
    $oracleCheck = python -c "import oracledb; print('oracledb module available')" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Log "Python oracledb module not found" "ERROR"
        Write-Log "Install with: pip install oracledb" "ERROR"
        exit 1
    }
    Write-Log "Python oracledb module is available" "INFO"
}
catch {
    Write-Log "Failed to check Python dependencies: $($_.Exception.Message)" "ERROR"
    exit 1
}

if ($TestConnection) {
    Write-Log "Testing Oracle connection (test mode only)..." "INFO"
    $connectionSuccess = Test-OracleConnection -ConnString $ConnectionString -User $Username -Pass $Password
    
    if ($connectionSuccess) {
        Write-Log "Oracle connection test completed successfully" "INFO"
        Write-Log "You can now enable Oracle integration with -Enable flag" "INFO"
    }
    else {
        Write-Log "Oracle connection test failed" "ERROR"
        Write-Log "Please verify your connection details and Oracle database status" "ERROR"
        exit 1
    }
}

if ($Enable) {
    Write-Log "Enabling Oracle integration..." "INFO"
    
    # Test connection first
    $connectionSuccess = Test-OracleConnection -ConnString $ConnectionString -User $Username -Pass $Password
    
    if (-not $connectionSuccess) {
        Write-Log "Cannot enable Oracle integration - connection test failed" "ERROR"
        exit 1
    }
    
    # Update .env file
    Update-EnvFile -ConnString $ConnectionString -User $Username -Pass $Password -SchemaList $Schemas -EnableOracle $true
    
    Write-Log "Oracle integration has been enabled successfully" "INFO"
    Write-Log "Configuration:" "INFO"
    Write-Log "  Connection: $ConnectionString" "INFO"
    Write-Log "  Username: $Username" "INFO"
    Write-Log "  Schemas: $Schemas" "INFO"
    Write-Log "" "INFO"
    Write-Log "Next steps:" "INFO"
    Write-Log "1. Restart the GraphRAG system: .\START.ps1" "INFO"
    Write-Log "2. Test Oracle health: curl http://localhost:8080/api/v1/oracle/health" "INFO"
    Write-Log "3. Analyze schemas: POST to http://localhost:8080/api/v1/oracle/analyze-schemas" "INFO"
}

Write-Log "Oracle setup completed" "INFO"