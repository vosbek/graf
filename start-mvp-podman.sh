#!/bin/bash

# Codebase RAG MVP - Podman-only Startup Script
# For systems with only Podman (no docker-compose or podman-compose)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=================================================================="
echo -e "🚀 Starting Codebase RAG MVP (Podman-only)"
echo -e "==================================================================${NC}"
echo

# Check if podman is installed
if ! command -v podman &> /dev/null; then
    echo -e "${RED}❌ Podman is not installed or not in PATH${NC}"
    echo "Please install Podman first."
    exit 1
fi

echo -e "${GREEN}✅ Podman found${NC}"

# Create necessary directories
echo -e "${BLUE}📁 Creating directories...${NC}"
mkdir -p logs data

# Load .env file if it exists
if [ -f ".env" ]; then
    echo -e "${BLUE}📋 Loading configuration from .env file...${NC}"
    export $(grep -v '^#' .env | xargs)
    echo -e "${GREEN}✅ Configuration loaded${NC}"
else
    echo -e "${YELLOW}💡 No .env file found. Copy .env.example to .env to configure repositories${NC}"
fi

# Check if local repos path is set
if [ -z "$REPOS_PATH" ]; then
    echo -e "${YELLOW}⚠️  REPOS_PATH not set in environment${NC}"
    echo "Please set REPOS_PATH to point to your local repositories:"
    echo "  export REPOS_PATH=/path/to/your/repos"
    echo
    
    # Default suggestion
    DEFAULT_REPOS_PATH="$HOME/repos"
    if [ -d "$DEFAULT_REPOS_PATH" ]; then
        echo -e "${BLUE}Found potential repos directory: $DEFAULT_REPOS_PATH${NC}"
        read -p "Use this directory? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            export REPOS_PATH="$DEFAULT_REPOS_PATH"
            echo -e "${GREEN}✅ Using $REPOS_PATH${NC}"
        fi
    fi
    
    if [ -z "$REPOS_PATH" ]; then
        echo -e "${YELLOW}Continuing without REPOS_PATH set - you'll need to index repos manually${NC}"
        echo
        REPOS_PATH="/path/to/your/repos"
    fi
fi

# Create a network
echo -e "${BLUE}🌐 Creating Podman network...${NC}"
podman network exists codebase-rag-network || podman network create codebase-rag-network

# Stop and remove existing containers
echo -e "${BLUE}🛑 Stopping any existing containers...${NC}"
podman stop codebase-rag-chromadb codebase-rag-neo4j codebase-rag-api 2>/dev/null || true
podman rm codebase-rag-chromadb codebase-rag-neo4j codebase-rag-api 2>/dev/null || true

# Start ChromaDB
echo -e "${BLUE}🚀 Starting ChromaDB...${NC}"
CHROMADB_PORT=${CHROMADB_PORT:-8001}
podman run -d \
  --replace \
  --name codebase-rag-chromadb \
  --network codebase-rag-network \
  -p ${CHROMADB_PORT}:8000 \
  -v chromadb_data:/chroma/chroma \
  -e CHROMA_DB_IMPL=clickhouse \
  -e CLICKHOUSE_HOST=localhost \
  -e CLICKHOUSE_PORT=8123 \
  docker.io/chromadb/chroma:latest

# Start Neo4j
echo -e "${BLUE}🚀 Starting Neo4j...${NC}"
NEO4J_HTTP_PORT=${NEO4J_HTTP_PORT:-7474}
NEO4J_BOLT_PORT=${NEO4J_BOLT_PORT:-7687}
NEO4J_PASSWORD=${NEO4J_PASSWORD:-codebase-rag-2024}
podman run -d \
  --replace \
  --name codebase-rag-neo4j \
  --network codebase-rag-network \
  -p ${NEO4J_HTTP_PORT}:7474 \
  -p ${NEO4J_BOLT_PORT}:7687 \
  -v neo4j_data:/data \
  -v neo4j_logs:/logs \
  -e NEO4J_AUTH=neo4j/${NEO4J_PASSWORD} \
  -e NEO4J_dbms_memory_heap_initial__size=1G \
  -e NEO4J_dbms_memory_heap_max__size=2G \
  -e NEO4J_dbms_memory_pagecache_size=1G \
  docker.io/library/neo4j:5.15

# Build API container from local Dockerfile
echo -e "${BLUE}🔨 Building API container...${NC}"
podman build -t codebase-rag-api:latest -f mvp/Dockerfile.api mvp/

# Start API
echo -e "${BLUE}🚀 Starting API...${NC}"
API_PORT=${API_PORT:-8082}
CHROMADB_HOST=${CHROMADB_HOST:-codebase-rag-chromadb}
NEO4J_HOST=${NEO4J_HOST:-codebase-rag-neo4j}
podman run -d \
  --replace \
  --name codebase-rag-api \
  --network codebase-rag-network \
  -p ${API_PORT}:8080 \
  -v "${REPOS_PATH}:/repos:ro" \
  -e CHROMADB_HOST=${CHROMADB_HOST} \
  -e CHROMADB_PORT=8000 \
  -e NEO4J_HOST=${NEO4J_HOST} \
  -e NEO4J_PORT=7687 \
  -e NEO4J_USER=neo4j \
  -e NEO4J_PASSWORD=${NEO4J_PASSWORD} \
  -e REPOS_PATH=/repos \
  codebase-rag-api:latest

# Wait for services to be ready
echo -e "${BLUE}⏳ Waiting for services to be ready...${NC}"

# Wait for ChromaDB
echo -n "Waiting for ChromaDB..."
for i in {1..30}; do
    if curl -s http://localhost:${CHROMADB_PORT}/api/v1/heartbeat > /dev/null 2>&1; then
        echo -e " ${GREEN}✅${NC}"
        break
    fi
    echo -n "."
    sleep 2
done

# Wait for Neo4j
echo -n "Waiting for Neo4j..."
for i in {1..60}; do
    if curl -s http://localhost:${NEO4J_HTTP_PORT} > /dev/null 2>&1; then
        echo -e " ${GREEN}✅${NC}"
        break
    fi
    echo -n "."
    sleep 2
done

# Wait for API
echo -n "Waiting for API..."
for i in {1..30}; do
    if curl -s http://localhost:${API_PORT}/health > /dev/null 2>&1; then
        echo -e " ${GREEN}✅${NC}"
        break
    fi
    echo -n "."
    sleep 2
done

echo
echo -e "${GREEN}=================================================================="
echo -e "🎉 MVP is now running!"
echo -e "==================================================================${NC}"
echo
echo -e "${BLUE}🌐 Available Endpoints:${NC}"
echo "   • API Documentation: http://localhost:${API_PORT}/docs"
echo "   • Health Check:      http://localhost:${API_PORT}/health"
echo "   • Search API:        http://localhost:${API_PORT}/search?q=your-query"
echo "   • ChromaDB:          http://localhost:${CHROMADB_PORT}"
echo "   • Neo4j Browser:     http://localhost:${NEO4J_HTTP_PORT} (neo4j / ${NEO4J_PASSWORD})"
echo
echo -e "${BLUE}📖 Quick Start Guide:${NC}"
echo
echo "1. Index a repository:"
echo "   curl -X POST \"http://localhost:${API_PORT}/index\" \\"
echo '     -H "Content-Type: application/json" \'
echo '     -d '"'"'{"repo_path": "/path/to/your/repo", "repo_name": "my-repo"}'"'"''
echo
echo "2. Search your code:"
echo "   curl \"http://localhost:${API_PORT}/search?q=function%20authentication\""
echo
echo "3. Find dependency conflicts:"
echo "   curl \"http://localhost:${API_PORT}/maven/conflicts\""
echo
echo -e "${BLUE}🛠️  Management Commands:${NC}"
echo "   • View logs:         podman logs codebase-rag-api"
echo "   • Stop services:     podman stop codebase-rag-chromadb codebase-rag-neo4j codebase-rag-api"
echo "   • Check status:      podman ps"
echo
echo -e "${YELLOW}📝 Next Steps:${NC}"
echo "   1. Open http://localhost:${API_PORT}/docs in your browser"
echo "   2. Index your repositories using the /index endpoint"
echo "   3. Use dependency analysis to find missing repositories"
echo
echo -e "${GREEN}Happy coding! 🚀${NC}"
echo