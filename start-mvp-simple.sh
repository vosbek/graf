#!/bin/bash

# Codebase RAG MVP - Ultra Simple Startup Script
# Optimized for local development with reduced resource usage

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting Codebase RAG MVP (Optimized)${NC}"
echo

# Check if podman is installed
if ! command -v podman &> /dev/null; then
    echo -e "${RED}❌ Podman is not installed. Please install Podman first.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Podman found${NC}"

# Use podman compose
COMPOSE_CMD="podman compose"

# Check if repos path is set
if [ -z "$REPOS_PATH" ]; then
    echo -e "${YELLOW}⚠️  REPOS_PATH not set. Please set it to your repositories directory:${NC}"
    echo "  export REPOS_PATH=/path/to/your/repos"
    echo "  ./start-mvp-simple.sh"
    echo
    echo -e "${YELLOW}Or edit mvp-compose-optimized.yml manually${NC}"
    echo
fi

# Update compose file with repos path if set
if [ ! -z "$REPOS_PATH" ]; then
    echo -e "${BLUE}📝 Updating compose file with repos path: $REPOS_PATH${NC}"
    sed -i.bak "s|/path/to/your/repos|$REPOS_PATH|g" mvp-compose-optimized.yml
fi

# Create directories
echo -e "${BLUE}📁 Creating directories...${NC}"
mkdir -p logs data

# Stop any existing containers
echo -e "${BLUE}🛑 Stopping any existing containers...${NC}"
$COMPOSE_CMD -f mvp-compose-optimized.yml down 2>/dev/null || true

# Pull and start
echo -e "${BLUE}📥 Starting services (optimized for local dev)...${NC}"
$COMPOSE_CMD -f mvp-compose-optimized.yml up -d --build

# Wait for services
echo -e "${BLUE}⏳ Waiting for services...${NC}"

# Simple wait for API
echo -n "Waiting for API..."
for i in {1..30}; do
    if curl -s http://localhost:8080/health > /dev/null 2>&1; then
        echo -e " ${GREEN}✅${NC}"
        break
    fi
    echo -n "."
    sleep 2
done

echo
echo -e "${GREEN}🎉 MVP is ready!${NC}"
echo
echo -e "${BLUE}Quick Start:${NC}"
echo "1. Open: http://localhost:8080/docs"
echo "2. Index a repo: curl -X POST 'http://localhost:8080/index' -H 'Content-Type: application/json' -d '{\"repo_path\":\"/your/repo\",\"repo_name\":\"my-repo\"}'"
echo "3. Find missing deps: curl 'http://localhost:8080/maven/conflicts'"
echo
echo -e "${BLUE}Resource Usage (Optimized):${NC}"
echo "• ChromaDB: 2GB RAM"
echo "• Neo4j: 4GB RAM"
echo "• API: 2GB RAM"
echo "• Total: ~8GB RAM"
echo
echo -e "${GREEN}Happy coding! 🚀${NC}"