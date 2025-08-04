// Neo4j Schema for Codebase RAG System
// Business Logic Relationships and Cross-Repository Dependencies

// =============================================================================
// CONSTRAINTS AND INDEXES
// =============================================================================

// Repository constraints
CREATE CONSTRAINT repo_name_unique IF NOT EXISTS FOR (r:Repository) REQUIRE r.name IS UNIQUE;
CREATE CONSTRAINT repo_url_unique IF NOT EXISTS FOR (r:Repository) REQUIRE r.url IS UNIQUE;

// File constraints
CREATE CONSTRAINT file_path_unique IF NOT EXISTS FOR (f:File) REQUIRE f.full_path IS UNIQUE;

// Code entity constraints
CREATE CONSTRAINT function_id_unique IF NOT EXISTS FOR (fn:Function) REQUIRE fn.id IS UNIQUE;
CREATE CONSTRAINT class_id_unique IF NOT EXISTS FOR (c:Class) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT variable_id_unique IF NOT EXISTS FOR (v:Variable) REQUIRE v.id IS UNIQUE;
CREATE CONSTRAINT module_id_unique IF NOT EXISTS FOR (m:Module) REQUIRE m.id IS UNIQUE;

// Business domain constraints
CREATE CONSTRAINT domain_name_unique IF NOT EXISTS FOR (d:Domain) REQUIRE d.name IS UNIQUE;
CREATE CONSTRAINT service_name_unique IF NOT EXISTS FOR (s:Service) REQUIRE s.name IS UNIQUE;

// Performance indexes
CREATE INDEX repo_name_idx IF NOT EXISTS FOR (r:Repository) ON (r.name);
CREATE INDEX file_path_idx IF NOT EXISTS FOR (f:File) ON (f.path);
CREATE INDEX file_language_idx IF NOT EXISTS FOR (f:File) ON (f.language);
CREATE INDEX function_name_idx IF NOT EXISTS FOR (fn:Function) ON (fn.name);
CREATE INDEX class_name_idx IF NOT EXISTS FOR (c:Class) ON (c.name);
CREATE INDEX variable_name_idx IF NOT EXISTS FOR (v:Variable) ON (v.name);
CREATE INDEX domain_name_idx IF NOT EXISTS FOR (d:Domain) ON (d.name);
CREATE INDEX service_name_idx IF NOT EXISTS FOR (s:Service) ON (s.name);

// Database constraints and indexes (Additions)
// Constraints (unique identifiers)
CREATE CONSTRAINT database_name_unique IF NOT EXISTS FOR (d:Database) REQUIRE d.name IS UNIQUE;

// Indexes for lookup performance
CREATE INDEX schema_name_idx IF NOT EXISTS FOR (s:Schema) ON (s.name);
CREATE INDEX table_name_idx IF NOT EXISTS FOR (t:Table) ON (t.name);
CREATE INDEX view_name_idx IF NOT EXISTS FOR (v:View) ON (v.name);
CREATE INDEX procedure_name_idx IF NOT EXISTS FOR (p:Procedure) ON (p.name);
CREATE INDEX function_name2_idx IF NOT EXISTS FOR (f:Function) ON (f.name);
CREATE INDEX column_name_idx IF NOT EXISTS FOR (c:Column) ON (c.name);

// Full-text search indexes
CREATE FULLTEXT INDEX code_search_idx IF NOT EXISTS FOR (n:Function|Class|Variable|Module) ON EACH [n.name, n.content, n.docstring];
CREATE FULLTEXT INDEX repo_search_idx IF NOT EXISTS FOR (r:Repository) ON EACH [r.name, r.description];
CREATE FULLTEXT INDEX domain_search_idx IF NOT EXISTS FOR (d:Domain) ON EACH [d.name, d.description];

// =============================================================================
// NODE LABELS AND PROPERTIES
// =============================================================================

// Repository level
// :Repository
// Properties: name, url, description, language, framework, domain, stars, forks, 
//            last_commit, created_at, updated_at, is_active, size_mb, complexity_score

// :File
// Properties: path, full_path, name, extension, language, size_bytes, line_count,
//            complexity_score, last_modified, content_hash, is_test, is_config

// :Directory
// Properties: path, name, level, file_count, total_size_bytes

// Code Structure
// :Module
// Properties: id, name, path, language, docstring, imports, exports, complexity_score

// :Class
// Properties: id, name, full_name, docstring, is_abstract, is_interface, access_modifier,
//            line_start, line_end, complexity_score, method_count, property_count

// :Function
// Properties: id, name, full_name, docstring, return_type, parameters, is_async, 
//            is_static, is_private, access_modifier, line_start, line_end, 
//            complexity_score, parameter_count

// :Variable
// Properties: id, name, type, scope, is_constant, is_global, line_number, default_value

// :Parameter
// Properties: name, type, is_optional, default_value, position

// :Property
// Properties: name, type, is_static, is_readonly, access_modifier, default_value

// Business Logic
// :Domain
// Properties: name, description, keywords, priority, owner_team

// :Service
// Properties: name, description, type, endpoints, dependencies, domain

// :BusinessRule
// Properties: name, description, condition, action, priority, domain

// :Workflow
// Properties: name, description, steps, triggers, domain

// :Entity
// Properties: name, description, attributes, domain, is_aggregate_root

// :Event
// Properties: name, description, payload_schema, domain, is_domain_event

// Integration and Dependencies
// :Dependency
// Properties: name, version, type, scope, is_dev_dependency

// :API
// Properties: name, base_url, version, type, authentication, documentation_url

// :Database
// Properties: name, type, host, schema, connection_string_template

// Database-aware Nodes (Additions)
// :Schema
// Properties: name, owner
//
// :Table
// Properties: name, schema, pk, row_count, last_analyzed
//
// :Column
// Properties: name, data_type, nullable, default, sensitive, comment
//
// :View
// Properties: name, schema, definition_hash
//
// :Procedure
// Properties: name, schema, language, deterministic, authz_enforced
//
// :Function
// Properties: name, schema, language, deterministic
//
// :Package
// Properties: name, schema
//
// :Trigger
// Properties: name, table, event, timing, enabled
//
// :Job
// Properties: name, schedule, owner

// :Queue
// Properties: name, type, topic, exchange, routing_key

// :ExternalService
// Properties: name, type, base_url, authentication, sla, documentation_url

// =============================================================================
// RELATIONSHIP TYPES
// =============================================================================

// Repository Structure
// (:Repository)-[:CONTAINS]->(:File)
// (:Repository)-[:CONTAINS]->(:Directory)
// (:Repository)-[:DEPENDS_ON]->(:Repository)
// (:Repository)-[:BELONGS_TO]->(:Domain)
// (:Repository)-[:IMPLEMENTS]->(:Service)

// Database Relationships (Additions)
// (:Repository)-[:READS_FROM]->(:Table|:View|:Column)
// (:Repository)-[:WRITES_TO]->(:Table|:Column)
// (:Repository)-[:CALLS_DB_PROC]->(:Procedure|:Function)
// (:Table)-[:FK_REF]->(:Table)
// (:Table)-[:CONTAINS]->(:Column)
// (:Schema)-[:CONTAINS]->(:Table)
// (:Schema)-[:CONTAINS]->(:View)
// (:Schema)-[:CONTAINS]->(:Procedure)
// (:Schema)-[:CONTAINS]->(:Function)
// (:Schema)-[:CONTAINS]->(:Package)
// (:Database)-[:CONTAINS]->(:Schema)
// (:Trigger)-[:ATTACHED_TO]->(:Table)
// (:View)-[:DERIVES_FROM]->(:Table|:View)

// File Structure
// (:Directory)-[:CONTAINS]->(:File)
// (:Directory)-[:CONTAINS]->(:Directory)
// (:File)-[:DEFINES]->(:Class)
// (:File)-[:DEFINES]->(:Function)
// (:File)-[:DEFINES]->(:Variable)
// (:File)-[:IMPORTS]->(:Module)
// (:File)-[:BELONGS_TO]->(:Repository)

// Code Relationships
// (:Class)-[:INHERITS]->(:Class)
// (:Class)-[:IMPLEMENTS]->(:Class)  // Interface
// (:Class)-[:CONTAINS]->(:Function)
// (:Class)-[:CONTAINS]->(:Property)
// (:Class)-[:DEPENDS_ON]->(:Class)
// (:Class)-[:BELONGS_TO]->(:Domain)

// (:Function)-[:CALLS]->(:Function)
// (:Function)-[:RETURNS]->(:Type)
// (:Function)-[:TAKES]->(:Parameter)
// (:Function)-[:ACCESSES]->(:Variable)
// (:Function)-[:ACCESSES]->(:Property)
// (:Function)-[:HANDLES]->(:Event)
// (:Function)-[:THROWS]->(:Exception)
// (:Function)-[:BELONGS_TO]->(:Domain)

// (:Variable)-[:OF_TYPE]->(:Type)
// (:Variable)-[:INITIALIZED_BY]->(:Function)

// Module and Import Relationships
// (:Module)-[:IMPORTS]->(:Module)
// (:Module)-[:EXPORTS]->(:Function)
// (:Module)-[:EXPORTS]->(:Class)
// (:Module)-[:EXPORTS]->(:Variable)

// Business Logic Relationships
// (:Domain)-[:CONTAINS]->(:Service)
// (:Domain)-[:CONTAINS]->(:Entity)
// (:Domain)-[:CONTAINS]->(:BusinessRule)
// (:Domain)-[:DEPENDS_ON]->(:Domain)

// (:Service)-[:EXPOSES]->(:API)
// (:Service)-[:USES]->(:Database)
// (:Service)-[:PUBLISHES]->(:Event)
// (:Service)-[:SUBSCRIBES]->(:Event)
// (:Service)-[:CALLS]->(:ExternalService)
// (:Service)-[:IMPLEMENTS]->(:BusinessRule)

// (:Entity)-[:HAS_PROPERTY]->(:Property)
// (:Entity)-[:RAISES]->(:Event)
// (:Entity)-[:FOLLOWS]->(:BusinessRule)

// (:BusinessRule)-[:APPLIES_TO]->(:Entity)
// (:BusinessRule)-[:TRIGGERS]->(:Event)
// (:BusinessRule)-[:DEPENDS_ON]->(:BusinessRule)

// (:Workflow)-[:STARTS_WITH]->(:Event)
// (:Workflow)-[:INCLUDES]->(:BusinessRule)
// (:Workflow)-[:CALLS]->(:Service)

// Cross-Repository Dependencies
// (:Repository)-[:USES_LIBRARY]->(:Dependency)
// (:Repository)-[:CALLS_API]->(:API)
// (:Repository)-[:SHARES_DATA]->(:Repository)
// (:Repository)-[:EXTENDS]->(:Repository)

// Integration Relationships
// (:API)-[:BELONGS_TO]->(:Service)
// (:API)-[:SECURED_BY]->(:Authentication)
// (:Database)-[:STORES]->(:Entity)
// (:Queue)-[:CARRIES]->(:Event)
// (:ExternalService)-[:PROVIDES]->(:API)

// =============================================================================
// SAMPLE DATA AND QUERIES
// =============================================================================

// Create sample domains
CREATE (auth:Domain {
    name: 'Authentication',
    description: 'User authentication and authorization',
    keywords: ['auth', 'login', 'jwt', 'session', 'oauth'],
    priority: 1,
    owner_team: 'Security'
});

CREATE (billing:Domain {
    name: 'Billing',
    description: 'Payment processing and billing',
    keywords: ['payment', 'billing', 'invoice', 'subscription'],
    priority: 1,
    owner_team: 'Finance'
});

CREATE (user:Domain {
    name: 'User Management',
    description: 'User profiles and management',
    keywords: ['user', 'profile', 'management', 'crud'],
    priority: 1,
    owner_team: 'Platform'
});

CREATE (notification:Domain {
    name: 'Notification',
    description: 'Email, SMS, and push notifications',
    keywords: ['email', 'sms', 'push', 'notification', 'alert'],
    priority: 2,
    owner_team: 'Platform'
});

// Create sample services
CREATE (auth_service:Service {
    name: 'AuthService',
    description: 'Handles user authentication',
    type: 'microservice',
    endpoints: ['POST /login', 'POST /logout', 'POST /refresh'],
    dependencies: ['UserService', 'TokenService']
});

CREATE (user_service:Service {
    name: 'UserService',
    description: 'Manages user profiles',
    type: 'microservice',
    endpoints: ['GET /users', 'POST /users', 'PUT /users/:id'],
    dependencies: ['DatabaseService']
});

CREATE (billing_service:Service {
    name: 'BillingService',
    description: 'Handles payment processing',
    type: 'microservice',
    endpoints: ['POST /payments', 'GET /invoices'],
    dependencies: ['PaymentGateway', 'UserService']
});

// Create relationships
CREATE (auth_service)-[:BELONGS_TO]->(auth);
CREATE (user_service)-[:BELONGS_TO]->(user);
CREATE (billing_service)-[:BELONGS_TO]->(billing);

// Domain dependencies
CREATE (auth)-[:DEPENDS_ON]->(user);
CREATE (billing)-[:DEPENDS_ON]->(user);

// =============================================================================
// UTILITY PROCEDURES
// =============================================================================

// Procedure to find all functions that call a specific function
// CALL db.create.setNodeProperty(node, 'property', value)

// =============================================================================
// PERFORMANCE OPTIMIZATION QUERIES
// =============================================================================

// Pre-warm commonly used queries
MATCH (r:Repository) RETURN count(r);
MATCH (f:File) RETURN count(f);
MATCH (fn:Function) RETURN count(fn);
MATCH (c:Class) RETURN count(c);
MATCH (d:Domain) RETURN count(d);

// Create materialized views for common patterns
// Note: Neo4j doesn't have traditional materialized views, but we can use periodic queries

// =============================================================================
// MONITORING AND MAINTENANCE
// =============================================================================

// Query to monitor database health
CALL db.stats.retrieve('GRAPH COUNTS');

// Query to check constraint violations
CALL db.constraints();

// Query to check index usage
CALL db.indexes();

// =============================================================================
// EXAMPLE QUERIES FOR BUSINESS LOGIC ANALYSIS
// =============================================================================

// Find all functions in a specific domain
// MATCH (d:Domain {name: 'Authentication'})<-[:BELONGS_TO]-(fn:Function)
// RETURN fn.name, fn.docstring;

// Find cross-repository dependencies
// MATCH (r1:Repository)-[:DEPENDS_ON]->(r2:Repository)
// RETURN r1.name AS source, r2.name AS target;

// Find circular dependencies
// MATCH (r1:Repository)-[:DEPENDS_ON*]->(r2:Repository)-[:DEPENDS_ON*]->(r1)
// RETURN r1.name, r2.name;

// Find most connected functions (hub functions)
// MATCH (fn:Function)
// OPTIONAL MATCH (fn)-[:CALLS]->(called:Function)
// OPTIONAL MATCH (caller:Function)-[:CALLS]->(fn)
// RETURN fn.name, 
//        count(DISTINCT called) AS calls_count,
//        count(DISTINCT caller) AS called_by_count,
//        count(DISTINCT called) + count(DISTINCT caller) AS total_connections
// ORDER BY total_connections DESC
// LIMIT 10;

// Find business rules that affect multiple domains
// MATCH (br:BusinessRule)-[:APPLIES_TO]->(e:Entity)-[:BELONGS_TO]->(d:Domain)
// WITH br, count(DISTINCT d) AS domain_count
// WHERE domain_count > 1
// RETURN br.name, br.description, domain_count;

// Find services with highest complexity
// MATCH (s:Service)-[:BELONGS_TO]->(d:Domain)
// MATCH (s)<-[:IMPLEMENTS]-(r:Repository)
// MATCH (r)-[:CONTAINS]->(f:File)-[:DEFINES]->(fn:Function)
// RETURN s.name, d.name, avg(fn.complexity_score) AS avg_complexity
// ORDER BY avg_complexity DESC;

// =============================================================================
// DATA VALIDATION RULES
// =============================================================================

// Ensure every function belongs to a file
// MATCH (fn:Function)
// WHERE NOT (fn)<-[:DEFINES]-(:File)
// RETURN fn.name AS orphaned_function;

// Ensure every class has at least one method or property
// MATCH (c:Class)
// WHERE NOT (c)-[:CONTAINS]->(:Function) AND NOT (c)-[:CONTAINS]->(:Property)
// RETURN c.name AS empty_class;

// Ensure repositories have valid URLs
// MATCH (r:Repository)
// WHERE NOT r.url =~ 'https?://.*'
// RETURN r.name AS invalid_repo_url;

// =============================================================================
// PERFORMANCE TUNING SETTINGS
// =============================================================================

// These would be set in neo4j.conf, but documented here for reference:
// dbms.memory.heap.initial_size=8g
// dbms.memory.heap.max_size=16g
// dbms.memory.pagecache.size=32g
// dbms.tx.log.rotation.retention_policy=100M size
// dbms.checkpoint.interval.time=300s
// dbms.checkpoint.interval.tx=100000

// =============================================================================
// BACKUP AND MAINTENANCE PROCEDURES
// =============================================================================

// Regular maintenance queries to run:

// 1. Clean up orphaned nodes (run weekly)
// MATCH (n)
// WHERE size((n)--()) = 0
// DELETE n;

// 2. Update repository statistics (run daily)
// MATCH (r:Repository)-[:CONTAINS]->(f:File)
// SET r.file_count = count(f),
//     r.total_size_bytes = sum(f.size_bytes);

// 3. Refresh complexity scores (run after major updates)
// MATCH (fn:Function)
// SET fn.complexity_score = 
//     CASE 
//         WHEN fn.content IS NOT NULL 
//         THEN apoc.text.regexCount(fn.content, '\\b(if|while|for|try|catch|switch)\\b') + 1
//         ELSE 1
//     END;

// =============================================================================
// SCHEMA EVOLUTION PROCEDURES
// =============================================================================

// Procedure to add new properties to existing nodes
// MATCH (n:Function)
// WHERE n.is_deprecated IS NULL
// SET n.is_deprecated = false;

// Procedure to migrate relationships
// MATCH (a:Class)-[r:USES]->(b:Class)
// CREATE (a)-[:DEPENDS_ON]->(b)
// DELETE r;

// =============================================================================
// SECURITY CONSIDERATIONS
// =============================================================================

// Create roles for different access levels
// CREATE ROLE developer;
// CREATE ROLE architect;
// CREATE ROLE admin;

// Grant permissions
// GRANT TRAVERSE ON GRAPH * TO developer;
// GRANT READ {*} ON GRAPH * TO developer;
// GRANT WRITE {*} ON GRAPH * TO architect;
// GRANT ALL ON GRAPH * TO admin;

// =============================================================================
// INITIAL SETUP COMPLETE
// =============================================================================

// Return setup confirmation
RETURN 'Neo4j schema for Codebase RAG system has been successfully initialized' AS status;