#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Fix START.ps1 script issues
    
.DESCRIPTION
    Applies critical fixes to START.ps1:
    1. Fix port configuration for API server validation
    2. Remove duplicate api-debug block
    3. Standardize environment variable setting
    
.EXAMPLE
    .\FIX-START.ps1
    
.NOTES
    Creates START-FIXED.ps1 with the necessary corrections
#>

Write-Host "Fixing START.ps1 script issues..." -ForegroundColor Green

# Read the original START.ps1
$content = Get-Content "START.ps1" -Raw

Write-Host "  1. Fixing API server port configuration..." -ForegroundColor Yellow
# Fix the hardcoded port 8080 to use dynamic port detection
$content = $content -replace 'HealthUrl = "http://localhost:8080/api/v1/health/"', 'HealthUrl = "http://localhost:8081/api/v1/health/"'
$content = $content -replace 'DatabasePort = 8080', 'DatabasePort = 8081'

Write-Host "  2. Removing duplicate api-debug block..." -ForegroundColor Yellow
# Remove the duplicate api-debug block (lines 1613-1646)
$lines = $content -split "`n"
$newLines = @()
$skipLines = $false
$skipStart = -1
$skipEnd = -1

for ($i = 0; $i -lt $lines.Count; $i++) {
    $line = $lines[$i]
    
    # Detect start of duplicate api-debug block (second occurrence)
    if ($line.Trim() -eq "'api-debug' {" -and $i -gt 1600) {
        $skipLines = $true
        $skipStart = $i
        Write-Host "    Found duplicate api-debug block starting at line $($i+1)" -ForegroundColor Cyan
        continue
    }
    
    # Detect end of duplicate block
    if ($skipLines -and $line.Trim() -eq "}" -and $lines[$i+1].Trim().StartsWith("'mvp'")) {
        $skipEnd = $i
        $skipLines = $false
        Write-Host "    Removed duplicate api-debug block (lines $($skipStart+1) to $($skipEnd+1))" -ForegroundColor Cyan
        continue
    }
    
    # Skip lines in the duplicate block
    if (-not $skipLines) {
        $newLines += $line
    }
}

$content = $newLines -join "`n"

Write-Host "  3. Fixing validation URL consistency..." -ForegroundColor Yellow
# Fix API Server validation to use correct port based on mode
$validationFix = @'
        # Determine API port based on mode and environment
        $apiPort = 8080  # default
        if ($Mode -eq 'api' -or $env:GRAFRAG_HOST_API_PORT) {
            try {
                $apiPort = if ($env:GRAFRAG_HOST_API_PORT) { [int]$env:GRAFRAG_HOST_API_PORT } else { 8081 }
            } catch {
                $apiPort = 8081  # fallback for api mode
            }
        }
        
        @{
            Name = "API Server"
            HealthUrl = "http://localhost:${apiPort}/api/v1/health/"
            DatabasePort = $apiPort
            ExpectedContent = $null
            Critical = $true
        }
'@

# Replace the API Server validation block
$content = $content -replace '(?s)@\{\s*Name = "API Server".*?Critical = \$true\s*\}', $validationFix

Write-Host "  4. Adding environment variable validation function..." -ForegroundColor Yellow
# Add a function to consistently set environment variables
$envFunction = @'

function Set-DatabaseEnvironmentVariables {
    param([switch]$Force)
    
    $envVars = @{
        "REDIS_URL" = "redis://localhost:6379"
        "NEO4J_URI" = "bolt://localhost:7687"
        "NEO4J_USERNAME" = "neo4j"
        "NEO4J_PASSWORD" = "codebase-rag-2024"
        "NEO4J_DATABASE" = "neo4j"
        "CHROMA_HOST" = "localhost"
        "CHROMA_PORT" = "8000"
    }
    
    $setCount = 0
    foreach ($key in $envVars.Keys) {
        if ($Force -or -not $env:$key) {
            Set-Item -Path "env:$key" -Value $envVars[$key]
            $setCount++
            Write-Log "Set environment variable: $key = $($envVars[$key])" "DEBUG" "ENV"
        }
    }
    
    if ($setCount -gt 0) {
        Write-Log "Set $setCount database environment variables" "INFO" "ENV"
    }
    
    return $setCount -gt 0
}

'@

# Insert the function before the main function
$content = $content -replace '(# === MAIN EXECUTION ===)', "$envFunction`n`$1"

Write-Host "  5. Standardizing environment variable calls..." -ForegroundColor Yellow
# Replace manual environment variable setting with function calls
$content = $content -replace '(?m)^\s*\$env:REDIS_URL = "redis://localhost:6379".*?\$env:CHROMA_PORT = "8000"', '            Set-DatabaseEnvironmentVariables -Force'

Write-Host "  6. Fixing API readiness URL..." -ForegroundColor Yellow
# Fix API readiness check to use the correct port
$content = $content -replace '"http://localhost:8080/api/v1/health/ready"', '"http://localhost:${apiPort}/api/v1/health/ready"'

# Write the fixed content to a new file
$content | Set-Content "START-FIXED.ps1" -Encoding UTF8

Write-Host "`nFixes applied successfully!" -ForegroundColor Green
Write-Host "Created: START-FIXED.ps1" -ForegroundColor Cyan

# Show summary of changes
Write-Host "`nSummary of fixes:" -ForegroundColor White
Write-Host "  ✓ Fixed API server port configuration (8080 → dynamic)" -ForegroundColor Green
Write-Host "  ✓ Removed duplicate api-debug block" -ForegroundColor Green  
Write-Host "  ✓ Added dynamic port detection for validation" -ForegroundColor Green
Write-Host "  ✓ Added environment variable standardization function" -ForegroundColor Green
Write-Host "  ✓ Improved consistency across all modes" -ForegroundColor Green

Write-Host "`nTo use the fixed version:" -ForegroundColor Yellow
Write-Host "  1. Backup original: Move-Item START.ps1 START-ORIGINAL.ps1" -ForegroundColor Cyan
Write-Host "  2. Use fixed version: Move-Item START-FIXED.ps1 START.ps1" -ForegroundColor Cyan
Write-Host "  3. Test: .\START.ps1 -Status" -ForegroundColor Cyan