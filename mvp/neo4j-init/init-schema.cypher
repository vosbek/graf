// Neo4j Schema Initialization for Codebase RAG MVP
// This script sets up the basic schema for repositories, files, Maven artifacts, and dependencies

// ============================================================================
// NODE CONSTRAINTS
// ============================================================================

// Repository constraints
CREATE CONSTRAINT repo_name_unique IF NOT EXISTS 
FOR (r:Repository) REQUIRE r.name IS UNIQUE;

// File constraints  
CREATE CONSTRAINT file_path_unique IF NOT EXISTS 
FOR (f:File) REQUIRE (f.path) IS UNIQUE;

// Maven artifact constraints
CREATE CONSTRAINT artifact_id_unique IF NOT EXISTS 
FOR (a:MavenArtifact) REQUIRE a.id IS UNIQUE;

// ============================================================================
// INDEXES FOR PERFORMANCE
// ============================================================================

// Repository indexes
CREATE INDEX repo_name_idx IF NOT EXISTS 
FOR (r:Repository) ON (r.name);

CREATE INDEX repo_path_idx IF NOT EXISTS 
FOR (r:Repository) ON (r.path);

// File indexes
CREATE INDEX file_language_idx IF NOT EXISTS 
FOR (f:File) ON (f.language);

CREATE INDEX file_extension_idx IF NOT EXISTS 
FOR (f:File) ON (f.extension);

// Maven artifact indexes
CREATE INDEX artifact_group_idx IF NOT EXISTS 
FOR (a:MavenArtifact) ON (a.group_id);

CREATE INDEX artifact_name_idx IF NOT EXISTS 
FOR (a:MavenArtifact) ON (a.artifact_id);

CREATE INDEX artifact_version_idx IF NOT EXISTS 
FOR (a:MavenArtifact) ON (a.version);

// ============================================================================
// RELATIONSHIP INDEXES
// ============================================================================

// Dependency relationship indexes
CREATE INDEX dependency_scope_idx IF NOT EXISTS 
FOR ()-[d:DEPENDS_ON]-() ON (d.scope);

CREATE INDEX dependency_optional_idx IF NOT EXISTS 
FOR ()-[d:DEPENDS_ON]-() ON (d.optional);

// ============================================================================
// SAMPLE QUERIES FOR VERIFICATION
// ============================================================================

// Count nodes by type
// MATCH (n) RETURN labels(n)[0] as node_type, count(n) as count ORDER BY count DESC;

// Show schema
// CALL db.schema.visualization();

// List all constraints
// CALL db.constraints();

// List all indexes  
// CALL db.indexes();

RETURN "Schema initialization completed" as status;