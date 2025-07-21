# Windows Setup Guide

Essential steps to get the Codebase RAG MVP running on Windows.

## 📋 System Requirements

- **Windows 10 Pro/Enterprise** or **Windows 11** (64-bit)
- **8GB RAM minimum** (16GB recommended)
- **10GB free disk space**
- **Administrator access** for installation

### Check Your System
```powershell
Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion, TotalPhysicalMemory
```

## 🔧 Install Prerequisites

### 1. Podman Desktop

1. **Download**: https://podman-desktop.io/downloads/windows
2. **Install**: Right-click → "Run as administrator"
   - ✅ Check "Add Podman to PATH"
   - ✅ Check "Install for all users"
   - ✅ Choose "Native Windows Installation" (not WSL2)
3. **Restart** your computer
4. **Verify**: 
   ```powershell
   podman --version
   ```

### 2. Git for Windows (if not installed)

1. **Download**: https://git-scm.com/download/win
2. **Install** with default settings
3. **Verify**:
   ```powershell
   git --version
   ```

## 🚀 Get Started

### 1. Clone the Repository
```powershell
git clone <your-repository-url> C:\CodebaseRAG
cd C:\CodebaseRAG
```

### 2. Configure Your Repositories (Recommended)

**Create a `.env` file** for easy configuration:

```powershell
# Copy the example file
Copy-Item .env.windows.example .env

# Edit the .env file with your settings
notepad .env
```

**Example `.env` configuration:**
```bash
# Repository Configuration
REPOS_PATH=C:/repos

# Container ports (optional - uses defaults if not set)
API_PORT=8082
CHROMADB_PORT=8001
NEO4J_HTTP_PORT=7474

# Neo4j password
NEO4J_PASSWORD=codebase-rag-2024
```

**Alternative: Set manually** (if you prefer not to use .env):
```powershell
# Point to where your repositories are stored
$env:REPOS_PATH = "C:\your\repos"
```

**Common repository locations:**
- `C:\repos\`
- `C:\dev\projects\`
- `C:\Users\<YourName>\source\repos\` (Visual Studio default)
- `C:\workspace\`

### 3. Start the MVP

**Recommended approach** (uses `.env` configuration):

```powershell
# Podman-only script (more reliable, reads .env automatically)
.\start-mvp-podman.sh
```

**Alternative** (if you prefer the compose approach):
```powershell
# Standard script (tries compose first, may need manual env vars)
.\start-mvp.ps1
```

The script will:
- Check system requirements
- **Load configuration from `.env` file** (if present)
- Prompt for repository path if not configured
- Download container images (takes 5-10 minutes first time)
- Start ChromaDB, Neo4j, and API services with your custom settings
- Show you the next steps with your actual port numbers

### 4. Verify Installation

**Test the API** (uses ports from your `.env` file):

```powershell
# Test the API (default port 8082, or your custom port)
Invoke-RestMethod "http://localhost:8082/health"
```

**Note**: If you customized `API_PORT` in your `.env` file, use that port instead.

Expected response:
```json
{
  "status": "healthy",
  "chromadb": "connected",
  "repos_path": "C:/your/repos/path"
}
```

## 🎯 First Steps

### Access the System

**Default Ports** (when using `.env` configuration):
- **API Documentation**: http://localhost:8082/docs
- **ChromaDB**: http://localhost:8001
- **Neo4j Browser**: http://localhost:7474 (neo4j / codebase-rag-2024)

**Legacy Ports** (compose script without `.env`):
- **API Documentation**: http://localhost:8080/docs
- **Neo4j Browser**: http://localhost:7474 (neo4j / codebase-rag-2024)

**Custom Ports**: If you set custom ports in your `.env` file, use those instead.

### Index Your First Repository

```powershell
$repoData = @{
    repo_path = "C:\your\repos\main-project"
    repo_name = "main-project"
} | ConvertTo-Json

# Use the correct port based on which script you used
Invoke-RestMethod -Uri "http://localhost:8082/index" `
  -Method POST -ContentType "application/json" `
  -Body $repoData
```

### Find Missing Dependencies

```powershell
# See what repositories you need to clone
Invoke-RestMethod "http://localhost:8082/maven/conflicts"
```

## 🚨 Common Issues

### "Podman command not found"
```powershell
# Restart PowerShell or add to PATH manually
$env:PATH += ";C:\Program Files\Podman Desktop\resources\bin"
```

### "Port already in use"
```powershell
# Find what's using the port
netstat -ano | findstr :8082
netstat -ano | findstr :8001
netstat -ano | findstr :7474

# Kill the process (replace <PID> with actual ID)
taskkill /PID <PID> /F
```

### "Access denied"
- Run PowerShell as Administrator
- Right-click PowerShell → "Run as administrator"

### Containers won't start
```powershell
# Check logs
podman logs codebase-rag-api
podman logs codebase-rag-neo4j
podman logs codebase-rag-chromadb

# Check system resources (need 8GB+ RAM)
Get-ComputerInfo | Select-Object TotalPhysicalMemory
```

### Can't access repositories
- Verify the repository path exists and contains your projects
- Use absolute paths (e.g., `C:\repos\project`)
- Avoid network drives if possible

### WSL2 Port Forwarding Issues

If you're running in WSL2 and can't access from Windows browser:

```bash
# In WSL2, get your IP address
hostname -I

# Use WSL IP from Windows browser:
# http://<WSL-IP>:8082/docs
```

Or set up port forwarding:
```powershell
# In Windows PowerShell (as Administrator)
netsh interface portproxy add v4tov4 listenport=8082 listenaddress=0.0.0.0 connectport=8082 connectaddress=<WSL-IP>
```

## 🔧 Daily Operations

### Start the system (after reboot)
```powershell
cd C:\CodebaseRAG

# Recommended: Podman-only script (reads .env automatically)
.\start-mvp-podman.sh

# Alternative: Compose script  
.\start-mvp.ps1
```

### Stop the system
```powershell
# For Podman-only script
podman stop codebase-rag-chromadb codebase-rag-neo4j codebase-rag-api

# For compose script
podman-compose -f mvp-compose.yml down
```

### Check what's running
```powershell
podman ps
```

## 🎯 Success Checklist

After setup, you should be able to:
- [ ] Access http://localhost:8082/docs (or 8080 for compose)
- [ ] Index a repository successfully
- [ ] See dependency conflicts that identify missing repositories
- [ ] Use Neo4j Browser to explore relationships

## 📖 Next Steps

- **[Back to Main Guide](../README.md)** for dependency discovery workflow
- **[Dependency Discovery Guide](DEPENDENCY-DISCOVERY.md)** for advanced analysis
- **[Troubleshooting Guide](TROUBLESHOOTING.md)** for detailed issue resolution

---

**💡 The Podman-only script (`start-mvp-podman.sh`) is more reliable than the compose version for most setups. Use it if you encounter any issues with the standard script.**