# Codebase RAG MVP - Windows Enterprise Setup

## Overview
This is a minimal viable product (MVP) for code analysis and dependency discovery designed for Windows enterprise environments. It uses containerized services with Podman for easy deployment and management.

## Prerequisites

### System Requirements
- **Windows 10/11 Pro or Enterprise** (Windows Home supported via WSL2)
- **8GB+ RAM** recommended (minimum 4GB)
- **10GB+ free disk space**
- **PowerShell 5.1+** (built into Windows)

### Required Software
- **Podman Desktop** - Container runtime
  - Download: https://podman.io/desktop
  - Alternative: Use WSL2 if Hyper-V is not available

## Quick Start

### 1. Download and Extract
```powershell
# Extract the codebase to your desired location
cd C:\enterprise-apps\codebase-rag
```

### 2. Set Repository Path (Optional)
```powershell
# Set environment variable for your code repositories
$env:REPOS_PATH = "C:\source\repos"
```

### 3. Start the MVP
```powershell
# Run the startup script
.\start-mvp.ps1
```

The script will:
- Check system requirements
- Install and configure Podman if needed
- Start all required services (ChromaDB, Neo4j, API)
- Display available endpoints

### 4. Access the Application
- **API Documentation**: http://localhost:8080/docs
- **Health Check**: http://localhost:8080/health
- **Neo4j Browser**: http://localhost:7474 (neo4j / codebase-rag-2024)
- **ChromaDB**: http://localhost:8000

## Enterprise Features

### Dependency Discovery
The primary use case - discover missing repositories based on your codebase dependencies:

```powershell
# Index your repositories
Invoke-RestMethod -Uri "http://localhost:8080/index" `
  -Method POST -ContentType "application/json" `
  -Body '{"repo_path": "C:/source/my-project", "repo_name": "my-project"}'

# Discover missing dependencies
Invoke-RestMethod -Uri "http://localhost:8080/maven/missing-repos"
```

### Code Search
Semantic code search across all indexed repositories:

```powershell
# Search for authentication functions
Invoke-RestMethod -Uri "http://localhost:8080/search?q=authentication function"

# Search for specific patterns
Invoke-RestMethod -Uri "http://localhost:8080/search?q=database connection"
```

### Maven Dependency Analysis
For Java projects, analyze Maven dependencies:

```powershell
# View all dependencies
Invoke-RestMethod -Uri "http://localhost:8080/maven/dependencies"

# Check for conflicts
Invoke-RestMethod -Uri "http://localhost:8080/maven/conflicts"

# Find specific dependency usage
Invoke-RestMethod -Uri "http://localhost:8080/maven/dependencies/org.springframework/spring-core/5.3.21"
```

## Enterprise Deployment

### Network Configuration
The MVP uses these ports:
- **8080** - API Service
- **8000** - ChromaDB (Vector Database)
- **7474** - Neo4j HTTP (Graph Database)
- **7687** - Neo4j Bolt Protocol

### Security Considerations
- All services run locally in containers
- No external network access required
- Default credentials: neo4j / codebase-rag-2024
- Change default passwords in production

### Resource Management
- **Total Memory**: ~6GB allocated across services
- **CPU**: ~8 cores recommended for optimal performance
- **Storage**: Data persisted in named volumes

## Management Commands

### Service Management
```powershell
# Stop all services
podman compose -f mvp-compose.yml down

# Restart services
podman compose -f mvp-compose.yml restart

# View service status
podman compose -f mvp-compose.yml ps

# View logs
podman compose -f mvp-compose.yml logs -f api
```

### Data Management
```powershell
# Backup data volumes
podman volume export chromadb_data > chromadb_backup.tar
podman volume export neo4j_data > neo4j_backup.tar

# Clean up (removes all data)
podman compose -f mvp-compose.yml down -v
```

## Troubleshooting

### Common Issues

**Podman not found**
```powershell
# Install Podman Desktop from https://podman.io/desktop
# Or use WSL2 backend if Hyper-V is unavailable
```

**Services not starting**
```powershell
# Check container logs
podman logs codebase-rag-api
podman logs codebase-rag-neo4j
podman logs codebase-rag-chromadb

# Check system resources
podman stats
```

**Port conflicts**
```powershell
# Check if ports are in use
netstat -an | findstr "8080"
netstat -an | findstr "7474"
netstat -an | findstr "8000"
```

### Performance Optimization
- Ensure sufficient RAM allocation
- Use SSD storage for better performance
- Adjust memory settings in mvp-compose.yml
- Monitor resource usage with `podman stats`

## Enterprise Support

### Configuration
- Service configurations in `mvp-compose.yml`
- Environment variables supported via `.env` file
- Persistent data storage in named volumes

### Monitoring
- Health checks built into all services
- Prometheus metrics available (optional)
- Container resource monitoring via Podman

### Backup Strategy
- Database backups via volume exports
- Configuration files in version control
- Automated backup scripts available

## Next Steps

1. **Index your repositories** using the `/index` endpoint
2. **Analyze dependencies** to find missing repositories
3. **Search your codebase** with semantic queries
4. **Explore the Neo4j browser** for dependency visualization
5. **Set up automated indexing** for new repositories

For detailed usage instructions, see the API documentation at http://localhost:8080/docs

---

**Enterprise Support**: This MVP is designed for enterprise deployment with security, performance, and reliability in mind.