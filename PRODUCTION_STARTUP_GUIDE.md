# GraphRAG Production Startup Guide

## 🚀 **Quick Start (Recommended)**

```powershell
# Start the system
.\CLEAN-RESTART-V2.ps1

# Verify it's working  
.\HEALTH-CHECK.ps1

# Access the application
# Frontend: http://localhost:3000
# API: http://localhost:8082/api/v1/health/ready
```

## 📋 **Essential Scripts**

| Script | Purpose | When to Use |
|--------|---------|-------------|
| **CLEAN-RESTART-V2.ps1** | Complete system restart with v2 ChromaDB architecture | Daily startup, after changes |
| **STOP.ps1** | Safe shutdown with PID tracking (won't kill Claude Code) | End of day, maintenance |
| **HEALTH-CHECK.ps1** | Quick health verification | Troubleshooting, monitoring |

## ⚙️ **Configuration Files**

### Root `.env` (Backend Configuration)
```bash
# API Configuration
API_PORT=8082                    # Backend port
API_HOST=0.0.0.0

# ChromaDB v2 Configuration (CRITICAL)
CHROMA_HOST=localhost
CHROMA_PORT=8000
CHROMA_TENANT=default_tenant     # Required for v2 API
CHROMA_DATABASE=default_database # Required for v2 API

# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=codebase-rag-2024

# Redis Configuration
REDIS_URL=redis://localhost:6379
```

### Frontend `.env` (React Configuration)
```bash
# Frontend must match backend port
REACT_APP_API_URL=http://localhost:8082  # MUST match API_PORT above
SKIP_PREFLIGHT_CHECK=true
```

## 🎯 **System Architecture**

- **Frontend**: React on port 3000 → proxies to → **Backend** on port 8082
- **ChromaDB**: v2 tenant architecture on port 8000
- **Neo4j**: Graph database on port 7687  
- **Redis**: Cache on port 6379

## ✅ **Health Check Verification**

When working correctly, `.\HEALTH-CHECK.ps1` should show:

```json
{
  "status": "ready",
  "health_score": 100.0,
  "checks": {
    "chromadb": {
      "status": "healthy",
      "checks": {
        "v2_healthcheck": {"status": "pass"},
        "tenant": {"status": "pass", "tenant": "default_tenant"},
        "database": {"status": "pass", "database": "default_database"}
      }
    },
    "neo4j": {"status": "healthy"},
    "processor": {"status": "healthy"}
  }
}
```

## 🔧 **Troubleshooting**

### "System is starting up" Message
- **Cause**: Frontend can't reach backend API
- **Fix**: Check ports match between frontend/.env and root/.env
- **Test**: Open `http://localhost:3000/api/v1/health/ready` directly

### Port Conflicts
- **Check**: `netstat -ano | findstr ":8082"`
- **Fix**: Run `.\STOP.ps1` then `.\CLEAN-RESTART-V2.ps1`

### ChromaDB Errors
- **Verify**: `curl http://localhost:8000/api/v2/tenants/default_tenant`
- **Fix**: Restart Docker containers if needed

## 📁 **File Structure**

```
graf/
├── .env                         # Backend configuration
├── frontend/.env                # Frontend configuration  
├── CLEAN-RESTART-V2.ps1        # Main startup script
├── STOP.ps1                     # Safe shutdown script
├── HEALTH-CHECK.ps1             # Health verification
├── src/                         # Backend source code
└── frontend/                    # React frontend
    ├── package.json             # Has proxy: "http://localhost:8082"
    └── src/
```

## 🛡️ **Production Hardening**

1. **Minimal Script Set**: Only essential scripts remain
2. **Consistent Configuration**: Frontend and backend ports aligned
3. **v2 Architecture**: Modern ChromaDB multi-tenant setup
4. **Safe Shutdown**: PID tracking prevents killing other processes
5. **Health Monitoring**: Built-in system status verification

## 🗑️ **Cleanup Old Scripts** 

To remove debug/temporary scripts from troubleshooting:

```powershell
.\CLEANUP-DEBUG-SCRIPTS.ps1
```

This will remove all debug scripts while keeping the essential production set.

---

## 🎉 **Success Indicators**

- ✅ Frontend loads dashboard (not "System is starting up")
- ✅ Health check returns `"status": "ready"`  
- ✅ Can index repositories and run queries
- ✅ All database connections working (ChromaDB v2, Neo4j, Redis)

Your GraphRAG system is now production-ready with rock-solid startup/shutdown! 🚀