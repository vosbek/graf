# Codebase RAG MVP - Repository Dependency Discovery

**Find missing repositories your codebase depends on.** Analyze Maven dependencies across multiple repositories and discover which ones you need to clone locally.

## 🎯 What This Solves

**Problem:** "I have one repository that depends on multiple others, but I don't know which ones I need."

**Solution:** This MVP analyzes your Maven dependencies and tells you exactly which repositories are missing from your local setup.

## ⚡ Quick Start

### Windows Setup

1. **Install Prerequisites**
   - **Podman Desktop**: Download from [podman-desktop.io](https://podman-desktop.io/downloads/windows)
   - **Git for Windows**: Download from [git-scm.com](https://git-scm.com/download/win)

2. **Get the MVP**
   ```powershell
   git clone <your-repository-url> CodebaseRAG
   cd CodebaseRAG
   ```

3. **Configure Repositories (Optional)**
   ```powershell
   # Copy example configuration
   Copy-Item .env.windows.example .env
   
   # Edit with your repository paths
   notepad .env
   ```
   
   Example `.env`:
   ```bash
   REPOS_PATH=C:/your/repos
   API_PORT=8082
   ```

4. **Start the System**
   ```powershell
   .\start-mvp-podman.sh
   ```
   
   The script will:
   - Check your system requirements
   - Load configuration from `.env` file (if present)
   - Download and start ChromaDB + Neo4j + API
   - Show you the next steps

5. **Verify It's Working**
   - Open: http://localhost:8082/docs (or your custom API_PORT)
   - Should see the API documentation

### Linux/macOS Setup

```bash
git clone <your-repository-url> CodebaseRAG
cd CodebaseRAG

# Configure repositories (optional)
cp .env.example .env
# Edit .env with your repository paths

# Use the Podman-only script (works better than compose)
chmod +x start-mvp-podman.sh
./start-mvp-podman.sh
```

## 🔍 Discover Missing Dependencies

### Step 1: Index Your Main Repository

```powershell
# Replace with your actual repository path
$repoData = @{
    repo_path = "C:\your\repos\main-project"
    repo_name = "main-project"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8080/index" `
  -Method POST -ContentType "application/json" `
  -Body $repoData
```

### Step 2: Find Missing Repositories

```powershell
# See what repositories you're missing
Invoke-RestMethod "http://localhost:8080/maven/conflicts"
```

This will show you dependencies like:
```json
{
  "conflicts": [
    {
      "group_artifact": "com.yourcompany:user-service",
      "conflicting_versions": ["2.1.0"],
      "dependencies": [
        {
          "from_artifact": "com.yourcompany:main-project:1.0.0",
          "to_artifact_id": "user-service",
          "scope": "compile"
        }
      ]
    }
  ]
}
```

**Translation:** You need to clone the `user-service` repository!

### Step 3: Clone Missing Repositories

```powershell
# Based on the analysis above
cd C:\your\repos
git clone https://your-git-server/user-service.git
```

### Step 4: Index New Repositories

```powershell
# Add the new repository to the system
$newRepoData = @{
    repo_path = "C:\your\repos\user-service"
    repo_name = "user-service"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8080/index" `
  -Method POST -ContentType "application/json" `
  -Body $newRepoData
```

### Step 5: Repeat Until Complete

```powershell
# Check for remaining missing dependencies
Invoke-RestMethod "http://localhost:8080/maven/conflicts"
```

Repeat until no more internal dependencies are missing.

## 🧭 Visual Exploration

### Neo4j Browser
- **URL**: http://localhost:7474
- **Login**: `neo4j` / `codebase-rag-2024`

### Find Missing Dependencies Visually
```cypher
// Find internal dependencies without corresponding repositories
MATCH (a:MavenArtifact)-[:DEPENDS_ON]->(dep:MavenArtifact)
WHERE dep.group_id CONTAINS 'yourcompany'  // Replace with your org
  AND NOT EXISTS {
    MATCH (r:Repository)-[:DEFINES_ARTIFACT]->(dep)
  }
RETURN dep.group_id, dep.artifact_id, dep.version
ORDER BY dep.group_id, dep.artifact_id
```

## 🔧 Daily Operations

### Start/Stop System
```powershell
# Start
.\start-mvp.ps1

# Stop
podman-compose -f mvp-compose.yml down

# Check status
podman-compose -f mvp-compose.yml ps
```

### Search Your Code
```powershell
# Semantic search across all repositories
Invoke-RestMethod "http://localhost:8080/search?q=authentication function"
```

### Get System Status
```powershell
# Overall system health
Invoke-RestMethod "http://localhost:8080/status"

# Repository statistics
Invoke-RestMethod "http://localhost:8080/repositories"
```

## 🛠️ What's Included

### Core Components
- **ChromaDB**: Semantic search across your code
- **Neo4j**: Dependency graph analysis
- **FastAPI**: REST API for all operations
- **Maven Parser**: POM.xml analysis and conflict detection

### Supported Languages
- Java, Python, JavaScript/TypeScript, Go, Rust, C/C++, C#
- Configuration files: JSON, YAML, XML, properties files
- Documentation: Markdown, text files

### Key Features
- **Dependency Discovery**: Find missing repositories
- **Conflict Detection**: Identify version conflicts
- **Semantic Search**: Find code by meaning, not keywords
- **Cross-Repository Analysis**: Understand relationships between projects
- **Local Processing**: Everything runs on your machine

## 🚨 Quick Troubleshooting

### Service Won't Start
```powershell
# Check what's using the ports
netstat -ano | findstr :8080
netstat -ano | findstr :7474

# Kill conflicting processes
taskkill /PID <PID> /F
```

### Out of Memory
```powershell
# Check system resources
Get-ComputerInfo | Select-Object TotalPhysicalMemory
```
Need at least 8GB RAM for optimal performance.

### Can't Find Repositories
- Make sure `REPOS_PATH` points to your repositories directory
- Verify the path exists and contains your projects
- Use absolute paths (e.g., `C:\repos\project` not `repos\project`)

### Containers Won't Start
```powershell
# Check container logs
podman logs codebase-rag-api
podman logs codebase-rag-neo4j
podman logs codebase-rag-chromadb
```

## 📚 Available Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | System health check |
| `GET` | `/docs` | Interactive API documentation |
| `POST` | `/index` | Index a repository |
| `GET` | `/search` | Search across repositories |
| `GET` | `/repositories` | List indexed repositories |
| `GET` | `/status` | System status and statistics |
| `GET` | `/maven/conflicts` | Find dependency conflicts |
| `GET` | `/maven/dependencies/{group}/{artifact}/{version}` | Get Maven dependencies |

## 📖 Advanced Guides

For detailed workflows and enterprise setup:
- **[Dependency Discovery Guide](docs/DEPENDENCY-DISCOVERY.md)** - Complete workflow for finding missing repositories
- **[Windows Setup](docs/WINDOWS-SETUP.md)** - Detailed Windows installation guide
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions

## 💡 Tips for Success

1. **Start Small**: Index your main repository first
2. **Use Descriptive Names**: Give repositories meaningful names when indexing
3. **Check Regularly**: Re-run conflict analysis after adding new repositories
4. **Use the Browser**: Visit `/docs` for interactive API testing
5. **Visual Analysis**: Use Neo4j Browser to explore dependency relationships

---

**🎯 This MVP helps you quickly discover and manage repository dependencies in enterprise environments. Perfect for understanding your complete codebase landscape.**