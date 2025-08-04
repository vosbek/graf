# 🔧 GraphRAG Troubleshooting Guide

**Comprehensive troubleshooting for your AI-powered codebase analysis platform.**

## 🚨 Quick Diagnostics

**First, always run the system status check:**
```powershell
.\START.ps1 -Status
```

This shows you exactly what's running and what's not.

## 🔍 Common Issues & Solutions

### **1. Startup Failures**

#### **"Podman not found" or "Docker not found"**
```powershell
# Solution: Install container runtime
# Option A: Podman Desktop (recommended)
# Download from: https://podman-desktop.io/

# Option B: Docker Desktop  
# Download from: https://www.docker.com/products/docker-desktop/

# Verify installation
podman --version
# or
docker --version
```

#### **"podman-compose not found"**
```powershell
# Solution: Install podman-compose
pip install podman-compose

# Verify installation
podman-compose --version
```

#### **"Python not found"**
```powershell
# Solution: Install Python 3.8+
winget install Python.Python.3.11

# Verify installation
python --version
pip --version
```

#### **"Permission denied" or "Access denied"**
```powershell
# Solution: Run PowerShell as Administrator
# Right-click PowerShell → "Run as Administrator"

# Check execution policy
Get-ExecutionPolicy
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### **2. Service Health Issues**

#### **Services Not Starting**
```powershell
# Check what's running
.\START.ps1 -Status
podman ps -a

# Clean restart
.\START.ps1 -Clean

# View container logs
podman logs codebase-rag-postgres
podman logs codebase-rag-neo4j
podman logs codebase-rag-chromadb
```

#### **Port Conflicts**
```powershell
# Check what's using your ports
netstat -an | findstr "3000 5432 6379 7474 8000 8080 9000 9001"

# Kill processes using conflicting ports
Get-Process -Id (Get-NetTCPConnection -LocalPort 3000).OwningProcess | Stop-Process -Force
```

#### **PostgreSQL Won't Start**
```powershell
# Check PostgreSQL logs
podman logs codebase-rag-postgres

# Common fix: Remove old volume
podman volume rm codebase-rag_postgres_data
.\START.ps1 -Clean
```

#### **Neo4j Keeps Restarting**
```powershell
# Neo4j needs time to initialize (2-3 minutes)
# Check logs for specific errors
podman logs codebase-rag-neo4j

# Common fix: Increase memory allocation
# Edit docker-compose.yml:
# NEO4J_dbms_memory_heap_initial__size: 512m
# NEO4J_dbms_memory_heap_max__size: 2g
```

#### **ChromaDB "Unhealthy" Status**
```powershell
# ChromaDB often shows "unhealthy" but works fine
# Test API directly:
curl http://localhost:8000/api/v1/heartbeat

# If API responds, ChromaDB is working despite health check
```

### **3. Web Interface Issues**

#### **Frontend Won't Load (localhost:3000)**
```powershell
# Check if Node.js is installed
node --version
npm --version

# Install Node.js if missing
winget install OpenJS.NodeJS

# Install frontend dependencies
cd frontend
npm install
cd ..

# Start frontend only
.\START.ps1 -Mode frontend
```

#### **"Module not found" Errors**
```powershell
# Clean install dependencies
cd frontend
Remove-Item -Recurse -Force node_modules
Remove-Item package-lock.json
npm install
cd ..
```

#### **Frontend Build Failures**
```powershell
# Check for JavaScript errors
cd frontend
npm run build

# Fix common issues:
# 1. Update dependencies
npm update

# 2. Clear cache
npm cache clean --force
```

### **4. API Server Issues**

#### **API Server Won't Start (localhost:8080)**
```powershell
# Check Python dependencies
pip install -r requirements.txt

# Start API manually for debugging
python -m uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload

# Check for import errors
python -c "from src.main import app; print('API imports OK')"
```

#### **Database Connection Errors**
```powershell
# Verify database services are running
.\START.ps1 -Status

# Test database connections manually
# PostgreSQL
psql -h localhost -p 5432 -U codebase_rag -d codebase_rag

# Neo4j
curl http://localhost:7474/db/data/
```

#### **AWS Credentials Issues**
```powershell
# Check AWS configuration
aws configure list

# Test AWS connectivity
aws sts get-caller-identity

# Set environment variables if needed
$env:AWS_ACCESS_KEY_ID="your-key"
$env:AWS_SECRET_ACCESS_KEY="your-secret"
$env:AWS_DEFAULT_REGION="us-east-1"
```

### **5. Memory and Performance Issues**

#### **System Running Slowly**
```powershell
# Check system resources
Get-Process | Sort-Object CPU -Descending | Select-Object -First 10
Get-Counter "\Memory\Available MBytes"

# System requirements:
# Minimum: 8GB RAM, 4 CPU cores
# Recommended: 16GB+ RAM, 8+ CPU cores
```

#### **Container Memory Issues**
```powershell
# Check container resource usage
podman stats

# Increase container memory limits in compose files
# Edit docker-compose.yml or podman-compose-services-only.yml:
# mem_limit: 2g
# memswap_limit: 2g
```

#### **Disk Space Issues**
```powershell
# Check disk space
Get-WmiObject -Class Win32_LogicalDisk | Select-Object Size,FreeSpace,DeviceID

# Clean up Docker/Podman images and volumes
podman system prune -a
podman volume prune
```

### **6. Network and Connectivity Issues**

#### **Services Can't Communicate**
```powershell
# Check Docker/Podman network
podman network ls
podman network inspect codebase-rag_default

# Recreate network if needed
podman-compose down
podman network rm codebase-rag_default
podman-compose up -d
```

#### **Firewall Blocking Connections**
```powershell
# Check Windows Firewall
Get-NetFirewallRule | Where-Object {$_.DisplayName -like "*podman*"}

# Add firewall rules for required ports
New-NetFirewallRule -DisplayName "GraphRAG-3000" -Direction Inbound -Protocol TCP -LocalPort 3000 -Action Allow
New-NetFirewallRule -DisplayName "GraphRAG-8080" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow
```

### **7. Data and Configuration Issues**

#### **Lost Data After Restart**
```powershell
# Check if volumes are persistent
podman volume ls

# Volumes should be:
# codebase-rag_postgres_data
# codebase-rag_neo4j_data  
# codebase-rag_minio_data

# If missing, recreate with:
.\START.ps1 -Clean
```

#### **Configuration File Errors**
```powershell
# Validate YAML files
# Use online YAML validator or:
python -c "import yaml; yaml.safe_load(open('docker-compose.yml'))"

# Check .env file format
Get-Content .env | Where-Object {$_ -notmatch '^#' -and $_ -notmatch '^\s*$'}
```

## 🐛 Advanced Debugging

### **Enable Debug Logging**
```powershell
# Set debug environment variables
$env:LOG_LEVEL="DEBUG"
$env:PYTHONPATH="."

# Start with verbose logging
.\START.ps1 -Mode backend
```

### **Container Deep Dive**
```powershell
# Inspect individual containers
podman inspect codebase-rag-postgres
podman exec -it codebase-rag-postgres bash

# Check container networking
podman exec -it codebase-rag-api ping codebase-rag-postgres
```

### **Database Debugging**

#### **PostgreSQL**
```powershell
# Connect to PostgreSQL directly
podman exec -it codebase-rag-postgres psql -U codebase_rag -d codebase_rag

# Check tables and data
\dt
SELECT COUNT(*) FROM repositories;
```

#### **Neo4j**
```powershell
# Connect to Neo4j directly
podman exec -it codebase-rag-neo4j cypher-shell -u neo4j -p codebase-rag-2024

# Check graph data
MATCH (n) RETURN count(n);
MATCH (n)-[r]->(m) RETURN count(r);
```

#### **ChromaDB**
```powershell
# Test ChromaDB API
curl -X GET http://localhost:8000/api/v1/collections
curl -X POST http://localhost:8000/api/v1/collections -d '{"name":"test"}'
```

## 📊 Performance Monitoring

### **System Health Dashboard**
```powershell
# Continuous monitoring
while ($true) {
    Clear-Host
    Write-Host "=== GraphRAG System Monitor ===" -ForegroundColor Green
    Write-Host "Time: $(Get-Date)" -ForegroundColor Yellow
    
    # Container status
    podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    
    # System resources
    $mem = Get-Counter "\Memory\Available MBytes"
    Write-Host "Available Memory: $($mem.CounterSamples.CookedValue) MB" -ForegroundColor Cyan
    
    # Service health
    try { $api = Invoke-WebRequest -Uri "http://localhost:8080/health" -TimeoutSec 2; Write-Host "API: OK" -ForegroundColor Green } catch { Write-Host "API: FAIL" -ForegroundColor Red }
    try { $chroma = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/heartbeat" -TimeoutSec 2; Write-Host "ChromaDB: OK" -ForegroundColor Green } catch { Write-Host "ChromaDB: FAIL" -ForegroundColor Red }
    
    Start-Sleep -Seconds 5
}
```

### **Log Analysis**
```powershell
# Real-time log monitoring
Get-Content logs\start-*.log -Wait -Tail 20

# Error analysis
Select-String -Path "logs\*.log" -Pattern "ERROR|FAIL|Exception" | Select-Object -Last 10

# Performance analysis  
Select-String -Path "logs\*.log" -Pattern "started|completed" | Measure-Object
```

## 🔄 Recovery Procedures

### **Complete System Reset**
```powershell
# Nuclear option: Clean everything
podman-compose down --remove-orphans
podman system prune -a --volumes
podman volume prune -f

# Remove all logs
Remove-Item logs\*.log -Force
Remove-Item *startup*.log -Force

# Fresh restart
.\START.ps1 -Clean
```

### **Selective Service Restart**
```powershell
# Restart specific service
podman restart codebase-rag-neo4j
podman logs codebase-rag-neo4j --follow

# Restart database services only
podman restart codebase-rag-postgres codebase-rag-redis
```

### **Backup Important Data**
```powershell
# Backup PostgreSQL data
podman exec codebase-rag-postgres pg_dump -U codebase_rag codebase_rag > backup.sql

# Backup Neo4j data  
podman exec codebase-rag-neo4j neo4j-admin backup --backup-dir=/backups

# Backup MinIO data
# Data is stored in Docker volumes - backup entire volume:
podman volume export codebase-rag_minio_data > minio_backup.tar
```

## 📞 Getting Help

### **Log Collection for Support**
```powershell
# Collect all logs for support
$timestamp = Get-Date -Format "yyyy-MM-dd-HH-mm"
$supportDir = "support-logs-$timestamp"
New-Item -ItemType Directory $supportDir

# Copy system logs
Copy-Item logs\*.log $supportDir\
Copy-Item *startup*.log $supportDir\ -ErrorAction SilentlyContinue

# Copy container logs
podman ps --format "{{.Names}}" | ForEach-Object {
    podman logs $_ > "$supportDir\$_.log" 2>&1
}

# System info
Get-ComputerInfo | Out-File "$supportDir\system-info.txt"
.\START.ps1 -Status > "$supportDir\system-status.txt"

Write-Host "Support logs collected in: $supportDir"
Compress-Archive -Path $supportDir -DestinationPath "$supportDir.zip"
```

### **Common Support Information**
When reporting issues, include:
- Output of `.\START.ps1 -Status`
- Relevant log files from `logs\` directory
- Your system specifications (RAM, CPU, OS version)
- Steps to reproduce the issue
- Error messages (exact text)

---

## ✅ Prevention Tips

1. **Regular Maintenance**
   ```powershell
   # Weekly cleanup
   .\START.ps1 -Clean
   podman system prune
   ```

2. **Monitor Resources**
   ```powershell
   # Check available resources before starting
   Get-Counter "\Memory\Available MBytes"
   Get-Counter "\Processor(_Total)\% Processor Time"
   ```

3. **Keep Dependencies Updated**
   ```powershell
   # Update Python packages
   pip install --upgrade -r requirements.txt
   
   # Update Node.js packages
   cd frontend && npm update && cd ..
   ```

4. **Regular Backups**
   ```powershell
   # Weekly data backup
   podman exec codebase-rag-postgres pg_dump -U codebase_rag codebase_rag > "backup-$(Get-Date -Format 'yyyy-MM-dd').sql"
   ```

**Remember: Most issues are resolved by a clean restart with `.\START.ps1 -Clean` 🚀**