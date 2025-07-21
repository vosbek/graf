# Windows Troubleshooting Guide

Common issues and solutions when running the Codebase RAG MVP on Windows enterprise machines.

## 🔧 Installation Issues

### Podman Installation Problems

**Issue: "Podman Desktop won't install"**
```
Error: "This app can't run on your PC" or "Installation failed"
```

**Solutions:**
1. **Check Windows version:**
   ```powershell
   Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion
   ```
   Requires Windows 10 Pro/Enterprise or Windows 11

2. **Run as Administrator:**
   - Right-click installer → "Run as administrator"

3. **Enable Hyper-V:**
   ```powershell
   # Check if Hyper-V is enabled
   Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All
   
   # Enable Hyper-V if needed
   Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All
   Enable-WindowsOptionalFeature -Online -FeatureName Containers -All
   ```
   Restart computer after enabling.

4. **Check virtualization in BIOS:**
   - Restart computer → Enter BIOS
   - Enable "Intel VT-x" or "AMD-V"
   - Enable "Hyper-V" or "Virtualization Technology"

**Issue: "podman command not found"**

**Solutions:**
1. **Restart PowerShell:**
   Close and reopen PowerShell to refresh PATH

2. **Manually add to PATH:**
   ```powershell
   $env:PATH += ";C:\Program Files\Podman Desktop\resources\bin"
   ```

3. **Verify installation location:**
   ```powershell
   Get-ChildItem "C:\Program Files" -Name "*Podman*"
   ```

### Git Installation Problems

**Issue: "git command not found"**

**Solutions:**
1. **Install Git for Windows:**
   - Download: https://git-scm.com/download/win
   - Use default installation options

2. **Check PATH:**
   ```powershell
   $env:PATH -split ';' | Where-Object { $_ -like "*Git*" }
   ```

3. **Manual PATH addition:**
   ```powershell
   $env:PATH += ";C:\Program Files\Git\bin"
   ```

## 🚀 Startup Issues

### Port Conflicts

**Issue: "Port already in use" errors**
```
Error: bind: address already in use: listen tcp 0.0.0.0:8080
```

**Solutions:**
1. **Find what's using the port:**
   ```powershell
   # Check common ports
   netstat -ano | findstr :8080  # API
   netstat -ano | findstr :7474  # Neo4j HTTP
   netstat -ano | findstr :7687  # Neo4j Bolt
   netstat -ano | findstr :8000  # ChromaDB
   ```

2. **Kill the conflicting process:**
   ```powershell
   # Replace <PID> with the process ID from netstat output
   taskkill /PID <PID> /F
   ```

3. **Change ports (if needed):**
   Edit `mvp-compose.yml` to use different ports:
   ```yaml
   api:
     ports:
       - "8081:8080"  # Change external port
   ```

### Container Startup Failures

**Issue: "Container failed to start"**

**Solutions:**
1. **Check container logs:**
   ```powershell
   podman logs codebase-rag-api
   podman logs codebase-rag-neo4j
   podman logs codebase-rag-chromadb
   ```

2. **Check available resources:**
   ```powershell
   # Check memory
   Get-ComputerInfo | Select-Object TotalPhysicalMemory, AvailablePhysicalMemory
   
   # Check disk space
   Get-WmiObject -Class Win32_LogicalDisk | Where-Object {$_.DriveType -eq 3} | 
     Select-Object DeviceID, @{Name="Size(GB)";Expression={[math]::Round($_.Size/1GB,2)}}, 
     @{Name="FreeSpace(GB)";Expression={[math]::Round($_.FreeSpace/1GB,2)}}
   ```

3. **Increase resource limits:**
   Edit `mvp-compose.yml`:
   ```yaml
   neo4j:
     mem_limit: 4g  # Reduce if needed
     cpus: 2        # Reduce if needed
   ```

4. **Clear Podman cache:**
   ```powershell
   podman system prune -f
   podman volume prune -f
   ```

### Network Issues

**Issue: "Cannot connect to services"**

**Solutions:**
1. **Check Windows Firewall:**
   ```powershell
   # Allow the ports through firewall
   New-NetFirewallRule -DisplayName "Codebase RAG API" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow
   New-NetFirewallRule -DisplayName "Codebase RAG Neo4j" -Direction Inbound -Protocol TCP -LocalPort 7474 -Action Allow
   New-NetFirewallRule -DisplayName "Codebase RAG ChromaDB" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
   ```

2. **Check if services are listening:**
   ```powershell
   Test-NetConnection -ComputerName localhost -Port 8080
   Test-NetConnection -ComputerName localhost -Port 7474
   Test-NetConnection -ComputerName localhost -Port 8000
   ```

3. **Test container networking:**
   ```powershell
   # Check if containers can communicate
   podman exec codebase-rag-api curl http://chromadb:8000/api/v1/heartbeat
   ```

## 💾 Storage and Performance Issues

### Disk Space Problems

**Issue: "No space left" or "Volume full"**

**Solutions:**
1. **Check disk usage:**
   ```powershell
   # Check container disk usage
   podman system df
   
   # Check volume usage
   podman volume ls
   ```

2. **Clean up Podman data:**
   ```powershell
   # Remove unused containers
   podman container prune -f
   
   # Remove unused images
   podman image prune -f
   
   # Remove unused volumes (WARNING: This deletes data)
   podman volume prune -f
   ```

3. **Move Podman storage location:**
   ```powershell
   # Stop all containers first
   podman-compose -f mvp-compose.yml down
   
   # Edit Podman configuration to use different drive
   # Location: %APPDATA%\containers\storage.conf
   ```

### Performance Issues

**Issue: "System is slow" or "High CPU/Memory usage"**

**Solutions:**
1. **Monitor resource usage:**
   ```powershell
   # Check container stats
   podman stats
   
   # Check Windows performance
   Get-Counter "\Processor(_Total)\% Processor Time" -SampleInterval 5 -MaxSamples 3
   Get-Counter "\Memory\Available MBytes" -SampleInterval 5 -MaxSamples 3
   ```

2. **Optimize container resources:**
   Edit `mvp-compose.yml`:
   ```yaml
   # Reduce Neo4j memory if system is constrained
   neo4j:
     environment:
       - NEO4J_dbms_memory_heap_initial_size=2G
       - NEO4J_dbms_memory_heap_max_size=4G
       - NEO4J_dbms_memory_pagecache_size=2G
     mem_limit: 6g
   
   # Reduce ChromaDB memory
   chromadb:
     mem_limit: 2g
   ```

3. **Close unnecessary applications:**
   ```powershell
   # Find memory-hungry processes
   Get-Process | Sort-Object WorkingSet -Descending | Select-Object -First 10
   ```

## 🔐 Security and Access Issues

### Permission Problems

**Issue: "Access denied" or "Permission denied"**

**Solutions:**
1. **Run PowerShell as Administrator:**
   - Right-click PowerShell → "Run as administrator"

2. **Check repository access:**
   ```powershell
   # Test if you can read the repository directory
   Test-Path "C:\your\repos\your-project"
   Get-ChildItem "C:\your\repos\your-project" | Select-Object Name -First 5
   ```

3. **Fix file permissions:**
   ```powershell
   # Give full control to your user account
   icacls "C:\your\repos" /grant "$env:USERNAME:(OI)(CI)F" /T
   ```

### Enterprise Network Issues

**Issue: "Cannot download images" or "Network timeouts"**

**Solutions:**
1. **Configure proxy (if needed):**
   ```powershell
   # Set proxy for Podman
   [Environment]::SetEnvironmentVariable("HTTP_PROXY", "http://proxy.company.com:8080", "User")
   [Environment]::SetEnvironmentVariable("HTTPS_PROXY", "http://proxy.company.com:8080", "User")
   ```

2. **Check corporate firewall:**
   ```powershell
   # Test connectivity to container registries
   Test-NetConnection -ComputerName registry-1.docker.io -Port 443
   Test-NetConnection -ComputerName quay.io -Port 443
   ```

3. **Use internal registry (if available):**
   Edit `mvp-compose.yml` to use your company's internal registry:
   ```yaml
   chromadb:
     image: internal-registry.company.com/chromadb/chroma:latest
   ```

### Antivirus Issues

**Issue: "Files being quarantined" or "Slow file access"**

**Solutions:**
1. **Add exclusions to Windows Defender:**
   ```powershell
   # Exclude Podman directories
   Add-MpPreference -ExclusionPath "C:\Program Files\Podman"
   Add-MpPreference -ExclusionPath "$env:APPDATA\containers"
   Add-MpPreference -ExclusionPath "C:\CodebaseRAG"
   
   # Exclude processes
   Add-MpPreference -ExclusionProcess "podman.exe"
   Add-MpPreference -ExclusionProcess "conmon.exe"
   ```

2. **Configure corporate antivirus:**
   Work with IT to exclude:
   - Podman installation directory
   - Container storage locations
   - Repository directories

## 🔄 Recovery and Reset

### Complete System Reset

**When to use:** If everything is broken and you want to start fresh.

```powershell
# 1. Stop all containers
podman-compose -f mvp-compose.yml down

# 2. Remove all containers
podman container rm -f $(podman container ls -aq)

# 3. Remove all images
podman image rm -f $(podman image ls -aq)

# 4. Remove all volumes (WARNING: Deletes all data)
podman volume rm -f $(podman volume ls -q)

# 5. Clean system
podman system prune -af

# 6. Restart from beginning
.\start-mvp.ps1
```

### Backup and Restore Data

**Backup your indexed data:**
```powershell
# Create backup directory
New-Item -ItemType Directory -Path "C:\CodebaseRAG-Backup" -Force

# Export Neo4j data
podman exec codebase-rag-neo4j neo4j-admin dump --database=neo4j --to=/tmp/neo4j-backup.dump
podman cp codebase-rag-neo4j:/tmp/neo4j-backup.dump C:\CodebaseRAG-Backup\

# Export ChromaDB data (copy the volume)
podman volume export chromadb_data > C:\CodebaseRAG-Backup\chromadb_data.tar
```

**Restore your data:**
```powershell
# Stop services
podman-compose -f mvp-compose.yml down

# Restore ChromaDB volume
podman volume import chromadb_data C:\CodebaseRAG-Backup\chromadb_data.tar

# Restore Neo4j data
podman cp C:\CodebaseRAG-Backup\neo4j-backup.dump codebase-rag-neo4j:/tmp/
podman exec codebase-rag-neo4j neo4j-admin load --database=neo4j --from=/tmp/neo4j-backup.dump

# Restart services
podman-compose -f mvp-compose.yml up -d
```

## 📞 Getting Help

### Diagnostic Information

When asking for help, provide this information:

```powershell
# System information
Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion, TotalPhysicalMemory

# Podman version
podman --version

# Container status
podman-compose -f mvp-compose.yml ps

# Recent logs
podman logs codebase-rag-api --tail 50
podman logs codebase-rag-neo4j --tail 50
podman logs codebase-rag-chromadb --tail 50

# System resources
Get-Counter "\Processor(_Total)\% Processor Time" -MaxSamples 1
Get-Counter "\Memory\Available MBytes" -MaxSamples 1
```

### Common Error Messages and Solutions

| Error Message | Likely Cause | Solution |
|---------------|--------------|----------|
| "bind: address already in use" | Port conflict | Kill process using port or change port |
| "no space left on device" | Disk full | Clean up disk space or move storage |
| "permission denied" | Access rights | Run as Administrator |
| "network timeout" | Firewall/proxy | Configure network settings |
| "container failed to start" | Resource limits | Reduce memory/CPU limits |
| "command not found" | PATH issue | Restart PowerShell or fix PATH |

### Enterprise IT Support

If you need to involve your IT department:

**Information to provide:**
- You're running containerized applications for code analysis
- Uses ports 8080, 7474, 7687, 8000 locally
- Requires container runtime (Podman)
- Downloads container images from public registries
- No external network connections from containers

**Requests for IT:**
- Firewall exceptions for local ports
- Antivirus exclusions for Podman directories
- Proxy configuration if needed
- Access to internal container registry (if available)

---

**🔧 This troubleshooting guide covers the most common issues encountered when running the MVP on Windows enterprise machines. Most problems can be resolved with these solutions.**