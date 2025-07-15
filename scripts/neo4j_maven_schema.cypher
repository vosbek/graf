// Enhanced Neo4j Schema with Maven Dependencies and POM Parsing Support
// Comprehensive Maven ecosystem modeling for multi-repository analysis

// =============================================================================
// MAVEN-SPECIFIC CONSTRAINTS AND INDEXES
// =============================================================================

// Maven artifact constraints
CREATE CONSTRAINT maven_artifact_unique IF NOT EXISTS FOR (ma:MavenArtifact) REQUIRE (ma.group_id, ma.artifact_id, ma.version) IS UNIQUE;
CREATE CONSTRAINT maven_coord_unique IF NOT EXISTS FOR (ma:MavenArtifact) REQUIRE ma.coordinates IS UNIQUE;

// Maven repository constraints
CREATE CONSTRAINT maven_repo_unique IF NOT EXISTS FOR (mr:MavenRepository) REQUIRE mr.url IS UNIQUE;

// Build file constraints
CREATE CONSTRAINT pom_file_unique IF NOT EXISTS FOR (p:PomFile) REQUIRE p.file_path IS UNIQUE;
CREATE CONSTRAINT build_file_unique IF NOT EXISTS FOR (bf:BuildFile) REQUIRE bf.file_path IS UNIQUE;

// Version constraints
CREATE CONSTRAINT version_unique IF NOT EXISTS FOR (v:Version) REQUIRE (v.artifact_coordinates, v.number) IS UNIQUE;

// License constraints
CREATE CONSTRAINT license_unique IF NOT EXISTS FOR (l:License) REQUIRE l.name IS UNIQUE;

// Maven-specific indexes
CREATE INDEX maven_group_idx IF NOT EXISTS FOR (ma:MavenArtifact) ON (ma.group_id);
CREATE INDEX maven_artifact_idx IF NOT EXISTS FOR (ma:MavenArtifact) ON (ma.artifact_id);
CREATE INDEX maven_version_idx IF NOT EXISTS FOR (ma:MavenArtifact) ON (ma.version);
CREATE INDEX maven_scope_idx IF NOT EXISTS FOR (md:MavenDependency) ON (md.scope);
CREATE INDEX maven_type_idx IF NOT EXISTS FOR (ma:MavenArtifact) ON (ma.type);
CREATE INDEX build_tool_idx IF NOT EXISTS FOR (bf:BuildFile) ON (bf.build_tool);
CREATE INDEX version_number_idx IF NOT EXISTS FOR (v:Version) ON (v.number);
CREATE INDEX vulnerability_idx IF NOT EXISTS FOR (vuln:Vulnerability) ON (vuln.cve_id);

// Performance indexes for dependency resolution
CREATE INDEX dep_resolution_idx IF NOT EXISTS FOR (md:MavenDependency) ON (md.group_id, md.artifact_id);
CREATE INDEX parent_pom_idx IF NOT EXISTS FOR (p:PomFile) ON (p.parent_group_id, p.parent_artifact_id, p.parent_version);

// Full-text search for Maven artifacts
CREATE FULLTEXT INDEX maven_search_idx IF NOT EXISTS FOR (ma:MavenArtifact) ON EACH [ma.group_id, ma.artifact_id, ma.description, ma.name];

// =============================================================================
// MAVEN-SPECIFIC NODE LABELS AND PROPERTIES
// =============================================================================

// Maven Artifacts
// :MavenArtifact
// Properties: group_id, artifact_id, version, coordinates, name, description, 
//            type, packaging, classifier, file_size, checksum_md5, checksum_sha1,
//            created_date, last_modified, download_count, is_snapshot, is_release,
//            source_url, javadoc_url, pom_url, jar_url, parent_coordinates

// Maven Dependencies (relationship properties)
// :MavenDependency
// Properties: group_id, artifact_id, version, version_range, scope, type, 
//            classifier, is_optional, exclusions, system_path, is_inherited,
//            effective_version, resolved_version, dependency_path, depth_level

// Maven Repositories
// :MavenRepository
// Properties: id, name, url, type, layout, is_snapshots_enabled, is_releases_enabled,
//            update_policy, checksum_policy, authentication_required, priority,
//            is_active, mirror_of, blocked_repositories

// POM Files
// :PomFile
// Properties: file_path, group_id, artifact_id, version, packaging, name, 
//            description, url, organization, license_names, developer_names,
//            scm_url, issue_tracker_url, distribution_management, properties,
//            parent_group_id, parent_artifact_id, parent_version, parent_relative_path,
//            modules, profiles, build_plugins, dependencies_count, plugins_count,
//            effective_properties, inheritance_chain, last_parsed, checksum

// Build Files (for multi-tool support)
// :BuildFile
// Properties: file_path, build_tool, version, dependencies_count, plugins_count,
//            properties, tasks, configurations, language, framework, last_parsed

// Version Management
// :Version
// Properties: number, artifact_coordinates, is_snapshot, is_release, is_latest,
//            is_stable, semantic_version, major, minor, patch, pre_release,
//            build_metadata, release_date, deprecation_date, is_deprecated,
//            is_vulnerable, vulnerability_score, compatibility_score

// Vulnerability Information
// :Vulnerability
// Properties: cve_id, severity, score, description, published_date, modified_date,
//            affected_versions, patched_versions, vulnerable_configurations,
//            references, vendor_advisory, exploit_available, fix_available

// License Information
// :License
// Properties: name, spdx_id, url, is_osi_approved, is_copyleft, is_commercial,
//            permissions, conditions, limitations, description, compatibility_issues

// Build Profiles
// :BuildProfile
// Properties: id, activation_conditions, properties, dependencies, plugins,
//            repositories, is_active_by_default, operating_system, jdk_version

// Maven Plugins
// :MavenPlugin
// Properties: group_id, artifact_id, version, goals, configuration, executions,
//            phase_bindings, is_inherited, dependencies

// Dependency Scopes
// :DependencyScope
// Properties: name, description, transitive, compile_classpath, runtime_classpath,
//            test_classpath, provided_classpath

// =============================================================================
// MAVEN-SPECIFIC RELATIONSHIP TYPES
// =============================================================================

// Artifact and Dependency Relationships
// (:Repository)-[:HAS_BUILD_FILE]->(:BuildFile)
// (:Repository)-[:HAS_POM]->(:PomFile)
// (:BuildFile)-[:DEFINES_ARTIFACT]->(:MavenArtifact)
// (:PomFile)-[:DEFINES_ARTIFACT]->(:MavenArtifact)
// (:PomFile)-[:EXTENDS]->(:PomFile)  // Parent POM
// (:PomFile)-[:INCLUDES]->(:PomFile)  // Module POM

// Direct Dependencies
// (:MavenArtifact)-[:DEPENDS_ON]->(:MavenArtifact)
// (:MavenArtifact)-[:DIRECT_DEPENDENCY]->(:MavenDependency)
// (:MavenDependency)-[:RESOLVES_TO]->(:MavenArtifact)

// Transitive Dependencies
// (:MavenArtifact)-[:TRANSITIVE_DEPENDENCY]->(:MavenDependency)
// (:MavenDependency)-[:BRINGS_IN]->(:MavenDependency)
// (:MavenDependency)-[:EXCLUDED_BY]->(:MavenDependency)

// Version Relationships
// (:MavenArtifact)-[:HAS_VERSION]->(:Version)
// (:Version)-[:SUPERSEDES]->(:Version)
// (:Version)-[:COMPATIBLE_WITH]->(:Version)
// (:Version)-[:CONFLICTS_WITH]->(:Version)
// (:Version)-[:VULNERABLE_TO]->(:Vulnerability)

// Repository and Distribution
// (:MavenArtifact)-[:AVAILABLE_IN]->(:MavenRepository)
// (:MavenRepository)-[:MIRRORS]->(:MavenRepository)
// (:MavenRepository)-[:PROXIES]->(:MavenRepository)

// License and Legal
// (:MavenArtifact)-[:LICENSED_UNDER]->(:License)
// (:License)-[:COMPATIBLE_WITH]->(:License)
// (:License)-[:INCOMPATIBLE_WITH]->(:License)

// Build and Plugin Relationships
// (:PomFile)-[:USES_PLUGIN]->(:MavenPlugin)
// (:MavenPlugin)-[:DEPENDS_ON]->(:MavenArtifact)
// (:PomFile)-[:HAS_PROFILE]->(:BuildProfile)
// (:BuildProfile)-[:ADDS_DEPENDENCY]->(:MavenDependency)

// Conflict Resolution
// (:MavenDependency)-[:NEAREST_WINS]->(:MavenDependency)
// (:MavenDependency)-[:OVERRIDDEN_BY]->(:MavenDependency)
// (:MavenDependency)-[:MEDIATED_BY]->(:MavenDependency)

// Business Logic Integration
// (:MavenArtifact)-[:IMPLEMENTS]->(:Service)
// (:MavenArtifact)-[:BELONGS_TO]->(:Domain)
// (:MavenArtifact)-[:USED_BY]->(:BusinessRule)

// =============================================================================
// DEPENDENCY SCOPES SETUP
// =============================================================================

// Create standard Maven dependency scopes
CREATE (compile:DependencyScope {
    name: 'compile',
    description: 'Default scope, available in all classpaths',
    transitive: true,
    compile_classpath: true,
    runtime_classpath: true,
    test_classpath: true,
    provided_classpath: false
});

CREATE (provided:DependencyScope {
    name: 'provided',
    description: 'Available at compile time, not bundled',
    transitive: false,
    compile_classpath: true,
    runtime_classpath: false,
    test_classpath: true,
    provided_classpath: true
});

CREATE (runtime:DependencyScope {
    name: 'runtime',
    description: 'Not needed for compilation, required at runtime',
    transitive: true,
    compile_classpath: false,
    runtime_classpath: true,
    test_classpath: true,
    provided_classpath: false
});

CREATE (test:DependencyScope {
    name: 'test',
    description: 'Only available for test compilation and execution',
    transitive: true,
    compile_classpath: false,
    runtime_classpath: false,
    test_classpath: true,
    provided_classpath: false
});

CREATE (system:DependencyScope {
    name: 'system',
    description: 'Similar to provided, but with explicit path',
    transitive: false,
    compile_classpath: true,
    runtime_classpath: false,
    test_classpath: true,
    provided_classpath: true
});

CREATE (import:DependencyScope {
    name: 'import',
    description: 'Only used for dependency management',
    transitive: false,
    compile_classpath: false,
    runtime_classpath: false,
    test_classpath: false,
    provided_classpath: false
});

// =============================================================================
// MAVEN REPOSITORIES SETUP
// =============================================================================

// Create standard Maven repositories
CREATE (central:MavenRepository {
    id: 'central',
    name: 'Maven Central Repository',
    url: 'https://repo1.maven.org/maven2',
    type: 'public',
    layout: 'default',
    is_snapshots_enabled: false,
    is_releases_enabled: true,
    update_policy: 'daily',
    checksum_policy: 'warn',
    authentication_required: false,
    priority: 1,
    is_active: true
});

CREATE (snapshots:MavenRepository {
    id: 'apache-snapshots',
    name: 'Apache Snapshots Repository',
    url: 'https://repository.apache.org/snapshots',
    type: 'public',
    layout: 'default',
    is_snapshots_enabled: true,
    is_releases_enabled: false,
    update_policy: 'daily',
    checksum_policy: 'warn',
    authentication_required: false,
    priority: 2,
    is_active: true
});

CREATE (jcenter:MavenRepository {
    id: 'jcenter',
    name: 'JCenter Repository',
    url: 'https://jcenter.bintray.com',
    type: 'public',
    layout: 'default',
    is_snapshots_enabled: false,
    is_releases_enabled: true,
    update_policy: 'daily',
    checksum_policy: 'warn',
    authentication_required: false,
    priority: 3,
    is_active: false
});

// =============================================================================
// COMMON LICENSES SETUP
// =============================================================================

CREATE (apache2:License {
    name: 'Apache License 2.0',
    spdx_id: 'Apache-2.0',
    url: 'https://www.apache.org/licenses/LICENSE-2.0',
    is_osi_approved: true,
    is_copyleft: false,
    is_commercial: true,
    permissions: ['commercial-use', 'distribution', 'modification', 'patent-use', 'private-use'],
    conditions: ['include-copyright', 'document-changes'],
    limitations: ['liability', 'warranty'],
    description: 'A permissive license with explicit grant of patent rights'
});

CREATE (mit:License {
    name: 'MIT License',
    spdx_id: 'MIT',
    url: 'https://opensource.org/licenses/MIT',
    is_osi_approved: true,
    is_copyleft: false,
    is_commercial: true,
    permissions: ['commercial-use', 'distribution', 'modification', 'private-use'],
    conditions: ['include-copyright'],
    limitations: ['liability', 'warranty'],
    description: 'A simple permissive license'
});

CREATE (gpl3:License {
    name: 'GNU General Public License v3.0',
    spdx_id: 'GPL-3.0',
    url: 'https://www.gnu.org/licenses/gpl-3.0.html',
    is_osi_approved: true,
    is_copyleft: true,
    is_commercial: false,
    permissions: ['commercial-use', 'distribution', 'modification', 'patent-use', 'private-use'],
    conditions: ['disclose-source', 'include-copyright', 'same-license', 'document-changes'],
    limitations: ['liability', 'warranty'],
    description: 'Strong copyleft license'
});

// License compatibility rules
CREATE (apache2)-[:COMPATIBLE_WITH]->(mit);
CREATE (mit)-[:COMPATIBLE_WITH]->(apache2);
CREATE (gpl3)-[:INCOMPATIBLE_WITH]->(apache2);
CREATE (gpl3)-[:INCOMPATIBLE_WITH]->(mit);

// =============================================================================
// DEPENDENCY RESOLUTION ALGORITHMS (CYPHER PROCEDURES)
// =============================================================================

// Find all transitive dependencies for an artifact
// CALL apoc.cypher.doIt('
//   MATCH (artifact:MavenArtifact {coordinates: $coordinates})
//   CALL apoc.path.expandConfig(artifact, {
//     relationshipFilter: "DEPENDS_ON>",
//     labelFilter: "MavenArtifact",
//     uniqueness: "NODE_GLOBAL",
//     bfs: true
//   }) YIELD path
//   RETURN path
// ', {coordinates: 'com.example:my-artifact:1.0.0'})

// Detect circular dependencies
// MATCH (a:MavenArtifact)-[:DEPENDS_ON*]->(b:MavenArtifact)-[:DEPENDS_ON*]->(a)
// RETURN DISTINCT a.coordinates, b.coordinates

// Find dependency conflicts (same group:artifact, different versions)
// MATCH (root:MavenArtifact {coordinates: $root})
// CALL apoc.path.expandConfig(root, {
//   relationshipFilter: "DEPENDS_ON>",
//   labelFilter: "MavenArtifact",
//   uniqueness: "NODE_GLOBAL"
// }) YIELD path
// WITH nodes(path) AS artifacts
// UNWIND artifacts AS artifact
// WITH artifact.group_id + ':' + artifact.artifact_id AS ga, 
//      collect(DISTINCT artifact.version) AS versions
// WHERE size(versions) > 1
// RETURN ga, versions

// =============================================================================
// DEPENDENCY TREE ANALYSIS QUERIES
// =============================================================================

// Get dependency tree for a specific artifact
// MATCH (root:MavenArtifact {coordinates: $coordinates})
// CALL apoc.path.expandConfig(root, {
//   relationshipFilter: "DEPENDS_ON>",
//   labelFilter: "MavenArtifact",
//   uniqueness: "NODE_PATH",
//   bfs: true,
//   limit: 1000
// }) YIELD path
// RETURN path, length(path) AS depth
// ORDER BY depth

// Find artifacts with most dependencies (complexity analysis)
// MATCH (a:MavenArtifact)
// OPTIONAL MATCH (a)-[:DEPENDS_ON]->(direct:MavenArtifact)
// OPTIONAL MATCH (a)-[:DEPENDS_ON*]->(transitive:MavenArtifact)
// RETURN a.coordinates, 
//        count(DISTINCT direct) AS direct_deps,
//        count(DISTINCT transitive) AS total_deps,
//        count(DISTINCT transitive) - count(DISTINCT direct) AS transitive_deps
// ORDER BY total_deps DESC

// Find most depended-upon artifacts (hub analysis)
// MATCH (a:MavenArtifact)<-[:DEPENDS_ON]-(dependent:MavenArtifact)
// RETURN a.coordinates, count(dependent) AS dependent_count
// ORDER BY dependent_count DESC

// =============================================================================
// VULNERABILITY ANALYSIS QUERIES
// =============================================================================

// Find all vulnerable dependencies in a repository
// MATCH (repo:Repository)-[:HAS_POM]->(pom:PomFile)-[:DEFINES_ARTIFACT]->(artifact:MavenArtifact)
// MATCH (artifact)-[:DEPENDS_ON*]->(dep:MavenArtifact)-[:HAS_VERSION]->(v:Version)-[:VULNERABLE_TO]->(vuln:Vulnerability)
// RETURN repo.name, dep.coordinates, vuln.cve_id, vuln.severity, vuln.score
// ORDER BY vuln.score DESC

// Find critical vulnerabilities across all repositories
// MATCH (vuln:Vulnerability)
// WHERE vuln.severity = 'CRITICAL'
// MATCH (vuln)<-[:VULNERABLE_TO]-(version:Version)<-[:HAS_VERSION]-(artifact:MavenArtifact)
// MATCH (artifact)<-[:DEPENDS_ON*]-(root:MavenArtifact)<-[:DEFINES_ARTIFACT]-(pom:PomFile)<-[:HAS_POM]-(repo:Repository)
// RETURN repo.name, artifact.coordinates, vuln.cve_id, vuln.description
// ORDER BY repo.name, vuln.score DESC

// =============================================================================
// LICENSE COMPLIANCE QUERIES
// =============================================================================

// Find license conflicts in dependencies
// MATCH (repo:Repository)-[:HAS_POM]->(pom:PomFile)-[:DEFINES_ARTIFACT]->(artifact:MavenArtifact)
// MATCH (artifact)-[:DEPENDS_ON*]->(dep:MavenArtifact)-[:LICENSED_UNDER]->(license:License)
// MATCH (license)-[:INCOMPATIBLE_WITH]->(conflicting:License)<-[:LICENSED_UNDER]-(other_dep:MavenArtifact)
// WHERE (artifact)-[:DEPENDS_ON*]->(other_dep)
// RETURN repo.name, dep.coordinates, license.name, other_dep.coordinates, conflicting.name

// Find all licenses used in a repository
// MATCH (repo:Repository)-[:HAS_POM]->(pom:PomFile)-[:DEFINES_ARTIFACT]->(artifact:MavenArtifact)
// MATCH (artifact)-[:DEPENDS_ON*]->(dep:MavenArtifact)-[:LICENSED_UNDER]->(license:License)
// RETURN repo.name, collect(DISTINCT license.name) AS licenses
// ORDER BY repo.name

// =============================================================================
// BUILD OPTIMIZATION QUERIES
// =============================================================================

// Find unused dependencies (defined but not referenced in code)
// MATCH (pom:PomFile)-[:DEFINES_ARTIFACT]->(artifact:MavenArtifact)-[:DEPENDS_ON]->(dep:MavenArtifact)
// MATCH (pom)<-[:HAS_POM]-(repo:Repository)-[:CONTAINS]->(file:File)
// WHERE NOT EXISTS {
//   MATCH (file)-[:DEFINES]->(entity)
//   WHERE entity.content CONTAINS dep.group_id OR entity.content CONTAINS dep.artifact_id
// }
// RETURN repo.name, dep.coordinates AS unused_dependency

// Find duplicate dependencies (same functionality, different artifacts)
// MATCH (a1:MavenArtifact), (a2:MavenArtifact)
// WHERE a1.group_id = a2.group_id AND a1.artifact_id <> a2.artifact_id
//   AND a1.description CONTAINS a2.description
// RETURN a1.coordinates, a2.coordinates AS potential_duplicates

// =============================================================================
// PERFORMANCE MONITORING QUERIES
// =============================================================================

// Monitor dependency resolution performance
// MATCH (pom:PomFile)
// RETURN pom.file_path, 
//        pom.dependencies_count,
//        pom.last_parsed,
//        duration.between(pom.last_parsed, datetime()) AS time_since_parsed
// ORDER BY time_since_parsed DESC

// Repository dependency health score
// MATCH (repo:Repository)-[:HAS_POM]->(pom:PomFile)-[:DEFINES_ARTIFACT]->(artifact:MavenArtifact)
// OPTIONAL MATCH (artifact)-[:DEPENDS_ON*]->(dep:MavenArtifact)-[:HAS_VERSION]->(v:Version)
// WHERE v.is_vulnerable = true
// WITH repo, 
//      count(DISTINCT dep) AS vulnerable_deps,
//      count(DISTINCT artifact) AS total_deps,
//      (1.0 - (toFloat(vulnerable_deps) / total_deps)) * 100 AS health_score
// RETURN repo.name, health_score, vulnerable_deps, total_deps
// ORDER BY health_score ASC

// =============================================================================
// SAMPLE MAVEN ARTIFACTS AND DEPENDENCIES
// =============================================================================

// Create sample Spring Boot artifacts
CREATE (spring_boot:MavenArtifact {
    group_id: 'org.springframework.boot',
    artifact_id: 'spring-boot-starter-web',
    version: '2.7.0',
    coordinates: 'org.springframework.boot:spring-boot-starter-web:2.7.0',
    name: 'Spring Boot Starter Web',
    description: 'Starter for building web applications with Spring Boot',
    type: 'jar',
    packaging: 'jar',
    is_snapshot: false,
    is_release: true
});

CREATE (spring_core:MavenArtifact {
    group_id: 'org.springframework',
    artifact_id: 'spring-core',
    version: '5.3.21',
    coordinates: 'org.springframework:spring-core:5.3.21',
    name: 'Spring Core',
    description: 'Spring Core framework',
    type: 'jar',
    packaging: 'jar',
    is_snapshot: false,
    is_release: true
});

CREATE (jackson:MavenArtifact {
    group_id: 'com.fasterxml.jackson.core',
    artifact_id: 'jackson-databind',
    version: '2.13.3',
    coordinates: 'com.fasterxml.jackson.core:jackson-databind:2.13.3',
    name: 'Jackson Databind',
    description: 'JSON data binding for Java',
    type: 'jar',
    packaging: 'jar',
    is_snapshot: false,
    is_release: true
});

// Create dependency relationships
CREATE (spring_boot)-[:DEPENDS_ON]->(spring_core);
CREATE (spring_boot)-[:DEPENDS_ON]->(jackson);

// License relationships
CREATE (spring_boot)-[:LICENSED_UNDER]->(apache2);
CREATE (spring_core)-[:LICENSED_UNDER]->(apache2);
CREATE (jackson)-[:LICENSED_UNDER]->(apache2);

// Repository relationships
CREATE (spring_boot)-[:AVAILABLE_IN]->(central);
CREATE (spring_core)-[:AVAILABLE_IN]->(central);
CREATE (jackson)-[:AVAILABLE_IN]->(central);

// =============================================================================
// INITIALIZATION COMPLETE
// =============================================================================

RETURN 'Enhanced Neo4j schema with comprehensive Maven support has been successfully initialized' AS status;