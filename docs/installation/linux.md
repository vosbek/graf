# 🐧 Linux Installation Guide

## 🎯 **Linux Setup for Codebase RAG MVP**

Complete installation guide for Ubuntu, CentOS, and other Linux distributions.

---

## 📋 **System Requirements**

### **Minimum Requirements**
- **OS**: Ubuntu 20.04+, CentOS 8+, or compatible Linux distribution
- **RAM**: 8GB minimum, 16GB+ recommended  
- **Disk Space**: 10GB free space minimum
- **CPU**: 4+ cores recommended

### **Recommended for Large Codebases**
- **RAM**: 32GB+ for enterprise repositories
- **Disk Space**: 50GB+ for extensive analysis
- **CPU**: 8+ cores with good I/O performance
- **Storage**: SSD recommended for indexing performance

---

## 🚀 **Quick Installation (Ubuntu/Debian)**

### **Step 1: Install Prerequisites**
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y curl git build-essential

# Install Podman
sudo apt install -y podman

# Verify installation
podman --version
git --version
```

### **Step 2: Setup MVP**
```bash
# Clone repository
git clone <repository-url> CodebaseRAG
cd CodebaseRAG

# Set repository path
export REPOS_PATH="/path/to/your/repos"

# Make scripts executable
chmod +x start-mvp-simple.sh

# Start MVP
./start-mvp-simple.sh
```

### **Step 3: Verify Installation**
```bash
# Check health
curl http://localhost:8080/health

# Check AI agent  
curl http://localhost:8080/agent/health
```

---

## 🔧 **Distribution-Specific Installation**

### **CentOS/RHEL/Fedora**
```bash
# Install Podman
sudo dnf install -y podman git

# For older versions (CentOS 7)
sudo yum install -y podman git

# Enable and start Podman
sudo systemctl enable --now podman
```

### **Arch Linux**
```bash
# Install from official repositories
sudo pacman -S podman git

# Enable user namespaces
echo 'kernel.unprivileged_userns_clone=1' | sudo tee /etc/sysctl.d/userns.conf
sudo sysctl --system
```

### **SUSE/openSUSE**
```bash
# Add container repository
sudo zypper addrepo https://download.opensuse.org/repositories/devel:/kubic:/libcontainers:/stable/openSUSE_Tumbleweed/devel:kubic:libcontainers:stable.repo
sudo zypper refresh

# Install Podman
sudo zypper install podman git
```

---

## ⚙️ **Configuration**

### **Environment Setup**
```bash
# Create environment file
cat > .env << EOF
# Repository configuration
REPOS_PATH=/opt/repositories
API_PORT=8080

# Resource limits
NEO4J_MEMORY=4G
CHROMADB_MEMORY=2G

# Logging
LOG_LEVEL=INFO
EOF
```

### **Podman Configuration**
```bash
# Configure rootless Podman
echo 'export XDG_RUNTIME_DIR="/run/user/$UID"' >> ~/.bashrc
echo 'export DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"' >> ~/.bashrc

# Configure subuid/subgid for rootless containers
sudo usermod --add-subuids 100000-165535 --add-subgids 100000-165535 $USER

# Enable linger for user
sudo loginctl enable-linger $USER
```

### **Systemd Service (Optional)**
```bash
# Create systemd service for automatic startup
sudo tee /etc/systemd/system/codebase-rag.service << EOF
[Unit]
Description=Codebase RAG MVP
After=network.target

[Service]
Type=forking
User=codebase-rag
WorkingDirectory=/opt/CodebaseRAG
Environment=REPOS_PATH=/opt/repositories
ExecStart=/opt/CodebaseRAG/start-mvp-simple.sh
ExecStop=/usr/bin/podman compose -f mvp-compose-optimized.yml down
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable codebase-rag
sudo systemctl start codebase-rag
```

---

## 🔐 **Security Configuration**

### **Firewall Setup**
```bash
# UFW (Ubuntu)
sudo ufw allow 8080/tcp
sudo ufw allow 7474/tcp  # Neo4j browser (optional)
sudo ufw enable

# firewalld (CentOS/RHEL)
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --reload

# iptables (manual)
sudo iptables -A INPUT -p tcp --dport 8080 -j ACCEPT
sudo iptables-save > /etc/iptables/rules.v4
```

### **SELinux Configuration (CentOS/RHEL)**
```bash
# Check SELinux status
sestatus

# Configure SELinux for containers
sudo setsebool -P container_manage_cgroup on
sudo setsebool -P virt_use_fusefs on

# If needed, create custom policy
sudo ausearch -c 'podman' --raw | audit2allow -M podman-local
sudo semodule -i podman-local.pp
```

### **User Permissions**
```bash
# Create dedicated user for MVP
sudo useradd -m -s /bin/bash codebase-rag
sudo usermod -aG docker codebase-rag  # If using Docker instead

# Set repository permissions
sudo chown -R codebase-rag:codebase-rag /opt/repositories
sudo chmod -R 755 /opt/repositories
```

---

## 📊 **Performance Optimization**

### **System Tuning**
```bash
# Increase file limits for large repositories
echo "* soft nofile 65536" | sudo tee -a /etc/security/limits.conf
echo "* hard nofile 65536" | sudo tee -a /etc/security/limits.conf

# Optimize virtual memory
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

# Configure swap (for systems with limited RAM)
sudo fallocate -l 8G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### **Storage Optimization**
```bash
# Use faster storage for data volumes
sudo mkdir -p /fast-storage/codebase-rag
sudo ln -s /fast-storage/codebase-rag /var/lib/containers/storage

# Configure tmpfs for temporary files
sudo mount -t tmpfs -o size=2G tmpfs /tmp/codebase-rag
```

---

## 🚨 **Troubleshooting**

### **Common Issues**

#### **Permission Errors**
```bash
# Fix: "permission denied" for containers
sudo chmod 666 /run/user/$UID/podman/podman.sock

# Fix: Repository access issues
sudo chown -R $USER:$USER $REPOS_PATH
chmod -R 755 $REPOS_PATH
```

#### **Memory Issues**
```bash
# Check available memory
free -h

# Check container memory usage
podman stats

# Reduce memory limits if needed
# Edit mvp-compose-optimized.yml:
# mem_limit: 2g (instead of 4g)
```

#### **Network Issues**
```bash
# Reset Podman networking
podman system reset
podman network create codebase-rag-network

# Check port availability
ss -tlnp | grep :8080

# Kill processes using required ports
sudo fuser -k 8080/tcp
```

### **Container Issues**

#### **Podman Socket Issues**
```bash
# Enable Podman socket
systemctl --user enable --now podman.socket

# Check socket status
systemctl --user status podman.socket

# Restart if needed
systemctl --user restart podman.socket
```

#### **Storage Issues**
```bash
# Clean up old containers and images
podman system prune -a

# Check disk usage
podman system df

# Move storage location if needed
podman system migrate --new-runtime /new/storage/path
```

---

## 🔧 **Advanced Configuration**

### **Resource Monitoring**
```bash
# Install monitoring tools
sudo apt install htop iotop nethogs

# Monitor during indexing
htop  # CPU and memory
iotop  # Disk I/O
nethogs  # Network usage
```

### **Log Management**
```bash
# Configure log rotation
sudo tee /etc/logrotate.d/codebase-rag << EOF
/opt/CodebaseRAG/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 codebase-rag codebase-rag
}
EOF
```

### **Backup Configuration**
```bash
# Create backup script
sudo tee /usr/local/bin/backup-codebase-rag.sh << EOF
#!/bin/bash
BACKUP_DIR="/backup/codebase-rag/\$(date +%Y%m%d)"
mkdir -p "\$BACKUP_DIR"

# Backup volumes
podman run --rm -v chromadb_data:/source -v "\$BACKUP_DIR":/backup alpine tar czf /backup/chromadb.tar.gz -C /source .
podman run --rm -v neo4j_data:/source -v "\$BACKUP_DIR":/backup alpine tar czf /backup/neo4j.tar.gz -C /source .

echo "Backup completed: \$BACKUP_DIR"
EOF

chmod +x /usr/local/bin/backup-codebase-rag.sh

# Add to crontab for daily backups
(crontab -l 2>/dev/null; echo "0 2 * * * /usr/local/bin/backup-codebase-rag.sh") | crontab -
```

---

## ✅ **Verification Steps**

### **Installation Verification**
```bash
# Check all services are running
podman ps

# Test API endpoints
curl -s http://localhost:8080/health | jq
curl -s http://localhost:8080/agent/capabilities | jq

# Test indexing with sample data
curl -X POST http://localhost:8080/index \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "/path/to/test/repo", "repo_name": "test"}'
```

### **Performance Verification**
```bash
# Check resource usage
podman stats --no-stream

# Test query performance
time curl -s "http://localhost:8080/search?q=test"

# Monitor during indexing
watch -n 5 'podman stats --no-stream'
```

---

## 📞 **Getting Help**

### **Log Locations**
```bash
# Application logs
tail -f /opt/CodebaseRAG/logs/*.log

# Container logs
podman logs codebase-rag-api
podman logs codebase-rag-neo4j
podman logs codebase-rag-chromadb

# System logs
journalctl -u codebase-rag -f
```

### **Debug Information**
```bash
# Collect debug information
podman info
podman version
free -h
df -h
cat /etc/os-release
```

---

**Your Linux environment is now ready for enterprise-grade codebase analysis!**

➡️ **Next**: [Start analyzing your repositories](../usage/dependency-discovery.md) or [Configure the AI agent](../usage/ai-agent.md)