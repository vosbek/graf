# Codebase RAG System - Ubuntu Podman Installation Guide

Complete installation guide for deploying the Enterprise Codebase RAG System on Ubuntu using Podman.

## Prerequisites

### System Requirements

**Minimum System Requirements:**
- Ubuntu 20.04 LTS or later (22.04 LTS recommended)
- 32 GB RAM (64 GB recommended for production)
- 500 GB SSD storage (1 TB recommended)
- 8 CPU cores (16 cores recommended)
- Reliable internet connection

**Production System Requirements:**
- Ubuntu 22.04 LTS
- 128 GB RAM
- 2 TB NVMe SSD storage
- 32 CPU cores with AVX2 support
- 10 Gbps network interface

### Software Prerequisites

- Git
- Python 3.9+ 
- Podman 4.0+
- Podman Compose
- Make (for build automation)

## Installation Steps

### 1. Update System Packages

```bash
# Update package lists
sudo apt update && sudo apt upgrade -y

# Install essential packages
sudo apt install -y curl wget git build-essential software-properties-common apt-transport-https ca-certificates gnupg lsb-release
```

### 2. Install Podman

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

### 3. Install Podman Compose

```bash
# Download podman-compose
sudo curl -o /usr/local/bin/podman-compose https://raw.githubusercontent.com/containers/podman-compose/devel/podman_compose.py

# Make executable
sudo chmod +x /usr/local/bin/podman-compose

# Create symlink for compatibility
sudo ln -sf /usr/local/bin/podman-compose /usr/local/bin/docker-compose

# Verify installation
podman-compose --version
```

### 4. Configure Podman

```bash
# Enable lingering for your user (allows containers to run without login)
sudo loginctl enable-linger $USER

# Configure registries (optional, for private registries)
mkdir -p ~/.config/containers
cat > ~/.config/containers/registries.conf << 'EOF'
[registries.search]
registries = ['docker.io', 'quay.io', 'registry.fedoraproject.org']

[registries.insecure]
registries = []

[registries.block]
registries = []
EOF

# Set up storage configuration
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

# Create Podman network for system containers
podman network create codebase-rag-network 2>/dev/null || true
```

### 5. System Optimization

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

### 6. Clone and Setup Project

```bash
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

### 7. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit environment file with your settings
nano .env
```

**Key environment variables to configure:**

```bash
# Application Environment
APP_ENV=production
LOG_LEVEL=INFO

# Security - CHANGE THESE IN PRODUCTION
JWT_SECRET_KEY=your-super-secret-jwt-key-here
NEO4J_PASSWORD=your-secure-neo4j-password
POSTGRES_PASSWORD=your-secure-postgres-password

# Resource Configuration
MAX_CONCURRENT_REPOS=10
MAX_WORKERS=8
BATCH_SIZE=1000

# Embedding Configuration
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DEVICE=cpu  # Change to 'cuda' if you have GPU support

# Network Configuration
API_HOST=0.0.0.0
API_PORT=8080
```

### 8. Configure Services

#### ChromaDB Configuration

```bash
# Create ChromaDB auth file
cat > config/chromadb/auth.txt << 'EOF'
admin:$2b$12$8jU8Ub8qZ4xvNK5gL9Mj8e7vG3hF2wQ9xC5nD8mE7fA6bH1cI9jK0l
user:$2b$12$9kV9Wc9rA5ywOL6hM0Nk9f8xH4iG3xR0yD6oE9nF8gB7cI2dJ0kL1m
EOF

# Create ChromaDB configuration
cat > config/chromadb/chroma.conf << 'EOF'
# ChromaDB Configuration
server_host = "0.0.0.0"
server_port = 8000
telemetry = false
allow_reset = false

# Security
auth_provider = "chromadb.auth.basic_authn.BasicAuthenticationServerProvider"
auth_credentials_file = "/chroma/config/auth.txt"

# Performance
max_batch_size = 10000
collection_segment_size = 1000000
EOF
```

#### Neo4j Configuration

```bash
# Create Neo4j configuration
cat > config/neo4j/neo4j.conf << 'EOF'
# Network connector configuration
server.default_listen_address=0.0.0.0
server.bolt.listen_address=:7687
server.http.listen_address=:7474

# Memory settings (adjust based on your system)
server.memory.heap.initial_size=8g
server.memory.heap.max_size=16g
server.memory.pagecache.size=32g

# Transaction log settings
server.tx_log.rotation.retention_policy=100M size
server.checkpoint.interval.time=300s

# Security
server.security.auth_enabled=true
server.security.procedures.unrestricted=apoc.*,gds.*,algo.*
server.security.procedures.allowlist=apoc.*,gds.*,algo.*

# Performance
server.cypher.runtime=pipelined
server.cypher.parallel_runtime_workers=8
EOF
```

#### Redis Configuration

```bash
# Create Redis configuration
cat > config/redis/redis.conf << 'EOF'
# Basic configuration
bind 0.0.0.0
port 6379
protected-mode no
timeout 0
keepalive 300

# Memory management
maxmemory 4gb
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
```

#### PostgreSQL Configuration

```bash
# Create PostgreSQL configuration
cat > config/postgres/postgresql.conf << 'EOF'
# Connection settings
listen_addresses = '*'
port = 5432
max_connections = 200

# Memory settings
shared_buffers = 1GB
effective_cache_size = 3GB
work_mem = 64MB
maintenance_work_mem = 256MB

# WAL settings
wal_level = replica
max_wal_size = 2GB
min_wal_size = 80MB
checkpoint_completion_target = 0.9

# Performance
random_page_cost = 1.1
effective_io_concurrency = 200
max_worker_processes = 8
max_parallel_workers_per_gather = 4
max_parallel_workers = 8
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

### 9. Deploy with Podman Compose

```bash
# Build and start all services
podman-compose -f podman-compose.yml up -d

# Monitor the startup process
podman-compose -f podman-compose.yml logs -f

# Verify all services are running
podman-compose -f podman-compose.yml ps
```

### 10. Initialize Databases

```bash
# Wait for services to be ready (may take 2-3 minutes)
sleep 180

# Initialize Neo4j schema
podman exec -i codebase-rag-neo4j cypher-shell -u neo4j -p codebase-rag-2024 < scripts/neo4j/schema.cypher

# Create ChromaDB collection
curl -X POST http://localhost:8000/api/v1/collections \
  -H "Content-Type: application/json" \
  -d '{"name": "codebase_chunks", "metadata": {"hnsw:space": "cosine"}}'

# Verify API is responding
curl http://localhost:8080/api/v1/health
```

### 11. Verification and Testing

```bash
# Check service health
curl http://localhost:8080/api/v1/health/detailed

# Check individual services
curl http://localhost:8000/api/v1/heartbeat  # ChromaDB
curl http://localhost:7474/                  # Neo4j
curl http://localhost:6379                   # Redis (should refuse connection)
curl http://localhost:9000/minio/health/live # MinIO

# View logs
podman-compose -f podman-compose.yml logs api
podman-compose -f podman-compose.yml logs worker
```

### 12. Configure Systemd Services (Optional)

For production deployment, set up systemd services to auto-start:

```bash
# Create systemd service for the entire stack
sudo tee /etc/systemd/system/codebase-rag.service << 'EOF'
[Unit]
Description=Codebase RAG System
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/USERNAME/codebase-rag
ExecStart=/usr/local/bin/podman-compose -f podman-compose.yml up -d
ExecStop=/usr/local/bin/podman-compose -f podman-compose.yml down
User=USERNAME
Group=USERNAME

[Install]
WantedBy=multi-user.target
EOF

# Replace USERNAME with your actual username
sudo sed -i "s/USERNAME/$USER/g" /etc/systemd/system/codebase-rag.service

# Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable codebase-rag.service
sudo systemctl start codebase-rag.service

# Check status
sudo systemctl status codebase-rag.service
```

## Monitoring and Management

### Access Web Interfaces

- **API Documentation**: http://localhost:8080/docs
- **Neo4j Browser**: http://localhost:7474 (neo4j / codebase-rag-2024)
- **MinIO Console**: http://localhost:9001 (codebase-rag / codebase-rag-2024)
- **Grafana Dashboard**: http://localhost:3000 (admin / codebase-rag-2024)
- **Prometheus Metrics**: http://localhost:9090
- **Jaeger Tracing**: http://localhost:16686
- **Kibana Logs**: http://localhost:5601

### Common Management Commands

```bash
# View running containers
podman ps

# View logs for specific service
podman logs codebase-rag-api -f

# Restart specific service
podman-compose -f podman-compose.yml restart api

# Scale worker service
podman-compose -f podman-compose.yml up -d --scale worker=4

# Update images
podman-compose -f podman-compose.yml pull
podman-compose -f podman-compose.yml up -d

# Backup data
podman exec codebase-rag-postgres pg_dump -U codebase_rag codebase_rag > backup.sql

# Stop all services
podman-compose -f podman-compose.yml down

# Remove all containers and volumes (WARNING: DATA LOSS)
podman-compose -f podman-compose.yml down -v
```

## Troubleshooting

### Common Issues

**1. Permission Denied Errors**
```bash
# Fix ownership of data directories
sudo chown -R $USER:$USER data/ logs/
chmod -R 755 data/ logs/
```

**2. Out of Memory Errors**
```bash
# Check system memory
free -h
# Reduce resource limits in podman-compose.yml if needed
```

**3. Port Conflicts**
```bash
# Check which process is using a port
sudo netstat -tulpn | grep :8080
# Kill the process or change port in configuration
```

**4. Container Fails to Start**
```bash
# Check container logs
podman logs codebase-rag-chromadb
# Check system logs
journalctl -u podman
```

**5. Network Issues**
```bash
# Recreate network
podman network rm codebase-rag-network
podman network create codebase-rag-network
# Restart services
podman-compose -f podman-compose.yml restart
```

### Performance Tuning

**For Production Systems:**

1. **Enable GPU Support** (if available):
```bash
# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart podman

# Update environment to use GPU
echo "EMBEDDING_DEVICE=cuda" >> .env
```

2. **Optimize for SSD**:
```bash
# Set scheduler for SSD
echo 'ACTION=="add|change", KERNEL=="sd[a-z]*", ATTR{queue/rotational}=="0", ATTR{queue/scheduler}="mq-deadline"' | sudo tee /etc/udev/rules.d/60-ssd-scheduler.rules
```

3. **Increase File Limits**:
```bash
echo "fs.file-max = 2097152" | sudo tee -a /etc/sysctl.conf
echo "$USER soft nproc 65536" | sudo tee -a /etc/security/limits.conf
echo "$USER hard nproc 65536" | sudo tee -a /etc/security/limits.conf
```

## Security Considerations

### Production Security Checklist

- [ ] Change all default passwords
- [ ] Enable TLS/SSL for all services
- [ ] Configure firewall (ufw)
- [ ] Set up log rotation
- [ ] Enable audit logging
- [ ] Configure backup encryption
- [ ] Set up intrusion detection
- [ ] Regular security updates

### Firewall Configuration

```bash
# Enable UFW
sudo ufw enable

# Allow SSH (adjust port as needed)
sudo ufw allow 22/tcp

# Allow application ports
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw allow 8080/tcp  # API

# For development/internal access only
sudo ufw allow from 192.168.0.0/16 to any port 3000  # Grafana
sudo ufw allow from 192.168.0.0/16 to any port 7474  # Neo4j
sudo ufw allow from 192.168.0.0/16 to any port 9001  # MinIO Console

# Check status
sudo ufw status
```

## Next Steps

After successful installation:

1. **Configure API Authentication**: Update JWT settings and create user accounts
2. **Set Up Repository Processing**: Configure Git repositories to index
3. **Customize Dashboards**: Set up Grafana dashboards for monitoring
4. **Schedule Backups**: Set up automated backup procedures
5. **Performance Testing**: Run load tests to verify system performance

For detailed usage instructions, see [API Usage Guide](../api-usage.md) and [Configuration Reference](../configuration.md).