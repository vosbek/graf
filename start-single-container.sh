#!/bin/bash

# Ultra-minimal single container startup
# Perfect for users who just want semantic search without dependency analysis

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}🚀 Starting Ultra-Minimal Codebase RAG (Single Container)${NC}"
echo

# Check podman
if ! command -v podman &> /dev/null; then
    echo "❌ Podman required. Install from: https://podman.io"
    exit 1
fi

echo -e "${GREEN}✅ Podman found${NC}"

# Check repos path
if [ -z "$REPOS_PATH" ]; then
    echo -e "${YELLOW}⚠️  Set REPOS_PATH first:${NC}"
    echo "  export REPOS_PATH=/path/to/your/repos"
    echo "  ./start-single-container.sh"
    exit 1
fi

echo -e "${BLUE}📝 Using repos: $REPOS_PATH${NC}"

# Update compose file
sed -i.bak "s|/path/to/your/repos|$REPOS_PATH|g" single-container-compose.yml

# Create directories
mkdir -p logs data

# Start ChromaDB first (required for single container to connect)
echo -e "${BLUE}🗄️  Starting ChromaDB...${NC}"
podman run -d --name chromadb-temp -p 8000:8000 chromadb/chroma:latest

# Wait for ChromaDB
echo -n "Waiting for ChromaDB..."
for i in {1..30}; do
    if curl -s http://localhost:8000/api/v1/heartbeat > /dev/null 2>&1; then
        echo -e " ${GREEN}✅${NC}"
        break
    fi
    echo -n "."
    sleep 2
done

# Start single container
echo -e "${BLUE}🚀 Starting single container...${NC}"
podman compose -f single-container-compose.yml up -d --build

# Wait for API
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
echo -e "${GREEN}🎉 Ultra-minimal setup ready!${NC}"
echo
echo -e "${BLUE}What you get:${NC}"
echo "• Semantic search across repositories"
echo "• Simple indexing and querying"
echo "• No dependency analysis (simplified)"
echo "• Only 4GB RAM required"
echo
echo -e "${BLUE}Quick start:${NC}"
echo "1. Open: http://localhost:8080/docs"
echo "2. Index: curl -X POST 'http://localhost:8080/index' -d '{\"repo_path\":\"/your/repo\"}'"
echo "3. Search: curl 'http://localhost:8080/search?q=authentication'"
echo
echo -e "${BLUE}Stop:${NC} podman compose -f single-container-compose.yml down && podman stop chromadb-temp"
echo