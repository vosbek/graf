# 🚀 Complete MVP Setup Guide

## Quick Start (2 Minutes)

### Option 1: Instant Local Setup (Recommended)
```bash
# 1. Clone and enter directory
git clone <this-repo> codebase-rag-mvp
cd codebase-rag-mvp

# 2. Start everything (builds frontend + installs dependencies + starts backend)
./start-mvp-with-ui.sh

# 3. Open browser
open http://localhost:8080
```

### Option 2: Docker Container Setup
```bash
# Build and start all services
docker-compose -f docker-compose-mvp-ui.yml up -d

# Access application
open http://localhost:8080
```

## Detailed Setup Instructions

### 📋 **Prerequisites**

**Required:**
- Python 3.8+ 
- Node.js 14+ (for frontend)
- Git

**Recommended:**
- 8GB+ RAM
- Docker & Docker Compose (for containerized setup)
- Neo4j Desktop (for advanced graph analysis)

### 🔧 **Environment Configuration**

The MVP includes complete environment configuration files:

#### 1. **Default Configuration (.env)**
```bash
# Already configured for local development
# Uses localhost services and safe defaults
# AI Agent works in fallback mode (no AWS required)
```

#### 2. **Custom Configuration (.env.template)**
```bash
# Copy template for customization
cp .env.template .env.custom

# Edit your custom settings
vim .env.custom

# Use custom config
export ENV_FILE=.env.custom
```

#### 3. **AWS Credentials (Optional)**
```bash
# For full AI Agent functionality
# See .aws-credentials.template for setup instructions

# Option A: Environment variables
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret

# Option B: AWS CLI profile
aws configure
export AWS_PROFILE=default

# Option C: IAM Role (production)
# Automatic credential management
```

### ⚙️ **Configuration Options**

#### **Database Settings**
```bash
# ChromaDB (Vector Search)
CHROMA_HOST=localhost
CHROMA_PORT=8000

# Neo4j (Knowledge Graph) 
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=codebase-rag-2024
```

#### **AI Agent Settings**
```bash
# Works with or without AWS
AI_AGENT_ENABLED=true
AI_AGENT_FALLBACK_MODE=true

# AWS Credentials (optional)
AWS_ACCESS_KEY_ID=your_key_here
AWS_SECRET_ACCESS_KEY=your_secret_here
AWS_DEFAULT_REGION=us-east-1
```

#### **Processing Settings**
```bash
# Repository analysis
REPOS_PATH=./data/repositories
MAX_CONCURRENT_REPOS=10
MAX_FILE_SIZE=1048576

# Maven analysis
MAVEN_ENABLED=true
MAVEN_LOCAL_REPO=~/.m2/repository
```

## 📦 **Installation Methods**

### Method 1: Automated Script (Recommended)
```bash
# Handles everything automatically
./start-mvp-with-ui.sh

# What it does:
# ✅ Checks Node.js and npm
# ✅ Installs frontend dependencies
# ✅ Builds React application
# ✅ Loads environment variables
# ✅ Installs Python dependencies
# ✅ Starts backend server
# ✅ Serves frontend at http://localhost:8080
```

### Method 2: Manual Installation
```bash
# 1. Frontend setup
cd frontend
npm install
npm run build
cd ..

# 2. Backend setup
cd mvp
pip install -r requirements.txt

# 3. Start server
python main.py
```

### Method 3: Docker Compose
```bash
# Full containerized setup
docker-compose -f docker-compose-mvp-ui.yml up -d

# Services included:
# ✅ ChromaDB vector database
# ✅ Neo4j graph database  
# ✅ FastAPI backend
# ✅ React frontend
# ✅ All dependencies installed
```

## 🎯 **First Use Workflow**

### 1. **Verify Installation**
```bash
# Check system is working
python3 verify-mvp.py

# Should show:
# ✅ All tests passed - MVP is ready to run!
```

### 2. **Access Web Interface**
```
Open: http://localhost:8080

You'll see:
✅ Dashboard with system status
✅ Navigation to all features
✅ Quick start guide
```

### 3. **Index Your First Repository**
```
1. Click "Index Repositories"
2. Enter path: /path/to/your/struts-app
3. Enter name: my-struts-app
4. Click "Index Repository"
5. Wait for processing to complete
```

### 4. **Explore Your Application**
```
Dashboard → Shows indexed repositories
Search → Find specific code patterns
AI Chat → Ask questions in natural language
Dependency Graph → Visual architecture exploration
Migration Planner → GraphQL recommendations
```

## 🛠️ **Troubleshooting**

### Common Issues

#### **Frontend Build Fails**
```bash
# Check Node.js version
node --version  # Should be 14+

# Clear cache and reinstall
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run build
```

#### **Backend Won't Start**
```bash
# Check Python version
python3 --version  # Should be 3.8+

# Install dependencies explicitly
cd mvp
pip install -r requirements.txt

# Check environment
python3 -c "import chromadb, neo4j, fastapi; print('Dependencies OK')"
```

#### **AI Agent Not Working**
```bash
# Check AWS credentials (optional)
aws sts get-caller-identity

# Check fallback mode (should work without AWS)
curl http://localhost:8080/agent/health

# Expected response:
{"status": "healthy", "agent_initialized": false, "fallback_mode": true}
```

#### **Database Connection Issues**
```bash
# Check services are running
curl http://localhost:8000/api/v1/heartbeat  # ChromaDB
curl http://localhost:7474                   # Neo4j

# For Docker setup
docker-compose ps

# For local setup, install databases separately:
# Neo4j: https://neo4j.com/download/
# ChromaDB: Installed via pip with MVP
```

### Performance Issues

#### **Slow Indexing**
```bash
# Reduce concurrent processing
export MAX_CONCURRENT_REPOS=5
export BATCH_SIZE=50

# Increase chunk size for large files
export CHUNK_SIZE=2000
```

#### **High Memory Usage**
```bash
# Reduce embedding model size
export EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Limit file size
export MAX_FILE_SIZE=524288  # 512KB
```

## 🔐 **Security Configuration**

### Local Development (Default)
```bash
# Authentication disabled
AUTH_ENABLED=false

# CORS allows all origins
CORS_ORIGINS=["*"]

# Default passwords (change for production)
NEO4J_PASSWORD=codebase-rag-2024
```

### Production Setup
```bash
# Enable authentication
AUTH_ENABLED=true
JWT_SECRET_KEY=your-super-secret-key

# Restrict CORS
CORS_ORIGINS=["https://yourdomain.com"]

# Strong passwords
NEO4J_PASSWORD=strong-random-password

# AWS IAM roles instead of keys
```

## 📊 **Resource Requirements**

### Minimum (Development)
- **RAM**: 4GB
- **CPU**: 2 cores
- **Storage**: 2GB
- **Repositories**: 1-5 small repos

### Recommended (Local MVP)
- **RAM**: 8GB
- **CPU**: 4 cores  
- **Storage**: 10GB
- **Repositories**: 5-20 medium repos

### Production (Enterprise)
- **RAM**: 32GB
- **CPU**: 8+ cores
- **Storage**: 100GB+
- **Repositories**: 20-500+ repos

## 🎉 **Success Verification**

After setup, you should be able to:

### ✅ **Web Interface Works**
- Dashboard loads at http://localhost:8080
- All navigation sections accessible
- System health shows green status

### ✅ **Repository Indexing Works**  
- Can add local repository paths
- Indexing completes without errors
- Repository appears in dashboard

### ✅ **Search Functionality Works**
- Can search for code patterns
- Results show relevant code snippets
- Search suggestions work

### ✅ **AI Chat Works**
- Can ask questions about codebase
- Gets helpful responses (even in fallback mode)
- Chat history maintains context

### ✅ **Visual Features Work**
- Dependency graph displays
- Migration planner generates recommendations
- Can export graphs and reports

## 📞 **Support**

### Getting Help
1. **Verification Script**: `python3 verify-mvp.py`
2. **Log Files**: Check `./logs/` directory
3. **Browser Console**: Check for JavaScript errors
4. **API Health**: Visit `http://localhost:8080/health`

### Common Solutions
- **Restart services**: `./start-mvp-with-ui.sh`
- **Clear data**: `rm -rf ./data/repositories/*`
- **Reset frontend**: `rm -rf frontend/node_modules && npm install`
- **Check dependencies**: `pip install -r mvp/requirements.txt`

---

**🎯 Your MVP is now ready to transform legacy application analysis with AI-powered insights and visual exploration!**