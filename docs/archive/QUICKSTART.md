# 🚀 Codebase RAG MVP - Ultra Quick Start

**Find all repositories your project depends on in 5 minutes.**

## Prerequisites

- **Podman** installed ([Download here](https://podman.io/getting-started/installation))
- **8GB+ RAM** (recommended)
- **Git repositories** on your local machine

## 1-Command Setup

```bash
# Clone and start
git clone <this-repo-url> codebase-rag
cd codebase-rag
export REPOS_PATH="/path/to/your/repos"  # Replace with your repos folder
./start-mvp.sh
```

**That's it!** The system will:
- Pull required Docker images
- Start 3 services (ChromaDB, Neo4j, FastAPI)
- Be ready in ~2-3 minutes

## 🎯 Core Workflow: Find Missing Repositories

### Step 1: Index Your Main Repository

```bash
curl -X POST "http://localhost:8080/index" \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "/path/to/your/main-repo", "repo_name": "main-project"}'
```

### Step 2: Discover Missing Dependencies

```bash
curl "http://localhost:8080/maven/conflicts"
```

This shows you which internal repositories you're missing:

```json
{
  "conflicts": [
    {
      "group_artifact": "com.yourcompany:user-service",
      "missing_repository": true,
      "dependencies": [...]
    }
  ]
}
```

### Step 3: Clone Missing Repos & Repeat

```bash
# Based on the output above
git clone https://your-git-server/user-service.git /path/to/your/repos/user-service

# Index the new repo
curl -X POST "http://localhost:8080/index" \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "/path/to/your/repos/user-service", "repo_name": "user-service"}'

# Check for more missing deps
curl "http://localhost:8080/maven/conflicts"
```

Repeat until no more internal dependencies are missing!

## 📊 Browse Your Knowledge Graph

- **API Docs**: http://localhost:8080/docs
- **Neo4j Browser**: http://localhost:7474 (neo4j / codebase-rag-2024)
- **Search**: http://localhost:8080/search?q=authentication

## 🛠️ Management

```bash
# View logs
podman compose -f mvp-compose-optimized.yml logs -f

# Stop everything
podman compose -f mvp-compose-optimized.yml down

# Resource usage (optimized for 8GB+ machines)
# - ChromaDB: 2GB RAM
# - Neo4j: 4GB RAM  
# - API: 2GB RAM
# Total: ~8GB RAM + overhead
```

## 🔍 Advanced Usage

### Search Your Codebase
```bash
curl "http://localhost:8080/search?q=payment processing logic"
```

### Query Dependency Graph
```bash
curl "http://localhost:8080/graph/query?cypher=MATCH (r:Repository)-[:DEPENDS_ON]->(dep) RETURN r.name, dep.artifact_id"
```

### Repository Statistics
```bash
curl "http://localhost:8080/status"
```

## ❓ Troubleshooting

**Services won't start?**
- Check ports 8000, 7474, 7687, 8080 aren't in use
- Ensure 8GB+ RAM available
- Run `podman system prune` to clean up

**Can't find repositories?**
- Verify `REPOS_PATH` points to correct directory
- Check repository paths in API calls
- Ensure repositories contain Maven projects (pom.xml files)

**Need help?** Check the full docs in the `docs/` folder.

---

## What This MVP Does

✅ **Recursively discovers all Git repos in dependencies**  
✅ **Loads everything into a knowledge graph (Neo4j)**  
✅ **Enables semantic search with AI agents (ChromaDB)**  
✅ **Runs locally with containers (Podman)**  
✅ **No AWS dependencies - uses local sentence transformers**

Perfect for enterprise teams who need to understand their complete codebase landscape!