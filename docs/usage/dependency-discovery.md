# 🔍 Complete Dependency Discovery Guide

## 🎯 **Find All Missing Repositories for Your Struts Application**

This comprehensive guide shows you how to systematically discover every repository your project depends on, from business-friendly workflows to technical deep-dives.

---

## 💼 **For Business Users - Natural Language Approach**

### **Ask the AI Agent Instead of Technical Commands**

**Instead of complex technical processes, simply ask:**

```python
# Using the AI agent
agent.ask("What repositories am I missing for this application?")
agent.ask("Show me all the internal dependencies that don't have local repositories")
agent.ask("What do I need to clone to have a complete development environment?")
```

### **Business-Friendly Discovery Workflow**

#### **Step 1: Understand Your Application**
```python
agent.ask("What are the main features of this application?")
agent.ask("How many different components does this system have?")
```

#### **Step 2: Identify Missing Pieces**  
```python
agent.ask("What internal libraries does this application depend on?")
agent.ask("Are there any missing repositories I need to clone?")
```

#### **Step 3: Get Specific Recommendations**
```python
agent.ask("Give me a list of repository names I need to clone")
agent.ask("What's the priority order for cloning missing repositories?")
```

---

## 🔧 **For Developers - Technical Workflow**

### **Systematic Discovery Process**

#### **Phase 1: Initial Setup**
```bash
# 1. Start the MVP system
export REPOS_PATH="/path/to/your/repos"
./start-mvp-simple.sh

# 2. Verify system health
curl http://localhost:8080/health
curl http://localhost:8080/agent/health
```

#### **Phase 2: Index Your Main Repository**
```bash
# Index your primary Struts application
curl -X POST "http://localhost:8080/index" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_path": "/path/to/your/repos/main-application",
    "repo_name": "main-application"
  }'
```

**Expected Response:**
```json
{
  "status": "success",
  "repository": "main-application",
  "files_indexed": 1247,
  "chunks_created": 3891,
  "processing_time": 45.2
}
```

#### **Phase 3: Analyze Dependencies**
```bash
# Find missing Maven dependencies
curl "http://localhost:8080/maven/conflicts" | jq '.'
```

**Example Output:**
```json
{
  "conflicts": [
    {
      "group_artifact": "com.yourcompany:user-service",
      "conflicting_versions": ["2.1.0"],
      "dependencies": [
        {
          "from_artifact": "com.yourcompany:main-application:1.0.0",
          "to_artifact_id": "user-service",
          "scope": "compile"
        }
      ]
    },
    {
      "group_artifact": "com.yourcompany:payment-api",
      "conflicting_versions": ["1.5.2"],
      "dependencies": [...]
    }
  ],
  "total_conflicts": 2
}
```

#### **Phase 4: Map Artifacts to Repositories**

**Common Artifact → Repository Mappings:**
| Artifact ID | Likely Repository Name |
|-------------|----------------------|
| `user-service` | `user-service` or `users` |
| `payment-api` | `payment-service` or `payments` |
| `auth-core` | `authentication` or `auth` |
| `data-models` | `shared-models` or `commons` |

#### **Phase 5: Clone Missing Repositories**
```bash
# For each missing dependency
cd $REPOS_PATH
git clone https://your-git-server/user-service.git
git clone https://your-git-server/payment-service.git

# Index new repositories
curl -X POST "http://localhost:8080/index" \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "'$REPOS_PATH'/user-service", "repo_name": "user-service"}'
```

#### **Phase 6: Iterate Until Complete**
```bash
# Re-analyze dependencies
curl "http://localhost:8080/maven/conflicts"

# Repeat until you get:
# {"conflicts": [], "total_conflicts": 0}
```

---

## 🎯 **Common Scenarios & Examples**

### **Scenario 1: E-commerce Application**

**Typical Dependencies Found:**
```json
{
  "missing_repositories": [
    "user-management-service",
    "product-catalog-api", 
    "payment-processing-service",
    "order-management-system",
    "inventory-service",
    "notification-service"
  ]
}
```

**AI Agent Guidance:**
```python
agent.ask("I'm working on an e-commerce application. What repositories am I likely missing?")
# Response: "Based on e-commerce patterns, you'll typically need user management, 
#           product catalog, payment processing, order management, and inventory services..."
```

### **Scenario 2: Financial Services Application**

**Security and Compliance Dependencies:**
```python
agent.ask("What security-related repositories does this financial application depend on?")
# Response: "I found dependencies on authentication-service, audit-logging, 
#           compliance-reporting, and fraud-detection modules..."
```

### **Scenario 3: Microservices Migration**

**Service Boundary Discovery:**
```python
agent.ask("If I want to break this monolith into microservices, what are the natural service boundaries?")
# Response: "Based on the dependency analysis, I can see clear boundaries around 
#           user management, order processing, and payment handling..."
```

---

## 🚨 **Troubleshooting Common Issues**

### **Issue 1: No Dependencies Found**
**Symptoms:**
```json
{"conflicts": [], "total_conflicts": 0}
```
**But you know there should be internal dependencies.**

**Solutions:**
```python
# Check if Maven files were properly indexed
agent.ask("How many Maven POM files did you find in this repository?")

# Verify repository structure
agent.ask("What build system does this application use?")

# Manual verification
curl "http://localhost:8080/search?q=pom.xml dependencies"
```

### **Issue 2: Can't Find Repository for Artifact**
**Problem:** You know `com.company:user-service` is missing but can't find the repository.

**AI Agent Solution:**
```python
agent.ask("I need to find the repository for 'user-service' artifact. What should I look for?")
# Response: "Look for repositories named 'user-service', 'users', 'user-management', 
#           or 'identity-service'. Check if it might be part of a larger monorepo..."
```

**Manual Investigation:**
```bash
# Search your Git server for related names
# Check team documentation
# Ask team members about naming conventions
```

### **Issue 3: Circular Dependencies**
**Problem:** Repository A depends on B, which depends on A.

**Analysis:**
```python
agent.ask("Are there any circular dependencies in this application?")
agent.ask("What's the dependency relationship between user-service and auth-service?")
```

**Resolution:**
```bash
# Clone both repositories
# Index both simultaneously
# Analyze the circular dependency pattern
```

### **Issue 4: Large Number of Missing Dependencies**
**Problem:** System reports 50+ missing repositories.

**Prioritization:**
```python
agent.ask("Which missing repositories are most critical for this application to function?")
agent.ask("What's the order I should clone repositories in for fastest development setup?")
```

### **Issue 5: Private/Internal Repository Access**
**Problem:** Can't access company-internal repositories.

**Solutions:**
```bash
# Configure Git credentials
git config --global credential.helper store

# Set up SSH keys for Git server access
ssh-keygen -t rsa -b 4096 -C "your.email@company.com"

# Configure VPN/network access for internal Git servers
```

---

## 🤖 **AI Agent Integration for Efficient Discovery**

### **Smart Discovery with Natural Language**

#### **Instead of Complex Analysis:**
```bash
# Old way: Multiple technical commands
curl "http://localhost:8080/maven/conflicts"
curl "http://localhost:8080/search?q=internal dependencies"
curl "http://localhost:8080/struts/actions"
# Then manually interpret JSON responses...
```

#### **Use AI Agent:**
```python
# New way: Simple questions
agent.ask("What repositories am I missing and why?")
agent.ask("Show me the complete list of repositories I need to clone")
agent.ask("What's my development environment setup checklist?")
```

### **Advanced AI-Powered Analysis**

#### **Business Impact Assessment:**
```python
agent.ask("Which missing repositories affect core business functionality?")
agent.ask("What happens if I don't clone the payment-service repository?")
agent.ask("Which repositories are needed for a minimal working system?")
```

#### **Migration Planning:**
```python
agent.ask("How do these missing dependencies affect my GraphQL migration plan?")
agent.ask("Which repositories should I migrate first for the new architecture?")
agent.ask("What's the dependency order for migrating to microservices?")
```

#### **Team Coordination:**
```python
agent.ask("Which team owns each of these missing repositories?")
agent.ask("What's the development workflow if I need changes to multiple repositories?")
agent.ask("How do these repositories typically interact with each other?")
```

---

## 📊 **Verification & Validation**

### **Completion Verification**
```python
# Verify you have everything
agent.ask("Do I now have all the repositories needed for complete development?")
agent.ask("Are there any remaining missing dependencies?")

# Technical verification
curl "http://localhost:8080/maven/conflicts"
# Should return: {"conflicts": [], "total_conflicts": 0}
```

### **Build Environment Validation**
```python
agent.ask("Can I now build the complete application locally?")
agent.ask("What's the build order for all these repositories?")
agent.ask("Are there any runtime dependencies I still need to set up?")
```

### **Development Environment Check**
```bash
# Verify all repositories indexed
curl "http://localhost:8080/repositories"

# Check system statistics
curl "http://localhost:8080/status"
```

**Expected Complete State:**
```json
{
  "status": "running",
  "repositories": [
    "main-application",
    "user-service", 
    "payment-service",
    "order-service",
    ...
  ],
  "neo4j": {
    "total_repositories": 8,
    "total_dependencies": 45
  }
}
```

---

## 🎯 **Success Criteria**

### **You're Done When:**
- ✅ **No Maven conflicts** - `/maven/conflicts` returns empty array
- ✅ **All builds work** - Local compilation succeeds for all projects
- ✅ **Complete dependency graph** - Neo4j shows all relationships
- ✅ **Team can develop** - New developers can clone and build everything

### **Expected Timeline:**
- **Small projects (5-10 repos)**: 2-4 hours
- **Medium projects (20-50 repos)**: 1-2 days  
- **Large enterprises (100+ repos)**: 3-5 days

---

## 💡 **Pro Tips**

### **Efficiency Tips**
```python
# Use batch questions for faster discovery
agent.ask("Give me the complete repository setup checklist for this application")

# Get prioritized recommendations
agent.ask("What's the minimum set of repositories I need to start development?")

# Understand team context
agent.ask("How are these repositories typically organized in development teams?")
```

### **Automation Opportunities**
```bash
# Script repository cloning once you have the list
for repo in user-service payment-service order-service; do
  git clone https://git.company.com/$repo.git
  curl -X POST "http://localhost:8080/index" \
    -d "{\"repo_path\": \"$(pwd)/$repo\", \"repo_name\": \"$repo\"}"
done
```

---

**With this systematic approach, you'll transform repository discovery from a frustrating guessing game into a confident, data-driven process that ensures complete development environment setup.**

➡️ **Next**: [Learn about the AI Agent](ai-agent.md) or [Explore all MVP features](../features.md)