# Database Cleanup Guide
## Clear Neo4j & ChromaDB for Enhanced Ingestion Testing

---

## **🎯 Quick Start**

You now have **3 ways** to clear your databases for clean re-indexing:

### **Option 1: Web UI (Easiest)**
1. Go to **System Status** page in your web app
2. Scroll to **Database Management** section
3. Click **"Reset Databases"** button
4. Choose your options:
   - ✅ Reset Neo4j (business relationships, graph data)
   - ✅ Reset ChromaDB (code embeddings, semantic search)
   - ⚪ Create backup before reset (optional)
   - ⚠️ **Check confirmation box** (required)
5. Click **"Reset Databases"** to proceed

### **Option 2: Command Line Script (Most Control)**
```bash
# From project root directory
python scripts/cleanup-databases.py

# With options
python scripts/cleanup-databases.py --backup          # Create backup first
python scripts/cleanup-databases.py --neo4j-only     # Clear only Neo4j
python scripts/cleanup-databases.py --chroma-only    # Clear only ChromaDB
python scripts/cleanup-databases.py --dry-run        # Preview what would be deleted
python scripts/cleanup-databases.py --confirm        # Skip confirmation prompt
```

### **Option 3: API Endpoint (For Automation)**
```bash
curl -X POST "http://localhost:8080/api/v1/admin/database/reset" \
  -H "Content-Type: application/json" \
  -d '{
    "reset_neo4j": true,
    "reset_chromadb": true,
    "create_backup": false,
    "confirm": true
  }'
```

---

## **⚡ Quick Test Workflow**

### **Step 1: Clear Databases**
Use any of the methods above to clear your databases.

### **Step 2: Restart Containers (if needed)**
```bash
# If you updated embedding model or schema
docker-compose down
docker-compose up -d

# Wait for all services to be ready
docker-compose logs -f api
```

### **Step 3: Verify Clean State**
- **Web UI:** Check System Status shows 0 nodes/chunks
- **API:** `GET /api/v1/health/database-status` should show empty databases

### **Step 4: Test Enhanced Ingestion**
1. **Create Test Repository** with sample files:
   ```
   test-repo/
   ├── src/
   │   ├── CustomerAction.java          # Struts Action
   │   ├── customer.jsp                 # JSP with scriptlets
   │   └── CustomerService.idl          # CORBA interface
   ├── WEB-INF/
   │   └── struts-config.xml           # Struts configuration
   └── pom.xml                         # Maven dependencies
   ```

2. **Index Repository:**
   - **Web UI:** Go to "Index Repositories" → Add test repository
   - **API:** `POST /api/v1/repositories` with repository details

3. **Verify Enhanced Results:**
   - **Dependency Graph:** Should show business components (not just files)
   - **Neo4j Browser:** Query `MATCH (n) RETURN labels(n), count(n)` should show:
     - `StrutsAction` nodes
     - `JSPComponent` nodes  
     - `BusinessRule` nodes
     - `CORBAInterface` nodes (if .idl files present)

---

## **🔍 What Gets Cleared**

### **Neo4j Database:**
- **Nodes:** Repository, File, MavenArtifact, BusinessRule, StrutsAction, CORBAInterface, JSPComponent
- **Relationships:** CONTAINS, DEPENDS_ON, IMPLEMENTS_BUSINESS_RULE, CALLS_SERVICE, etc.
- **Indexes & Constraints:** Recreated automatically

### **ChromaDB Vector Store:**
- **Collections:** All collections deleted and main collection recreated
- **Embeddings:** All code chunk embeddings cleared
- **Metadata:** All enhanced business metadata cleared

---

## **🛡️ Safety Features**

### **Confirmation Required**
- Web UI requires checking confirmation box
- Script prompts for "yes" confirmation (unless `--confirm` flag)
- API requires `"confirm": true` in request body

### **Backup Options**
- **Web UI:** Checkbox to create backup before reset
- **Script:** `--backup` flag creates full backup
- **API:** `"create_backup": true` in request

### **Dry Run Mode**
- **Script:** `--dry-run` shows what would be deleted without deleting
- Shows exact counts of nodes, relationships, collections, chunks

### **Selective Reset**
- Choose Neo4j only: `--neo4j-only` or `"reset_neo4j": true, "reset_chromadb": false`
- Choose ChromaDB only: `--chroma-only` or `"reset_neo4j": false, "reset_chromadb": true`

---

## **🚨 Troubleshooting**

### **Script Issues:**
```bash
# Import errors
pip install -r requirements.txt

# Permission errors  
chmod +x scripts/cleanup-databases.py

# Connection errors
docker-compose ps  # Check services are running
```

### **Web UI Issues:**
- **Button doesn't appear:** Check System Status page loaded completely
- **Reset fails:** Check browser developer console for errors
- **Confirmation not working:** Make sure to check the confirmation checkbox

### **API Issues:**
```bash
# Test API health first
curl http://localhost:8080/api/v1/health/ready

# Check API documentation
curl http://localhost:8080/docs

# View detailed error response
curl -v -X POST "http://localhost:8080/api/v1/admin/database/reset" \
  -H "Content-Type: application/json" \
  -d '{"confirm": true}'
```

### **After Reset Issues:**
- **Schema not recreated:** Restart the application
- **Graph shows no data:** Verify databases were actually cleared
- **Re-indexing fails:** Check logs for embedding model or parsing errors

---

## **📊 Verification Commands**

### **Check Database State:**
```bash
# Neo4j node count
echo "MATCH (n) RETURN count(n) as total_nodes" | cypher-shell -u neo4j -p codebase-rag-2024

# ChromaDB collection count
curl http://localhost:8000/api/v1/collections
```

### **Monitor Reset Progress:**
```bash
# Watch API logs during reset
docker-compose logs -f api

# Check system health after reset
curl http://localhost:8080/api/v1/health/detailed
```

---

## **🎯 Expected Results After Reset**

✅ **Neo4j:** 0 nodes, 0 relationships, schema constraints recreated  
✅ **ChromaDB:** 1 empty collection (`codebase_chunks`)  
✅ **System Status:** All services healthy, ready for indexing  
✅ **Dependency Graph:** Empty graph, ready for new business relationships  

Your databases are now clean and ready for testing the enhanced business relationship extraction with Struts/CORBA/JSP repositories!