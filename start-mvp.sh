#!/bin/bash

# Codebase RAG MVP - Simple Startup Script
# This script starts the minimal viable product for local development

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=================================================================="
echo -e "🚀 Starting Codebase RAG MVP"
echo -e "==================================================================${NC}"
echo

# Check if podman is installed
if ! command -v podman &> /dev/null; then
    echo -e "${RED}❌ Podman is not installed or not in PATH${NC}"
    echo "Please install Podman first."
    exit 1
fi

echo -e "${GREEN}✅ Podman found${NC}"

# Check if podman-compose is available
if ! command -v podman-compose &> /dev/null; then
    echo -e "${YELLOW}⚠️  podman-compose not found, using podman compose${NC}"
    COMPOSE_CMD="podman compose"
else
    echo -e "${GREEN}✅ podman-compose found${NC}"
    COMPOSE_CMD="podman-compose"
fi

# Create necessary directories
echo -e "${BLUE}📁 Creating directories...${NC}"
mkdir -p logs data

# Check if local repos path is set
if [ -z "$REPOS_PATH" ]; then
    echo -e "${YELLOW}⚠️  REPOS_PATH not set in environment${NC}"
    echo "Please set REPOS_PATH to point to your local repositories:"
    echo "  export REPOS_PATH=/path/to/your/repos"
    echo "  OR"
    echo "  Update the mvp-compose.yml file to point to your repos directory"
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
    fi
fi

# Update compose file with repos path if set
if [ ! -z "$REPOS_PATH" ]; then
    echo -e "${BLUE}📝 Updating compose file with repos path...${NC}"
    sed -i.bak "s|/path/to/your/repos|$REPOS_PATH|g" mvp-compose.yml
    echo -e "${GREEN}✅ Updated mvp-compose.yml with $REPOS_PATH${NC}"
fi

# Stop any existing containers
echo -e "${BLUE}🛑 Stopping any existing containers...${NC}"
$COMPOSE_CMD -f mvp-compose.yml down 2>/dev/null || true

# Pull latest images
echo -e "${BLUE}📥 Pulling latest images...${NC}"
$COMPOSE_CMD -f mvp-compose.yml pull

# Build the API container
echo -e "${BLUE}🔨 Building API container...${NC}"
$COMPOSE_CMD -f mvp-compose.yml build

# Start the services
echo -e "${BLUE}🚀 Starting services...${NC}"
$COMPOSE_CMD -f mvp-compose.yml up -d

# Wait for services to be ready
echo -e "${BLUE}⏳ Waiting for services to be ready...${NC}"

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

# Wait for Neo4j
echo -n "Waiting for Neo4j..."
for i in {1..60}; do
    if curl -s http://localhost:7474 > /dev/null 2>&1; then
        echo -e " ${GREEN}✅${NC}"
        break
    fi
    echo -n "."
    sleep 2
done

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
echo -e "${GREEN}=================================================================="
echo -e "🎉 MVP is now running!"
echo -e "==================================================================${NC}"
echo
echo -e "${BLUE}🌐 Available Endpoints:${NC}"
echo "   • API Documentation: http://localhost:8080/docs"
echo "   • Health Check:      http://localhost:8080/health"
echo "   • Search API:        http://localhost:8080/search?q=your-query"
echo "   • ChromaDB:          http://localhost:8000"
echo "   • Neo4j Browser:     http://localhost:7474 (neo4j / codebase-rag-2024)"
echo
echo -e "${BLUE}📖 Quick Start Guide:${NC}"
echo
echo "1. Index a repository:"
echo '   curl -X POST "http://localhost:8080/index" \'
echo '     -H "Content-Type: application/json" \'
echo '     -d '"'"'{"repo_path": "/path/to/your/repo", "repo_name": "my-repo"}'"'"''
echo
echo "2. Search your code:"
echo '   curl "http://localhost:8080/search?q=function%20authentication"'
echo
echo "3. List repositories:"
echo '   curl "http://localhost:8080/repositories"'
echo
echo "4. View system status:"
echo '   curl "http://localhost:8080/status"'
echo
echo "5. Analyze Maven dependencies (for Java projects):"
echo '   curl "http://localhost:8080/maven/dependencies/org.springframework/spring-core/5.3.21"'
echo
echo "6. Find dependency conflicts:"
echo '   curl "http://localhost:8080/maven/conflicts"'
echo
echo -e "${BLUE}🛠️  Management Commands:${NC}"
echo "   • View logs:         $COMPOSE_CMD -f mvp-compose.yml logs -f"
echo "   • Stop services:     $COMPOSE_CMD -f mvp-compose.yml down"  
echo "   • Restart services:  $COMPOSE_CMD -f mvp-compose.yml restart"
echo "   • Check status:      $COMPOSE_CMD -f mvp-compose.yml ps"
echo
echo -e "${YELLOW}📝 Next Steps:${NC}"
echo "   1. Open http://localhost:8080/docs in your browser"
echo "   2. Index your repositories using the /index endpoint"
echo "   3. Start searching your code with semantic queries"
echo
echo -e "${GREEN}Happy coding! 🚀${NC}"
echo