# Codebase RAG MVP - Simple Startup Script for Windows
# This script starts the minimal viable product for local development

# Set error handling
$ErrorActionPreference = "Stop"

# Colors for output
function Write-ColorOutput {
    param([string]$Message, [string]$Color = "White")
    switch ($Color) {
        "Red" { Write-Host $Message -ForegroundColor Red }
        "Green" { Write-Host $Message -ForegroundColor Green }
        "Yellow" { Write-Host $Message -ForegroundColor Yellow }
        "Blue" { Write-Host $Message -ForegroundColor Blue }
        "Cyan" { Write-Host $Message -ForegroundColor Cyan }
        default { Write-Host $Message }
    }
}

# System requirements check
function Test-SystemRequirements {
    Write-ColorOutput "🔍 Checking system requirements..." "Blue"
    
    # Check Windows version
    $osInfo = Get-ComputerInfo
    $windowsVersion = $osInfo.WindowsVersion
    if ([version]$windowsVersion -lt [version]"10.0") {
        Write-ColorOutput "❌ Windows 10 or later required. Current: $($osInfo.WindowsProductName)" "Red"
        return $false
    }
    Write-ColorOutput "✅ Windows version: $($osInfo.WindowsProductName)" "Green"
    
    # Check RAM
    $totalRAM = [math]::Round($osInfo.TotalPhysicalMemory / 1GB, 1)
    if ($totalRAM -lt 8) {
        Write-ColorOutput "⚠️  Warning: $totalRAM GB RAM detected. 8GB+ recommended for optimal performance." "Yellow"
    } else {
        Write-ColorOutput "✅ System RAM: $totalRAM GB" "Green"
    }
    
    # Check disk space
    $systemDrive = Get-WmiObject -Class Win32_LogicalDisk | Where-Object { $_.DeviceID -eq $env:SystemDrive }
    $freeSpaceGB = [math]::Round($systemDrive.FreeSpace / 1GB, 1)
    if ($freeSpaceGB -lt 10) {
        Write-ColorOutput "❌ Insufficient disk space: $freeSpaceGB GB free. Need at least 10GB." "Red"
        return $false
    }
    Write-ColorOutput "✅ Free disk space: $freeSpaceGB GB" "Green"
    
    return $true
}

Write-ColorOutput "==================================================================" "Blue"
Write-ColorOutput "🚀 Starting Codebase RAG MVP with Neo4j & Maven" "Blue"
Write-ColorOutput "==================================================================" "Blue"
Write-Host ""

# Check system requirements first
if (-not (Test-SystemRequirements)) {
    Write-ColorOutput "❌ System requirements not met. Please check the issues above." "Red"
    Write-Host ""
    Write-ColorOutput "📖 For help, see: docs/WINDOWS-QUICKSTART.md" "Yellow"
    exit 1
}
Write-Host ""

# Check if podman is installed
if (-not (Get-Command podman -ErrorAction SilentlyContinue)) {
    Write-ColorOutput "❌ Podman is not installed or not in PATH" "Red"
    Write-Host "Please install Podman Desktop first."
    Write-Host ""
    Write-ColorOutput "📖 Installation guide: docs/WINDOWS-QUICKSTART.md#step-1-install-prerequisites" "Yellow"
    exit 1
}

Write-ColorOutput "✅ Podman found" "Green"

# Check if podman-compose is available
if (-not (Get-Command podman-compose -ErrorAction SilentlyContinue)) {
    Write-ColorOutput "⚠️  podman-compose not found, using podman compose" "Yellow"
    $ComposeCmd = "podman"
    $ComposeArgs = "compose"
} else {
    Write-ColorOutput "✅ podman-compose found" "Green"
    $ComposeCmd = "podman-compose"
    $ComposeArgs = ""
}

# Create necessary directories
Write-ColorOutput "📁 Creating directories..." "Blue"
New-Item -ItemType Directory -Force -Path "logs", "data" | Out-Null

# Check if local repos path is set
$ReposPath = $env:REPOS_PATH
if (-not $ReposPath) {
    Write-ColorOutput "⚠️  REPOS_PATH not set in environment" "Yellow"
    Write-Host "Please set REPOS_PATH to point to your local repositories:"
    Write-Host "  `$env:REPOS_PATH = 'C:\path\to\your\repos'"
    Write-Host "  OR"
    Write-Host "  Update the mvp-compose.yml file to point to your repos directory"
    Write-Host ""
    
    # Default suggestions
    $DefaultPaths = @(
        "$env:USERPROFILE\repos",
        "$env:USERPROFILE\Documents\repos",
        "C:\repos",
        "$env:USERPROFILE\source\repos"
    )
    
    foreach ($DefaultPath in $DefaultPaths) {
        if (Test-Path $DefaultPath) {
            Write-ColorOutput "Found potential repos directory: $DefaultPath" "Blue"
            $Response = Read-Host "Use this directory? (y/n)"
            if ($Response -match "^[Yy]") {
                $ReposPath = $DefaultPath
                $env:REPOS_PATH = $ReposPath
                Write-ColorOutput "✅ Using $ReposPath" "Green"
                break
            }
        }
    }
    
    if (-not $ReposPath) {
        Write-ColorOutput "Continuing without REPOS_PATH set - you'll need to index repos manually" "Yellow"
        Write-Host ""
    }
}

# Update compose file with repos path if set
if ($ReposPath) {
    Write-ColorOutput "📝 Updating compose file with repos path..." "Blue"
    
    # Read, update, and write the compose file
    $ComposeContent = Get-Content "mvp-compose.yml" -Raw
    $UpdatedContent = $ComposeContent -replace "/path/to/your/repos", $ReposPath.Replace('\', '/')
    $UpdatedContent | Set-Content "mvp-compose.yml" -NoNewline
    
    Write-ColorOutput "✅ Updated mvp-compose.yml with $ReposPath" "Green"
}

# Stop any existing containers
Write-ColorOutput "🛑 Stopping any existing containers..." "Blue"
try {
    if ($ComposeArgs) {
        & $ComposeCmd $ComposeArgs -f mvp-compose.yml down 2>$null
    } else {
        & $ComposeCmd -f mvp-compose.yml down 2>$null
    }
} catch {
    # Ignore errors - containers might not be running
}

# Pull latest images
Write-ColorOutput "📥 Pulling latest images..." "Blue"
if ($ComposeArgs) {
    & $ComposeCmd $ComposeArgs -f mvp-compose.yml pull
} else {
    & $ComposeCmd -f mvp-compose.yml pull
}

# Build the API container
Write-ColorOutput "🔨 Building API container..." "Blue"
if ($ComposeArgs) {
    & $ComposeCmd $ComposeArgs -f mvp-compose.yml build
} else {
    & $ComposeCmd -f mvp-compose.yml build
}

# Start the services
Write-ColorOutput "🚀 Starting services..." "Blue"
if ($ComposeArgs) {
    & $ComposeCmd $ComposeArgs -f mvp-compose.yml up -d
} else {
    & $ComposeCmd -f mvp-compose.yml up -d
}

# Wait for services to be ready
Write-ColorOutput "⏳ Waiting for services to be ready..." "Blue"

# Wait for ChromaDB
Write-Host "Waiting for ChromaDB..." -NoNewline
for ($i = 1; $i -le 30; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/heartbeat" -TimeoutSec 2 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-ColorOutput " ✅" "Green"
            break
        }
    } catch {
        Write-Host "." -NoNewline
        Start-Sleep -Seconds 2
    }
}

# Wait for Neo4j
Write-Host "Waiting for Neo4j..." -NoNewline
for ($i = 1; $i -le 60; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:7474" -TimeoutSec 2 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-ColorOutput " ✅" "Green"
            break
        }
    } catch {
        Write-Host "." -NoNewline
        Start-Sleep -Seconds 2
    }
}

# Wait for API
Write-Host "Waiting for API..." -NoNewline
for ($i = 1; $i -le 30; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8080/health" -TimeoutSec 2 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-ColorOutput " ✅" "Green"
            break
        }
    } catch {
        Write-Host "." -NoNewline
        Start-Sleep -Seconds 2
    }
}

Write-Host ""
Write-ColorOutput "==================================================================" "Green"
Write-ColorOutput "🎉 MVP is now running!" "Green"
Write-ColorOutput "==================================================================" "Green"
Write-Host ""
Write-ColorOutput "🌐 Available Endpoints:" "Blue"
Write-Host "   • API Documentation: http://localhost:8080/docs"
Write-Host "   • Health Check:      http://localhost:8080/health"
Write-Host "   • Search API:        http://localhost:8080/search?q=your-query"
Write-Host "   • ChromaDB:          http://localhost:8000"
Write-Host "   • Neo4j Browser:     http://localhost:7474 (neo4j / codebase-rag-2024)"
Write-Host ""
Write-ColorOutput "📖 Quick Start Guide:" "Blue"
Write-Host ""
Write-Host "1. Index a repository:"
Write-Host '   Invoke-RestMethod -Uri "http://localhost:8080/index" \'
Write-Host '     -Method POST -ContentType "application/json" \'
Write-Host '     -Body ''{"repo_path": "C:/path/to/your/repo", "repo_name": "my-repo"}'''
Write-Host ""
Write-Host "2. Search your code:"
Write-Host '   Invoke-RestMethod -Uri "http://localhost:8080/search?q=function authentication"'
Write-Host ""
Write-Host "3. List repositories:"
Write-Host '   Invoke-RestMethod -Uri "http://localhost:8080/repositories"'
Write-Host ""
Write-Host "4. View system status:"
Write-Host '   Invoke-RestMethod "http://localhost:8080/status"'
Write-Host ""
Write-Host "5. Analyze Maven dependencies (for Java projects):"
Write-Host '   Invoke-RestMethod "http://localhost:8080/maven/dependencies/org.springframework/spring-core/5.3.21"'
Write-Host ""
Write-Host "6. Find dependency conflicts:"
Write-Host '   Invoke-RestMethod "http://localhost:8080/maven/conflicts"'
Write-Host ""
Write-Host "7. Discover missing repositories (your main use case):"
Write-Host '   📖 See: docs/DEPENDENCY-DISCOVERY.md'
Write-Host ""
Write-ColorOutput "🛠️  Management Commands:" "Blue"
if ($ComposeArgs) {
    Write-Host "   • View logs:         $ComposeCmd $ComposeArgs -f mvp-compose.yml logs -f"
    Write-Host "   • Stop services:     $ComposeCmd $ComposeArgs -f mvp-compose.yml down"
    Write-Host "   • Restart services:  $ComposeCmd $ComposeArgs -f mvp-compose.yml restart"
    Write-Host "   • Check status:      $ComposeCmd $ComposeArgs -f mvp-compose.yml ps"
} else {
    Write-Host "   • View logs:         $ComposeCmd -f mvp-compose.yml logs -f"
    Write-Host "   • Stop services:     $ComposeCmd -f mvp-compose.yml down"
    Write-Host "   • Restart services:  $ComposeCmd -f mvp-compose.yml restart"
    Write-Host "   • Check status:      $ComposeCmd -f mvp-compose.yml ps"
}
Write-Host ""
Write-ColorOutput "📝 Next Steps:" "Yellow"
Write-Host "   1. Open http://localhost:8080/docs in your browser"
Write-Host "   2. Index your repositories using the /index endpoint"
Write-Host "   3. Use dependency analysis to find missing repositories"
Write-Host "   4. Start searching your code with semantic queries"
Write-Host ""
Write-ColorOutput "📖 Documentation:" "Yellow"
Write-Host "   • Dependency Discovery: docs/DEPENDENCY-DISCOVERY.md"
Write-Host "   • Troubleshooting: docs/WINDOWS-TROUBLESHOOTING.md"
Write-Host ""
Write-ColorOutput "Happy coding! 🚀" "Green"
Write-Host ""