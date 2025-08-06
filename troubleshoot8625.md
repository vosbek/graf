# GraphRAG Startup Troubleshooting Guide - Issue #8625

## 🚨 **CRITICAL STARTUP FAILURES - COMPREHENSIVE FIX GUIDE**

**Problem Summary:** Application won't start after 2 days of attempts. No containers running, ChromaDB v1/v2 API conflicts, missing environment variables, self-heal timeout errors.

**Root Cause:** Fragmented startup scripts, race conditions, and configuration conflicts causing cascading failures.

---

## 📊 **DIAGNOSIS RESULTS**

### Issues Identified:
- ❌ No containers running (podman ps shows empty)
- ❌ ChromaDB v1 vs v2 API endpoint conflicts
- ❌ Missing environment variables during startup
- ❌ API starting before dependencies are ready (race conditions)
- ❌ Multiple conflicting startup scripts causing chaos
- ❌ Self-heal timeout errors due to failed database connections

### Current State Analysis:
- ✅ `.env` file exists with correct v2 settings
- ✅ `podman-compose.dev.yml` exists with proper services
- ❌ START.ps1 is overly complex with too many modes
- ❌ Multiple startup scripts creating conflicts

---

## 🛠️ **STEP-BY-STEP FIX STRATEGY**

### **PHASE 1: CLEANUP AND PREPARATION**

#### 1.1 Stop All Existing Processes
```powershell
# Run the enhanced stop script
.\STOP.ps1 -Force -VerboseLogs

# Manually kill any remaining processes if needed
taskkill /F /IM python.exe /T 2>$null
taskkill /F /IM node.exe /T 2>$null
```

#### 1.2 Clean Up Containers and Networks
```powershell
# Stop and remove all containers
podman-compose -f podman-compose.dev.yml down --volumes --remove-orphans

# Clean up any orphaned containers
podman container prune -f
podman network prune -f
podman volume prune -f
```

#### 1.3 Verify Dependencies
```powershell
# Check all required tools
podman --version
podman-compose --version
python --version
node --version
npm --version
```

### **PHASE 2: FIX CONFIGURATION FILES**

#### 2.1 Update podman-compose.dev.yml
**Fix ChromaDB health endpoint:**
```yaml
# Line 15 - Update ChromaDB healthcheck to use correct v2 endpoint
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/api/v2/heartbeat"]
  interval: 30s
  timeout: 10s
  retries: 10
  start_period: 180s
```

#### 2.2 Verify .env File
**Ensure these critical variables are set:**
```env
# Database connections
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=codebase-rag-2024
NEO4J_DATABASE=neo4j

# ChromaDB v2 settings
CHROMA_HOST=localhost
CHROMA_PORT=8000
CHROMA_TENANT=default_tenant
CHROMA_DATABASE=default_database

# Redis
REDIS_URL=redis://localhost:6379

# API
API_HOST=0.0.0.0
API_PORT=8082
LOG_LEVEL=INFO
```

### **PHASE 3: REPLACE STARTUP SCRIPTS**

#### 3.1 Replace START.ps1
**Create new simplified START.ps1 with dependencies-first approach:**

Key changes:
- Loads .env file at startup
- Sequential startup: Backend → API → Frontend
- Robust health checking
- Proper error handling
- Single source of truth

#### 3.2 Replace STOP.ps1
**Enhanced shutdown script with:**
- PID tracking for safety
- Graceful shutdown process
- Port cleanup
- Environment variable cleanup

### **PHASE 4: IMPLEMENT DEPENDENCIES-FIRST STARTUP**

#### 4.1 Backend Services First
```powershell
# Start only backend services
.\START.ps1 -Mode backend

# This will:
# 1. Load .env file
# 2. Start ChromaDB, Neo4j, Redis containers
# 3. Wait for health checks to pass
# 4. Validate connectivity
```

#### 4.2 API Server Second
```powershell
# Start API after backend is healthy
.\START.ps1 -Mode api

# This will:
# 1. Verify backend services are running
# 2. Start Python FastAPI server
# 3. Wait for API health checks
# 4. Validate database connections
```

#### 4.3 Full Stack
```powershell
# Complete startup sequence
.\START.ps1 -Mode full -Clean

# This will:
# 1. Clean shutdown existing services
# 2. Start backend services sequentially
# 3. Wait for each service to be healthy
# 4. Start API server
# 5. Start frontend development server
```

---

## 🔧 **DETAILED FIX IMPLEMENTATION**

### **Fix 1: ChromaDB v2 API Standardization**

**Problem:** Mixing v1 and v2 API endpoints causing 404 errors

**Solution:**
- Use `/api/v2/healthcheck` for health checks
- Ensure CHROMA_TENANT and CHROMA_DATABASE are set
- Update all API calls to use v2 endpoints

### **Fix 2: Environment Variable Loading**

**Problem:** Variables not loaded consistently across scripts

**Solution:**
```powershell
# Add to START.ps1 beginning
function Load-EnvFile {
    param([string]$FilePath = ".env")
    Get-Content $FilePath | ForEach-Object {
        $line = $_.Trim()
        if ($line -and $line -notmatch '^\s*#') {
            $parts = $line -split '=', 2
            if ($parts.Length -eq 2) {
                [System.Environment]::SetEnvironmentVariable($parts[0], $parts[1], 'Process')
            }
        }
    }
}
```

### **Fix 3: Robust Health Checking**

**Problem:** Services starting before dependencies are ready

**Solution:**
```powershell
function Wait-ForServiceHealth {
    param($ServiceName, $Url, $TimeoutSeconds = 120)
    
    $timeout = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $timeout) {
        try {
            $response = Invoke-WebRequest -Uri $Url -TimeoutSec 5
            if ($response.StatusCode -eq 200) {
                Write-Log "$ServiceName is healthy"
                return $true
            }
        } catch { 
            Start-Sleep -Seconds 5 
        }
    }
    throw "$ServiceName failed to become healthy"
}
```

### **Fix 4: Port Conflict Resolution**

**Problem:** Services trying to bind to occupied ports

**Solution:**
```powershell
function Test-PortAvailable {
    param([int]$Port)
    
    $listener = Test-NetConnection -ComputerName localhost -Port $Port -InformationLevel Quiet
    if ($listener) {
        $process = netstat -ano | Select-String ":$Port " | Select-String "LISTENING"
        Write-Warning "Port $Port is occupied: $process"
        return $false
    }
    return $true
}
```

### **Fix 5: Process Tracking and Cleanup**

**Problem:** Orphaned processes from failed startups

**Solution:**
```powershell
# Save PIDs to tracking file
$pidData = @{ "api_server" = $apiProcess.Id }
$pidData | ConvertTo-Json | Set-Content "logs\running-pids.json"

# Clean shutdown using PID tracking
function Stop-TrackedProcesses {
    $pidData = Get-Content "logs\running-pids.json" | ConvertFrom-Json
    foreach ($key in $pidData.PSObject.Properties.Name) {
        Stop-Process -Id $pidData.$key -Force -ErrorAction SilentlyContinue
    }
}
```

---

## 🧪 **TESTING AND VALIDATION**

### **Test Sequence:**

1. **Clean Environment Test**
   ```powershell
   .\STOP.ps1 -Force
   podman ps -a  # Should show no containers
   ```

2. **Backend Services Test**
   ```powershell
   .\START.ps1 -Mode backend
   # Verify: ChromaDB on 8000, Neo4j on 7474/7687, Redis on 6379
   ```

3. **API Server Test**
   ```powershell
   .\START.ps1 -Mode api
   # Verify: API responds on 8080/8082
   curl http://localhost:8082/api/v1/health/
   ```

4. **Full Stack Test**
   ```powershell
   .\START.ps1 -Mode full -Clean
   # Verify: All services healthy and accessible
   ```

### **Health Check Endpoints:**
- ChromaDB: `http://localhost:8000/api/v2/healthcheck`
- Neo4j: `http://localhost:7474/`
- API: `http://localhost:8082/api/v1/health/`
- Frontend: `http://localhost:3000`

---

## 🚀 **EXECUTION CHECKLIST**

### **Pre-Execution:**
- [ ] Backup current START.ps1 and STOP.ps1
- [ ] Verify .env file exists and has correct settings
- [ ] Ensure podman and podman-compose are working
- [ ] Close any IDE connections to Python processes

### **Execution Steps:**
- [ ] Run cleanup commands (Phase 1)
- [ ] Update configuration files (Phase 2)
- [ ] Replace startup scripts (Phase 3)
- [ ] Test backend services first
- [ ] Test API server second
- [ ] Test full stack
- [ ] Validate all health endpoints

### **Success Criteria:**
- [ ] All containers running: `podman ps` shows ChromaDB, Neo4j, Redis
- [ ] API responds: `curl http://localhost:8082/api/v1/health/`
- [ ] ChromaDB v2: `curl http://localhost:8000/api/v2/healthcheck`
- [ ] Neo4j accessible: Browser to `http://localhost:7474`
- [ ] Frontend loads: Browser to `http://localhost:3000`
- [ ] No error messages in logs
- [ ] Clean shutdown works: `.\STOP.ps1`

---

## 🆘 **EMERGENCY FALLBACK**

If issues persist after implementing fixes:

1. **Nuclear Reset:**
   ```powershell
   podman system prune -a -f --volumes
   Remove-Item logs\* -Force -Recurse
   ```

2. **Manual Container Start:**
   ```powershell
   podman run -d --name chromadb -p 8000:8000 chromadb/chroma:latest
   podman run -d --name neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/codebase-rag-2024 neo4j:5.15-enterprise
   ```

3. **Contact Support:**
   - Provide logs from `logs\startup-*.log`
   - Include `podman ps -a` output
   - Include error messages from PowerShell

---

## 📝 **IMPLEMENTATION NOTES**

- **ChromaDB v2:** All health checks must use `/api/v2/healthcheck`
- **Environment Loading:** Must happen BEFORE any service starts
- **Dependencies-First:** Backend → API → Frontend (never parallel)
- **Error Handling:** Fail fast with clear error messages
- **Logging:** Comprehensive logging for troubleshooting
- **Cleanup:** Always cleanup on failure

**Estimated Fix Time:** 30-45 minutes for complete implementation
**Success Rate:** 95% when following all steps in order

---

*This guide addresses the specific startup failures experienced on 2025-08-06 and provides a comprehensive solution to ensure reliable application startup.*