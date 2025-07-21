# Troubleshooting Guide

Common issues and quick solutions for the Codebase RAG MVP.

## 🚨 Quick Diagnostics

### Check System Status
```powershell
# Test if services are running (use correct port for your setup)
Invoke-RestMethod "http://localhost:8082/health"  # Podman-only script
# OR
Invoke-RestMethod "http://localhost:8080/health"  # Compose script

# Check container status
podman ps

# View recent logs
podman logs codebase-rag-api --tail 20
```

### System Requirements Check
```powershell
# Check Windows version and RAM
Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion, TotalPhysicalMemory

# Check disk space
Get-WmiObject -Class Win32_LogicalDisk | Where-Object {$_.DriveType -eq 3} | 
  Select-Object DeviceID, @{Name="FreeSpace(GB)";Expression={[math]::Round($_.FreeSpace/1GB,2)}}
```

## 🔧 Installation Issues

### "Podman command not found"
```powershell
# Solution 1: Restart PowerShell
# Close and reopen PowerShell

# Solution 2: Add to PATH manually
$env:PATH += ";C:\Program Files\Podman Desktop\resources\bin"

# Solution 3: Check installation
Get-ChildItem "C:\Program Files" -Name "*Podman*"
```

### "Git command not found"
```powershell
# Install Git for Windows from: https://git-scm.com/download/win
# Or add to PATH manually
$env:PATH += ";C:\Program Files\Git\bin"
```

### Podman Won't Install
1. **Check Windows version** - Need Windows 10 Pro/Enterprise or Windows 11
2. **Run as Administrator** - Right-click installer → "Run as administrator"
3. **Enable Hyper-V** (if needed):
   ```powershell
   Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All
   ```
   Restart computer after enabling.

## 🚀 Service Startup Issues

### "Port already in use"
```powershell
# Find what's using the ports (check all possible ports)
netstat -ano | findstr :8080   # API (compose script)
netstat -ano | findstr :8082   # API (Podman-only script)
netstat -ano | findstr :7474   # Neo4j
netstat -ano | findstr :8000   # ChromaDB (compose)
netstat -ano | findstr :8001   # ChromaDB (Podman-only)

# Kill the conflicting process (replace <PID> with actual process ID)
taskkill /PID <PID> /F
```

### Containers Won't Start
```powershell
# Check container logs
podman logs codebase-rag-api
podman logs codebase-rag-neo4j
podman logs codebase-rag-chromadb

# Check available memory (need 8GB+)
Get-ComputerInfo | Select-Object TotalPhysicalMemory, AvailablePhysicalMemory
```

### Out of Memory Errors
```powershell
# Check container resource usage
podman stats

# Free up memory by closing other applications
Get-Process | Sort-Object WorkingSet -Descending | Select-Object -First 10

# Restart with reduced memory limits (edit mvp-compose.yml)
```

### Services Start But Can't Connect
```powershell
# Check Windows Firewall
New-NetFirewallRule -DisplayName "Codebase RAG API" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow
New-NetFirewallRule -DisplayName "Codebase RAG Neo4j" -Direction Inbound -Protocol TCP -LocalPort 7474 -Action Allow
New-NetFirewallRule -DisplayName "Codebase RAG ChromaDB" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow

# Test connectivity
Test-NetConnection -ComputerName localhost -Port 8080
Test-NetConnection -ComputerName localhost -Port 7474
```

## 📋 Configuration Issues

### .env File Not Loading
```powershell
# Check if .env file exists
Test-Path .env

# If not, copy from example
Copy-Item .env.windows.example .env

# Verify .env file contents
Get-Content .env
```

### Wrong Repository Path in .env
```powershell
# Check if path exists
Test-Path "C:\your\repos"

# Fix path in .env file
notepad .env

# Verify repositories are accessible
Get-ChildItem "C:\your\repos"
```

### Port Conflicts from .env
```powershell
# Check what ports you're using
Get-Content .env | Select-String "PORT"

# Test if ports are available
Test-NetConnection -ComputerName localhost -Port 8082
Test-NetConnection -ComputerName localhost -Port 8001
```

## 💾 Repository and Indexing Issues

### "Can't find repositories" or "Access denied"
```powershell
# Check if repository path exists
Test-Path "C:\your\repos\your-project"

# Check if you can read the directory
Get-ChildItem "C:\your\repos\your-project" | Select-Object Name -First 5

# Run PowerShell as Administrator if needed
# Right-click PowerShell → "Run as administrator"
```

### Indexing Fails
```powershell
# Check repository path is correct and absolute
# Use: C:\repos\project (not repos\project)

# Check disk space
Get-WmiObject -Class Win32_LogicalDisk | Where-Object {$_.DriveType -eq 3}

# Check container logs for specific errors
podman logs codebase-rag-api --tail 50
```

### "No search results" After Indexing
```powershell
# Verify indexing completed successfully
Invoke-RestMethod "http://localhost:8080/status"

# Check repository was actually indexed
Invoke-RestMethod "http://localhost:8080/repositories"

# Try different search terms
Invoke-RestMethod "http://localhost:8080/search?q=function"
```

## 🔍 API and Search Issues

### API Returns Errors
```powershell
# Check API health (use correct port)
Invoke-RestMethod "http://localhost:8082/health"  # Podman-only
# OR
Invoke-RestMethod "http://localhost:8080/health"  # Compose

# Check detailed logs
podman logs codebase-rag-api --tail 50

# Restart API if needed
podman restart codebase-rag-api
```

### Dependency Analysis Not Working
```powershell
# Make sure you're analyzing Java/Maven projects
# Check if POM files exist in your repository
Get-ChildItem "C:\your\repos\your-project" -Recurse -Name "pom.xml"

# Check Maven parsing logs
podman logs codebase-rag-api | Select-String "maven"
```

### Neo4j Browser Won't Load
```powershell
# Check if Neo4j is running
Test-NetConnection -ComputerName localhost -Port 7474

# Check Neo4j logs
podman logs codebase-rag-neo4j --tail 20

# Try restarting Neo4j
podman-compose -f mvp-compose.yml restart neo4j
```

## 🔄 Performance Issues

### System is Slow
```powershell
# Check container resource usage
podman stats

# Check system performance
Get-Counter "\Processor(_Total)\% Processor Time" -MaxSamples 1
Get-Counter "\Memory\Available MBytes" -MaxSamples 1

# Close unnecessary applications
```

### Indexing Takes Too Long
```powershell
# Check if processing large files
# Look for repositories with many files
Get-ChildItem "C:\your\repos" -Recurse -File | Group-Object Directory | Sort-Object Count -Descending

# Consider indexing smaller repositories first
```

## 🆘 Emergency Recovery

### Complete System Reset
```powershell
# When everything is broken and you want to start fresh

# 1. Stop all containers
podman-compose -f mvp-compose.yml down

# 2. Remove all containers and images
podman container rm -f $(podman container ls -aq)
podman image rm -f $(podman image ls -aq)

# 3. Clean system
podman system prune -af

# 4. Restart from beginning
.\start-mvp.ps1
```

### Clear Data and Start Over
```powershell
# Stop services
podman-compose -f mvp-compose.yml down

# Remove data volumes (WARNING: Deletes all indexed data)
podman volume rm -f chromadb_data neo4j_data neo4j_logs

# Restart services (will recreate fresh databases)
.\start-mvp.ps1
```

## 📞 When to Get Help

### Collect This Information Before Asking for Help

```powershell
# System information
Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion, TotalPhysicalMemory

# Podman version
podman --version

# Container status
podman-compose -f mvp-compose.yml ps

# Recent API logs
podman logs codebase-rag-api --tail 50

# Health check
Invoke-RestMethod "http://localhost:8080/health" -ErrorAction SilentlyContinue
```

### Common Error Messages

| Error Message | Likely Cause | Quick Fix |
|---------------|--------------|-----------|
| "bind: address already in use" | Port conflict | Kill process using port |
| "no space left on device" | Disk full | Clean up disk space |
| "permission denied" | Access rights | Run as Administrator |
| "command not found" | PATH issue | Restart PowerShell |
| "connection refused" | Service not running | Check container status |

## 💡 Prevention Tips

1. **Always run PowerShell as Administrator** for initial setup
2. **Use absolute paths** for repositories (e.g., `C:\repos\project`)
3. **Keep at least 10GB free disk space**
4. **Close memory-hungry applications** before starting
5. **Use local drives** (avoid network drives when possible)
6. **Regular restarts** help with Windows resource management

---

**🔧 Most issues can be resolved with these solutions. For complex enterprise issues, refer to the detailed guides or contact your IT department.**