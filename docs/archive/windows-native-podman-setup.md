# Codebase RAG System - Windows Native Podman Installation Guide

Complete installation guide for deploying the Enterprise Codebase RAG System on Windows using native Podman (without WSL2).

## Prerequisites

### System Requirements

**Minimum System Requirements:**
- Windows 10 Pro/Enterprise (64-bit) or Windows 11
- 32 GB RAM (64 GB recommended for production)
- 500 GB SSD storage (1 TB recommended)
- 8 CPU cores (16 cores recommended)
- Hyper-V enabled (for virtualization)
- PowerShell 5.1 or PowerShell 7+
- Reliable internet connection

**Production System Requirements:**
- Windows Server 2019/2022 or Windows 11 Pro/Enterprise
- 128 GB RAM
- 2 TB NVMe SSD storage
- 32 CPU cores with AVX2 support
- 10 Gbps network interface
- Dedicated GPU (optional, for ML acceleration)

### Software Prerequisites

- Windows Terminal (recommended)
- Podman Desktop 5.0+ (native Windows version)
- Git for Windows
- PowerShell 7+ (recommended)
- Visual Studio Code (optional, for development)

## Installation Steps

### 1. Enable Hyper-V and Containers Feature

**Enable Required Windows Features:**

Open PowerShell as Administrator and run:

```powershell
# Enable Hyper-V
Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All

# Enable Containers feature
Enable-WindowsOptionalFeature -Online -FeatureName Containers -All

# Enable Windows Hypervisor Platform
Enable-WindowsOptionalFeature -Online -FeatureName HypervisorPlatform -All

# Restart required after enabling features
Restart-Computer
```

**Verify Hyper-V Installation:**
```powershell
# Check if Hyper-V is enabled
Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All
```

### 2. Install Podman Desktop for Windows

**Download and Install:**

1. **Download Podman Desktop:**
   - Go to https://podman-desktop.io/downloads/windows
   - Download the native Windows installer (.exe)
   - Choose the version without WSL2 requirement

2. **Install Podman Desktop:**
   - Run the installer as Administrator
   - Select "Native Windows Installation" (not WSL2)
   - Choose "Install for all users"
   - Select "Add to PATH" during installation
   - Configure to use Hyper-V backend

3. **Initial Configuration:**
   - Launch Podman Desktop
   - Skip WSL2 setup when prompted
   - Select "Use native Windows containers"
   - Complete the machine initialization

**Configure Podman Machine:**
```powershell
# Initialize Podman machine with adequate resources
podman machine init --cpus 8 --memory 16384 --disk-size 200

# Start the machine
podman machine start

# Verify installation
podman --version
podman info
```

### 3. Install Podman Compose

**Install via PowerShell:**
```powershell
# Create directory for podman-compose
New-Item -Path "C:\Program Files\Podman" -ItemType Directory -Force

# Download podman-compose
Invoke-WebRequest -Uri "https://github.com/containers/podman-compose/releases/latest/download/podman-compose-win64.exe" -OutFile "C:\Program Files\Podman\podman-compose.exe"

# Add to PATH
$env:PATH += ";C:\Program Files\Podman"
[Environment]::SetEnvironmentVariable("PATH", $env:PATH, [EnvironmentVariableTarget]::Machine)

# Create compatibility alias
New-Alias -Name "docker-compose" -Value "podman-compose" -Scope Global

# Verify installation
podman-compose --version
```

### 4. Configure Windows Environment

**Create Podman configuration directory:**
```powershell
# Create configuration directory
New-Item -Path "$env:APPDATA\containers" -ItemType Directory -Force

# Configure registries
@"
[registries.search]
registries = ['docker.io', 'quay.io', 'registry.fedoraproject.org']

[registries.insecure]
registries = []

[registries.block]
registries = []
"@ | Out-File -FilePath "$env:APPDATA\containers\registries.conf" -Encoding UTF8

# Configure storage
@"
[storage]
driver = "overlay"

[storage.options]
additionalimagestores = []

[storage.options.overlay]
mountopt = "nodev"
"@ | Out-File -FilePath "$env:APPDATA\containers\storage.conf" -Encoding UTF8
```

**Configure PowerShell Profile:**
```powershell
# Add Podman aliases to PowerShell profile
$profilePath = $PROFILE
if (!(Test-Path $profilePath)) {
    New-Item -Path $profilePath -Type File -Force
}

@"
# Podman aliases for compatibility
Set-Alias docker podman
Set-Alias docker-compose podman-compose

# Helper functions
function Start-CodebaseRAG {
    Set-Location "C:\CodebaseRAG"
    podman-compose -f podman-compose.yml up -d
}

function Stop-CodebaseRAG {
    Set-Location "C:\CodebaseRAG"
    podman-compose -f podman-compose.yml down
}

function Get-CodebaseRAGStatus {
    Set-Location "C:\CodebaseRAG"
    podman-compose -f podman-compose.yml ps
}
"@ | Add-Content -Path $profilePath
```

### 5. System Optimization for Windows

**Configure Power Settings:**
```powershell
# Set high performance power plan
powercfg -setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c

# Disable USB selective suspend
powercfg -setacvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0
powercfg -setdcvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0

# Apply settings
powercfg -setactive SCHEME_CURRENT
```

**Optimize Virtual Memory:**
```powershell
# Configure page file for optimal performance
$computersystem = Get-WmiObject Win32_ComputerSystem -EnableAllPrivileges
$computersystem.AutomaticManagedPagefile = $false
$computersystem.Put()

$pagefile = Get-WmiObject -Query "SELECT * FROM Win32_PageFileSetting WHERE Name='C:\\pagefile.sys'"
if ($pagefile -ne $null) {
    $pagefile.Delete()
}

# Create new page file (16GB initial, 32GB maximum)
Set-WmiInstance -Class Win32_PageFileSetting -Arguments @{name="C:\pagefile.sys"; InitialSize = 16384; MaximumSize = 32768}
```

**Configure Windows Defender Exclusions:**
```powershell
# Add Podman directories to Windows Defender exclusions for better performance
Add-MpPreference -ExclusionPath "C:\Users\$env:USERNAME\.local\share\containers"
Add-MpPreference -ExclusionPath "C:\ProgramData\containers"
Add-MpPreference -ExclusionPath "C:\Program Files\Podman"
Add-MpPreference -ExclusionProcess "podman.exe"
Add-MpPreference -ExclusionProcess "conmon.exe"
```

### 6. Clone and Setup Project

**Setup project directory:**
```powershell
# Create project directory
New-Item -Path "C:\CodebaseRAG" -ItemType Directory -Force
Set-Location "C:\CodebaseRAG"

# Clone repository (replace with your actual repository URL)
git clone <your-repository-url> .

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
    "config\elasticsearch",
    "config\kibana",
    "config\api",
    "config\worker",
    "ssl"
)

foreach ($dir in $directories) {
    New-Item -Path $dir -ItemType Directory -Force
}

Write-Host "Project directories created successfully" -ForegroundColor Green
```

### 7. Configure Environment

**Create environment file:**
```powershell
# Copy example environment file
if (Test-Path ".env.example") {
    Copy-Item ".env.example" ".env"
} else {
    # Create basic .env file
    @"
# Application Environment
APP_ENV=production
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
"@ | Out-File -FilePath ".env" -Encoding UTF8
}

Write-Host "Environment file created. Please review and update with your specific configuration." -ForegroundColor Yellow
```

### 8. Configure Services for Windows

**ChromaDB Configuration:**
```powershell
# Create ChromaDB auth file
@"
admin:`$2b`$12`$8jU8Ub8qZ4xvNK5gL9Mj8e7vG3hF2wQ9xC5nD8mE7fA6bH1cI9jK0l
user:`$2b`$12`$9kV9Wc9rA5ywOL6hM0Nk9f8xH4iG3xR0yD6oE9nF8gB7cI2dJ0kL1m
"@ | Out-File -FilePath "config\chromadb\auth.txt" -Encoding UTF8

# Create ChromaDB configuration
@"
# ChromaDB Configuration for Windows
server_host = "0.0.0.0"
server_port = 8000
telemetry = false
allow_reset = false

# Security
auth_provider = "chromadb.auth.basic_authn.BasicAuthenticationServerProvider"
auth_credentials_file = "/chroma/config/auth.txt"

# Performance (Windows optimized)
max_batch_size = 5000
collection_segment_size = 500000
"@ | Out-File -FilePath "config\chromadb\chroma.conf" -Encoding UTF8
```

**Neo4j Configuration:**
```powershell
# Create Neo4j configuration
@"
# Network connector configuration
server.default_listen_address=0.0.0.0
server.bolt.listen_address=:7687
server.http.listen_address=:7474

# Memory settings (Windows optimized)
server.memory.heap.initial_size=4g
server.memory.heap.max_size=8g
server.memory.pagecache.size=16g

# Transaction log settings
server.tx_log.rotation.retention_policy=50M size
server.checkpoint.interval.time=300s

# Security
server.security.auth_enabled=true
server.security.procedures.unrestricted=apoc.*,gds.*,algo.*
server.security.procedures.allowlist=apoc.*,gds.*,algo.*

# Performance
server.cypher.runtime=pipelined
server.cypher.parallel_runtime_workers=4
"@ | Out-File -FilePath "config\neo4j\neo4j.conf" -Encoding UTF8
```

**Redis Configuration:**
```powershell
# Create Redis configuration
@"
# Basic configuration
bind 0.0.0.0
port 6379
protected-mode no
timeout 0
keepalive 300

# Memory management
maxmemory 2gb
maxmemory-policy allkeys-lru

# Persistence
save 900 1
save 300 10
save 60 10000

# Logging
loglevel notice
logfile ""

# Performance
tcp-keepalive 300
tcp-backlog 511
"@ | Out-File -FilePath "config\redis\redis.conf" -Encoding UTF8
```

**PostgreSQL Configuration:**
```powershell
# Create PostgreSQL configuration
@"
# Connection settings
listen_addresses = '*'
port = 5432
max_connections = 100

# Memory settings
shared_buffers = 512MB
effective_cache_size = 1GB
work_mem = 32MB
maintenance_work_mem = 128MB

# WAL settings
wal_level = replica
max_wal_size = 1GB
min_wal_size = 80MB
checkpoint_completion_target = 0.9

# Performance
random_page_cost = 1.1
effective_io_concurrency = 100
max_worker_processes = 4
max_parallel_workers_per_gather = 2
max_parallel_workers = 4
"@ | Out-File -FilePath "config\postgres\postgresql.conf" -Encoding UTF8

# Create pg_hba.conf
@"
# TYPE  DATABASE        USER            ADDRESS                 METHOD
local   all             all                                     trust
host    all             all             127.0.0.1/32            md5
host    all             all             ::1/128                 md5
host    all             all             172.20.0.0/16           md5
"@ | Out-File -FilePath "config\postgres\pg_hba.conf" -Encoding UTF8
```

### 9. Create Windows-Optimized Podman Compose File

**Create Windows-specific compose file:**
```powershell
# Create Windows-optimized podman-compose file
@"
version: '3.8'

services:
  # ChromaDB - Vector Database
  chromadb:
    image: chromadb/chroma:latest
    container_name: codebase-rag-chromadb
    ports:
      - "8000:8000"
    volumes:
      - chromadb_data:/chroma/chroma
      - ./config/chromadb:/chroma/config
    environment:
      - CHROMA_SERVER_HOST=0.0.0.0
      - CHROMA_SERVER_HTTP_PORT=8000
      - CHROMA_SERVER_GRPC_PORT=50051
      - CHROMA_SERVER_AUTHN_PROVIDER=chromadb.auth.basic_authn.BasicAuthenticationServerProvider
      - CHROMA_SERVER_AUTHN_CREDENTIALS_FILE=/chroma/config/auth.txt
      - CHROMA_DB_IMPL=clickhouse
      - CHROMA_MEMORY_LIMIT_BYTES=17179869184  # 16GB for Windows
      - ANONYMIZED_TELEMETRY=false
    networks:
      - codebase-rag-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/heartbeat"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s
    restart: unless-stopped
    # Windows resource limits
    mem_limit: 16g
    cpus: 8

  # Neo4j - Graph Database
  neo4j:
    image: neo4j:5.15-enterprise
    container_name: codebase-rag-neo4j
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/codebase-rag-2024-windows
      - NEO4J_ACCEPT_LICENSE_AGREEMENT=yes
      - NEO4J_PLUGINS=["apoc", "graph-data-science"]
      - NEO4J_dbms_security_procedures_unrestricted=apoc.*,gds.*
      - NEO4J_dbms_security_procedures_allowlist=apoc.*,gds.*
      - NEO4J_dbms_memory_heap_initial_size=4G
      - NEO4J_dbms_memory_heap_max_size=8G
      - NEO4J_dbms_memory_pagecache_size=16G
      - NEO4J_dbms_default_listen_address=0.0.0.0
      - NEO4J_dbms_connector_bolt_advertised_address=localhost:7687
      - NEO4J_dbms_connector_http_advertised_address=localhost:7474
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
      - neo4j_import:/import
      - neo4j_plugins:/plugins
      - ./config/neo4j:/conf
    networks:
      - codebase-rag-network
    healthcheck:
      test: ["CMD", "cypher-shell", "-u", "neo4j", "-p", "codebase-rag-2024-windows", "MATCH () RETURN count(*) as count"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s
    restart: unless-stopped
    mem_limit: 24g
    cpus: 8

  # Redis - Task Queue and Caching
  redis:
    image: redis:7-alpine
    container_name: codebase-rag-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
      - ./config/redis/redis.conf:/usr/local/etc/redis/redis.conf
    command: redis-server /usr/local/etc/redis/redis.conf
    networks:
      - codebase-rag-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped
    mem_limit: 2g
    cpus: 2

  # MinIO - S3-compatible storage
  minio:
    image: minio/minio:latest
    container_name: codebase-rag-minio
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      - MINIO_ROOT_USER=codebase-rag
      - MINIO_ROOT_PASSWORD=codebase-rag-2024-windows
      - MINIO_DOMAIN=localhost
    volumes:
      - minio_data:/data
    command: server /data --console-address ":9001"
    networks:
      - codebase-rag-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped
    mem_limit: 2g
    cpus: 2

  # PostgreSQL - Metadata and application data
  postgres:
    image: postgres:15-alpine
    container_name: codebase-rag-postgres
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_DB=codebase_rag
      - POSTGRES_USER=codebase_rag
      - POSTGRES_PASSWORD=codebase-rag-2024
      - POSTGRES_INITDB_ARGS="--data-checksums"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./config/postgres/postgresql.conf:/etc/postgresql/postgresql.conf
      - ./config/postgres/pg_hba.conf:/etc/postgresql/pg_hba.conf
    networks:
      - codebase-rag-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U codebase_rag -d codebase_rag"]
      interval: 30s
      timeout: 10s
      retries: 5
    restart: unless-stopped
    mem_limit: 4g
    cpus: 4

  # API Service - FastAPI application
  api:
    build:
      context: .
      dockerfile: docker/Dockerfile.api
    container_name: codebase-rag-api
    ports:
      - "8080:8080"
    depends_on:
      - chromadb
      - neo4j
      - redis
      - postgres
    environment:
      - APP_ENV=production
      - API_HOST=0.0.0.0
      - API_PORT=8080
      - API_WORKERS=4
      - CHROMA_HOST=chromadb
      - CHROMA_PORT=8000
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USERNAME=neo4j
      - NEO4J_PASSWORD=codebase-rag-2024-windows
      - NEO4J_DATABASE=neo4j
      - REDIS_URL=redis://redis:6379
      - POSTGRES_URL=postgresql://codebase_rag:codebase-rag-2024@postgres:5432/codebase_rag
      - MINIO_ENDPOINT=minio:9000
      - MINIO_ACCESS_KEY=codebase-rag
      - MINIO_SECRET_KEY=codebase-rag-2024-windows
      - LOG_LEVEL=INFO
      - EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
    volumes:
      - ./data/repositories:/app/data/repositories
      - ./logs:/app/logs
      - ./config/api:/app/config
    networks:
      - codebase-rag-network
    restart: unless-stopped
    mem_limit: 8g
    cpus: 4

  # Worker Service - Background processing
  worker:
    build:
      context: .
      dockerfile: docker/Dockerfile.worker
    container_name: codebase-rag-worker
    depends_on:
      - chromadb
      - neo4j
      - redis
      - postgres
    environment:
      - APP_ENV=production
      - CHROMA_HOST=chromadb
      - CHROMA_PORT=8000
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USERNAME=neo4j
      - NEO4J_PASSWORD=codebase-rag-2024-windows
      - NEO4J_DATABASE=neo4j
      - REDIS_URL=redis://redis:6379
      - POSTGRES_URL=postgresql://codebase_rag:codebase-rag-2024@postgres:5432/codebase_rag
      - MINIO_ENDPOINT=minio:9000
      - MINIO_ACCESS_KEY=codebase-rag
      - MINIO_SECRET_KEY=codebase-rag-2024-windows
      - LOG_LEVEL=INFO
      - EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
      - MAX_CONCURRENT_REPOS=8
      - BATCH_SIZE=500
    volumes:
      - ./data/repositories:/app/data/repositories
      - ./logs:/app/logs
      - ./config/worker:/app/config
    networks:
      - codebase-rag-network
    restart: unless-stopped
    mem_limit: 6g
    cpus: 4

  # Prometheus - Metrics collection
  prometheus:
    image: prom/prometheus:latest
    container_name: codebase-rag-prometheus
    ports:
      - "9090:9090"
    volumes:
      - prometheus_data:/prometheus
      - ./config/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'
      - '--storage.tsdb.retention.size=20GB'
      - '--web.enable-lifecycle'
      - '--web.enable-admin-api'
    networks:
      - codebase-rag-network
    restart: unless-stopped
    mem_limit: 4g
    cpus: 2

  # Grafana - Monitoring dashboard
  grafana:
    image: grafana/grafana:latest
    container_name: codebase-rag-grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=codebase-rag-2024
      - GF_INSTALL_PLUGINS=grafana-piechart-panel,grafana-worldmap-panel
    volumes:
      - grafana_data:/var/lib/grafana
      - ./config/grafana/provisioning:/etc/grafana/provisioning
    depends_on:
      - prometheus
    networks:
      - codebase-rag-network
    restart: unless-stopped
    mem_limit: 2g
    cpus: 2

networks:
  codebase-rag-network:
    driver: bridge

volumes:
  chromadb_data:
  neo4j_data:
  neo4j_logs:
  neo4j_import:
  neo4j_plugins:
  redis_data:
  minio_data:
  postgres_data:
  prometheus_data:
  grafana_data:
"@ | Out-File -FilePath "podman-compose-windows.yml" -Encoding UTF8
```

### 10. Deploy Services

**Start services with Podman Compose:**
```powershell
# Create network
podman network create codebase-rag-network

# Pull images (this may take 10-15 minutes)
Write-Host "Pulling container images..." -ForegroundColor Blue
podman-compose -f podman-compose-windows.yml pull

# Start services
Write-Host "Starting services..." -ForegroundColor Blue
podman-compose -f podman-compose-windows.yml up -d

# Monitor startup
Write-Host "Monitoring service startup..." -ForegroundColor Blue
podman-compose -f podman-compose-windows.yml logs -f
```

### 11. Initialize Databases

**Wait for services and initialize:**
```powershell
# Wait for services to be ready
Write-Host "Waiting for services to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 180

# Test API health
$maxAttempts = 20
$attempt = 1
do {
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:8080/api/v1/health" -Method GET
        Write-Host "API is ready!" -ForegroundColor Green
        break
    } catch {
        Write-Host "Attempt $attempt/$maxAttempts - API not ready yet..." -ForegroundColor Yellow
        Start-Sleep -Seconds 15
        $attempt++
    }
} while ($attempt -le $maxAttempts)

# Initialize Neo4j schema (if script exists)
if (Test-Path "scripts\neo4j\schema.cypher") {
    Write-Host "Initializing Neo4j schema..." -ForegroundColor Blue
    podman exec -i codebase-rag-neo4j cypher-shell -u neo4j -p codebase-rag-2024-windows -f /scripts/schema.cypher
}

# Create ChromaDB collection
Write-Host "Creating ChromaDB collection..." -ForegroundColor Blue
$body = @{
    name = "codebase_chunks"
    metadata = @{
        "hnsw:space" = "cosine"
    }
} | ConvertTo-Json

try {
    Invoke-RestMethod -Uri "http://localhost:8000/api/v1/collections" -Method POST -Body $body -ContentType "application/json"
    Write-Host "ChromaDB collection created successfully" -ForegroundColor Green
} catch {
    Write-Host "ChromaDB collection may already exist" -ForegroundColor Yellow
}
```

### 12. Configure Windows Firewall

**Allow required ports:**
```powershell
# Allow API port
New-NetFirewallRule -DisplayName "Codebase RAG API" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow

# For development access (remove in production)
New-NetFirewallRule -DisplayName "Codebase RAG Grafana" -Direction Inbound -Protocol TCP -LocalPort 3000 -Action Allow
New-NetFirewallRule -DisplayName "Codebase RAG Neo4j" -Direction Inbound -Protocol TCP -LocalPort 7474 -Action Allow
New-NetFirewallRule -DisplayName "Codebase RAG MinIO Console" -Direction Inbound -Protocol TCP -LocalPort 9001 -Action Allow

Write-Host "Firewall rules created successfully" -ForegroundColor Green
```

### 13. Create Management Scripts

**Create PowerShell management scripts:**

**Start Services Script:**
```powershell
# Create start-codebase-rag.ps1
@"
# Start Codebase RAG Services
Write-Host "Starting Codebase RAG System..." -ForegroundColor Green

Set-Location "C:\CodebaseRAG"

# Start Podman machine if not running
`$machineStatus = podman machine list --format json | ConvertFrom-Json
if (`$machineStatus.Running -eq `$false) {
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
"@ | Out-File -FilePath "start-codebase-rag.ps1" -Encoding UTF8

# Create stop-codebase-rag.ps1
@"
# Stop Codebase RAG Services
Write-Host "Stopping Codebase RAG System..." -ForegroundColor Red

Set-Location "C:\CodebaseRAG"
podman-compose -f podman-compose-windows.yml down

Write-Host "Services stopped successfully!" -ForegroundColor Green
"@ | Out-File -FilePath "stop-codebase-rag.ps1" -Encoding UTF8

# Create status-codebase-rag.ps1
@"
# Check Codebase RAG Status
Write-Host "Codebase RAG System Status" -ForegroundColor Blue
Write-Host "=========================" -ForegroundColor Blue

Set-Location "C:\CodebaseRAG"

# Check Podman machine
Write-Host "`nPodman Machine Status:" -ForegroundColor Yellow
podman machine list

# Check containers
Write-Host "`nContainer Status:" -ForegroundColor Yellow
podman-compose -f podman-compose-windows.yml ps

# Check API health
Write-Host "`nAPI Health Check:" -ForegroundColor Yellow
try {
    `$response = Invoke-RestMethod -Uri "http://localhost:8080/api/v1/health" -Method GET
    Write-Host "API Status: " -NoNewline
    Write-Host "HEALTHY" -ForegroundColor Green
} catch {
    Write-Host "API Status: " -NoNewline  
    Write-Host "UNHEALTHY" -ForegroundColor Red
}
"@ | Out-File -FilePath "status-codebase-rag.ps1" -Encoding UTF8

Write-Host "Management scripts created successfully" -ForegroundColor Green
```

### 14. Create Windows Service (Optional)

**Create Windows Service for auto-start:**
```powershell
# Create service wrapper script
@"
# Windows Service Wrapper for Codebase RAG
param([string]`$Action)

`$logFile = "C:\CodebaseRAG\logs\service.log"

function Write-ServiceLog {
    param([string]`$Message)
    `$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "`$timestamp - `$Message" | Out-File -FilePath `$logFile -Append
}

switch (`$Action) {
    "start" {
        Write-ServiceLog "Starting Codebase RAG services"
        Set-Location "C:\CodebaseRAG"
        
        # Start Podman machine
        podman machine start
        Start-Sleep -Seconds 30
        
        # Start services
        podman-compose -f podman-compose-windows.yml up -d
        Write-ServiceLog "Services started"
    }
    "stop" {
        Write-ServiceLog "Stopping Codebase RAG services"
        Set-Location "C:\CodebaseRAG"
        podman-compose -f podman-compose-windows.yml down
        Write-ServiceLog "Services stopped"
    }
}
"@ | Out-File -FilePath "service-wrapper.ps1" -Encoding UTF8

# Install NSSM (Non-Sucking Service Manager) for service creation
Write-Host "To create a Windows service, install NSSM and run:" -ForegroundColor Yellow
Write-Host "nssm install CodebaseRAG `"powershell.exe`" `"-ExecutionPolicy Bypass -File C:\CodebaseRAG\service-wrapper.ps1 start`"" -ForegroundColor Yellow
```

## Verification and Testing

### 15. Verify Installation

**Test all components:**
```powershell
# Test API
Invoke-RestMethod -Uri "http://localhost:8080/api/v1/health/detailed" | ConvertTo-Json -Depth 10

# Test individual services
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/heartbeat"  # ChromaDB
Invoke-RestMethod -Uri "http://localhost:7474/"                  # Neo4j
Invoke-RestMethod -Uri "http://localhost:9000/minio/health/live" # MinIO

# Test database connections
podman exec codebase-rag-postgres pg_isready -U codebase_rag
podman exec codebase-rag-neo4j cypher-shell -u neo4j -p codebase-rag-2024-windows "RETURN 1 as test"
```

### 16. Performance Monitoring

**Monitor system performance:**
```powershell
# Check Podman stats
podman stats

# Monitor Windows performance
Get-Counter -Counter "\Processor(_Total)\% Processor Time", "\Memory\Available MBytes" -SampleInterval 5 -MaxSamples 10

# Check disk space
Get-WmiObject -Class Win32_LogicalDisk | Where-Object {$_.DriveType -eq 3} | Select-Object DeviceID, @{Name="Size(GB)";Expression={[math]::Round($_.Size/1GB,2)}}, @{Name="FreeSpace(GB)";Expression={[math]::Round($_.FreeSpace/1GB,2)}}
```

## Windows-Specific Management

### Access Web Interfaces

All interfaces are accessible from Windows browsers:

- **API Documentation**: http://localhost:8080/docs
- **Neo4j Browser**: http://localhost:7474 (neo4j / codebase-rag-2024-windows)
- **MinIO Console**: http://localhost:9001 (codebase-rag / codebase-rag-2024-windows)
- **Grafana Dashboard**: http://localhost:3000 (admin / codebase-rag-2024)
- **Prometheus Metrics**: http://localhost:9090

### PowerShell Management Commands

```powershell
# Start system
.\start-codebase-rag.ps1

# Stop system
.\stop-codebase-rag.ps1

# Check status
.\status-codebase-rag.ps1

# View logs
podman-compose -f podman-compose-windows.yml logs -f api

# Scale services
podman-compose -f podman-compose-windows.yml up -d --scale worker=2

# Backup data
podman exec codebase-rag-postgres pg_dump -U codebase_rag codebase_rag > "backup-$(Get-Date -Format 'yyyyMMdd-HHmmss').sql"
```

### Visual Studio Code Integration

1. **Install Extensions:**
   - Docker (for container management)
   - Python (for development)
   - PowerShell (for script editing)

2. **Configure Workspace:**
   - Open `C:\CodebaseRAG` as workspace
   - Use integrated terminal for PowerShell commands

## Troubleshooting Windows-Specific Issues

### Podman Machine Issues

**Machine won't start:**
```powershell
# Check Hyper-V status
Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All

# Recreate machine
podman machine stop
podman machine rm
podman machine init --cpus 8 --memory 16384 --disk-size 200
podman machine start
```

**Virtualization errors:**
```powershell
# Check if virtualization is enabled in BIOS
Get-ComputerInfo | Select-Object -Property "HyperV*"

# Enable Hyper-V if needed
Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All
```

### Performance Issues

**High memory usage:**
```powershell
# Check memory usage
Get-Process | Sort-Object WorkingSet -Descending | Select-Object -First 10

# Adjust Podman machine memory
podman machine stop
podman machine set --memory 20480  # Increase to 20GB
podman machine start
```

**Slow container startup:**
```powershell
# Check Windows Defender exclusions
Get-MpPreference | Select-Object -Property ExclusionPath

# Add more exclusions if needed
Add-MpPreference -ExclusionPath "C:\Users\$env:USERNAME\.local\share\containers"
```

### Network Issues

**Port conflicts:**
```powershell
# Check which process is using a port
netstat -ano | findstr :8080

# Kill process if needed
taskkill /PID <pid> /F
```

**Container networking problems:**
```powershell
# Recreate network
podman network rm codebase-rag-network
podman network create codebase-rag-network

# Restart containers
podman-compose -f podman-compose-windows.yml restart
```

## Security Considerations

### Windows-Specific Security

1. **Windows Defender Configuration:**
   - Exclude Podman directories from real-time scanning
   - Configure controlled folder access if enabled

2. **User Account Control:**
   - Run PowerShell as Administrator only when necessary
   - Use standard user account for daily operations

3. **Network Security:**
   - Configure Windows Firewall appropriately
   - Use private networks for development

4. **Service Security:**
   - Change all default passwords
   - Use strong authentication tokens
   - Enable TLS for production deployments

### Enterprise Security

```powershell
# Enable Windows Event Logging for containers
wevtutil sl Microsoft-Windows-Containers/Operational /e:true

# Configure audit logging
auditpol /set /subcategory:"Process Creation" /success:enable /failure:enable

# Set up log forwarding (if using SIEM)
# Configure Windows Event Forwarding to central log server
```

## Production Deployment

### Windows Server Considerations

For production deployment on Windows Server:

1. **Use Windows Server 2019/2022**
2. **Configure IIS as reverse proxy** (alternative to nginx)
3. **Set up Windows Performance Toolkit** for monitoring
4. **Use Windows Task Scheduler** for automated tasks
5. **Configure Windows Server Backup** for data protection

### High Availability

1. **Windows Failover Clustering**
2. **Shared storage (SMB 3.0 or iSCSI)**
3. **Network Load Balancing**
4. **Database clustering** (PostgreSQL and Neo4j)

## Next Steps

After successful installation:

1. **Configure API Authentication**: Set up user accounts and API keys
2. **Add Repositories**: Configure Git repositories to index
3. **Set Up Monitoring**: Configure Grafana dashboards
4. **Backup Strategy**: Implement automated backup procedures
5. **Performance Tuning**: Optimize for your specific workload

For detailed usage instructions, see [API Usage Guide](../api-usage.md) and [Configuration Reference](../configuration.md).

---

**This installation provides a complete, enterprise-ready Codebase RAG system running natively on Windows without WSL2 dependency.**