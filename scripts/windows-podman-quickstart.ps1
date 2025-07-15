# Codebase RAG System - Windows Native Podman Quick Start Script
# This script helps set up the Codebase RAG system with native Podman on Windows

param(
    [switch]$SkipPrereqs,
    [switch]$SkipOptimization,
    [string]$InstallPath = "C:\CodebaseRAG"
)

# Set strict mode for better error handling
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Colors for output (using Write-Host with -ForegroundColor)
function Write-Log {
    param([string]$Message)
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message" -ForegroundColor Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

# Check if running as Administrator
function Test-IsAdmin {
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# Check prerequisites
function Test-Prerequisites {
    Write-Log "Checking prerequisites..."
    
    $missingPrereqs = @()
    
    # Check if running as Administrator
    if (-not (Test-IsAdmin)) {
        Write-Error "This script must be run as Administrator for initial setup"
        Write-Host "Please restart PowerShell as Administrator and run this script again."
        exit 1
    }
    
    # Check Windows version
    $osVersion = [System.Environment]::OSVersion.Version
    if ($osVersion.Major -lt 10) {
        $missingPrereqs += "Windows 10 or later required"
    }
    
    # Check for Hyper-V
    $hypervFeature = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All
    if ($hypervFeature.State -ne "Enabled") {
        Write-Warning "Hyper-V is not enabled. This script will enable it."
    }
    
    # Check for required commands
    $requiredCommands = @("git", "curl")
    foreach ($cmd in $requiredCommands) {
        if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
            $missingPrereqs += $cmd
        }
    }
    
    # Check for Podman
    if (-not (Get-Command "podman" -ErrorAction SilentlyContinue)) {
        Write-Warning "Podman not found. This script will install it."
    }
    
    if ($missingPrereqs.Count -gt 0) {
        Write-Error "Missing prerequisites: $($missingPrereqs -join ', ')"
        Write-Host "Please install the missing prerequisites:"
        Write-Host "  - Git for Windows: https://git-scm.com/download/win"
        Write-Host "  - curl (usually included with Windows 10+)"
        exit 1
    }
    
    Write-Success "Prerequisites check completed"
}

# Install and configure Hyper-V
function Install-HyperV {
    Write-Log "Configuring Hyper-V..."
    
    try {
        # Enable Hyper-V features
        $features = @(
            "Microsoft-Hyper-V-All",
            "Containers",
            "HypervisorPlatform"
        )
        
        $rebootRequired = $false
        foreach ($feature in $features) {
            $featureStatus = Get-WindowsOptionalFeature -Online -FeatureName $feature
            if ($featureStatus.State -ne "Enabled") {
                Write-Log "Enabling Windows feature: $feature"
                Enable-WindowsOptionalFeature -Online -FeatureName $feature -All -NoRestart
                $rebootRequired = $true
            }
        }
        
        if ($rebootRequired) {
            Write-Warning "Windows features have been enabled. A reboot is required."
            Write-Host "Please reboot your system and run this script again to continue."
            exit 0
        }
        
        Write-Success "Hyper-V configuration completed"
    }
    catch {
        Write-Error "Failed to configure Hyper-V: $($_.Exception.Message)"
        exit 1
    }
}

# Install Podman Desktop
function Install-Podman {
    Write-Log "Installing Podman Desktop..."
    
    if (Get-Command "podman" -ErrorAction SilentlyContinue) {
        Write-Log "Podman already installed, checking version..."
        $podmanVersion = podman --version
        Write-Log "Current Podman version: $podmanVersion"
        return
    }
    
    try {
        # Download Podman Desktop installer
        $tempDir = $env:TEMP
        $installerPath = Join-Path $tempDir "podman-desktop-installer.exe"
        
        Write-Log "Downloading Podman Desktop installer..."
        $downloadUrl = "https://github.com/containers/podman-desktop/releases/latest/download/podman-desktop-win32-x64.exe"
        Invoke-WebRequest -Uri $downloadUrl -OutFile $installerPath
        
        Write-Log "Running Podman Desktop installer..."
        Start-Process -FilePath $installerPath -ArgumentList "/S" -Wait
        
        # Add to PATH if not already there
        $podmanPath = "C:\Program Files\Podman Desktop\resources\bin"
        $currentPath = [Environment]::GetEnvironmentVariable("PATH", [EnvironmentVariableTarget]::Machine)
        if ($currentPath -notlike "*$podmanPath*") {
            [Environment]::SetEnvironmentVariable("PATH", "$currentPath;$podmanPath", [EnvironmentVariableTarget]::Machine)
            $env:PATH += ";$podmanPath"
        }
        
        # Clean up installer
        Remove-Item $installerPath -Force
        
        Write-Success "Podman Desktop installed successfully"
    }
    catch {
        Write-Error "Failed to install Podman Desktop: $($_.Exception.Message)"
        exit 1
    }
}

# Install Podman Compose
function Install-PodmanCompose {
    Write-Log "Installing Podman Compose..."
    
    if (Get-Command "podman-compose" -ErrorAction SilentlyContinue) {
        Write-Log "Podman Compose already installed"
        return
    }
    
    try {
        $composeDir = "C:\Program Files\Podman"
        New-Item -Path $composeDir -ItemType Directory -Force | Out-Null
        
        $composePath = Join-Path $composeDir "podman-compose.exe"
        Write-Log "Downloading Podman Compose..."
        Invoke-WebRequest -Uri "https://github.com/containers/podman-compose/releases/latest/download/podman-compose-win64.exe" -OutFile $composePath
        
        # Add to PATH
        $currentPath = [Environment]::GetEnvironmentVariable("PATH", [EnvironmentVariableTarget]::Machine)
        if ($currentPath -notlike "*$composeDir*") {
            [Environment]::SetEnvironmentVariable("PATH", "$currentPath;$composeDir", [EnvironmentVariableTarget]::Machine)
            $env:PATH += ";$composeDir"
        }
        
        Write-Success "Podman Compose installed successfully"
    }
    catch {
        Write-Error "Failed to install Podman Compose: $($_.Exception.Message)"
        exit 1
    }
}

# Configure Podman machine
function Initialize-PodmanMachine {
    Write-Log "Initializing Podman machine..."
    
    try {
        # Check if machine already exists
        $machines = podman machine list --format json 2>$null | ConvertFrom-Json
        if ($machines -and $machines.Count -gt 0) {
            Write-Log "Podman machine already exists"
            
            # Start machine if not running
            $runningMachine = $machines | Where-Object { $_.Running -eq $true }
            if (-not $runningMachine) {
                Write-Log "Starting Podman machine..."
                podman machine start
            }
            return
        }
        
        # Initialize new machine
        Write-Log "Creating new Podman machine..."
        podman machine init --cpus 8 --memory 16384 --disk-size 200
        
        Write-Log "Starting Podman machine..."
        podman machine start
        
        Write-Success "Podman machine initialized and started"
    }
    catch {
        Write-Error "Failed to initialize Podman machine: $($_.Exception.Message)"
        exit 1
    }
}

# Check system resources
function Test-SystemResources {
    Write-Log "Checking system resources..."
    
    # Check RAM
    $totalRam = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 2)
    if ($totalRam -lt 16) {
        Write-Warning "System has ${totalRam}GB RAM. Minimum 16GB recommended for development, 64GB for production."
    } else {
        Write-Success "System has ${totalRam}GB RAM"
    }
    
    # Check available disk space
    $systemDrive = Get-CimInstance -ClassName Win32_LogicalDisk | Where-Object { $_.DriveType -eq 3 -and $_.DeviceID -eq $env:SystemDrive }
    $freeSpaceGB = [math]::Round($systemDrive.FreeSpace / 1GB, 2)
    if ($freeSpaceGB -lt 100) {
        Write-Warning "Available disk space: ${freeSpaceGB}GB. Minimum 100GB recommended."
    } else {
        Write-Success "Available disk space: ${freeSpaceGB}GB"
    }
    
    # Check CPU cores
    $cpuCores = (Get-CimInstance Win32_ComputerSystem).NumberOfProcessors
    if ($cpuCores -lt 4) {
        Write-Warning "System has $cpuCores CPU cores. Minimum 4 cores recommended for development, 16 for production."
    } else {
        Write-Success "System has $cpuCores CPU cores"
    }
}

# Optimize Windows settings
function Optimize-WindowsSettings {
    if ($SkipOptimization) {
        Write-Log "Skipping Windows optimization (SkipOptimization flag set)"
        return
    }
    
    Write-Log "Optimizing Windows settings..."
    
    try {
        # Set high performance power plan
        Write-Log "Setting high performance power plan..."
        powercfg -setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c
        
        # Disable USB selective suspend
        powercfg -setacvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0
        powercfg -setdcvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0
        powercfg -setactive SCHEME_CURRENT
        
        # Configure page file
        Write-Log "Configuring virtual memory..."
        $computersystem = Get-WmiObject Win32_ComputerSystem -EnableAllPrivileges
        $computersystem.AutomaticManagedPagefile = $false
        $computersystem.Put() | Out-Null
        
        # Remove existing page file
        $pagefile = Get-WmiObject -Query "SELECT * FROM Win32_PageFileSetting WHERE Name='C:\\pagefile.sys'"
        if ($pagefile) {
            $pagefile.Delete()
        }
        
        # Create new page file
        Set-WmiInstance -Class Win32_PageFileSetting -Arguments @{name="C:\pagefile.sys"; InitialSize = 16384; MaximumSize = 32768} | Out-Null
        
        # Add Windows Defender exclusions
        Write-Log "Configuring Windows Defender exclusions..."
        $exclusionPaths = @(
            "C:\Users\$env:USERNAME\.local\share\containers",
            "C:\ProgramData\containers",
            "C:\Program Files\Podman",
            $InstallPath
        )
        
        foreach ($path in $exclusionPaths) {
            try {
                Add-MpPreference -ExclusionPath $path -ErrorAction SilentlyContinue
            } catch {
                Write-Warning "Could not add Windows Defender exclusion for: $path"
            }
        }
        
        Add-MpPreference -ExclusionProcess "podman.exe" -ErrorAction SilentlyContinue
        Add-MpPreference -ExclusionProcess "conmon.exe" -ErrorAction SilentlyContinue
        
        Write-Success "Windows optimization completed"
    }
    catch {
        Write-Warning "Some optimizations failed: $($_.Exception.Message)"
    }
}

# Setup project
function Initialize-Project {
    Write-Log "Setting up project..."
    
    try {
        # Create project directory
        if (-not (Test-Path $InstallPath)) {
            New-Item -Path $InstallPath -ItemType Directory -Force | Out-Null
        }
        
        Set-Location $InstallPath
        
        # Clone repository if not exists
        if (-not (Test-Path ".git")) {
            Write-Log "Project directory is empty. Please clone your repository manually:"
            Write-Host "  cd `"$InstallPath`""
            Write-Host "  git clone <your-repository-url> ."
            Write-Host ""
            Write-Host "Then run this script again to continue setup."
            exit 0
        }
        
        # Create required directories
        $directories = @(
            "data\repositories",
            "logs",
            "config\chromadb",
            "config\neo4j",
            "config\redis",
            "config\postgres",
            "config\nginx",
            "config\prometheus",
            "config\grafana",
            "config\api",
            "config\worker",
            "ssl"
        )
        
        foreach ($dir in $directories) {
            if (-not (Test-Path $dir)) {
                New-Item -Path $dir -ItemType Directory -Force | Out-Null
            }
        }
        
        Write-Success "Project structure created"
    }
    catch {
        Write-Error "Failed to setup project: $($_.Exception.Message)"
        exit 1
    }
}

# Create environment configuration
function New-EnvironmentConfig {
    Write-Log "Creating environment configuration..."
    
    $envPath = Join-Path $InstallPath ".env"
    
    if (Test-Path $envPath) {
        Write-Log ".env file already exists, skipping creation"
        return
    }
    
    try {
        $envContent = @"
# Application Environment
APP_ENV=development
LOG_LEVEL=INFO
DEBUG=false

# API Configuration
API_HOST=0.0.0.0
API_PORT=8080
API_WORKERS=4

# ChromaDB Configuration
CHROMA_HOST=chromadb
CHROMA_PORT=8000
CHROMA_COLLECTION_NAME=codebase_chunks

# Neo4j Configuration
NEO4J_URI=bolt://neo4j:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=codebase-rag-2024-windows
NEO4J_DATABASE=neo4j

# Redis Configuration
REDIS_URL=redis://redis:6379

# PostgreSQL Configuration
POSTGRES_URL=postgresql://codebase_rag:codebase-rag-2024@postgres:5432/codebase_rag

# MinIO Configuration
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=codebase-rag
MINIO_SECRET_KEY=codebase-rag-2024-windows

# Security Configuration
JWT_SECRET_KEY=change-this-secret-key-in-production-windows
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Processing Configuration (Windows optimized)
MAX_CONCURRENT_REPOS=8
MAX_WORKERS=6
BATCH_SIZE=500
TIMEOUT_SECONDS=300

# Embedding Configuration
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DEVICE=cpu

# Maven Configuration
MAVEN_ENABLED=true
MAVEN_RESOLUTION_STRATEGY=nearest
MAVEN_INCLUDE_TEST_DEPENDENCIES=false

# Windows-specific optimizations
PYTHONUNBUFFERED=1
PYTHONIOENCODING=utf-8
"@
        
        $envContent | Out-File -FilePath $envPath -Encoding UTF8
        
        Write-Success "Environment configuration created"
        Write-Warning "Please review and update the .env file with your specific configuration"
    }
    catch {
        Write-Error "Failed to create environment configuration: $($_.Exception.Message)"
        exit 1
    }
}

# Configure services
function Set-ServiceConfigurations {
    Write-Log "Configuring services..."
    
    try {
        # ChromaDB auth file
        $chromaAuthPath = Join-Path $InstallPath "config\chromadb\auth.txt"
        if (-not (Test-Path $chromaAuthPath)) {
            @"
admin:`$2b`$12`$8jU8Ub8qZ4xvNK5gL9Mj8e7vG3hF2wQ9xC5nD8mE7fA6bH1cI9jK0l
user:`$2b`$12`$9kV9Wc9rA5ywOL6hM0Nk9f8xH4iG3xR0yD6oE9nF8gB7cI2dJ0kL1m
"@ | Out-File -FilePath $chromaAuthPath -Encoding UTF8
        }
        
        # Redis configuration
        $redisConfigPath = Join-Path $InstallPath "config\redis\redis.conf"
        if (-not (Test-Path $redisConfigPath)) {
            @"
bind 0.0.0.0
port 6379
protected-mode no
maxmemory 2gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
"@ | Out-File -FilePath $redisConfigPath -Encoding UTF8
        }
        
        # PostgreSQL configuration
        $pgConfigPath = Join-Path $InstallPath "config\postgres\postgresql.conf"
        if (-not (Test-Path $pgConfigPath)) {
            @"
listen_addresses = '*'
port = 5432
max_connections = 100
shared_buffers = 512MB
effective_cache_size = 1GB
work_mem = 32MB
maintenance_work_mem = 128MB
"@ | Out-File -FilePath $pgConfigPath -Encoding UTF8
        }
        
        $pgHbaPath = Join-Path $InstallPath "config\postgres\pg_hba.conf"
        if (-not (Test-Path $pgHbaPath)) {
            @"
local   all             all                                     trust
host    all             all             127.0.0.1/32            md5
host    all             all             ::1/128                 md5
host    all             all             172.20.0.0/16           md5
"@ | Out-File -FilePath $pgHbaPath -Encoding UTF8
        }
        
        Write-Success "Service configurations created"
    }
    catch {
        Write-Error "Failed to configure services: $($_.Exception.Message)"
        exit 1
    }
}

# Create network
function New-PodmanNetwork {
    Write-Log "Creating Podman network..."
    
    try {
        $networkExists = podman network exists codebase-rag-network 2>$null
        if ($LASTEXITCODE -ne 0) {
            podman network create codebase-rag-network
            Write-Success "Podman network created"
        } else {
            Write-Log "Podman network already exists"
        }
    }
    catch {
        Write-Error "Failed to create Podman network: $($_.Exception.Message)"
        exit 1
    }
}

# Start services
function Start-Services {
    Write-Log "Starting services with Podman Compose..."
    
    try {
        Set-Location $InstallPath
        
        # Check for compose file
        $composeFile = "podman-compose-windows.yml"
        if (-not (Test-Path $composeFile)) {
            $composeFile = "podman-compose.yml"
            if (-not (Test-Path $composeFile)) {
                Write-Error "No Podman Compose file found. Expected: podman-compose-windows.yml or podman-compose.yml"
                exit 1
            }
        }
        
        Write-Log "Pulling container images (this may take 10-15 minutes)..."
        podman-compose -f $composeFile pull
        
        Write-Log "Starting services in background..."
        podman-compose -f $composeFile up -d
        
        Write-Success "Services started successfully"
    }
    catch {
        Write-Error "Failed to start services: $($_.Exception.Message)"
        exit 1
    }
}

# Wait for services to be ready
function Wait-ForServices {
    Write-Log "Waiting for services to be ready..."
    
    $maxAttempts = 30
    $attempt = 1
    
    while ($attempt -le $maxAttempts) {
        try {
            $response = Invoke-RestMethod -Uri "http://localhost:8080/api/v1/health" -Method GET -TimeoutSec 5
            Write-Success "API service is ready!"
            break
        }
        catch {
            if ($attempt -eq $maxAttempts) {
                Write-Error "Services failed to start within expected time"
                Write-Host "Check logs with: podman-compose -f podman-compose-windows.yml logs"
                exit 1
            }
            
            Write-Host "." -NoNewline
            Start-Sleep -Seconds 10
            $attempt++
        }
    }
    
    # Test other services
    $services = @(
        @{ Url = "http://localhost:8000/api/v1/heartbeat"; Name = "ChromaDB" },
        @{ Url = "http://localhost:7474"; Name = "Neo4j" },
        @{ Url = "http://localhost:9000/minio/health/live"; Name = "MinIO" }
    )
    
    foreach ($service in $services) {
        try {
            Invoke-RestMethod -Uri $service.Url -Method GET -TimeoutSec 5 | Out-Null
            Write-Success "$($service.Name) is ready"
        }
        catch {
            Write-Warning "$($service.Name) may not be ready yet"
        }
    }
}

# Initialize databases
function Initialize-Databases {
    Write-Log "Initializing databases..."
    
    try {
        # Wait a bit more for databases to be fully ready
        Start-Sleep -Seconds 30
        
        # Initialize Neo4j schema if script exists
        $schemaScript = Join-Path $InstallPath "scripts\neo4j\schema.cypher"
        if (Test-Path $schemaScript) {
            Write-Log "Initializing Neo4j schema..."
            $schemaContent = Get-Content $schemaScript -Raw
            $schemaContent | podman exec -i codebase-rag-neo4j cypher-shell -u neo4j -p codebase-rag-2024-windows
            Write-Success "Neo4j schema initialized"
        }
        
        # Create ChromaDB collection
        Write-Log "Creating ChromaDB collection..."
        $body = @{
            name = "codebase_chunks"
            metadata = @{
                "hnsw:space" = "cosine"
            }
        } | ConvertTo-Json
        
        try {
            Invoke-RestMethod -Uri "http://localhost:8000/api/v1/collections" -Method POST -Body $body -ContentType "application/json" | Out-Null
            Write-Success "ChromaDB collection created"
        }
        catch {
            Write-Warning "ChromaDB collection creation failed - collection may already exist"
        }
    }
    catch {
        Write-Warning "Database initialization failed: $($_.Exception.Message)"
    }
}

# Configure Windows Firewall
function Set-FirewallRules {
    Write-Log "Configuring Windows Firewall..."
    
    try {
        # API port
        New-NetFirewallRule -DisplayName "Codebase RAG API" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow -ErrorAction SilentlyContinue
        
        # Development ports (comment out for production)
        New-NetFirewallRule -DisplayName "Codebase RAG Grafana" -Direction Inbound -Protocol TCP -LocalPort 3000 -Action Allow -ErrorAction SilentlyContinue
        New-NetFirewallRule -DisplayName "Codebase RAG Neo4j" -Direction Inbound -Protocol TCP -LocalPort 7474 -Action Allow -ErrorAction SilentlyContinue
        New-NetFirewallRule -DisplayName "Codebase RAG MinIO Console" -Direction Inbound -Protocol TCP -LocalPort 9001 -Action Allow -ErrorAction SilentlyContinue
        
        Write-Success "Firewall rules configured"
    }
    catch {
        Write-Warning "Some firewall rules could not be created: $($_.Exception.Message)"
    }
}

# Create management scripts
function New-ManagementScripts {
    Write-Log "Creating management scripts..."
    
    try {
        # Start script
        $startScript = @"
# Start Codebase RAG Services
Write-Host "Starting Codebase RAG System..." -ForegroundColor Green

Set-Location "$InstallPath"

# Start Podman machine if not running
`$machineList = podman machine list --format json 2>`$null | ConvertFrom-Json
if (`$machineList -and `$machineList.Running -eq `$false) {
    Write-Host "Starting Podman machine..." -ForegroundColor Yellow
    podman machine start
    Start-Sleep -Seconds 30
}

# Start services
podman-compose -f podman-compose-windows.yml up -d

Write-Host "Services started successfully!" -ForegroundColor Green
Write-Host "API available at: http://localhost:8080" -ForegroundColor Yellow
Write-Host "Grafana available at: http://localhost:3000" -ForegroundColor Yellow
Write-Host "Neo4j available at: http://localhost:7474" -ForegroundColor Yellow
"@
        
        $startScript | Out-File -FilePath (Join-Path $InstallPath "start-codebase-rag.ps1") -Encoding UTF8
        
        # Stop script
        $stopScript = @"
# Stop Codebase RAG Services
Write-Host "Stopping Codebase RAG System..." -ForegroundColor Red

Set-Location "$InstallPath"
podman-compose -f podman-compose-windows.yml down

Write-Host "Services stopped successfully!" -ForegroundColor Green
"@
        
        $stopScript | Out-File -FilePath (Join-Path $InstallPath "stop-codebase-rag.ps1") -Encoding UTF8
        
        # Status script
        $statusScript = @"
# Check Codebase RAG Status
Write-Host "Codebase RAG System Status" -ForegroundColor Blue
Write-Host "=========================" -ForegroundColor Blue

Set-Location "$InstallPath"

# Check Podman machine
Write-Host "`nPodman Machine Status:" -ForegroundColor Yellow
podman machine list

# Check containers
Write-Host "`nContainer Status:" -ForegroundColor Yellow
podman-compose -f podman-compose-windows.yml ps

# Check API health
Write-Host "`nAPI Health Check:" -ForegroundColor Yellow
try {
    `$response = Invoke-RestMethod -Uri "http://localhost:8080/api/v1/health" -Method GET -TimeoutSec 5
    Write-Host "API Status: " -NoNewline
    Write-Host "HEALTHY" -ForegroundColor Green
} catch {
    Write-Host "API Status: " -NoNewline  
    Write-Host "UNHEALTHY" -ForegroundColor Red
}
"@
        
        $statusScript | Out-File -FilePath (Join-Path $InstallPath "status-codebase-rag.ps1") -Encoding UTF8
        
        Write-Success "Management scripts created"
    }
    catch {
        Write-Error "Failed to create management scripts: $($_.Exception.Message)"
        exit 1
    }
}

# Display summary
function Show-Summary {
    Write-Host ""
    Write-Host "=================================================================="
    Write-Success "Codebase RAG System is now running on Windows!"
    Write-Host "=================================================================="
    Write-Host ""
    Write-Host "🌐 Web Interfaces:" -ForegroundColor Cyan
    Write-Host "   • API Documentation: http://localhost:8080/docs"
    Write-Host "   • Neo4j Browser:     http://localhost:7474 (neo4j / codebase-rag-2024-windows)"
    Write-Host "   • MinIO Console:     http://localhost:9001 (codebase-rag / codebase-rag-2024-windows)"
    Write-Host "   • Grafana Dashboard: http://localhost:3000 (admin / codebase-rag-2024)"
    Write-Host "   • Prometheus:        http://localhost:9090"
    Write-Host ""
    Write-Host "🔧 Management Commands:" -ForegroundColor Cyan
    Write-Host "   • Start services:    .\start-codebase-rag.ps1"
    Write-Host "   • Stop services:     .\stop-codebase-rag.ps1"  
    Write-Host "   • Check status:      .\status-codebase-rag.ps1"
    Write-Host "   • View logs:         podman-compose -f podman-compose-windows.yml logs -f"
    Write-Host ""
    Write-Host "📁 Project Location:" -ForegroundColor Cyan
    Write-Host "   • $InstallPath"
    Write-Host ""
    Write-Host "📚 Next Steps:" -ForegroundColor Cyan
    Write-Host "   1. Review and update .env configuration"
    Write-Host "   2. Configure repositories to index"
    Write-Host "   3. Set up monitoring dashboards"
    Write-Host "   4. Read the full documentation in docs/"
    Write-Host ""
    Write-Warning "Remember to change default passwords before production use!"
    Write-Host ""
}

# Main execution
function Main {
    Write-Host "==================================================================" -ForegroundColor Cyan
    Write-Host "🚀 Codebase RAG System - Windows Native Podman Quick Start" -ForegroundColor Cyan
    Write-Host "==================================================================" -ForegroundColor Cyan
    Write-Host ""
    
    if (-not $SkipPrereqs) {
        Test-Prerequisites
        Install-HyperV
        Install-Podman
        Install-PodmanCompose
        Initialize-PodmanMachine
    }
    
    Test-SystemResources
    Optimize-WindowsSettings
    Initialize-Project
    New-EnvironmentConfig
    Set-ServiceConfigurations
    New-PodmanNetwork
    Start-Services
    Wait-ForServices
    Initialize-Databases
    Set-FirewallRules
    New-ManagementScripts
    Show-Summary
    
    Write-Success "Windows native setup completed successfully!"
}

# Handle script interruption
trap {
    Write-Error "Script interrupted: $($_.Exception.Message)"
    exit 1
}

# Run main function
Main