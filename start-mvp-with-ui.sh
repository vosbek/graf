#!/bin/bash

# Start MVP with Web UI
# This script builds the React frontend and starts the backend with UI serving

set -e

echo "🚀 Starting Codebase RAG MVP with Web UI..."

# Check if we're in the right directory
if [ ! -f "mvp/main.py" ]; then
    echo "❌ Error: Please run this script from the root directory (where mvp/ folder is located)"
    exit 1
fi

# Install frontend dependencies if needed
if [ ! -d "frontend/node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    cd frontend
    npm install
    cd ..
fi

# Build the React frontend
echo "🔨 Building React frontend..."
cd frontend
npm run build
cd ..

# Check if build was successful
if [ ! -d "frontend/build" ]; then
    echo "❌ Frontend build failed"
    exit 1
fi

echo "✅ Frontend built successfully"

# Load environment variables from .env file if it exists
if [ -f ".env" ]; then
    echo "📝 Loading environment variables from .env file..."
    export $(grep -v '^#' .env | xargs)
else
    echo "⚠️  No .env file found, using defaults..."
fi

# Set default environment variables (fallback if not in .env)
export REPOS_PATH="${REPOS_PATH:-./data/repositories}"
export CHROMA_HOST="${CHROMA_HOST:-localhost}"
export CHROMA_PORT="${CHROMA_PORT:-8000}"
export NEO4J_URI="${NEO4J_URI:-bolt://localhost:7687}"
export NEO4J_USERNAME="${NEO4J_USERNAME:-neo4j}"
export NEO4J_PASSWORD="${NEO4J_PASSWORD:-codebase-rag-2024}"
export LOG_LEVEL="${LOG_LEVEL:-INFO}"
export APP_ENV="${APP_ENV:-development}"
export API_HOST="${API_HOST:-0.0.0.0}"
export API_PORT="${API_PORT:-8080}"

# Create data directories
mkdir -p "$REPOS_PATH"

echo "🐍 Starting Python backend with UI serving..."

# Start the MVP with UI serving enabled
cd mvp
python main.py

echo "✅ Codebase RAG MVP with Web UI is now running!"
echo "📱 Access the web interface at: http://localhost:8080"
echo "📚 API documentation at: http://localhost:8080/docs"