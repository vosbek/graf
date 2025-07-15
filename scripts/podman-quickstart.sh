#!/bin/bash

# Codebase RAG System - Podman Quick Start Script
# This script helps set up the Codebase RAG system with Podman

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   error "This script should not be run as root for security reasons"
   exit 1
fi

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if [[ -f /etc/os-release ]]; then
            . /etc/os-release
            OS=$NAME
            VER=$VERSION_ID
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macOS"
    else
        error "Unsupported operating system: $OSTYPE"
        exit 1
    fi
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check for required commands
    local required_commands=("curl" "git" "podman")
    local missing_commands=()
    
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            missing_commands+=("$cmd")
        fi
    done
    
    if [[ ${#missing_commands[@]} -gt 0 ]]; then
        error "Missing required commands: ${missing_commands[*]}"
        echo "Please install the missing commands and run this script again."
        
        if [[ "$OS" == *"Ubuntu"* ]]; then
            echo "For Ubuntu, you can install them with:"
            echo "  sudo apt update"
            echo "  sudo apt install -y curl git"
            echo "  # For Podman, follow the installation guide at docs/installation/ubuntu-podman-setup.md"
        fi
        exit 1
    fi
    
    # Check for podman-compose
    if ! command -v "podman-compose" &> /dev/null; then
        warning "podman-compose not found. Attempting to install..."
        
        # Try to install podman-compose
        sudo curl -o /usr/local/bin/podman-compose https://raw.githubusercontent.com/containers/podman-compose/devel/podman_compose.py
        sudo chmod +x /usr/local/bin/podman-compose
        
        if command -v "podman-compose" &> /dev/null; then
            success "podman-compose installed successfully"
        else
            error "Failed to install podman-compose"
            exit 1
        fi
    fi
    
    success "All prerequisites met"
}

# Check system resources
check_system_resources() {
    log "Checking system resources..."
    
    # Check available memory (in GB)
    local total_mem=$(free -g | awk '/^Mem:/ {print $2}')
    if [[ $total_mem -lt 16 ]]; then
        warning "System has ${total_mem}GB RAM. Minimum 16GB recommended for development, 64GB for production."
    else
        success "System has ${total_mem}GB RAM"
    fi
    
    # Check available disk space (in GB)
    local available_space=$(df . | awk 'NR==2 {print int($4/1024/1024)}')
    if [[ $available_space -lt 50 ]]; then
        warning "Available disk space: ${available_space}GB. Minimum 100GB recommended."
    else
        success "Available disk space: ${available_space}GB"
    fi
    
    # Check CPU cores
    local cpu_cores=$(nproc)
    if [[ $cpu_cores -lt 4 ]]; then
        warning "System has ${cpu_cores} CPU cores. Minimum 4 cores recommended for development, 16 for production."
    else
        success "System has ${cpu_cores} CPU cores"
    fi
}

# Setup project directories
setup_directories() {
    log "Setting up project directories..."
    
    local dirs=(
        "data/repositories"
        "logs"
        "config/chromadb"
        "config/neo4j"
        "config/redis"
        "config/postgres"
        "config/nginx"
        "config/prometheus"
        "config/grafana"
        "config/elasticsearch"
        "config/kibana"
        "config/api"
        "config/worker"
        "ssl"
    )
    
    for dir in "${dirs[@]}"; do
        if [[ ! -d "$dir" ]]; then
            mkdir -p "$dir"
            log "Created directory: $dir"
        fi
    done
    
    # Set proper permissions
    chmod -R 755 config/
    chmod -R 777 data/
    chmod -R 777 logs/
    
    success "Project directories created and configured"
}

# Create environment file
create_environment() {
    log "Creating environment configuration..."
    
    if [[ ! -f .env ]]; then
        if [[ -f .env.example ]]; then
            cp .env.example .env
            log "Copied .env.example to .env"
        else
            # Create basic .env file
            cat > .env << 'EOF'
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
NEO4J_PASSWORD=codebase-rag-2024
NEO4J_DATABASE=neo4j

# Redis Configuration
REDIS_URL=redis://redis:6379

# PostgreSQL Configuration
POSTGRES_URL=postgresql://codebase_rag:codebase-rag-2024@postgres:5432/codebase_rag

# MinIO Configuration
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=codebase-rag
MINIO_SECRET_KEY=codebase-rag-2024

# Security Configuration
JWT_SECRET_KEY=change-this-secret-key-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Processing Configuration
MAX_CONCURRENT_REPOS=10
MAX_WORKERS=4
BATCH_SIZE=1000
TIMEOUT_SECONDS=300

# Embedding Configuration
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DEVICE=cpu

# Maven Configuration
MAVEN_ENABLED=true
MAVEN_RESOLUTION_STRATEGY=nearest
MAVEN_INCLUDE_TEST_DEPENDENCIES=false
EOF
            log "Created basic .env file"
        fi
        
        warning "Please review and update the .env file with your specific configuration"
        warning "IMPORTANT: Change default passwords and secrets before production deployment!"
    else
        log ".env file already exists, skipping creation"
    fi
    
    success "Environment configuration ready"
}

# Configure basic service settings
configure_services() {
    log "Configuring basic service settings..."
    
    # ChromaDB auth file
    if [[ ! -f config/chromadb/auth.txt ]]; then
        cat > config/chromadb/auth.txt << 'EOF'
admin:$2b$12$8jU8Ub8qZ4xvNK5gL9Mj8e7vG3hF2wQ9xC5nD8mE7fA6bH1cI9jK0l
user:$2b$12$9kV9Wc9rA5ywOL6hM0Nk9f8xH4iG3xR0yD6oE9nF8gB7cI2dJ0kL1m
EOF
        log "Created ChromaDB auth file"
    fi
    
    # Basic Redis configuration
    if [[ ! -f config/redis/redis.conf ]]; then
        cat > config/redis/redis.conf << 'EOF'
bind 0.0.0.0
port 6379
protected-mode no
maxmemory 2gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
EOF
        log "Created Redis configuration"
    fi
    
    # Basic PostgreSQL configuration
    if [[ ! -f config/postgres/postgresql.conf ]]; then
        cat > config/postgres/postgresql.conf << 'EOF'
listen_addresses = '*'
port = 5432
max_connections = 100
shared_buffers = 512MB
effective_cache_size = 1GB
work_mem = 32MB
maintenance_work_mem = 128MB
EOF
        log "Created PostgreSQL configuration"
    fi
    
    if [[ ! -f config/postgres/pg_hba.conf ]]; then
        cat > config/postgres/pg_hba.conf << 'EOF'
local   all             all                                     trust
host    all             all             127.0.0.1/32            md5
host    all             all             ::1/128                 md5
host    all             all             172.20.0.0/16           md5
EOF
        log "Created PostgreSQL HBA configuration"
    fi
    
    success "Basic service configurations created"
}

# System optimization
optimize_system() {
    log "Applying system optimizations..."
    
    # Check if we can modify system settings
    if [[ -w /etc/sysctl.conf ]]; then
        # Increase virtual memory for Elasticsearch
        if ! grep -q "vm.max_map_count=262144" /etc/sysctl.conf; then
            echo 'vm.max_map_count=262144' | sudo tee -a /etc/sysctl.conf
            sudo sysctl -p
            log "Increased vm.max_map_count for Elasticsearch"
        fi
    else
        warning "Cannot modify /etc/sysctl.conf. You may need to run:"
        warning "  echo 'vm.max_map_count=262144' | sudo tee -a /etc/sysctl.conf"
        warning "  sudo sysctl -p"
    fi
    
    # Create Podman network
    if ! podman network exists codebase-rag-network 2>/dev/null; then
        podman network create codebase-rag-network
        log "Created Podman network: codebase-rag-network"
    fi
    
    success "System optimizations applied"
}

# Start services
start_services() {
    log "Starting services with Podman Compose..."
    
    if [[ ! -f podman-compose.yml ]]; then
        error "podman-compose.yml not found in current directory"
        error "Make sure you're running this script from the project root directory"
        exit 1
    fi
    
    # Pull images first
    log "Pulling container images (this may take several minutes)..."
    podman-compose -f podman-compose.yml pull
    
    # Start services
    log "Starting services in background..."
    podman-compose -f podman-compose.yml up -d
    
    success "Services started successfully"
}

# Wait for services to be ready
wait_for_services() {
    log "Waiting for services to be ready..."
    
    local max_attempts=60
    local attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        if curl -f -s http://localhost:8080/api/v1/health >/dev/null 2>&1; then
            success "API service is ready!"
            break
        fi
        
        if [[ $attempt -eq $max_attempts ]]; then
            error "Services failed to start within expected time"
            echo "Check logs with: podman-compose -f podman-compose.yml logs"
            exit 1
        fi
        
        echo -n "."
        sleep 5
        ((attempt++))
    done
    
    # Test other services
    local services=(
        "http://localhost:8000/api/v1/heartbeat|ChromaDB"
        "http://localhost:7474|Neo4j"
        "http://localhost:9000/minio/health/live|MinIO"
    )
    
    for service in "${services[@]}"; do
        IFS='|' read -r url name <<< "$service"
        if curl -f -s "$url" >/dev/null 2>&1; then
            success "$name is ready"
        else
            warning "$name may not be ready yet"
        fi
    done
}

# Initialize databases
initialize_databases() {
    log "Initializing databases..."
    
    # Wait a bit more for Neo4j to be fully ready
    sleep 30
    
    # Initialize Neo4j schema if script exists
    if [[ -f scripts/neo4j/schema.cypher ]]; then
        log "Initializing Neo4j schema..."
        if podman exec codebase-rag-neo4j cypher-shell -u neo4j -p codebase-rag-2024 < scripts/neo4j/schema.cypher; then
            success "Neo4j schema initialized"
        else
            warning "Neo4j schema initialization failed - you may need to do this manually"
        fi
    fi
    
    # Create ChromaDB collection
    log "Creating ChromaDB collection..."
    if curl -X POST http://localhost:8000/api/v1/collections \
        -H "Content-Type: application/json" \
        -d '{"name": "codebase_chunks", "metadata": {"hnsw:space": "cosine"}}' >/dev/null 2>&1; then
        success "ChromaDB collection created"
    else
        warning "ChromaDB collection creation failed - collection may already exist"
    fi
}

# Display summary
display_summary() {
    echo
    echo "=================================================================="
    success "Codebase RAG System is now running!"
    echo "=================================================================="
    echo
    echo "🌐 Web Interfaces:"
    echo "   • API Documentation: http://localhost:8080/docs"
    echo "   • Neo4j Browser:     http://localhost:7474 (neo4j / codebase-rag-2024)"
    echo "   • MinIO Console:     http://localhost:9001 (codebase-rag / codebase-rag-2024)"
    echo "   • Grafana Dashboard: http://localhost:3000 (admin / codebase-rag-2024)"
    echo "   • Prometheus:        http://localhost:9090"
    echo "   • Jaeger Tracing:    http://localhost:16686"
    echo "   • Kibana Logs:       http://localhost:5601"
    echo
    echo "🔧 Management Commands:"
    echo "   • View logs:         podman-compose -f podman-compose.yml logs -f"
    echo "   • Stop services:     podman-compose -f podman-compose.yml down"
    echo "   • Restart services:  podman-compose -f podman-compose.yml restart"
    echo "   • View containers:   podman ps"
    echo
    echo "📚 Next Steps:"
    echo "   1. Review and update .env configuration"
    echo "   2. Configure repositories to index"
    echo "   3. Set up monitoring dashboards"
    echo "   4. Read the full documentation in docs/"
    echo
    warning "Remember to change default passwords before production use!"
    echo
}

# Main execution
main() {
    echo "=================================================================="
    echo "🚀 Codebase RAG System - Podman Quick Start"
    echo "=================================================================="
    echo
    
    detect_os
    log "Detected OS: $OS"
    
    check_prerequisites
    check_system_resources
    setup_directories
    create_environment
    configure_services
    optimize_system
    start_services
    wait_for_services
    initialize_databases
    display_summary
    
    success "Setup completed successfully!"
}

# Handle script interruption
trap 'error "Script interrupted"; exit 1' INT TERM

# Run main function
main "$@"