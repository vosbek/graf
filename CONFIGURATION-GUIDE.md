# ⚙️ GraphRAG Configuration Guide

**Simplified configuration management for your GraphRAG deployment.**

---

## 🔑 Environment Variables Reference

Below is a consolidated map of effective environment variables consumed by the application. Defaults are shown from [src/config/settings.py](src/config/settings.py:21).

### Application
- APP_ENV: Environment name (development|production). Default: development
- DEBUG: Enable auto-reload and verbose logging. Default: false
- LOG_LEVEL: Logging level (DEBUG|INFO|WARNING|ERROR|CRITICAL). Default: INFO

### API
- API_HOST: Bind host. Default: 0.0.0.0
- API_PORT: API port. Default: 8080
- API_WORKERS: Uvicorn workers. Default: 4

### ChromaDB
- CHROMA_HOST: Host for Chroma v2 API. Default: localhost
- CHROMA_PORT: Port for Chroma v2 API. Default: 8000
- CHROMA_COLLECTION_NAME: Collection name. Default: codebase_chunks
- CHROMA_PERSIST_DIRECTORY: Local persist path (if applicable). Default: ./data/chroma
- CHROMA_TENANT: Optional tenant for v2 collections. Default: unset

### Neo4j
- NEO4J_URI: Bolt URI. Default: bolt://localhost:7687
- NEO4J_USERNAME: Username. Default: neo4j
- NEO4J_PASSWORD: Password. Default: codebase-rag-2024
- NEO4J_DATABASE: Database name. Default: neo4j

### Redis
- REDIS_URL: Redis URL. Default: redis://localhost:6379
- REDIS_PASSWORD: Password. Default: unset

### PostgreSQL
- POSTGRES_URL: Connection URL. Default: postgresql://user:password@localhost:5432/codebase_rag

### MinIO
- MINIO_ENDPOINT: host:port. Default: localhost:9000
- MINIO_ACCESS_KEY: Default: minioadmin
- MINIO_SECRET_KEY: Default: minioadmin
- MINIO_SECURE: Use TLS (true|false). Default: false

### Processing and Chunking
- MAX_CONCURRENT_REPOS: Default: 10
- MAX_WORKERS: Default: 4
- BATCH_SIZE: Default: 100
- TIMEOUT_SECONDS: Default: 300
- MAX_CHUNK_SIZE: Default: 1000
- MIN_CHUNK_SIZE: Default: 100
- OVERLAP_SIZE: Default: 200

### Maven
- MAVEN_ENABLED: Default: true
- MAVEN_RESOLUTION_STRATEGY: Default: nearest
- MAVEN_INCLUDE_TEST_DEPENDENCIES: Default: false

### Security
- AUTH_ENABLED: Default: false
- JWT_SECRET_KEY: Default: change-this-secret-key
- JWT_ALGORITHM: Default: HS256
- JWT_EXPIRATION_HOURS: Default: 24

### Monitoring
- PROMETHEUS_ENABLED: Default: true
- PROMETHEUS_PORT: Default: 9090
- JAEGER_ENABLED: Default: false
- JAEGER_ENDPOINT: Default: http://localhost:14268/api/traces

### File Processing
- MAX_FILE_SIZE: Max bytes per file. Default: 1048576
- SUPPORTED_EXTENSIONS: Default list covers .py, .java, .js, .ts, .go, .rs, .cpp, .c, .h, .hpp
- EXCLUDE_PATTERNS: Default excludes node_modules, target, .git, build, __pycache__

### Repositories
- WORKSPACE_DIR: Default: ./data/repositories
- GIT_TIMEOUT: Default: 300

### Cache and Performance
- CACHE_TTL: Default: 300
- CACHE_SIZE: Default: 1000
- QUERY_TIMEOUT: Default: 30
- CONNECTION_POOL_SIZE: Default: 10

### AWS Bedrock / LLM (required to enable Chat)
- BEDROCK_MODEL_ID: e.g., anthropic.claude-3-7-sonnet-2025-05-08
- AWS_REGION: e.g., us-east-1
- AWS_PROFILE: Profile to resolve credentials (optional)
- AWS_ACCESS_KEY_ID: Alternative to profile (optional)
- AWS_SECRET_ACCESS_KEY: Alternative to profile (optional)
- LLM_MAX_INPUT_TOKENS: Default: 8000
- LLM_MAX_OUTPUT_TOKENS: Default: 1024
- LLM_REQUEST_TIMEOUT_SECONDS: Default: 30.0

Validation behavior:
- Chat is only enabled when BEDROCK_MODEL_ID and AWS_REGION pass validation and credentials are provided via AWS_PROFILE or ACCESS_KEY/SECRET. See [strands/providers/bedrock_provider.py](strands/providers/bedrock_provider.py:34).
- The application registers chat routes only when validated. See [src/api/routes/chat.py](src/api/routes/chat.py:59) and feature flagging described in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## 🔐 Security Notes

- In production, set AUTH_ENABLED=true and provide a strong JWT_SECRET_KEY.
- Restrict CORS origins in production: see [src/config/settings.py](src/config/settings.py:197) for production CORS policy.
- Never commit secrets. Use deployment-specific .env files and secret managers.

## 🧪 Example .env (development)

```env
APP_ENV=development
LOG_LEVEL=INFO

API_HOST=0.0.0.0
API_PORT=8080

CHROMA_HOST=localhost
CHROMA_PORT=8000
CHROMA_COLLECTION_NAME=codebase_chunks

NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=codebase-rag-2024
NEO4J_DATABASE=neo4j

# Optional Chat (requires valid AWS credentials)
BEDROCK_MODEL_ID=anthropic.claude-3-7-sonnet-2025-05-08
AWS_REGION=us-east-1
AWS_PROFILE=default
LLM_MAX_INPUT_TOKENS=8000
LLM_MAX_OUTPUT_TOKENS=1024
LLM_REQUEST_TIMEOUT_SECONDS=30
```

## 🧩 Service Ports Matrix

- Frontend: 3000
- API: 8080
- ChromaDB: 8000
- Neo4j: 7474 (browser), 7687 (bolt as configured in [src/config/settings.py](src/config/settings.py:42))
- PostgreSQL: 5432
- Redis: 6379
- MinIO: 9000 (API), 9001 (console)

Adjust via .env or compose files (see resource sections already present above).

## 🧪 Readiness and Health

Use these endpoints to validate configuration and dependencies:
- API liveness: GET /api/v1/health/
- API readiness and component flags: GET /api/v1/health/enhanced/state (see [src/main.py](src/main.py:481))
- Neo4j probe: GET /api/v1/health/neo4j-probe (see [src/main.py](src/main.py:439))
- Graph diagnostics (if registered): GET /api/v1/graph/diag
- Chroma v2 healthcheck (container): GET http://CHROMA_HOST:CHROMA_PORT/api/v2/healthcheck

## 🧱 Production Overrides

Create docker-compose.prod.yml and override critical settings (replicas, TLS on Nginx, memory). See the Production Configuration section already in this guide for a template. Ensure HTTPS termination and set CORS allow_origins to your real domains in production.

## 📋 Configuration Overview

After the codebase cleanup, you now have **3 primary configuration files** instead of 9+ scattered YAML files. This guide explains when to use each configuration and how to customize them.

---

## 🎯 Primary Configuration Files (KEEP)

### **1. `podman-compose-services-only.yml` - RECOMMENDED**
**Purpose:** Core infrastructure services only (databases, storage)  
**Use Case:** Development, backend-only deployments, when you want to run API separately

```yaml
# What it includes:
✅ PostgreSQL (metadata storage)
✅ Redis (caching) 
✅ MinIO (file storage)
✅ ChromaDB (vector search)
✅ Neo4j (graph database)

❌ No API server (run separately)
❌ No frontend (run separately)
```

**When to use:**
- Daily development work
- Backend service testing
- When you want to run API server manually for debugging
- Minimal resource usage

**Startup command:**
```powershell
podman-compose -f podman-compose-services-only.yml up -d
```

### **2. `docker-compose.yml` - FULL ENTERPRISE**
**Purpose:** Complete enterprise stack with all services  
**Use Case:** Production deployments, full-system testing, demos

```yaml
# What it includes:
✅ All services from services-only
✅ API server container
✅ Worker containers  
✅ Monitoring (Prometheus)
✅ Reverse proxy (Nginx)
✅ Health checks

🎯 Production-ready
🔧 Full observability
🚀 Scalable architecture
```

**When to use:**
- Production deployments
- Full integration testing  
- Client demonstrations
- Performance testing

**Startup command:**
```powershell
docker-compose up -d
```

### **3. `mvp-compose.yml` - MINIMAL TESTING**
**Purpose:** Minimal viable product for quick testing  
**Use Case:** CI/CD testing, lightweight development, resource-constrained environments

```yaml
# What it includes:
✅ Essential databases only
✅ Minimal resource allocation
✅ Single-container API
✅ Fast startup time

⚡ Quick startup (< 2 minutes)
🔬 Testing and validation
💾 Low resource usage
```

**When to use:**
- Automated testing pipelines
- Low-resource development machines
- Quick validation and demos
- CI/CD environments

**Startup command:**
```powershell
podman-compose -f mvp-compose.yml up -d
```

---

## 🗂️ Archived Configuration Files (MOVED TO archive/)

The following configuration files have been moved to `archive/compose-configs/` as they were experimental or redundant:

### **Archived Files:**
- ~~`podman-compose-windows.yml`~~ - Windows-specific (now unified)
- ~~`mvp-compose-optimized.yml`~~ - Performance variant (merged into main)
- ~~`single-container-compose.yml`~~ - Single container experiment  
- ~~`docker-compose-mvp-ui.yml`~~ - UI-focused variant (redundant)
- ~~`podman-compose.yml`~~ - Generic version (replaced by specific versions)

**Why archived:**
- **Redundant functionality** - Same features as primary configs
- **Maintenance burden** - Multiple configs for same purpose
- **Configuration drift** - Easy for configs to get out of sync
- **User confusion** - Too many similar options

---

## 🎮 Quick Start Commands

### **Recommended Startup Patterns**

#### **Daily Development (Most Common)**
```powershell
# Start core services only
.\START.ps1 -Mode backend

# Or manually:
podman-compose -f podman-compose-services-only.yml up -d

# Then run API and frontend separately for development
python -m uvicorn src.main:app --reload --port 8080
cd frontend && npm start
```

#### **Full System Testing**  
```powershell
# Complete system startup
.\START.ps1 -Mode full

# Or manually:
docker-compose up -d
```

#### **Quick Testing/CI**
```powershell
# Minimal MVP mode
.\START.ps1 -Mode mvp

# Or manually:
podman-compose -f mvp-compose.yml up -d
```

---

## ⚙️ Configuration Customization

### **Environment Variables (.env)**

The `.env` file contains all customizable settings:

```bash
# === CORE SETTINGS ===
APP_ENV=development
API_HOST=0.0.0.0
API_PORT=8080

# === DATABASE CONFIGURATION ===
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=codebase_rag
POSTGRES_USER=codebase_rag
POSTGRES_PASSWORD=codebase-rag-2024

# === SERVICE PORTS ===
CHROMA_PORT=8000
NEO4J_PORT=7474
REDIS_PORT=6379
MINIO_PORT=9000
MINIO_CONSOLE_PORT=9001

# === PERFORMANCE TUNING ===
MAX_CONCURRENT_REPOS=10
BATCH_SIZE=100
CHUNK_SIZE=1000

# === AWS INTEGRATION ===
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=us-east-1
```

### **Port Configuration**

**Default Ports:**
| Service | Port | Purpose | Customizable |
|---------|------|---------|--------------|
| Frontend | 3000 | React development server | ✅ |
| API Server | 8080 | FastAPI backend | ✅ |
| ChromaDB | 8000 | Vector database API | ✅ |
| Neo4j | 7474 | Graph database browser | ✅ |
| PostgreSQL | 5432 | Relational database | ✅ |
| Redis | 6379 | Cache and sessions | ✅ |
| MinIO API | 9000 | Object storage API | ✅ |
| MinIO Console | 9001 | File management UI | ✅ |

**Change ports by editing `.env`:**
```bash
# Example: Change API port to 8090
API_PORT=8090

# Example: Change Neo4j port to 7475
NEO4J_PORT=7475
```

### **Resource Allocation**

**Memory Limits (edit in compose files):**
```yaml
services:
  postgres:
    mem_limit: 1g
    memswap_limit: 1g
    
  neo4j:
    mem_limit: 2g
    memswap_limit: 2g
    environment:
      - NEO4J_dbms_memory_heap_max__size=1g
      
  chromadb:
    mem_limit: 512m
    memswap_limit: 512m
```

**CPU Limits:**
```yaml
services:
  api:
    cpus: '2.0'
    cpu_shares: 1024
```

---

## 🔧 Troubleshooting Configuration Issues

### **Port Conflicts**
```powershell
# Check what's using your ports
netstat -an | findstr "8080 8000 7474 5432"

# Change ports in .env file if conflicts exist
# Then restart services
.\START.ps1 -Clean
```

### **Memory Issues**
```powershell
# Check available memory
Get-Counter "\Memory\Available MBytes"

# For systems with < 16GB RAM, use MVP configuration:
.\START.ps1 -Mode mvp

# Or adjust memory limits in compose files
```

### **Volume Issues**
```powershell
# Check Docker/Podman volumes
podman volume ls

# Clean up volumes if needed (DANGER: loses data)
podman volume prune

# Recreate volumes
.\START.ps1 -Clean
```

### **Service Dependencies**
```powershell
# Check service startup order
podman-compose logs

# Services start in this order:
# 1. PostgreSQL, Redis
# 2. MinIO, ChromaDB  
# 3. Neo4j
# 4. API Server
# 5. Frontend
```

---

## 🚀 Production Configuration

### **Production Settings (.env.production)**
```bash
# === PRODUCTION ENVIRONMENT ===
APP_ENV=production
DEBUG=false
LOG_LEVEL=INFO

# === SECURITY ===
JWT_SECRET_KEY=your-production-secret-key
AUTH_ENABLED=true
HTTPS_ONLY=true

# === PERFORMANCE ===
API_WORKERS=4
MAX_CONCURRENT_REPOS=50
BATCH_SIZE=500

# === MONITORING ===
PROMETHEUS_ENABLED=true
GRAFANA_ENABLED=true
HEALTH_CHECK_INTERVAL=30

# === BACKUP ===
BACKUP_ENABLED=true
BACKUP_SCHEDULE="0 2 * * *"  # Daily at 2 AM
```

### **Production Compose Override**
Create `docker-compose.prod.yml`:
```yaml
version: '3.8'
services:
  api:
    environment:
      - APP_ENV=production
    replicas: 3
    
  nginx:
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./ssl:/etc/ssl:ro
      
  postgres:
    environment:
      - POSTGRES_SHARED_PRELOAD_LIBRARIES=pg_stat_statements
    command: postgres -c shared_preload_libraries=pg_stat_statements
```

**Start production:**
```powershell
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## 📋 Configuration Best Practices

### **Development Workflow**
1. **Use services-only** for daily development
2. **Run API manually** for debugging and hot-reload
3. **Use full compose** for integration testing
4. **Use MVP compose** for CI/CD pipelines

### **Environment Management**
1. **Never commit secrets** to version control
2. **Use separate .env files** for different environments
3. **Document all configuration changes** in this guide
4. **Test configuration changes** in development first

### **Monitoring Configuration**
1. **Enable health checks** in production
2. **Set up log aggregation** for troubleshooting
3. **Monitor resource usage** to optimize limits
4. **Set up alerts** for service failures

---

## ✅ Configuration Checklist

Before deploying:

- [ ] Environment variables configured in `.env`
- [ ] Ports are available and not conflicting
- [ ] Resource limits appropriate for hardware
- [ ] Security settings enabled for production
- [ ] Backup configuration tested
- [ ] Health checks responding
- [ ] All services starting successfully
- [ ] Frontend connecting to backend APIs
- [ ] Database connections working
- [ ] File uploads working through MinIO

---

**Your GraphRAG system now has clean, maintainable configuration management! 🎉**

**For support:** Check `TROUBLESHOOTING.md` or run `.\START.ps1 -Status`