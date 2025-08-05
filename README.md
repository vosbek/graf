# 🎯 GraphRAG - Clean & Organized

**AI-Powered Codebase Analysis Platform - Simplified for Production Use**

---
## 📚 Documentation Index

- Start here: [docs/index.md](docs/index.md)
- Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Usage guides: [docs/usage/index.md](docs/usage/index.md)
- Installation: [docs/installation/index.md](docs/installation/index.md)
- Troubleshooting: [docs/troubleshooting-playbook.md](docs/troubleshooting-playbook.md)

## 👤 Choose Your Path

- Developers: Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), then [docs/installation/index.md](docs/installation/index.md), then [docs/usage/index.md](docs/usage/index.md)
- Operators: Use [CONFIGURATION-GUIDE.md](CONFIGURATION-GUIDE.md), [docker-compose.yml](docker-compose.yml), and [docs/troubleshooting-playbook.md](docs/troubleshooting-playbook.md)
- Users: Try the UI via [QUICK-START.md](QUICK-START.md) and follow [docs/usage/index.md](docs/usage/index.md)


## 🚀 Quick Start (One Command)

```powershell
# First-time setup: Check if your Windows machine is ready
.\check-windows-setup.ps1

# Start everything
.\START.ps1

# That's it! 🎉
```

**Access your GraphRAG system at:** http://localhost:3000

> **🖥️ Fresh Windows Machine?** See [WINDOWS-FRESH-INSTALL.md](WINDOWS-FRESH-INSTALL.md) for complete setup guide.
> 
> **🤖 Want AI Chat?** See [AI-CHAT-SETUP.md](AI-CHAT-SETUP.md) to configure AWS Bedrock credentials.

---

## 📁 Clean File Organization

### **🎯 Essential Files (Root Directory)**
```
C:\devl\workspaces\graf\
├── START.ps1                    # 🚀 Universal startup script
├── check-status.ps1             # 📊 System health checker
├── README.md                    # 📋 Main documentation
├── QUICK-START.md              # ⚡ 5-minute setup guide
├── TROUBLESHOOTING.md          # 🔧 Problem solving guide
├── CONFIGURATION-GUIDE.md      # ⚙️ Config management
├── PRD.md                      # 📄 Product requirements
├── CLAUDE.md                   # 🤖 AI assistant instructions
├── requirements.txt            # 📦 Python dependencies
└── .env                        # ⚙️ Environment configuration
```

### **🔧 Core Application**
```
├── src/                        # 🏗️ Main Python backend
├── frontend/                   # 💻 React web interface  
├── mvp/                        # 🧪 Minimal viable product
├── config/                     # ⚙️ Service configurations
├── docker/                     # 🐳 Container definitions
├── data/                       # 💾 Application data
└── logs/                       # 📝 System logs
```

### **📄 Active Configuration Files**
```
├── docker-compose.yml          # 🏢 Full enterprise stack
├── podman-compose-services-only.yml  # 🔧 Backend services only
└── mvp-compose.yml             # 🧪 Minimal testing version
```

### **🗄️ Organized Archives**
```
├── archive/
│   ├── scripts/               # 📜 Old startup scripts
│   ├── compose-configs/       # 🐳 Experimental YAML files
│   ├── documentation/         # 📚 Superseded documentation
│   ├── docker-configs/        # 🐳 Old Dockerfiles
│   ├── test-files/           # 🧪 Development test files
│   └── experimental/         # 🔬 Research and experiments
```

---

## 🎮 Usage Examples

### **Standard Operations**
```powershell
# Full system startup
.\START.ps1

# Backend services only
.\START.ps1 -Mode backend

# Check what's running
.\START.ps1 -Status

# Clean restart
.\START.ps1 -Clean
```

### **Health Monitoring**
```powershell
# Quick status check
.\check-status.ps1

# View system logs
Get-Content logs\*.log -Tail 20
```

---

## 🌐 Service Access

| Service | URL | Credentials |
|---------|-----|-------------|
| **Main App** | http://localhost:3000 | None |
| **API** | http://localhost:8080 | None |
| **MinIO Console** | http://localhost:9001 | `codebase-rag` / `codebase-rag-2024` |
| **Neo4j Browser** | http://localhost:7474 | `neo4j` / `codebase-rag-2024` |

---

## 📋 What Was Cleaned Up

### **✅ Files Moved to Archive (30+ files organized)**

**Scripts Archived:**
- ~~`universal-startup.ps1`~~ → `archive/scripts/`
- ~~`start-full-system.ps1`~~ → `archive/scripts/`  
- ~~`start-frontend.ps1`~~ → `archive/scripts/`
- ~~`quick-start-frontend.ps1`~~ → `archive/scripts/`
- ~~All shell scripts (.sh)`~~ → `archive/scripts/`

**Documentation Archived:**
- ~~`HOW-TO-RUN.md`~~ → `archive/documentation/` 
- ~~`UNIVERSAL-STARTUP-GUIDE.md`~~ → `archive/documentation/`
- ~~`WINDOWS-SETUP-GUIDE.md`~~ → `archive/documentation/`
- ~~`SETUP-GUIDE.md`~~ → `archive/documentation/`
- ~~`INTERACTIVE-GRAPH-GUIDE.md`~~ → `archive/documentation/`

**YAML Configs Archived:**
- ~~`mvp-compose-optimized.yml`~~ → `archive/compose-configs/`
- ~~`single-container-compose.yml`~~ → `archive/compose-configs/`
- ~~`docker-compose-mvp-ui.yml`~~ → `archive/compose-configs/`
- ~~`podman-compose.yml`~~ → `archive/compose-configs/`

**Test/Experimental Files Archived:**
- ~~`test_api.py`~~ → `archive/test-files/`
- ~~`verify-mvp.py`~~ → `archive/test-files/`
- ~~`hybrid_api.py`~~ → `archive/experimental/`
- ~~`real_dependency_analyzer.py`~~ → `archive/experimental/`

**Logs Organized:**
- ~~25+ scattered log files~~ → `logs/` directory

### **✅ Results**
- **Root directory:** Reduced from 50+ files to 10 essential files
- **Clear organization:** Everything has a logical place
- **Single startup method:** One `START.ps1` replaces 8+ scripts
- **Professional structure:** Ready for enterprise deployment

---

## 🏆 Benefits

### **Developer Experience**
- **⚡ Faster onboarding** - New developers know exactly what to run
- **🔧 Easier maintenance** - Clear separation of concerns
- **📊 Better troubleshooting** - Organized logs and diagnostics
- **🚀 Simplified deployment** - One command for any environment

### **Business Value**
- **📋 Professional appearance** - Clean, organized codebase
- **🔒 Reduced risk** - Less chance of running wrong scripts
- **📈 Faster development** - No time wasted finding the right files
- **🎯 Clear documentation** - Stakeholders understand the system

---

## 📞 Support

- **📋 Quick Issues:** Run `.\START.ps1 -Status` 
- **🔧 Troubleshooting:** See `TROUBLESHOOTING.md`
- **⚡ Getting Started:** See `QUICK-START.md`
- **⚙️ Configuration:** See `CONFIGURATION-GUIDE.md`

---

**🎉 Your GraphRAG system is now clean, organized, and enterprise-ready!**

**Next step:** Run `.\START.ps1` and access http://localhost:3000