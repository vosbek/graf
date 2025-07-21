# 💻 Windows Installation Guide

## 🎯 **Complete Windows Setup for Codebase RAG MVP**

This comprehensive guide covers all Windows installation methods, from quick setup to enterprise deployment.

---

## 📋 **System Requirements**

### **Minimum Requirements**
- **OS**: Windows 10 version 2004+ or Windows 11
- **RAM**: 8GB minimum, 16GB+ recommended
- **Disk Space**: 10GB free space minimum
- **CPU**: 4+ cores recommended for optimal performance

### **Recommended Enterprise Setup**
- **OS**: Windows 11 Enterprise or Windows Server 2022
- **RAM**: 32GB+ for large codebases
- **Disk Space**: 50GB+ for enterprise repositories
- **CPU**: 8+ cores with virtualization support
- **Network**: Corporate network access for repository cloning

### **Required Software**
- **Podman Desktop** (recommended) or Docker Desktop
- **Git for Windows** with bash support
- **PowerShell 7+** (optional but recommended)
- **WSL2** (for native Linux performance)

---

## 🚀 **Installation Methods**

### **Method 1: Quick Setup (Recommended)**

#### **Step 1: Install Prerequisites**
```powershell
# Install Podman Desktop (visit podman-desktop.io)
winget install podman-desktop

# Install Git for Windows
winget install Git.Git

# Verify installations
podman --version
git --version
```

#### **Step 2: Download and Setup MVP**
```powershell
# Clone the repository
git clone <repository-url> CodebaseRAG
cd CodebaseRAG

# Set your repositories path
$env:REPOS_PATH = "C:\your\repos\path"

# Start the MVP
.\start-enterprise-mvp.ps1
```

#### **Step 3: Verify Installation**
```powershell
# Check system health
Invoke-RestMethod "http://localhost:8080/health"

# Check AI agent
Invoke-RestMethod "http://localhost:8080/agent/health"
```

### **Method 2: WSL2 + Podman (Enterprise)**

#### **Step 1: Enable WSL2**
```powershell
# Run as Administrator
wsl --install
# Restart computer when prompted
```

#### **Step 2: Install Podman in WSL2**
```bash
# In WSL2 terminal
curl -fsSL https://download.opensuse.org/repositories/devel:kubic:libcontainers:stable/xUbuntu_20.04/Release.key | sudo apt-key add -
echo "deb https://download.opensuse.org/repositories/devel:kubic:libcontainers:stable/xUbuntu_20.04/ /" | sudo tee /etc/apt/sources.list.d/devel:kubic:libcontainers:stable.list
sudo apt update
sudo apt install podman
```

#### **Step 3: Setup and Run MVP**
```bash
# In WSL2 terminal
git clone <repository-url> CodebaseRAG
cd CodebaseRAG

# Set repository path (Windows path accessible from WSL)
export REPOS_PATH="/mnt/c/your/repos"

# Start MVP
./start-mvp-simple.sh
```

### **Method 3: Docker Desktop Alternative**

#### **If you prefer Docker Desktop**
```powershell
# Install Docker Desktop
winget install Docker.DockerDesktop

# Replace podman commands with docker
# In mvp-compose-optimized.yml, ensure Docker compatibility
docker compose -f mvp-compose-optimized.yml up -d
```

---

## ⚙️ **Configuration**

### **Environment Configuration**
Create a `.env` file in the project root:
```env
# Repository Settings
REPOS_PATH=C:\your\enterprise\repos
API_PORT=8080

# Resource Limits (adjust for your system)
NEO4J_MEMORY=4G
CHROMADB_MEMORY=2G

# Enterprise Settings
LOG_LEVEL=INFO
ENABLE_MONITORING=true
```

### **Corporate Network Configuration**
```powershell
# For corporate proxies
$env:HTTP_PROXY = "http://proxy.company.com:8080"
$env:HTTPS_PROXY = "http://proxy.company.com:8080"

# Configure Git for corporate environment
git config --global http.proxy http://proxy.company.com:8080
git config --global https.proxy http://proxy.company.com:8080
```

### **Repository Path Configuration**
```powershell
# Common enterprise repository structures
$env:REPOS_PATH = "C:\SourceCode\Repositories"          # Local development
$env:REPOS_PATH = "\\fileserver\shared\repositories"    # Network share
$env:REPOS_PATH = "C:\Projects\Legacy\StrutsApps"       # Migration projects
```

---

## 🏢 **Enterprise Considerations**

### **Security Configuration**
```powershell
# Run with least privilege
# Create dedicated service account for MVP
net user CodebaseRAGService /add
net localgroup "Users" CodebaseRAGService /add

# Configure firewall rules
netsh advfirewall firewall add rule name="Codebase RAG MVP" dir=in action=allow protocol=TCP localport=8080
```

### **Performance Optimization**
```powershell
# Increase virtual memory for large codebases
# Control Panel → System → Advanced → Performance → Settings → Advanced → Virtual Memory

# Configure Windows Defender exclusions
Add-MpPreference -ExclusionPath "C:\path\to\CodebaseRAG"
Add-MpPreference -ExclusionPath $env:REPOS_PATH
```

### **Monitoring Setup**
```powershell
# Enable Windows Performance Toolkit
# Monitor resource usage during indexing
Get-Counter "\Process(podman)\% Processor Time"
Get-Counter "\Process(podman)\Working Set"
```

### **Backup Configuration**
```powershell
# Backup MVP data volumes
podman volume ls
podman volume inspect chromadb_data
podman volume inspect neo4j_data

# Script for automated backups
$backupPath = "C:\Backups\CodebaseRAG"
podman run --rm -v chromadb_data:/source -v $backupPath:/backup alpine tar czf /backup/chromadb_backup.tar.gz -C /source .
```

---

## 🚨 **Troubleshooting**

### **Common Installation Issues**

#### **Podman Issues**
```powershell
# Fix: "podman machine not found"
podman machine init
podman machine start

# Fix: WSL2 integration issues
wsl --update
podman machine reset
```

#### **Memory Issues**
```powershell
# Check available memory
Get-ComputerInfo | Select-Object TotalPhysicalMemory, AvailablePhysicalMemory

# Reduce resource allocation in compose file
# Edit mvp-compose-optimized.yml:
# - Change mem_limit: 4g to mem_limit: 2g
# - Reduce Neo4j memory settings
```

#### **Port Conflicts**
```powershell
# Check what's using the ports
netstat -ano | findstr :8080
netstat -ano | findstr :7474
netstat -ano | findstr :8000

# Kill conflicting processes
taskkill /PID <PID> /F

# Or change ports in compose file
```

#### **Repository Access Issues**
```powershell
# Fix: "Permission denied" errors
icacls $env:REPOS_PATH /grant Everyone:R /T

# Fix: Network path issues  
net use Z: \\server\repositories /persistent:yes
$env:REPOS_PATH = "Z:\"
```

### **Performance Troubleshooting**

#### **Slow Indexing**
```powershell
# Check disk I/O
Get-Counter "\PhysicalDisk(_Total)\Disk Reads/sec"
Get-Counter "\PhysicalDisk(_Total)\Disk Writes/sec"

# Solutions:
# 1. Use SSD for better performance
# 2. Exclude build directories (target/, node_modules/)
# 3. Index repositories one at a time
```

#### **High Memory Usage**
```powershell
# Monitor memory usage
Get-Process -Name podman | Format-Table ProcessName, WorkingSet, VirtualMemorySize

# Solutions:
# 1. Increase virtual memory
# 2. Close other applications
# 3. Use smaller batch sizes for indexing
```

### **Network Troubleshooting**

#### **Container Communication Issues**
```powershell
# Check container networking
podman network ls
podman network inspect codebase-rag-network

# Reset networking if needed
podman network rm codebase-rag-network
podman network create codebase-rag-network
```

#### **Enterprise Firewall Issues**
```powershell
# Check Windows Firewall
Get-NetFirewallRule -DisplayName "*Codebase*"

# Allow PowerShell script execution
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser

# Corporate proxy configuration
$env:NO_PROXY = "localhost,127.0.0.1"
```

---

## 🔧 **Advanced Configuration**

### **Custom Resource Limits**
```yaml
# Edit mvp-compose-optimized.yml for your system
services:
  chromadb:
    mem_limit: 4g     # Adjust based on available RAM
    cpus: 2           # Adjust based on CPU cores
  
  neo4j:
    mem_limit: 8g     # Increase for large codebases
    environment:
      - NEO4J_dbms_memory_heap_max_size=4G
```

### **SSL/TLS Configuration**
```powershell
# For enterprise security requirements
# Generate certificates
New-SelfSignedCertificate -DnsName localhost -CertStoreLocation Cert:\LocalMachine\My

# Configure HTTPS in compose file
# Add SSL certificate volumes and environment variables
```

### **Active Directory Integration**
```powershell
# For enterprise user management
# Configure LDAP authentication in application settings
# Set environment variables for AD integration
$env:AUTH_PROVIDER = "ActiveDirectory"
$env:AD_SERVER = "ldap://company.com:389"
```

---

## ✅ **Verification Checklist**

### **Post-Installation Verification**
- [ ] Podman/Docker running correctly
- [ ] All containers started successfully
- [ ] API endpoints responding (http://localhost:8080/docs)
- [ ] AI agent healthy (http://localhost:8080/agent/health)
- [ ] Repository path accessible
- [ ] Test indexing with sample repository
- [ ] Natural language queries working

### **Enterprise Readiness Checklist**
- [ ] Security policies configured
- [ ] Monitoring setup complete
- [ ] Backup procedures documented
- [ ] Network access properly configured
- [ ] Resource limits appropriate for workload
- [ ] User access controls implemented
- [ ] Troubleshooting procedures documented

---

## 📞 **Getting Help**

### **Common Support Resources**
- **GitHub Issues**: Report bugs and feature requests
- **Documentation**: Check [docs/index.md](../index.md) for additional guides
- **Troubleshooting**: See [TROUBLESHOOTING.md](../../TROUBLESHOOTING.md)

### **Enterprise Support**
- **System Requirements**: Verify hardware meets enterprise workload needs
- **Security Review**: Ensure configuration meets corporate policies  
- **Performance Tuning**: Optimize for large codebase analysis
- **Integration**: Connect with existing enterprise tools and workflows

---

**Your Windows environment is now ready for enterprise-grade Struts application analysis and migration planning!**

➡️ **Next**: [Start analyzing your codebase](../usage/dependency-discovery.md) or [Learn about AI agent features](../usage/ai-agent.md)