#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Simple GraphRAG System Health Check
    
.DESCRIPTION
    Quick and reliable health check for GraphRAG system components
    
.EXAMPLE
    .\HEALTH-SIMPLE.ps1
    
.NOTES
    GraphRAG - Simple System Health Validation
#>

param([switch]$Detailed)

$StartTime = Get-Date
Write-Host "GraphRAG System Health Check - $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Green
Write-Host "=" * 70 -ForegroundColor Green

# System Information
Write-Host "`n📊 SYSTEM INFORMATION" -ForegroundColor Blue
Write-Host "OS: $(Get-CimInstance Win32_OperatingSystem | Select-Object -ExpandProperty Caption)" -ForegroundColor White
Write-Host "Working Directory: $(Get-Location)" -ForegroundColor White
$totalMem = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 2)
$freeMem = [math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1MB / 1024, 2)
Write-Host "Memory: ${freeMem}GB / ${totalMem}GB available" -ForegroundColor White

# Version Information  
Write-Host "`n📦 VERSION INFORMATION" -ForegroundColor Blue
$versions = @{
    "Python" = { python --version 2>&1 }
    "Node.js" = { node --version 2>&1 }
    "Podman" = { podman --version 2>&1 }
    "Git" = { git --version 2>&1 }
}

foreach ($tool in $versions.Keys) {
    try {
        $output = & $versions[$tool]
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ ${tool}: $($output.ToString().Trim())" -ForegroundColor Green
        } else {
            Write-Host "❌ ${tool}: Not available" -ForegroundColor Red
        }
    } catch {
        Write-Host "❌ ${tool}: Not available" -ForegroundColor Red
    }
}

# Service Health
Write-Host "`n🔧 SERVICE STATUS" -ForegroundColor Blue
$services = @(
    @{ Name = "ChromaDB"; Port = 8000; Url = "http://localhost:8000/api/v2/healthcheck" }
    @{ Name = "Neo4j"; Port = 7474; Url = "http://localhost:7474/" }
    @{ Name = "Redis"; Port = 6379; Url = $null }
    @{ Name = "API Server"; Port = 8080; Url = "http://localhost:8080/api/v1/health/" }
    @{ Name = "API Server (Alt)"; Port = 8081; Url = "http://localhost:8081/api/v1/health/" }
    @{ Name = "Frontend"; Port = 3000; Url = "http://localhost:3000" }
)

$healthyServices = 0
$totalServices = $services.Count

foreach ($service in $services) {
    $portOpen = Test-NetConnection -ComputerName localhost -Port $service.Port -InformationLevel Quiet -WarningAction SilentlyContinue
    $httpHealthy = $false
    $responseTime = "N/A"
    
    if ($portOpen -and $service.Url) {
        try {
            $start = Get-Date
            $response = Invoke-WebRequest -Uri $service.Url -Method GET -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
            $elapsed = ((Get-Date) - $start).TotalMilliseconds
            if ($response.StatusCode -eq 200) {
                $httpHealthy = $true
                $responseTime = "$([math]::Round($elapsed, 0))ms"
            }
        } catch {
            # HTTP failed but port is open
        }
    }
    
    if ($portOpen -and ($httpHealthy -or -not $service.Url)) {
        Write-Host "✅ $($service.Name): Healthy (Port: $($service.Port), Response: $responseTime)" -ForegroundColor Green
        $healthyServices++
    } elseif ($portOpen) {
        Write-Host "⚠️  $($service.Name): Port open but HTTP failed (Port: $($service.Port))" -ForegroundColor Yellow
    } else {
        Write-Host "❌ $($service.Name): Not running (Port: $($service.Port))" -ForegroundColor Red
    }
}

# Environment Variables
Write-Host "`n🌐 ENVIRONMENT CONFIGURATION" -ForegroundColor Blue
$requiredEnvVars = @("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD", "CHROMA_HOST", "CHROMA_PORT", "REDIS_URL")
$missingVars = @()
$presentVars = @()

foreach ($var in $requiredEnvVars) {
    $value = [Environment]::GetEnvironmentVariable($var)
    if ($value) {
        $presentVars += $var
        if ($Detailed) {
            Write-Host "✅ ${var}: $value" -ForegroundColor Green
        }
    } else {
        $missingVars += $var
        Write-Host "❌ ${var}: Missing" -ForegroundColor Red
    }
}

if (-not $Detailed) {
    Write-Host "Required Variables: $($presentVars.Count)/$($requiredEnvVars.Count) set" -ForegroundColor $(if ($missingVars.Count -eq 0) { "Green" } else { "Yellow" })
}

# Container Status
Write-Host "`n🐳 CONTAINER STATUS" -ForegroundColor Blue
try {
    $containers = podman ps --format "{{.Names}} {{.Status}}" 2>$null
    if ($containers) {
        foreach ($line in $containers) {
            $parts = $line -split ' ', 2
            $name = $parts[0]
            $status = $parts[1]
            if ($status -like "*Up*") {
                Write-Host "✅ $name`: $status" -ForegroundColor Green
            } else {
                Write-Host "❌ $name`: $status" -ForegroundColor Red
            }
        }
    } else {
        Write-Host "❌ No containers running" -ForegroundColor Red
    }
} catch {
    Write-Host "❌ Cannot check container status (Podman not available)" -ForegroundColor Red
}

# Overall Health Score
$healthPercentage = [math]::Round(($healthyServices / $totalServices) * 100, 1)
$overallStatus = if ($healthPercentage -ge 90) { "Excellent" } 
                elseif ($healthPercentage -ge 75) { "Good" }
                elseif ($healthPercentage -ge 50) { "Fair" }
                else { "Poor" }

$color = if ($healthPercentage -ge 75) { "Green" } 
         elseif ($healthPercentage -ge 50) { "Yellow" }
         else { "Red" }

# Summary
$elapsed = ((Get-Date) - $StartTime).TotalSeconds
Write-Host "`n" -NoNewline
Write-Host "╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║                    HEALTH SUMMARY                        ║" -ForegroundColor Cyan
Write-Host "╠═══════════════════════════════════════════════════════════╣" -ForegroundColor Cyan
Write-Host "║ Overall Health: $healthPercentage% ($overallStatus)                       ║" -ForegroundColor $color
Write-Host "║ Healthy Services: $healthyServices/$totalServices                              ║" -ForegroundColor White
Write-Host "║ Environment Vars: $($presentVars.Count)/$($requiredEnvVars.Count) configured                    ║" -ForegroundColor White
Write-Host "║ Check Duration: $([math]::Round($elapsed, 1))s                              ║" -ForegroundColor White
Write-Host "╚═══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan

# Recommendations
Write-Host "`n💡 RECOMMENDATIONS" -ForegroundColor Yellow
if ($healthPercentage -eq 100 -and $missingVars.Count -eq 0) {
    Write-Host "✅ System is running optimally! All services are healthy." -ForegroundColor Green
} else {
    if ($healthyServices -lt $totalServices) {
        Write-Host "• Start missing services: .\START.ps1" -ForegroundColor Yellow
    }
    if ($missingVars.Count -gt 0) {
        Write-Host "• Set missing environment variables: $($missingVars -join ', ')" -ForegroundColor Yellow
    }
    if ($healthPercentage -lt 50) {
        Write-Host "• Consider a clean restart: .\START.ps1 -Clean" -ForegroundColor Yellow
    }
}

Write-Host "`n🌐 ACCESS URLS" -ForegroundColor Blue
if ($services | Where-Object { $_.Name -eq "API Server" -and (Test-NetConnection -ComputerName localhost -Port $_.Port -InformationLevel Quiet -WarningAction SilentlyContinue) }) {
    Write-Host "API Server: http://localhost:8080/api/v1/health/" -ForegroundColor Cyan
}
if ($services | Where-Object { $_.Name -eq "API Server (Alt)" -and (Test-NetConnection -ComputerName localhost -Port $_.Port -InformationLevel Quiet -WarningAction SilentlyContinue) }) {
    Write-Host "API Server (Alt): http://localhost:8081/api/v1/health/" -ForegroundColor Cyan
}
if ($services | Where-Object { $_.Name -eq "ChromaDB" -and (Test-NetConnection -ComputerName localhost -Port $_.Port -InformationLevel Quiet -WarningAction SilentlyContinue) }) {
    Write-Host "ChromaDB API: http://localhost:8000/api/v2/healthcheck" -ForegroundColor Cyan
}
if ($services | Where-Object { $_.Name -eq "Neo4j" -and (Test-NetConnection -ComputerName localhost -Port $_.Port -InformationLevel Quiet -WarningAction SilentlyContinue) }) {
    Write-Host "Neo4j Browser: http://localhost:7474 (neo4j / codebase-rag-2024)" -ForegroundColor Cyan
}
if ($services | Where-Object { $_.Name -eq "Frontend" -and (Test-NetConnection -ComputerName localhost -Port $_.Port -InformationLevel Quiet -WarningAction SilentlyContinue) }) {
    Write-Host "Frontend App: http://localhost:3000" -ForegroundColor Cyan
}

Write-Host "`nHealth check completed in $([math]::Round($elapsed, 1))s" -ForegroundColor Gray

# Exit with appropriate code
if ($overallStatus -in @("Poor")) {
    exit 1
}