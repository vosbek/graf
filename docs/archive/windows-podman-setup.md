# Codebase RAG System - Windows Podman Installation Guide

Complete installation guide for deploying the Enterprise Codebase RAG System on Windows using Podman Desktop and WSL2.

## Prerequisites

### System Requirements

**Minimum System Requirements:**
- Windows 10 Pro/Enterprise (64-bit) or Windows 11
- 32 GB RAM (64 GB recommended for production)
- 500 GB SSD storage (1 TB recommended)
- 8 CPU cores (16 cores recommended)
- WSL2 enabled with Ubuntu 22.04 LTS
- Hyper-V enabled (for virtualization)
- Reliable internet connection

**Production System Requirements:**
- Windows 11 Pro/Enterprise
- 128 GB RAM
- 2 TB NVMe SSD storage
- 32 CPU cores with AVX2 support
- 10 Gbps network interface
- Dedicated GPU (optional, for ML acceleration)

### Software Prerequisites

- WSL2 with Ubuntu 22.04 LTS
- Windows Terminal (recommended)
- Podman Desktop 5.0+
- Git for Windows
- Visual Studio Code (optional, for development)

## Installation Steps

### 1. Enable WSL2 and Install Ubuntu

**Enable WSL2:**

1. Open PowerShell as Administrator and run:
```powershell
# Enable WSL feature
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart

# Enable Virtual Machine Platform
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart

# Restart Windows
shutdown /r /t 0
```

2. After restart, download and install the WSL2 Linux kernel update:
   - Download from: https://aka.ms/wsl2kernel
   - Run the installer as Administrator

3. Set WSL2 as default version:
```powershell
wsl --set-default-version 2
```

**Install Ubuntu 22.04 LTS:**

1. Open Microsoft Store and search for "Ubuntu 22.04.3 LTS"
2. Click "Install" and wait for download to complete
3. Launch Ubuntu and complete the initial setup (username/password)
4. Update the system:
```bash
sudo apt update && sudo apt upgrade -y
```

### 2. Configure WSL2 for Production

**Create .wslconfig file in Windows user directory:**

Open File Explorer and navigate to `C:\Users\<YourUsername>\` and create `.wslconfig`:

```ini
[wsl2]
# Allocate memory (75% of system RAM recommended)
memory=96GB

# Allocate CPU cores (75% of available cores recommended)
processors=24

# Enable nested virtualization
nestedVirtualization=true

# Swap size
swap=32GB

# Enable systemd
systemd=true

# Network mode
networkingMode=mirrored

# Enable DNS tunneling
dnsTunneling=true

# Enable auto-proxy
autoProxy=true
```

**Restart WSL to apply changes:**
```powershell
wsl --shutdown
wsl
```

### 3. Install Podman Desktop on Windows

1. **Download Podman Desktop:**
   - Go to https://podman-desktop.io/downloads/windows
   - Download the latest Windows installer (.exe)

2. **Install Podman Desktop:**
   - Run the installer as Administrator
   - Follow the installation wizard
   - Select "Add to PATH" during installation
   - Choose "Install for all users" (recommended)

3. **Initial Setup:**
   - Launch Podman Desktop
   - Complete the onboarding process
   - Verify WSL2 backend is detected and enabled

4. **Verify Installation:**
   - Open PowerShell and run:
   ```powershell
   podman --version
   podman-compose --version
   ```

### 4. Configure WSL2 Ubuntu Environment

**Switch to Ubuntu (WSL2):**
```powershell
wsl -d Ubuntu-22.04
```

**Install Required Packages:**
```bash
# Update package lists
sudo apt update && sudo apt upgrade -y

# Install essential packages
sudo apt install -y curl wget git build-essential software-properties-common apt-transport-https ca-certificates gnupg lsb-release python3 python3-pip make

# Install additional development tools
sudo apt install -y vim nano htop tree unzip zip jq
```

**Configure Git (if not already configured):**
```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@domain.com"
```

### 5. Install Podman in WSL2

**Install Podman in Ubuntu WSL2:**
```bash
# Add Podman repository
sudo sh -c "echo 'deb https://download.opensuse.org/repositories/devel:/kubic:/libcontainers:/testing/xUbuntu_$(lsb_release -rs)/ /' > /etc/apt/sources.list.d/devel:kubic:libcontainers:testing.list"

# Add GPG key
wget -nv https://download.opensuse.org/repositories/devel:kubic:libcontainers:testing/xUbuntu_$(lsb_release -rs)/Release.key -O- | sudo apt-key add -

# Update package lists
sudo apt update

# Install Podman
sudo apt install -y podman

# Verify installation
podman --version
```

**Install Podman Compose:**
```bash
# Download podman-compose
sudo curl -o /usr/local/bin/podman-compose https://raw.githubusercontent.com/containers/podman-compose/devel/podman_compose.py

# Make executable
sudo chmod +x /usr/local/bin/podman-compose

# Create compatibility symlink
sudo ln -sf /usr/local/bin/podman-compose /usr/local/bin/docker-compose

# Verify installation
podman-compose --version
```

### 6. Configure Podman for Windows/WSL2

**Configure Podman settings:**
```bash
# Enable lingering for your user
sudo loginctl enable-linger $USER

# Create Podman configuration directory
mkdir -p ~/.config/containers

# Configure registries
cat > ~/.config/containers/registries.conf << 'EOF'
[registries.search]
registries = ['docker.io', 'quay.io', 'registry.fedoraproject.org']

[registries.insecure]
registries = []

[registries.block]
registries = []
EOF

# Configure storage
cat > ~/.config/containers/storage.conf << 'EOF'
[storage]
driver = "overlay"
runroot = "/run/user/1000/containers"
graphroot = "/home/$USER/.local/share/containers/storage"

[storage.options]
additionalimagestores = []

[storage.options.overlay]
mountopt = "nodev,metacopy=on"
EOF

# Create network
podman network create codebase-rag-network 2>/dev/null || true
```

### 7. System Optimization for Windows/WSL2

**Configure WSL2 system limits:**
```bash
# Increase virtual memory limits for Elasticsearch
echo 'vm.max_map_count=262144' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

# Increase file descriptor limits
echo "$USER soft nofile 65536" | sudo tee -a /etc/security/limits.conf
echo "$USER hard nofile 65536" | sudo tee -a /etc/security/limits.conf

# Configure systemd for higher limits
sudo mkdir -p /etc/systemd/system/user@.service.d
cat << 'EOF' | sudo tee /etc/systemd/system/user@.service.d/override.conf
[Service]
LimitNOFILE=65536
LimitNPROC=65536
EOF

# Reload systemd configuration
sudo systemctl daemon-reload
```

**Windows Performance Optimization:**

1. **Disable Windows Defender real-time scanning for WSL2** (optional, but improves performance):
   - Open Windows Security
   - Go to Virus & threat protection
   - Add exclusions for: `%USERPROFILE%\AppData\Local\Docker\wsl\`

2. **Configure Windows Power Settings:**
   - Set power plan to "High Performance"
   - Disable USB selective suspend
   - Disable disk power management

### 8. Clone and Setup Project

**In WSL2 Ubuntu terminal:**
```bash
# Navigate to a convenient location (this will be accessible from Windows at \\wsl$\Ubuntu-22.04\home\yourusername\)
cd ~

# Clone the repository
git clone <your-repository-url> codebase-rag
cd codebase-rag

# Create required directories
mkdir -p {data/repositories,logs,config/{chromadb,neo4j,redis,postgres,nginx,prometheus,grafana,elasticsearch,kibana,api,worker},ssl}

# Set proper permissions
chmod -R 755 config/
chmod -R 777 data/
chmod -R 777 logs/
```

### 9. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit environment file with your settings (using nano or vim)
nano .env
```

**Key environment variables for Windows:**

```bash
# Application Environment
APP_ENV=production
LOG_LEVEL=INFO

# Security - CHANGE THESE IN PRODUCTION
JWT_SECRET_KEY=your-super-secret-jwt-key-here-windows
NEO4J_PASSWORD=your-secure-neo4j-password
POSTGRES_PASSWORD=your-secure-postgres-password

# Resource Configuration (adjust for Windows/WSL2)
MAX_CONCURRENT_REPOS=8
MAX_WORKERS=6
BATCH_SIZE=1000

# Embedding Configuration
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DEVICE=cpu  # Change to 'cuda' if you have GPU support

# Network Configuration
API_HOST=0.0.0.0
API_PORT=8080

# Windows-specific optimizations
PYTHONUNBUFFERED=1
PYTHONIOENCODING=utf-8
```

### 10. Configure Services for Windows

#### ChromaDB Configuration

```bash
# Create ChromaDB auth file
cat > config/chromadb/auth.txt << 'EOF'
admin:$2b$12$8jU8Ub8qZ4xvNK5gL9Mj8e7vG3hF2wQ9xC5nD8mE7fA6bH1cI9jK0l
user:$2b$12$9kV9Wc9rA5ywOL6hM0Nk9f8xH4iG3xR0yD6oE9nF8gB7cI2dJ0kL1m
EOF

# Create ChromaDB configuration
cat > config/chromadb/chroma.conf << 'EOF'
# ChromaDB Configuration for Windows/WSL2
server_host = "0.0.0.0"
server_port = 8000
telemetry = false
allow_reset = false

# Security
auth_provider = "chromadb.auth.basic_authn.BasicAuthenticationServerProvider"
auth_credentials_file = "/chroma/config/auth.txt"

# Performance (adjusted for Windows)
max_batch_size = 5000
collection_segment_size = 500000
EOF
```

#### Neo4j Configuration

```bash
# Create Neo4j configuration (optimized for Windows/WSL2)
cat > config/neo4j/neo4j.conf << 'EOF'
# Network connector configuration
server.default_listen_address=0.0.0.0
server.bolt.listen_address=:7687
server.http.listen_address=:7474

# Memory settings (conservative for WSL2)
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

# Performance (Windows optimized)
server.cypher.runtime=pipelined
server.cypher.parallel_runtime_workers=4
EOF
```

#### Additional Service Configurations

```bash
# Redis configuration (Windows optimized)
cat > config/redis/redis.conf << 'EOF'
# Basic configuration
bind 0.0.0.0
port 6379
protected-mode no
timeout 0
keepalive 300

# Memory management (conservative for WSL2)
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
EOF

# PostgreSQL configuration (Windows optimized)
cat > config/postgres/postgresql.conf << 'EOF'
# Connection settings
listen_addresses = '*'
port = 5432
max_connections = 100

# Memory settings (conservative for WSL2)
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
EOF

# Create pg_hba.conf
cat > config/postgres/pg_hba.conf << 'EOF'
# TYPE  DATABASE        USER            ADDRESS                 METHOD
local   all             all                                     trust
host    all             all             127.0.0.1/32            md5
host    all             all             ::1/128                 md5
host    all             all             172.20.0.0/16           md5
EOF
```

### 11. Deploy with Podman Compose

```bash
# Build and start all services
podman-compose -f podman-compose.yml up -d

# Monitor the startup process (may take 5-10 minutes on first run)
podman-compose -f podman-compose.yml logs -f

# In another terminal, verify all services are running
podman-compose -f podman-compose.yml ps
```

### 12. Initialize Databases

```bash
# Wait for services to be fully ready (may take 3-5 minutes on Windows)
sleep 300

# Initialize Neo4j schema
podman exec -i codebase-rag-neo4j cypher-shell -u neo4j -p codebase-rag-2024 < scripts/neo4j/schema.cypher

# Create ChromaDB collection
curl -X POST http://localhost:8000/api/v1/collections \
  -H "Content-Type: application/json" \
  -d '{"name": "codebase_chunks", "metadata": {"hnsw:space": "cosine"}}'

# Verify API is responding
curl http://localhost:8080/api/v1/health
```

### 13. Access from Windows

**The system will be accessible from Windows at:**

- **API Documentation**: http://localhost:8080/docs
- **Neo4j Browser**: http://localhost:7474 (neo4j / codebase-rag-2024)
- **MinIO Console**: http://localhost:9001 (codebase-rag / codebase-rag-2024)
- **Grafana Dashboard**: http://localhost:3000 (admin / codebase-rag-2024)
- **Prometheus Metrics**: http://localhost:9090
- **Jaeger Tracing**: http://localhost:16686
- **Kibana Logs**: http://localhost:5601

**Access project files from Windows:**
- File Explorer: `\\wsl$\Ubuntu-22.04\home\<yourusername>\codebase-rag\`
- VS Code: Install "Remote - WSL" extension and open folder in WSL

### 14. Configure Windows Firewall

**Allow application ports through Windows Firewall:**

1. Open Windows Security → Firewall & network protection
2. Click "Advanced settings"
3. Create inbound rules for ports:
   - Port 8080 (API)
   - Port 3000 (Grafana) - for development only
   - Port 7474 (Neo4j) - for development only

**Or use PowerShell (run as Administrator):**
```powershell
# Allow API port
New-NetFirewallRule -DisplayName "Codebase RAG API" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow

# For development (remove in production)
New-NetFirewallRule -DisplayName "Codebase RAG Grafana" -Direction Inbound -Protocol TCP -LocalPort 3000 -Action Allow
New-NetFirewallRule -DisplayName "Codebase RAG Neo4j" -Direction Inbound -Protocol TCP -LocalPort 7474 -Action Allow
```

### 15. Create Windows Service (Optional)

**Create a PowerShell script to manage the system:**

Create `C:\codebase-rag\start-services.ps1`:
```powershell
# Start Codebase RAG Services
Write-Host "Starting Codebase RAG System..." -ForegroundColor Green

# Start WSL if not running
wsl -d Ubuntu-22.04 -e bash -c "echo 'WSL Started'"

# Navigate to project directory and start services
wsl -d Ubuntu-22.04 -e bash -c "cd ~/codebase-rag && podman-compose -f podman-compose.yml up -d"

Write-Host "Services started successfully!" -ForegroundColor Green
Write-Host "API available at: http://localhost:8080" -ForegroundColor Yellow
Write-Host "Grafana available at: http://localhost:3000" -ForegroundColor Yellow
```

Create `C:\codebase-rag\stop-services.ps1`:
```powershell
# Stop Codebase RAG Services
Write-Host "Stopping Codebase RAG System..." -ForegroundColor Red

wsl -d Ubuntu-22.04 -e bash -c "cd ~/codebase-rag && podman-compose -f podman-compose.yml down"

Write-Host "Services stopped successfully!" -ForegroundColor Green
```

**Make scripts executable and create shortcuts:**
1. Right-click on Desktop → New → Shortcut
2. Target: `powershell.exe -ExecutionPolicy Bypass -File "C:\codebase-rag\start-services.ps1"`
3. Name: "Start Codebase RAG"

## Windows-Specific Management

### Using Podman Desktop GUI

1. **Open Podman Desktop**
2. **View Containers**: See all running containers with resource usage
3. **View Images**: Manage container images
4. **View Volumes**: Manage persistent storage
5. **View Networks**: Monitor container networking

### PowerShell Management Commands

```powershell
# Check WSL status
wsl --list --verbose

# Enter WSL Ubuntu environment
wsl -d Ubuntu-22.04

# Run commands in WSL from PowerShell
wsl -d Ubuntu-22.04 -e bash -c "podman ps"

# Access logs from PowerShell
wsl -d Ubuntu-22.04 -e bash -c "cd ~/codebase-rag && podman-compose logs api"

# Backup from PowerShell
wsl -d Ubuntu-22.04 -e bash -c "cd ~/codebase-rag && podman exec codebase-rag-postgres pg_dump -U codebase_rag codebase_rag > backup-$(date +%Y%m%d).sql"
```

### Visual Studio Code Integration

1. **Install Extensions:**
   - Remote - WSL
   - Docker (for container management)
   - Python (if developing)

2. **Open Project:**
   - Ctrl+Shift+P → "Remote-WSL: Open Folder in WSL"
   - Navigate to `/home/<username>/codebase-rag`

3. **Integrated Terminal:**
   - Terminal will automatically use WSL2 Ubuntu
   - Can run `podman` commands directly

## Troubleshooting Windows-Specific Issues

### WSL2 Issues

**WSL2 not starting:**
```powershell
# Restart WSL
wsl --shutdown
wsl

# Check WSL version
wsl --list --verbose

# Update WSL
wsl --update
```

**Out of memory in WSL2:**
1. Adjust `.wslconfig` memory allocation
2. Restart WSL: `wsl --shutdown`

**Network connectivity issues:**
```bash
# In WSL2, restart networking
sudo service networking restart

# Check IP configuration
ip addr show
```

### Podman Desktop Issues

**Podman machine not starting:**
1. Open Podman Desktop
2. Go to Settings → Connection
3. Reset/Recreate the machine

**Container networking issues:**
```bash
# Recreate network
podman network rm codebase-rag-network
podman network create codebase-rag-network

# Restart containers
podman-compose -f podman-compose.yml restart
```

### Performance Issues

**Slow file I/O:**
1. Store project files in WSL2 filesystem (not Windows mounted drives)
2. Use WSL2 terminal for all operations
3. Exclude WSL directories from Windows Defender

**High memory usage:**
1. Adjust `.wslconfig` memory settings
2. Reduce container resource limits
3. Close unnecessary Windows applications

### Security Considerations

**Windows-specific security:**

1. **Windows Defender Exclusions:**
   - Add WSL2 directories to exclusions for better performance
   - `%USERPROFILE%\AppData\Local\Docker\wsl\`
   - `\\wsl$\`

2. **Firewall Configuration:**
   - Only allow necessary ports
   - Use Windows Firewall with Advanced Security

3. **User Account Control:**
   - Run PowerShell as Administrator only when necessary
   - Use standard user account for daily operations

4. **WSL2 Security:**
   - Keep WSL2 updated: `wsl --update`
   - Regularly update Ubuntu: `sudo apt update && sudo apt upgrade`

## Production Deployment on Windows

### Windows Server Considerations

For production deployment on Windows Server:

1. **Use Windows Server 2022 with Containers feature**
2. **Install Podman for Windows Server**
3. **Configure IIS as reverse proxy (alternative to nginx)**
4. **Set up Windows Event Logging**
5. **Configure Windows Performance Toolkit monitoring**
6. **Use Windows Task Scheduler for automated tasks**

### High Availability Setup

1. **Use Windows Failover Clustering**
2. **Configure shared storage (SMB 3.0 or iSCSI)**
3. **Set up load balancing with Windows NLB**
4. **Implement backup strategies with Windows Server Backup**

## Next Steps

After successful installation:

1. **Configure Development Environment**: Set up VS Code with Remote-WSL
2. **Set Up Monitoring**: Configure Windows Performance Monitor integration
3. **Backup Strategy**: Implement automated backups using Windows tools
4. **Security Hardening**: Apply Windows-specific security configurations
5. **Performance Optimization**: Fine-tune WSL2 and container resource allocation

For detailed usage instructions, see [API Usage Guide](../api-usage.md) and [Configuration Reference](../configuration.md).