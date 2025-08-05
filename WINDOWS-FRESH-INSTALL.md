# 🖥️ GraphRAG Fresh Windows Installation Guide

**Complete setup guide for installing GraphRAG on a fresh Windows 10/11 machine.**

## 📋 Prerequisites Checklist

### **Required (Must Have)**
- [ ] **Windows 10/11** with administrator privileges
- [ ] **PowerShell 5.1+** (built into Windows 10/11)
- [ ] **8GB+ RAM** (16GB+ recommended for large codebases)
- [ ] **20GB+ free disk space** (for containers, Python packages, and data)
- [ ] **Internet connection** (for downloading dependencies)

### **Will Be Installed**  
- [ ] Podman Desktop or Docker Desktop
- [ ] Python 3.11+
- [ ] Node.js 18+
- [ ] Git (if not already installed)

---

## 🚀 Step-by-Step Installation

### **Step 1: Install Container Runtime**

Choose **ONE** of these options:

#### **Option A: Podman Desktop (Recommended)**
```powershell
# Download and install Podman Desktop
# Visit: https://podman-desktop.io/downloads/windows
# Or use winget:
winget install RedHat.Podman-Desktop
```

#### **Option B: Docker Desktop (Alternative)**
```powershell
# Download and install Docker Desktop
# Visit: https://www.docker.com/products/docker-desktop/
# Or use winget:
winget install Docker.DockerDesktop
```

**⚠️ Important:** 
- Restart your computer after installation
- Ensure the container service starts automatically
- Test with: `podman --version` or `docker --version`

### **Step 2: Install Python 3.11**

```powershell
# Install Python 3.11 (latest stable)
winget install Python.Python.3.11

# Verify installation
python --version
pip --version
```

**⚠️ Python Installation Notes:**
- Ensure "Add Python to PATH" is checked during installation
- If `python` command doesn't work, try `py` instead
- You may need to restart PowerShell after installation

### **Step 3: Install Node.js**

```powershell
# Install Node.js 18+ (LTS version)
winget install OpenJS.NodeJS.LTS

# Verify installation
node --version
npm --version
```

### **Step 4: Install Git (if needed)**

```powershell
# Install Git for Windows
winget install Git.Git

# Verify installation
git --version
```

### **Step 5: Clone and Setup GraphRAG**

```powershell
# Navigate to your development directory
cd C:\dev  # or wherever you want to install

# Clone the repository
git clone <your-repo-url> GraphRAG
cd GraphRAG

# Copy environment configuration
Copy-Item .env.windows.example .env

# Edit .env file with your paths
notepad .env
```

### **Step 6: Configure Environment**

Edit the `.env` file with your specific paths:

```env
# Example Windows configuration
REPOS_PATH=C:/repos
# OR specific repositories:
# MAIN_REPOS=my-app,shared-lib,api-service

# Default ports (change if conflicts exist)
API_PORT=8082
CHROMADB_PORT=8001
NEO4J_HTTP_PORT=7474
NEO4J_BOLT_PORT=7687

# Password for Neo4j
NEO4J_PASSWORD=codebase-rag-2024

# Auto-index repositories on startup
AUTO_INDEX=false
```

### **Step 7: Install Python Dependencies**

```powershell
# Install Python packages (this may take 10-15 minutes)
pip install -r requirements.txt

# If you encounter errors, try upgrading pip first:
python -m pip install --upgrade pip
pip install -r requirements.txt
```

**⚠️ Common Installation Issues:**

If you encounter errors with specific packages:

```powershell
# For psycopg2 issues:
pip install psycopg2-binary --no-cache-dir

# For python-magic issues on Windows:
pip install python-magic-bin

# For tree-sitter compilation issues:
pip install --upgrade setuptools wheel
pip install tree-sitter --no-cache-dir

# For torch issues (large download):
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

### **Step 8: Install podman-compose (if using Podman)**

```powershell
# Install podman-compose
pip install podman-compose

# Verify installation
podman-compose --version
```

### **Step 9: Test Installation**

```powershell
# Check all dependencies
.\START.ps1 -Status

# If everything looks good, start the system
.\START.ps1
```

---

## 🔧 Troubleshooting Common Issues

### **1. "Podman not found" Error**

```powershell
# Ensure Podman is in PATH
podman --version

# If not found, restart PowerShell or add to PATH manually
$env:PATH += ";C:\Program Files\RedHat\Podman"
```

### **2. "Python not found" Error**

```powershell
# Try alternative Python commands
py --version
python3 --version

# If none work, reinstall Python with PATH option
```

### **3. "Port already in use" Errors**

```powershell
# Check what's using the ports
netstat -an | findstr "8080 8000 7474 6379"

# Kill processes using the ports
taskkill /f /pid <PID>

# Or change ports in .env file
```

### **4. Docker/Podman Service Issues**

```powershell
# For Podman Desktop
# Restart Podman Desktop application

# For Docker Desktop  
# Restart Docker Desktop application

# Test container functionality
podman run hello-world
# OR
docker run hello-world
```

### **5. Python Package Installation Failures**

```powershell
# Use conda instead of pip (if you have Anaconda/Miniconda)
conda install -c conda-forge <package-name>

# Or install Visual Studio Build Tools for compilation
# Download from: https://visualstudio.microsoft.com/visual-cpp-build-tools/
```

### **6. Frontend npm Installation Issues**

```powershell
# Clear npm cache
npm cache clean --force

# Delete node_modules and reinstall
cd frontend
Remove-Item -Recurse -Force node_modules
Remove-Item package-lock.json -Force
npm install
```

### **7. Neo4j Container Issues**

```powershell
# The Neo4j container uses enterprise edition - might need license
# If you see license errors, switch to community edition in podman-compose.dev.yml:
# Change: neo4j:5.15-enterprise
# To: neo4j:5.15-community

# Also remove the license environment variable:
# Remove: NEO4J_ACCEPT_LICENSE_AGREEMENT=yes
```

---

## 🎯 Verification Steps

After installation, verify everything works:

### **1. Container Services**
```powershell
# Start containers
.\START.ps1 -Mode backend

# Check container status
podman ps
# OR
docker ps
```

### **2. API Server**
```powershell
# Start API server
.\START.ps1 -Mode api

# Test API endpoint
curl http://localhost:8081/api/v1/health/
```

### **3. Frontend**
```powershell
# Start frontend (in separate PowerShell window)
.\START.ps1 -Mode frontend

# Should open browser to http://localhost:3000
```

### **4. Full System**
```powershell
# Start everything
.\START.ps1

# Check system status
.\START.ps1 -Status
```

---

## 📊 Expected Resource Usage

**Memory Usage:**
- Neo4j: ~4-6GB RAM
- ChromaDB: ~1-2GB RAM  
- Python API: ~1-2GB RAM
- React Frontend: ~500MB RAM
- **Total: ~8-12GB RAM**

**Disk Usage:**
- Container images: ~3-4GB
- Python packages: ~2-3GB  
- Node.js modules: ~500MB
- Repository data: varies
- **Total: ~6-8GB + your data**

**Network Ports:**
- Frontend: 3000
- API: 8081 (configurable)
- ChromaDB: 8000  
- Neo4j HTTP: 7474
- Neo4j Bolt: 7687
- Redis: 6379
- PostgreSQL: 5432

---

## 🚨 Security Notes

**Default Passwords:**
- Neo4j: `neo4j` / `codebase-rag-2024`
- PostgreSQL: `codebase_rag` / `codebase-rag-2024`

**⚠️ Change these passwords in production!**

**Firewall:**
- The system binds to all interfaces (0.0.0.0)
- Ensure your firewall blocks external access if needed
- Only expose ports you need externally

---

## 🆘 Getting Help

If you encounter issues:

1. **Check the logs:**
   ```powershell
   Get-Content logs\start-*.log -Tail 50
   ```

2. **Run diagnostics:**
   ```powershell
   .\START.ps1 -Status
   ```

3. **Clean restart:**
   ```powershell
   .\START.ps1 -Clean
   ```

4. **View detailed startup:**
   ```powershell
   .\START.ps1 -LogLevel DEBUG
   ```

5. **Check system requirements:**
   - Windows 10/11 with latest updates
   - At least 8GB RAM available
   - At least 20GB free disk space
   - Administrator privileges for installation

---

## ✅ Success Indicators

When everything is working correctly, you should see:

```
✅ ChromaDB (port 8000): Healthy
✅ Neo4j (port 7474): Healthy  
✅ Redis (port 6379): Healthy
✅ API Server (port 8081): Healthy
✅ Frontend (port 3000): Healthy

🎉 Your GraphRAG system is ready!
```

**Access URLs:**
- **Main Application:** http://localhost:3000
- **API Documentation:** http://localhost:8081/docs
- **Neo4j Browser:** http://localhost:7474
- **ChromaDB:** http://localhost:8000

---

**🎯 Ready to analyze your legacy codebases with AI-powered insights!**