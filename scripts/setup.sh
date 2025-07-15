#!/bin/bash

# Codebase RAG Setup Script
# This script sets up the complete ChromaDB + Neo4j RAG environment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
    print_status "Docker is running"
}

# Check if Docker Compose is available
check_docker_compose() {
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose and try again."
        exit 1
    fi
    print_status "Docker Compose is available"
}

# Create necessary directories
create_directories() {
    print_status "Creating necessary directories..."
    
    directories=(
        "data/repositories"
        "data/chroma"
        "data/neo4j"
        "data/redis"
        "data/prometheus"
        "data/grafana"
        "data/elasticsearch"
        "logs"
        "ssl"
    )
    
    for dir in "${directories[@]}"; do
        mkdir -p "$dir"
        print_status "Created directory: $dir"
    done
}

# Set proper permissions
set_permissions() {
    print_status "Setting proper permissions..."
    
    # Make sure data directories are writable
    chmod 755 data/
    chmod 755 logs/
    
    # Neo4j specific permissions
    chmod 755 data/neo4j/
    
    # Elasticsearch specific permissions
    chmod 755 data/elasticsearch/
    
    # Make scripts executable
    chmod +x scripts/*.sh
    chmod +x scripts/*.py
    
    print_status "Permissions set successfully"
}

# Generate SSL certificates for production
generate_ssl_certificates() {
    print_status "Generating SSL certificates..."
    
    if [ ! -f "ssl/cert.pem" ] || [ ! -f "ssl/key.pem" ]; then
        openssl req -x509 -newkey rsa:4096 -keyout ssl/key.pem -out ssl/cert.pem -days 365 -nodes \
            -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
        print_status "SSL certificates generated"
    else
        print_status "SSL certificates already exist"
    fi
}

# Create environment file
create_env_file() {
    print_status "Creating environment file..."
    
    if [ ! -f ".env" ]; then
        cat > .env << EOF
# Environment configuration for Codebase RAG

# Application
APP_ENV=development
DEBUG=false

# API Configuration
API_HOST=0.0.0.0
API_PORT=8080
API_WORKERS=4

# ChromaDB Configuration
CHROMA_HOST=chromadb
CHROMA_PORT=8000
CHROMA_PERSIST_DIRECTORY=./data/chroma

# Neo4j Configuration
NEO4J_URI=bolt://neo4j:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=codebase-rag-2024
NEO4J_DATABASE=neo4j

# Redis Configuration
REDIS_URL=redis://:codebase-rag-2024@redis:6379

# PostgreSQL Configuration
POSTGRES_URL=postgresql://codebase_rag:codebase-rag-2024@postgres:5432/codebase_rag

# MinIO Configuration
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=codebase-rag
MINIO_SECRET_KEY=codebase-rag-2024

# Embedding Configuration
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384

# Processing Configuration
MAX_CHUNK_SIZE=1000
OVERLAP_SIZE=200
BATCH_SIZE=100
MAX_CONCURRENT_REPOS=10

# Monitoring
PROMETHEUS_URL=http://prometheus:9090
GRAFANA_URL=http://grafana:3000
JAEGER_URL=http://jaeger:16686

# Security
JWT_SECRET_KEY=your-secret-key-change-this-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
EOF
        print_status "Environment file created"
    else
        print_status "Environment file already exists"
    fi
}

# Pull Docker images
pull_docker_images() {
    print_status "Pulling Docker images..."
    docker-compose pull
    print_status "Docker images pulled successfully"
}

# Start services
start_services() {
    print_status "Starting services..."
    
    # Start infrastructure services first
    print_status "Starting infrastructure services..."
    docker-compose up -d chromadb neo4j redis postgres minio elasticsearch
    
    # Wait for services to be healthy
    print_status "Waiting for services to be healthy..."
    sleep 30
    
    # Check service health
    check_service_health
    
    # Start application services
    print_status "Starting application services..."
    docker-compose up -d api worker
    
    # Start monitoring services
    print_status "Starting monitoring services..."
    docker-compose up -d prometheus grafana jaeger kibana
    
    # Start nginx last
    print_status "Starting nginx..."
    docker-compose up -d nginx
    
    print_status "All services started successfully"
}

# Check service health
check_service_health() {
    print_status "Checking service health..."
    
    services=("chromadb" "neo4j" "redis" "postgres")
    
    for service in "${services[@]}"; do
        print_status "Checking $service health..."
        
        # Wait for service to be healthy
        timeout=60
        while [ $timeout -gt 0 ]; do
            if docker-compose ps $service | grep -q "healthy"; then
                print_status "$service is healthy"
                break
            fi
            sleep 5
            timeout=$((timeout - 5))
        done
        
        if [ $timeout -eq 0 ]; then
            print_error "$service failed to become healthy"
            exit 1
        fi
    done
}

# Initialize databases
initialize_databases() {
    print_status "Initializing databases..."
    
    # Initialize Neo4j schema
    print_status "Initializing Neo4j schema..."
    docker-compose exec neo4j cypher-shell -u neo4j -p codebase-rag-2024 < scripts/neo4j_schema.cypher
    
    # Initialize PostgreSQL schema
    print_status "Initializing PostgreSQL schema..."
    docker-compose exec postgres psql -U codebase_rag -d codebase_rag -f /docker-entrypoint-initdb.d/init_schema.sql
    
    # Initialize ChromaDB collections
    print_status "Initializing ChromaDB collections..."
    docker-compose exec api python scripts/init_chromadb.py
    
    print_status "Databases initialized successfully"
}

# Verify installation
verify_installation() {
    print_status "Verifying installation..."
    
    # Check API health
    if curl -f http://localhost:8080/health > /dev/null 2>&1; then
        print_status "API is responding"
    else
        print_error "API is not responding"
        exit 1
    fi
    
    # Check ChromaDB
    if curl -f http://localhost:8000/api/v1/heartbeat > /dev/null 2>&1; then
        print_status "ChromaDB is responding"
    else
        print_error "ChromaDB is not responding"
        exit 1
    fi
    
    # Check Neo4j
    if docker-compose exec neo4j cypher-shell -u neo4j -p codebase-rag-2024 "RETURN 1" > /dev/null 2>&1; then
        print_status "Neo4j is responding"
    else
        print_error "Neo4j is not responding"
        exit 1
    fi
    
    print_status "Installation verification completed successfully"
}

# Print service URLs
print_service_urls() {
    print_status "Service URLs:"
    echo "  API: http://localhost:8080"
    echo "  ChromaDB: http://localhost:8000"
    echo "  Neo4j Browser: http://localhost:7474"
    echo "  Grafana: http://localhost:3000 (admin/codebase-rag-2024)"
    echo "  Prometheus: http://localhost:9090"
    echo "  Jaeger: http://localhost:16686"
    echo "  Kibana: http://localhost:5601"
    echo "  MinIO: http://localhost:9001 (codebase-rag/codebase-rag-2024)"
}

# Main execution
main() {
    print_status "Starting Codebase RAG setup..."
    
    check_docker
    check_docker_compose
    create_directories
    set_permissions
    generate_ssl_certificates
    create_env_file
    pull_docker_images
    start_services
    initialize_databases
    verify_installation
    print_service_urls
    
    print_status "Setup completed successfully!"
    print_status "You can now start using the Codebase RAG system."
    print_status "Run 'docker-compose logs -f' to see the logs."
}

# Run main function
main "$@"