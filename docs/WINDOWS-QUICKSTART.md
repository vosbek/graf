# Windows Quick Start Guide - Codebase RAG MVP

Complete installation guide for Windows users to get the MVP running from scratch and discover missing repository dependencies.

## 🎯 What You'll Achieve

After following this guide, you'll have:
- ✅ A working Codebase RAG system on Windows
- ✅ Ability to index your repositories
- ✅ Semantic search across your codebase
- ✅ Maven dependency analysis
- ✅ Discovery of missing repositories your project depends on

## 📋 Prerequisites Check

Before starting, verify your system meets these requirements:

### System Requirements
- **Windows 10 Pro/Enterprise** or **Windows 11** (64-bit)
- **8GB RAM minimum** (16GB recommended)
- **10GB free disk space** minimum
- **Administrator access** for initial setup
- **Internet connection** for downloading components

### Check Your Windows Version
```powershell
# Open PowerShell and run:
Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion, TotalPhysicalMemory
```

Expected output should show Windows 10/11 and at least 8GB RAM.

## 🔧 Step 1: Install Prerequisites

### Install Podman Desktop

**What is Podman?** A container runtime that replaces Docker, better for enterprise environments.

1. **Download Podman Desktop:**
   - Go to: https://podman-desktop.io/downloads/windows
   - Click "Download for Windows"
   - Save the `.exe` file

2. **Install Podman Desktop:**
   - Right-click the downloaded file → "Run as administrator"
   - Follow the installation wizard:
     - ✅ Check "Add Podman to PATH"
     - ✅ Check "Install for all users"
     - ✅ Choose "Native Windows Installation" (not WSL2)
   - Click "Install"
   - Restart your computer when prompted

3. **Verify Installation:**
   ```powershell
   # Open PowerShell and run:
   podman --version
   ```
   Expected output: `podman version 4.x.x`

### Install Git for Windows (Skip if already installed)

1. **Download Git:**
   - Go to: https://git-scm.com/download/win
   - Download the 64-bit installer

2. **Install Git:**
   - Run the installer with default settings
   - Make sure "Add Git to PATH" is selected

3. **Verify Installation:**
   ```powershell
   git --version
   ```
   Expected output: `git version 2.x.x`

## 🚀 Step 2: Get the MVP System

### Clone the Repository

```powershell
# Create a directory for the project
New-Item -ItemType Directory -Path "C:\CodebaseRAG" -Force
cd C:\CodebaseRAG

# Clone the repository (replace with actual URL)
git clone <your-repository-url> .

# Verify files are present
ls
```

You should see files like `mvp-compose.yml`, `start-mvp.ps1`, and folders like `mvp/`, `docs/`.

## 🎯 Step 3: Configure Your Repository Path

The MVP needs to know where your local repositories are located.

### Find Your Repositories

Common locations for enterprise repositories:
- `C:\repos\`
- `C:\dev\projects\`
- `C:\Users\<YourName>\source\repos\` (Visual Studio default)
- `C:\workspace\`

### Set Repository Path

```powershell
# Option 1: Set environment variable
$env:REPOS_PATH = "C:\path\to\your\repos"

# Option 2: Let the startup script ask you (recommended for first time)
# The script will prompt you during startup
```

## 🚀 Step 4: Start the MVP

### Run the Startup Script

```powershell
# Make sure you're in the project directory
cd C:\CodebaseRAG

# Run the startup script
.\start-mvp.ps1
```

### What the Script Does

The startup script will:
1. ✅ Check Podman is installed and working
2. ✅ Prompt for your repository path (if not set)
3. ✅ Download container images (ChromaDB, Neo4j) - **This takes 5-10 minutes first time**
4. ✅ Build the API container
5. ✅ Start all services
6. ✅ Initialize the Neo4j database
7. ✅ Show you the next steps

### Expected Output

```
==================================================================
🚀 Starting Codebase RAG MVP with Neo4j and Maven support
==================================================================

✅ Podman found
✅ podman-compose found
📁 Creating directories...
📝 Updating compose file with repos path...
🔨 Building API container...
🚀 Starting services...
⏳ Waiting for services to be ready...
Waiting for ChromaDB... ✅
Waiting for Neo4j... ✅
Waiting for API... ✅

==================================================================
🎉 MVP is now running!
==================================================================
```

## ✅ Step 5: Verify Installation

### Check System Status

```powershell
# Test the API
Invoke-RestMethod "http://localhost:8080/health"
```

Expected response:
```json
{
  "status": "healthy",
  "chromadb": "connected",
  "repos_path": "C:/your/repos/path",
  "repos_available": true
}
```

### Access Web Interfaces

Open these URLs in your browser:
- **API Documentation**: http://localhost:8080/docs
- **System Status**: http://localhost:8080/status
- **Neo4j Browser**: http://localhost:7474 (username: `neo4j`, password: `codebase-rag-2024`)

## 🎯 Step 6: Index Your First Repository

### Index Your Main Repository

```powershell
# Replace with your actual repository path and name
$repoData = @{
    repo_path = "C:\your\repos\main-project"
    repo_name = "main-project"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8080/index" `
  -Method POST `
  -ContentType "application/json" `
  -Body $repoData
```

Expected response:
```json
{
  "status": "success",
  "repository": "main-project",
  "files_indexed": 245,
  "chunks_created": 1820,
  "maven_artifacts": 3,
  "maven_dependencies": 47,
  "processing_time": 12.5
}
```

## 🔍 Step 7: Discover Missing Dependencies

Now use the MVP to find what other repositories you need:

### Check Your Dependencies

```powershell
# Get overall system status
Invoke-RestMethod "http://localhost:8080/status"

# Find dependency conflicts (shows missing repos)
Invoke-RestMethod "http://localhost:8080/maven/conflicts"

# Get repository graph information
Invoke-RestMethod "http://localhost:8080/graph/repository/main-project"
```

### Analyze Missing Dependencies

The conflict analysis will show you dependencies like:
```json
{
  "conflicts": [
    {
      "group_artifact": "com.yourcompany:user-service",
      "conflicting_versions": ["2.1.0", "2.3.1"],
      "dependencies": [
        {
          "from_artifact": "com.yourcompany:main-project:1.0.0",
          "to_group_id": "com.yourcompany",
          "to_artifact_id": "user-service",
          "to_version": "2.3.1"
        }
      ]
    }
  ]
}
```

This tells you that you need the `user-service` repository!

### Visual Exploration

1. Go to **Neo4j Browser**: http://localhost:7474
2. Login: `neo4j` / `codebase-rag-2024`
3. Run this query to see missing dependencies:

```cypher
MATCH (a:MavenArtifact)-[:DEPENDS_ON]->(dep:MavenArtifact)
WHERE NOT EXISTS {
  MATCH (r:Repository)-[:DEFINES_ARTIFACT]->(dep)
}
AND dep.group_id CONTAINS 'yourcompany'
RETURN dep.group_id, dep.artifact_id, dep.version
```

## 🔄 Step 8: Iterative Repository Discovery

### Workflow for Finding All Dependencies

1. **Index your main repository** ✅ (Done above)
2. **Analyze dependencies** → Get list of missing internal repositories
3. **Clone missing repositories** → Based on artifact names
4. **Index new repositories** → Add them to the system
5. **Re-analyze** → See what's still missing
6. **Repeat** → Until all dependencies are resolved

### Example: Adding a Missing Repository

```powershell
# Based on the analysis, you found you need "user-service"
# Clone it from your organization's Git
cd C:\your\repos
git clone https://your-git-server/user-service.git

# Index the new repository
$newRepoData = @{
    repo_path = "C:\your\repos\user-service"
    repo_name = "user-service"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8080/index" `
  -Method POST `
  -ContentType "application/json" `
  -Body $newRepoData

# Check dependencies again
Invoke-RestMethod "http://localhost:8080/maven/conflicts"
```

## 🔧 Daily Operations

### Starting and Stopping

```powershell
# Start the system (after reboot)
cd C:\CodebaseRAG
.\start-mvp.ps1

# Stop the system
podman-compose -f mvp-compose.yml down

# Check what's running
podman-compose -f mvp-compose.yml ps
```

### Searching Your Code

```powershell
# Semantic search across all indexed repositories
Invoke-RestMethod "http://localhost:8080/search?q=authentication function&limit=5"

# Search within specific repository
$searchData = @{
    query = "database connection"
    limit = 10
    repository = "main-project"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8080/search" `
  -Method POST `
  -ContentType "application/json" `
  -Body $searchData
```

## 🚨 Troubleshooting

### Common Issues and Solutions

**Issue: "Podman command not found"**
```powershell
# Solution: Restart PowerShell or add to PATH manually
$env:PATH += ";C:\Program Files\Podman Desktop\resources\bin"
```

**Issue: "Port already in use"**
```powershell
# Check what's using the ports
netstat -ano | findstr :8080
netstat -ano | findstr :7474

# Kill the process if needed (replace <PID> with actual process ID)
taskkill /PID <PID> /F
```

**Issue: "Access denied" errors**
```powershell
# Run PowerShell as Administrator
# Right-click PowerShell → "Run as administrator"
```

**Issue: Containers won't start**
```powershell
# Check container logs
podman logs codebase-rag-api
podman logs codebase-rag-neo4j
podman logs codebase-rag-chromadb

# Check system resources
Get-ComputerInfo | Select-Object TotalPhysicalMemory
```

**Issue: Can't access repositories**
- Make sure the repository path exists
- Check that Podman can access the drive (especially network drives)
- Try using a local drive path instead

## 🎯 Success Checklist

After completing this guide, you should be able to:

- [ ] Access http://localhost:8080/docs and see the API documentation
- [ ] Index a repository and see files/chunks/dependencies processed
- [ ] Search your code semantically and get relevant results
- [ ] View dependency conflicts and identify missing repositories
- [ ] Use Neo4j Browser to explore your codebase relationships
- [ ] Add new repositories and re-analyze dependencies

## 🔗 Next Steps

- **Read the [Dependency Discovery Guide](DEPENDENCY-DISCOVERY.md)** for advanced dependency analysis
- **Check the [Windows Troubleshooting Guide](WINDOWS-TROUBLESHOOTING.md)** for enterprise-specific issues
- **Explore the API documentation** at http://localhost:8080/docs for all available endpoints
- **Use Neo4j Browser** to write custom queries for your specific analysis needs

---

**🎉 Congratulations! You now have a working enterprise codebase analysis system that can help you discover and manage repository dependencies.**