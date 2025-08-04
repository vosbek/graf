# 🚀 GraphRAG Quick Start Guide

**One command to start your AI-powered codebase analysis platform.**

> Environment files:
> - Copy [.env.example](.env.example) to `.env` for local defaults
> - Windows users may copy [.env.windows.example](.env.windows.example) to `.env` for sensible Windows defaults
> - For advanced overrides, see [CONFIGURATION-GUIDE.md](CONFIGURATION-GUIDE.md)

## ✅ Environment Setup (once)

```powershell
# In repo root
Copy-Item .env.example .env -Force
# Or on Windows defaults:
# Copy-Item .env.windows.example .env -Force

# Verify key variables; see CONFIGURATION-GUIDE for full list
Get-Content .env | Select-String -Pattern "API_PORT|CHROMA_PORT|NEO4J_PORT|BEDROCK_MODEL_ID|AWS_REGION"
```

## 🧭 Compose Profiles

Choose one of the supported stacks:
- Services only (dev): [podman-compose-services-only.yml](podman-compose-services-only.yml)
- Full stack (prod/demo): [docker-compose.yml](docker-compose.yml)
- Minimal CI/lightweight: [mvp-compose.yml](mvp-compose.yml)

Match commands to your runtime:
- Podman: `podman-compose -f <file> up -d`
- Docker: `docker-compose -f <file> up -d`

## 🔗 Frontend → API config

If the frontend cannot reach the API, set the base URL:
- Development: frontend uses proxy to `http://localhost:8080`
- Override via environment: set `REACT_APP_API_BASE=http://localhost:8080` before `npm start`
- Ensure CORS is permissive in dev; production origins should be locked down per [src/config/settings.py](src/config/settings.py:197)

## ⚡ Instant Start

```powershell
# Full system (recommended for first-time users)
.\START.ps1

# That's it! 🎉
```

## 🎯 What You Get

After running `.\START.ps1`, you'll have:

- **🔍 AI-Powered Codebase Search** - Ask questions in plain English
- **📊 Dependency Graph Visualization** - See code relationships  
- **🤖 Struts Migration Planning** - GraphQL migration recommendations
- **💾 5 Core Services** - PostgreSQL, Redis, MinIO, ChromaDB, Neo4j
- **🌐 Web Interface** - Beautiful React frontend at http://localhost:3000

## 🎮 Command Options

### **Start Modes**
```powershell
.\START.ps1 -Mode full       # Complete system (default)
.\START.ps1 -Mode backend    # Services only (databases, APIs)
.\START.ps1 -Mode frontend   # Web interface only
.\START.ps1 -Mode mvp        # Minimal version for testing
```

### **Management Options**
```powershell
.\START.ps1 -Status          # Check what's running
.\START.ps1 -Clean           # Fresh start (removes old logs)
.\START.ps1 -SkipDeps        # Skip dependency checking (faster)
```

### **Quick Commands**
```powershell
# Fresh startup
.\START.ps1 -Clean

# Check system health
.\START.ps1 -Status

# Developer mode (backend only)
.\START.ps1 -Mode backend -SkipDeps
```

## 🌐 Your Running Services

Once started, access these URLs:

| Service | URL | Login | Purpose |
|---------|-----|-------|---------|
| **Web App** | http://localhost:3000 | None | Main interface |
| **API Server** | http://localhost:8080 | None | REST API |
| **MinIO Console** | http://localhost:9001 | `codebase-rag` / `codebase-rag-2024` | File upload |
| **Neo4j Browser** | http://localhost:7474 | `neo4j` / `codebase-rag-2024` | Graph database |
| **ChromaDB** | http://localhost:8000 | None | Vector search |

## 📋 Prerequisites

**Required:**
- **Windows 10/11** with PowerShell 5.1+
- **Podman Desktop** or **Docker Desktop**
- **Python 3.8+** 
- **8GB+ RAM** (16GB+ recommended)

**Optional:**
- **Node.js 16+** (for frontend development)
- **AWS Credentials** (for enhanced AI features)

### **Quick Install (if missing):**
```powershell
# Install Podman Desktop (recommended)
# Download from: https://podman-desktop.io/

# Install Python (if needed)
winget install Python.Python.3.11

# Install Node.js (if needed)  
winget install OpenJS.NodeJS
```

## 🎯 First Time Setup

1. **Clone and enter directory:**
   ```powershell
   git clone <your-repo> GraphRAG
   cd GraphRAG
   ```

2. **Start the system:**
   ```powershell
   .\START.ps1
   ```

3. **Wait for startup (2-3 minutes)** - watch the logs

4. **Open web interface:** http://localhost:3000

5. **Upload your first codebase** via the web interface

## 🔧 Troubleshooting

### **Common Issues**

**"Podman not found"**
```powershell
# Install Podman Desktop from https://podman-desktop.io/
# Or use Docker Desktop as alternative
```

**"Services failed to start"**
```powershell
# Check what's running
.\START.ps1 -Status

# Try clean restart
.\START.ps1 -Clean
```

**"Web interface not loading"**
```powershell
# Check if frontend dependencies are installed
cd frontend
npm install
cd ..

# Restart frontend only
.\START.ps1 -Mode frontend
```

**"Port conflicts"**
```powershell
# Check what's using ports
netstat -an | findstr "3000 8080 8000 7474 9001"

# Stop conflicting services or change ports in configs
```

### **Getting Help**

```powershell
# View real-time logs
Get-Content logs\start-*.log -Wait

# Check system status
.\START.ps1 -Status

# View container logs
podman logs codebase-rag-chromadb
podman logs codebase-rag-neo4j
```

## 🏆 Success Indicators

When everything is working, you'll see:

```
✅ PostgreSQL (port 5432): Running
✅ Redis (port 6379): Running  
✅ MinIO (port 9000/9001): Running
✅ ChromaDB (port 8000): Running
✅ Neo4j (port 7474): Running
✅ API Server (port 8080): Running
✅ Frontend (port 3000): Running

🎉 Your GraphRAG system is ready!
```

## 🚀 Next Steps

1. **Upload Code** - Use the web interface to add your repositories
2. **Ask Questions** - Try the AI chat: "What are the main features?"  
3. **Explore Graph** - Visualize code dependencies
4. **Plan Migration** - Get GraphQL migration recommendations

## ⚡ Power User Tips

```powershell
# Daily development workflow
.\START.ps1 -Mode backend -SkipDeps    # Start services
# ... develop ...
podman-compose down                     # Stop when done

# Production mode
.\START.ps1 -Clean                     # Fresh startup with logs

# Debugging mode  
.\START.ps1 -Mode backend              # Services only for debugging
```

---

## 📞 Support

- **Quick Issues:** Check `.\START.ps1 -Status`
- **Logs:** All logs are in `logs\` directory  
- **Documentation:** See `docs\` for detailed guides
- **GitHub Issues:** Report problems in the repository

**Transform your massive Struts applications into intelligently searchable knowledge bases! 🎯**