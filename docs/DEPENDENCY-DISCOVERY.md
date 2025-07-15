# Dependency Discovery Guide

**Find all the repositories your project depends on.** This guide shows you how to systematically discover missing repositories using Maven dependency analysis.

## 🎯 The Problem

You have one repository but it depends on internal libraries from other repositories. You don't know which repositories to clone to have a complete local development environment.

## 🔄 The Solution Workflow

1. **Index your main repository**
2. **Analyze dependencies** to find missing internal artifacts  
3. **Map artifacts to repository names**
4. **Clone missing repositories**
5. **Index new repositories**
6. **Repeat until complete**

## 🚀 How It Works

The MVP:
- Parses all `pom.xml` files in your repositories
- Extracts Maven dependencies (group:artifact:version)
- Identifies which dependencies are internal (your organization's code) vs external (third-party)
- Shows you which internal dependencies have no corresponding local repository
- Helps you map artifact names to actual repository names

## 📋 Step-by-Step Discovery

### Step 1: Index Your Main Repository

```powershell
# Index your primary repository
$repoData = @{
    repo_path = "C:\your\repos\main-application"
    repo_name = "main-application"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8080/index" `
  -Method POST -ContentType "application/json" `
  -Body $repoData
```

### Step 2: Find Missing Dependencies

```powershell
# This shows which internal dependencies are missing repositories
Invoke-RestMethod "http://localhost:8080/maven/conflicts"
```

Example output:
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
    }
  ]
}
```

**Translation:** You need to clone the `user-service` repository!

### Step 3: Map Artifacts to Repository Names

Look at the missing artifacts and determine likely repository names:

| Missing Artifact | Likely Repository Name |
|------------------|----------------------|
| `user-service` | `user-service` |
| `common-utils` | `shared-common-utils` or `common-utilities` |
| `auth-service` | `authentication-service` |

### Step 4: Clone Missing Repositories

```powershell
# Navigate to your repositories directory
cd C:\your\repos

# Clone each missing repository (update URLs for your organization)
git clone https://your-git-server/user-service.git
git clone https://your-git-server/shared-common-utils.git
```

### Step 5: Index New Repositories

```powershell
# Index each new repository
$repos = @("user-service", "shared-common-utils")

foreach ($repo in $repos) {
    $repoData = @{
        repo_path = "C:\your\repos\$repo"
        repo_name = $repo
    } | ConvertTo-Json
    
    Write-Host "Indexing $repo..."
    Invoke-RestMethod -Uri "http://localhost:8080/index" `
      -Method POST -ContentType "application/json" `
      -Body $repoData
}
```

### Step 6: Check for Remaining Dependencies

```powershell
# Check conflicts again - should be fewer now
Invoke-RestMethod "http://localhost:8080/maven/conflicts"
```

**Repeat Steps 3-6** until the conflicts list is empty (or only contains external dependencies).

## 🧭 Visual Analysis with Neo4j

### Access Neo4j Browser
- **URL**: http://localhost:7474
- **Login**: `neo4j` / `codebase-rag-2024`

### Find Missing Dependencies Visually

```cypher
// Find all internal dependencies that don't have corresponding repositories
MATCH (a:MavenArtifact)-[:DEPENDS_ON]->(dep:MavenArtifact)
WHERE dep.group_id CONTAINS 'yourcompany'  // Replace with your organization's group ID
  AND NOT EXISTS {
    MATCH (r:Repository)-[:DEFINES_ARTIFACT]->(dep)
  }
RETURN DISTINCT 
  dep.group_id + ':' + dep.artifact_id as missing_dependency,
  dep.version,
  dep.artifact_id as likely_repo_name
ORDER BY missing_dependency
```

### Find High-Priority Dependencies

```cypher
// Find compile-scope dependencies (most critical to clone first)
MATCH (a:MavenArtifact)-[d:DEPENDS_ON]->(dep:MavenArtifact)
WHERE dep.group_id CONTAINS 'yourcompany'
  AND d.scope = 'compile'
  AND NOT EXISTS {
    MATCH (r:Repository)-[:DEFINES_ARTIFACT]->(dep)
  }
RETURN 
  dep.artifact_id as missing_repo,
  dep.version,
  count(*) as used_by_count
ORDER BY used_by_count DESC
```

## 🎯 Success Criteria

You'll know you're done when:
- ✅ **No internal dependencies** show up in conflict analysis
- ✅ **All compile-scope dependencies** are resolved  
- ✅ **You can build your main project** locally with all dependencies available
- ✅ **Conflict analysis returns empty** (or only external dependencies)

## 📋 Common Repository Naming Patterns

| Artifact Pattern | Likely Repository Name |
|------------------|----------------------|
| `user-service` | `user-service` |
| `common-utils` | `shared-common-utils` or `common-utilities` |
| `auth-*` | `authentication-service` or `auth-service` |
| `data-*` | `data-access-layer` or `data-services` |
| `ui-*` | `user-interface` or `frontend-components` |

## 🔄 Keeping Up-to-Date

### Re-analyze After Changes

```powershell
# After pulling changes or adding new repositories
Invoke-RestMethod "http://localhost:8080/maven/conflicts"

# Re-index if dependencies change
$repoData = @{
    repo_path = "C:\your\repos\updated-repo"
    repo_name = "updated-repo"
} | ConvertTo-Json

# Delete old index first
Invoke-RestMethod -Uri "http://localhost:8080/repositories/updated-repo" -Method DELETE

# Re-index with latest changes
Invoke-RestMethod -Uri "http://localhost:8080/index" `
  -Method POST -ContentType "application/json" `
  -Body $repoData
```

---

**🎯 This systematic approach ensures you discover ALL missing repositories and understand the complete dependency landscape of your codebase.**