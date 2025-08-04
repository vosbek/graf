# GraphRAG Codebase Analysis Platform - System Documentation

## System Overview

The GraphRAG platform is a comprehensive codebase analysis system that combines vector search (ChromaDB), graph databases (Neo4j), and traditional databases (PostgreSQL) to provide advanced code understanding and migration planning capabilities.

## Architecture Components

### Core Services

| Service | Container Name | Port(s) | Purpose | Status |
|---------|---------------|---------|---------|---------|
| PostgreSQL | codebase-rag-postgres | 5432 | Metadata and application data | ✅ Healthy |
| Redis | codebase-rag-redis | 6379 | Task queue and caching | ✅ Healthy |
| MinIO | codebase-rag-minio | 9000, 9001 | S3-compatible storage | ✅ Healthy |
| ChromaDB | codebase-rag-chromadb | 8000 | Vector database for semantic search | ⚠️ Version mismatch |
| Neo4j | codebase-rag-neo4j | 7474, 7687 | Graph database for relationships | ✅ Healthy |
| API Server | codebase-rag-api | 8080 | FastAPI REST API | ✅ Healthy |
| Frontend | React Dev Server | 3000 | React web interface | 🔧 Configured |

### Network Configuration

- **Pod Name**: pod_graf
- **Network**: codebase-rag-network (bridge)
- **Subnet**: 172.20.0.0/16 (docker-compose.yml)

## Port Mapping

| Port | Service | Protocol | Access |
|------|---------|----------|---------|
| 3000 | Frontend (React) | HTTP | Public |
| 5432 | PostgreSQL | TCP | Internal |
| 6379 | Redis | TCP | Internal |
| 7474 | Neo4j HTTP | HTTP | Public |
| 7687 | Neo4j Bolt | TCP | Internal |
| 8000 | ChromaDB | HTTP | Internal |
| 8080 | API Server | HTTP | Public |
| 9000 | MinIO API | HTTP | Internal |
| 9001 | MinIO Console | HTTP | Public |

## API Endpoints

### Health & Monitoring (/health/)
- `GET /` - Basic health check endpoint
- `GET /ready` - Readiness check endpoint  
- `GET /live` - Liveness check endpoint
- `GET /detailed` - Detailed health check endpoint
- `GET /metrics` - Get application metrics in Prometheus format
- `GET /database-status` - Get detailed database status and statistics
- `GET /performance` - Get performance metrics for all components
- `POST /reset-metrics` - Reset performance metrics
- `GET /version` - Get application version information

### Repository Indexing (/index/)
- `POST /repository` - Index a single repository
- `POST /bulk` - Index multiple repositories in bulk
- `GET /status/{task_id}` - Get the status of an indexing task
- `GET /status` - Get the status of all indexing tasks
- `POST /update/{repository_name}` - Perform incremental update for a repository
- `DELETE /repository/{repository_name}` - Delete a repository from the index
- `POST /filter` - Filter repositories based on criteria
- `GET /repositories` - List all indexed repositories
- `GET /repositories/{repository_name}` - Get detailed information about a specific repository
- `GET /statistics` - Get indexing pipeline statistics
- `POST /optimize` - Optimize database indices for better performance
- `POST /cleanup` - Clean up old completed tasks

### Query & Search (/query/)
- `POST /semantic` - Perform semantic search across codebase
- `GET /similar/{chunk_id}` - Find chunks similar to a specific chunk
- `POST /graph` - Execute a Cypher query against the graph database
- `GET /dependencies/transitive/{artifact_coordinates}` - Get transitive dependencies for a Maven artifact
- `GET /dependencies/conflicts` - Get dependency conflicts across repositories
- `GET /dependencies/circular` - Get circular dependencies in the system
- `GET /code/relationships/{chunk_id}` - Get relationships for a code chunk
- `GET /domains/{domain_name}/dependencies` - Get dependencies between business domains
- `GET /artifacts/most-connected` - Get most connected Maven artifacts (hub analysis)
- `GET /repositories/{repository_name}/health` - Get health analysis for a repository
- `GET /search/hybrid` - Perform hybrid search combining semantic and graph-based results
- `GET /statistics` - Get query and database statistics

### Multi-Repository Analysis (/query/multi-repo/)
- `POST /analyze` - Perform cross-repository analysis
- `GET /repositories` - Get list of available repositories with filtering options
- `POST /business-flows` - Get business flows that span the selected repositories
- `POST /dependencies/cross-repo` - Get dependencies between selected repositories
- `POST /migration-impact` - Analyze migration impact across selected repositories
- `GET /integration-points` - Get integration points for specified repositories

### System Administration (/admin/)
- `GET /system-info` - Get comprehensive system information
- `POST /maintenance` - Perform system maintenance operations
- `POST /backup` - Create system backup
- `GET /backups` - List all available backups
- `POST /restore/{backup_id}` - Restore from backup
- `GET /logs` - Get system logs
- `GET /configuration` - Get system configuration
- `POST /configuration` - Update system configuration
- `POST /cache/clear` - Clear system caches
- `GET /database-schema` - Get database schema information
- `POST /shutdown` - Shutdown the system gracefully
- `POST /restart` - Restart the system
- `GET /alerts` - Get system alerts and warnings

## Software Bill of Materials (SBOM)

### Backend Dependencies (Python)
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
chromadb==0.4.18
neo4j==5.15.0
sentence-transformers==2.2.2
redis==5.0.1
psycopg2-binary==2.9.9
minio==7.2.0
tree-sitter==0.20.4
tree-sitter-languages==1.8.0
pydantic==2.5.0
numpy==1.25.2
pandas==2.1.4
scikit-learn==1.3.2
pytest==7.4.3
```

### Frontend Dependencies (Node.js)
```
react==18.2.0
react-dom==18.2.0
react-scripts==5.0.1
react-router-dom==6.8.1
axios==1.3.4
@mui/material==5.11.10
@mui/icons-material==5.11.9
d3==7.8.2
cytoscape==3.24.0
```

### Infrastructure Services
```
postgres:15-alpine
redis:7-alpine
minio/minio:latest
chromadb/chroma:latest (v1.0.0)
neo4j:5.15
```

## Environment Variables

### API Configuration
```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=codebase-rag-2024
NEO4J_DATABASE=neo4j
CHROMA_HOST=localhost
CHROMA_PORT=8000
LOG_LEVEL=INFO
APP_ENV=development
API_HOST=0.0.0.0
API_PORT=8080
```

### Database Credentials
```bash
POSTGRES_DB=codebase_rag
POSTGRES_USER=codebase_rag
POSTGRES_PASSWORD=codebase-rag-2024
REDIS_URL=redis://localhost:6379
MINIO_ACCESS_KEY=codebase-rag
MINIO_SECRET_KEY=codebase-rag-2024
```

## Known Issues & Status

### ❌ Current Blocking Issues
1. **ChromaDB Version Incompatibility**
   - Client: v0.4.18
   - Server: v1.0.0
   - Impact: Semantic search disabled
   - Solution: Upgrade client or downgrade server

2. **Port 8080 Conflicts**
   - Port 8080 had persistent hanging processes (resolved)
   - API runs on port 8080 as configured
   - Solution: Proper process cleanup in startup script

### ✅ Issues Resolved
1. Health check blocking (`psutil.cpu_percent(interval=1)`)
2. Lifespan function exception handling
3. Frontend proxy configuration (8081 → 8080)
4. Container health checks (API v2)

## Access URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | - |
| API Docs | http://localhost:8080/docs | - |
| Neo4j Browser | http://localhost:7474 | neo4j / codebase-rag-2024 |
| MinIO Console | http://localhost:9001 | codebase-rag / codebase-rag-2024 |
| ChromaDB API | http://localhost:8000/api/v2/heartbeat | - |

## System Management

### Startup Scripts
- `START.ps1` - Complete system startup (infrastructure + API + frontend)
- `test_simple_api.py` - Minimal FastAPI test server for debugging

### Process Management

#### Normal Shutdown
```powershell
# Stop frontend (React dev server)
Get-Process -Name node -ErrorAction SilentlyContinue | Stop-Process

# Stop API server 
Get-Process -Name python | Where-Object {$_.CommandLine -like "*src.main*"} | Stop-Process

# Stop containers
podman stop --all
```

#### Force Stop All Services (if hanging)
```powershell
# Stop all Node.js processes (frontend)
Get-Process -Name node -ErrorAction SilentlyContinue | Stop-Process -Force

# Stop all Python processes (API server) - CAUTION: This kills ALL Python processes
Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force

# Stop containers
podman stop --all --force

# Check for specific port conflicts
netstat -ano | findstr ":8080"  # Find API processes
netstat -ano | findstr ":3000"  # Find frontend processes

# Kill specific process by PID if needed
taskkill /F /PID <process_id>
```

#### Restart Procedure
1. **Full System Restart**:
   ```powershell
   # Stop all services
   .\START.ps1 -Mode stop
   
   # Wait 10 seconds for cleanup
   Start-Sleep -Seconds 10
   
   # Start all services
   .\START.ps1 -Mode full
   ```

2. **Restart Only API Server**:
   ```powershell
   # Stop API only
   Get-Process -Name python | Where-Object {$_.CommandLine -like "*src.main*"} | Stop-Process
   
   # Start API only
   .\START.ps1 -Mode api
   ```

3. **Restart Only Frontend**:
   ```powershell
   # Stop frontend only
   Get-Process -Name node -ErrorAction SilentlyContinue | Stop-Process
   
   # Start frontend only
   .\START.ps1 -Mode frontend
   ```

## Troubleshooting Commands

### Container Management
```bash
podman ps -a                                    # List all containers
podman logs codebase-rag-[service]             # View service logs
podman-compose -f podman-compose-services-only.yml up -d  # Start infrastructure
```

### Health Checks
```bash
curl http://localhost:8080/health             # API health
curl http://localhost:8000/api/v2/heartbeat     # ChromaDB health
curl http://localhost:7474                      # Neo4j health
```

### Database Testing
```bash
# Neo4j
python -c "from neo4j import GraphDatabase; driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'codebase-rag-2024')); print('Neo4j OK')"

# Redis
redis-cli ping

# PostgreSQL
psql -h localhost -U codebase_rag -d codebase_rag -c "SELECT 1;"
```

## Deployment Configuration

### Resource Limits (Production)
- ChromaDB: 64GB RAM, 16 CPU cores
- Neo4j: 56GB RAM, 16 CPU cores  
- PostgreSQL: 4GB RAM, 2 CPU cores
- Redis: 4GB RAM, 2 CPU cores
- MinIO: 2GB RAM, 1 CPU core

### Resource Limits (Development)
- ChromaDB: 8GB RAM, 4 CPU cores
- Neo4j: 12GB RAM, 4 CPU cores
- PostgreSQL: 2GB RAM, 1 CPU core
- Redis: 2GB RAM, 1 CPU core
- MinIO: 1GB RAM, 1 CPU core

---
*Last Updated: 2025-08-02*
*System Status: Development - Partial Functionality*