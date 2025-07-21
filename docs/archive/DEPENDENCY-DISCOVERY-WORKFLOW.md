# 🔍 Complete Dependency Discovery Workflow

**The systematic process to find ALL repositories your project depends on.**

## 🎯 Overview

This workflow helps you discover every internal repository dependency by:
1. **Indexing** existing repositories
2. **Analyzing** Maven dependencies 
3. **Identifying** missing repositories
4. **Mapping** artifacts to repo names
5. **Iterating** until complete

## 📋 Step-by-Step Process

### Phase 1: Initial Setup

**1. Start the MVP System**
```bash
export REPOS_PATH="/path/to/your/repos"
./start-mvp-simple.sh
```

**2. Verify System Health**
```bash
curl http://localhost:8080/health
# Should return: {"status": "healthy", ...}
```

### Phase 2: Index Your Starting Repository

**3. Index Your Main Project**
```bash
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

### Phase 3: Discover Missing Dependencies

**4. Analyze Dependencies**
```bash
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

**5. Interpret Results**

For each conflict:
- `group_artifact`: The missing dependency
- `conflicting_versions`: Required version(s)
- `dependencies`: Where it's referenced from

### Phase 4: Map Artifacts to Repositories

**6. Common Artifact → Repository Mappings**

| Artifact ID | Likely Repository Name |
|-------------|----------------------|
| `user-service` | `user-service` or `users` |
| `payment-api` | `payment-service` or `payments` |
| `auth-core` | `authentication` or `auth` |
| `data-models` | `shared-models` or `commons` |

**7. Search for Repository Names**
```bash
# In your Git server/GitHub/etc., search for:
# - Exact artifact name: "user-service"
# - Shortened name: "users" 
# - Related terms: "user management"
```

### Phase 5: Clone and Index Missing Repositories

**8. Clone Missing Repositories**
```bash
# For each missing dependency
cd /path/to/your/repos
git clone https://your-git-server/user-service.git
git clone https://your-git-server/payment-service.git
```

**9. Index New Repositories**
```bash
# Index user-service
curl -X POST "http://localhost:8080/index" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_path": "/path/to/your/repos/user-service",
    "repo_name": "user-service"
  }'

# Index payment-service  
curl -X POST "http://localhost:8080/index" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_path": "/path/to/your/repos/payment-service", 
    "repo_name": "payment-service"
  }'
```

### Phase 6: Iterate Until Complete

**10. Re-analyze Dependencies**
```bash
curl "http://localhost:8080/maven/conflicts"
```

**Expected Result After Iteration:**
```json
{
  "conflicts": [
    {
      "group_artifact": "com.yourcompany:email-service",
      "conflicting_versions": ["1.2.0"]
    }
  ],
  "total_conflicts": 1
}
```

**11. Repeat Until Empty**
Keep cloning and indexing until:
```json
{
  "conflicts": [],
  "total_conflicts": 0
}
```

## 🎉 Completion Verification

**12. Verify Complete Dependency Graph**
```bash
# Check all repositories are indexed
curl "http://localhost:8080/repositories"

# Get overall statistics
curl "http://localhost:8080/status"
```

**Expected Final State:**
```json
{
  "status": "running",
  "chromadb": {
    "total_chunks": 15847
  },
  "neo4j": {
    "total_repositories": 8,
    "total_artifacts": 12,
    "total_dependencies": 45
  },
  "repositories": [
    "main-application",
    "user-service", 
    "payment-service",
    "email-service",
    ...
  ]
}
```

## 🔍 Advanced Analysis

**View Dependencies in Neo4j Browser**
1. Open: http://localhost:7474
2. Login: neo4j / codebase-rag-2024
3. Run queries:

```cypher
// Show all repositories and their dependencies
MATCH (r:Repository)-[:DEFINES_ARTIFACT]->(a:MavenArtifact)-[:DEPENDS_ON]->(dep:MavenArtifact)
RETURN r.name, a.artifact_id, dep.artifact_id

// Find repositories with the most dependencies
MATCH (r:Repository)-[:DEFINES_ARTIFACT]->(a:MavenArtifact)-[:DEPENDS_ON]->(dep)
RETURN r.name, count(dep) as dependency_count
ORDER BY dependency_count DESC

// Find missing external dependencies (third-party libraries)
MATCH (a:MavenArtifact)-[:DEPENDS_ON]->(dep:MavenArtifact)
WHERE NOT dep.group_id CONTAINS 'yourcompany'
  AND NOT EXISTS {
    MATCH (r:Repository)-[:DEFINES_ARTIFACT]->(dep)
  }
RETURN dep.group_id, dep.artifact_id, count(*) as usage_count
ORDER BY usage_count DESC
```

## 🚨 Troubleshooting

**Problem: No dependencies found**
- Verify your repositories contain `pom.xml` files
- Check Maven projects are properly structured
- Ensure indexing completed successfully

**Problem: Can't find repository for artifact**
- Check if artifact uses different naming convention
- Look for repositories with similar names
- Ask your team about artifact → repository mappings
- Check if it's an internal library in a different org namespace

**Problem: Dependencies keep appearing**
- Some artifacts might be in monorepos (multiple artifacts per repository)
- Check if you need to clone additional branches
- Verify you have access to all required repositories

**Problem: System running slow**
- Large repositories take time to index
- Consider excluding test directories and build artifacts
- Monitor resource usage with `curl http://localhost:8080/status`

## 📊 Success Metrics

You'll know you're done when:
- ✅ `maven/conflicts` returns empty array
- ✅ All team members can build projects locally
- ✅ Dependency graph shows complete relationships
- ✅ Semantic search finds code across all repositories

This workflow typically takes 1-3 hours for medium-sized enterprises (10-50 repositories).