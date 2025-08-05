"""
Neo4j client for MVP - simplified graph database operations.
Handles Maven dependencies and code relationships.
"""

import os
import logging
from typing import List, Dict, Any, Optional, Union
import asyncio

from neo4j import GraphDatabase, AsyncGraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Simplified Neo4j client for MVP."""
    
    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        username: str = "neo4j",
        password: str = "codebase-rag-2024"
    ):
        self.uri = uri
        self.username = username
        self.password = password
        self.driver = None
        
    async def initialize(self):
        """Initialize Neo4j connection."""
        try:
            self.driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password)
            )
            
            # Test connection
            await self.health_check()
            
            # Initialize schema
            await self.create_schema()
            
            logger.info("Neo4j client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Neo4j client: {e}")
            raise
    
    async def close(self):
        """Close Neo4j connection."""
        if self.driver:
            await self.driver.close()
    
    async def health_check(self) -> bool:
        """Check Neo4j connection health."""
        try:
            if not self.driver:
                return False
                
            async with self.driver.session() as session:
                result = await session.run("RETURN 1 as health")
                record = await result.single()
                return record["health"] == 1
                
        except Exception as e:
            logger.error(f"Neo4j health check failed: {e}")
            return False
    
    async def create_schema(self):
        """Create basic schema for MVP."""
        schema_queries = [
            # Node constraints
            "CREATE CONSTRAINT repo_name_unique IF NOT EXISTS FOR (r:Repository) REQUIRE r.name IS UNIQUE",
            "CREATE CONSTRAINT artifact_id_unique IF NOT EXISTS FOR (a:MavenArtifact) REQUIRE a.id IS UNIQUE",
            "CREATE CONSTRAINT file_path_unique IF NOT EXISTS FOR (f:File) REQUIRE f.path IS UNIQUE",
            
            # ENHANCED: Migration-specific constraints
            "CREATE CONSTRAINT business_rule_id_unique IF NOT EXISTS FOR (br:BusinessRule) REQUIRE br.id IS UNIQUE",
            "CREATE CONSTRAINT struts_action_path_unique IF NOT EXISTS FOR (sa:StrutsAction) REQUIRE sa.path IS UNIQUE",
            "CREATE CONSTRAINT corba_interface_name_unique IF NOT EXISTS FOR (ci:CORBAInterface) REQUIRE ci.name IS UNIQUE",
            "CREATE CONSTRAINT jsp_component_id_unique IF NOT EXISTS FOR (jsp:JSPComponent) REQUIRE jsp.id IS UNIQUE",
            
            # Indexes for performance
            "CREATE INDEX repo_name_idx IF NOT EXISTS FOR (r:Repository) ON (r.name)",
            "CREATE INDEX artifact_group_idx IF NOT EXISTS FOR (a:MavenArtifact) ON (a.group_id)",
            "CREATE INDEX file_language_idx IF NOT EXISTS FOR (f:File) ON (f.language)",
            "CREATE INDEX dependency_scope_idx IF NOT EXISTS FOR ()-[d:DEPENDS_ON]-() ON (d.scope)",
            
            # ENHANCED: Migration-specific indexes
            "CREATE INDEX business_rule_domain_idx IF NOT EXISTS FOR (br:BusinessRule) ON (br.domain)",
            "CREATE INDEX business_rule_complexity_idx IF NOT EXISTS FOR (br:BusinessRule) ON (br.complexity)",
            "CREATE INDEX struts_action_business_purpose_idx IF NOT EXISTS FOR (sa:StrutsAction) ON (sa.business_purpose)",
            "CREATE INDEX migration_complexity_idx IF NOT EXISTS FOR (f:File) ON (f.migration_complexity)",
            "CREATE INDEX framework_pattern_idx IF NOT EXISTS FOR ()-[fp:HAS_FRAMEWORK_PATTERN]-() ON (fp.pattern_type)",
            "CREATE INDEX business_relation_idx IF NOT EXISTS FOR ()-[br:IMPLEMENTS_BUSINESS_RULE]-() ON (br.rule_type)"
        ]
        
        try:
            async with self.driver.session() as session:
                for query in schema_queries:
                    try:
                        await session.run(query)
                    except Exception as e:
                        logger.warning(f"Schema query failed (may already exist): {query[:50]}... - {e}")
                        
            logger.info("Neo4j schema created/updated")
            
        except Exception as e:
            logger.error(f"Failed to create Neo4j schema: {e}")
            raise
    
    async def execute_query(self, query: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return results."""
        if not self.driver:
            raise Exception("Neo4j driver not initialized")
        
        try:
            async with self.driver.session() as session:
                result = await session.run(query, parameters or {})
                records = []
                async for record in result:
                    records.append(dict(record))
                return records
                
        except Exception as e:
            logger.error(f"Failed to execute query: {query[:100]}... - {e}")
            raise
    
    async def create_repository(self, repo_name: str, repo_path: str, metadata: Dict[str, Any] = None) -> str:
        """Create a repository node."""
        query = """
        MERGE (r:Repository {name: $repo_name})
        SET r.path = $repo_path,
            r.created_at = datetime(),
            r.updated_at = datetime()
        """
        
        # Add metadata properties
        if metadata:
            for key, value in metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    query += f", r.{key} = ${key}"
        
        query += " RETURN r.name as name"
        
        parameters = {
            "repo_name": repo_name,
            "repo_path": repo_path,
            **(metadata or {})
        }
        
        try:
            result = await self.execute_query(query, parameters)
            logger.info(f"Created/updated repository: {repo_name}")
            return result[0]["name"] if result else repo_name
            
        except Exception as e:
            logger.error(f"Failed to create repository {repo_name}: {e}")
            raise
    
    async def create_file(self, repo_name: str, file_path: str, language: str, metadata: Dict[str, Any] = None) -> str:
        """Create a file node and link to repository."""
        query = """
        MATCH (r:Repository {name: $repo_name})
        MERGE (f:File {path: $file_path})
        SET f.language = $language,
            f.created_at = datetime(),
            f.updated_at = datetime()
        """
        
        # Add metadata
        if metadata:
            for key, value in metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    query += f", f.{key} = ${key}"
        
        query += """
        MERGE (r)-[:CONTAINS]->(f)
        RETURN f.path as path
        """
        
        parameters = {
            "repo_name": repo_name,
            "file_path": file_path,
            "language": language,
            **(metadata or {})
        }
        
        try:
            result = await self.execute_query(query, parameters)
            return result[0]["path"] if result else file_path
            
        except Exception as e:
            logger.error(f"Failed to create file {file_path}: {e}")
            raise
    
    async def create_maven_artifact(
        self,
        group_id: str,
        artifact_id: str,
        version: str,
        repo_name: str,
        file_path: str = None,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Create a Maven artifact node."""
        artifact_id_full = f"{group_id}:{artifact_id}:{version}"
        
        query = """
        MATCH (r:Repository {name: $repo_name})
        MERGE (a:MavenArtifact {id: $artifact_id_full})
        SET a.group_id = $group_id,
            a.artifact_id = $artifact_id,
            a.version = $version,
            a.created_at = datetime(),
            a.updated_at = datetime()
        """
        
        # Add metadata
        if metadata:
            for key, value in metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    query += f", a.{key} = ${key}"
        
        query += """
        MERGE (r)-[:DEFINES_ARTIFACT]->(a)
        """
        
        # Link to POM file if provided
        if file_path:
            query += """
            WITH r, a
            MATCH (f:File {path: $file_path})
            MERGE (f)-[:DEFINES]->(a)
            """
        
        query += " RETURN a.id as id"
        
        parameters = {
            "repo_name": repo_name,
            "artifact_id_full": artifact_id_full,
            "group_id": group_id,
            "artifact_id": artifact_id,
            "version": version,
            "file_path": file_path,
            **(metadata or {})
        }
        
        try:
            result = await self.execute_query(query, parameters)
            logger.info(f"Created Maven artifact: {artifact_id_full}")
            return result[0]["id"] if result else artifact_id_full
            
        except Exception as e:
            logger.error(f"Failed to create Maven artifact {artifact_id_full}: {e}")
            raise
    
    async def create_dependency(
        self,
        from_artifact: str,
        to_group_id: str,
        to_artifact_id: str,
        to_version: str,
        scope: str = "compile",
        optional: bool = False,
        metadata: Dict[str, Any] = None
    ):
        """Create a dependency relationship between Maven artifacts."""
        to_artifact_full = f"{to_group_id}:{to_artifact_id}:{to_version}"
        
        query = """
        MATCH (from:MavenArtifact {id: $from_artifact})
        MERGE (to:MavenArtifact {
            id: $to_artifact_full,
            group_id: $to_group_id,
            artifact_id: $to_artifact_id,
            version: $to_version
        })
        MERGE (from)-[d:DEPENDS_ON]->(to)
        SET d.scope = $scope,
            d.optional = $optional,
            d.created_at = datetime()
        """
        
        # Add relationship metadata
        if metadata:
            for key, value in metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    query += f", d.{key} = ${key}"
        
        query += " RETURN d"
        
        parameters = {
            "from_artifact": from_artifact,
            "to_artifact_full": to_artifact_full,
            "to_group_id": to_group_id,
            "to_artifact_id": to_artifact_id,
            "to_version": to_version,
            "scope": scope,
            "optional": optional,
            **(metadata or {})
        }
        
        try:
            await self.execute_query(query, parameters)
            logger.debug(f"Created dependency: {from_artifact} -> {to_artifact_full}")
            
        except Exception as e:
            logger.error(f"Failed to create dependency {from_artifact} -> {to_artifact_full}: {e}")
            raise
    
    async def get_repository_stats(self, repo_name: str) -> Dict[str, Any]:
        """Get statistics for a repository."""
        query = """
        MATCH (r:Repository {name: $repo_name})
        OPTIONAL MATCH (r)-[:CONTAINS]->(f:File)
        OPTIONAL MATCH (r)-[:DEFINES_ARTIFACT]->(a:MavenArtifact)
        OPTIONAL MATCH (a)-[d:DEPENDS_ON]->()
        RETURN 
            r.name as repository,
            count(DISTINCT f) as total_files,
            count(DISTINCT a) as total_artifacts,
            count(DISTINCT d) as total_dependencies,
            collect(DISTINCT f.language) as languages
        """
        
        try:
            result = await self.execute_query(query, {"repo_name": repo_name})
            return result[0] if result else {}
            
        except Exception as e:
            logger.error(f"Failed to get repository stats for {repo_name}: {e}")
            raise
    
    async def get_maven_dependencies(
        self,
        artifact_id: str,
        max_depth: int = 3,
        include_transitive: bool = True
    ) -> List[Dict[str, Any]]:
        """Get Maven dependencies for an artifact."""
        if include_transitive:
            query = """
            MATCH path = (a:MavenArtifact {id: $artifact_id})-[:DEPENDS_ON*1..$max_depth]->(dep)
            RETURN 
                dep.id as dependency_id,
                dep.group_id as group_id,
                dep.artifact_id as artifact_id,
                dep.version as version,
                length(path) as depth,
                [rel in relationships(path) | rel.scope] as scopes
            ORDER BY depth, dep.group_id, dep.artifact_id
            """
        else:
            query = """
            MATCH (a:MavenArtifact {id: $artifact_id})-[d:DEPENDS_ON]->(dep)
            RETURN 
                dep.id as dependency_id,
                dep.group_id as group_id,
                dep.artifact_id as artifact_id,
                dep.version as version,
                1 as depth,
                d.scope as scope
            ORDER BY dep.group_id, dep.artifact_id
            """
        
        try:
            result = await self.execute_query(query, {
                "artifact_id": artifact_id,
                "max_depth": max_depth
            })
            return result
            
        except Exception as e:
            logger.error(f"Failed to get dependencies for {artifact_id}: {e}")
            raise
    
    async def find_dependency_conflicts(self, repo_name: str = None) -> List[Dict[str, Any]]:
        """Find conflicting Maven dependencies."""
        base_query = """
        MATCH (a1:MavenArtifact)-[:DEPENDS_ON]->(dep1:MavenArtifact),
              (a2:MavenArtifact)-[:DEPENDS_ON]->(dep2:MavenArtifact)
        WHERE dep1.group_id = dep2.group_id 
          AND dep1.artifact_id = dep2.artifact_id 
          AND dep1.version <> dep2.version
          AND a1.id <> a2.id
        """
        
        if repo_name:
            base_query += """
            AND EXISTS {
                MATCH (r:Repository {name: $repo_name})-[:DEFINES_ARTIFACT]->(a1)
            }
            AND EXISTS {
                MATCH (r:Repository {name: $repo_name})-[:DEFINES_ARTIFACT]->(a2)
            }
            """
        
        query = base_query + """
        RETURN 
            dep1.group_id as group_id,
            dep1.artifact_id as artifact_id,
            collect(DISTINCT dep1.version) + collect(DISTINCT dep2.version) as conflicting_versions,
            collect(DISTINCT a1.id) + collect(DISTINCT a2.id) as dependent_artifacts
        ORDER BY group_id, artifact_id
        """
        
        try:
            result = await self.execute_query(query, {"repo_name": repo_name} if repo_name else {})
            return result
            
        except Exception as e:
            logger.error(f"Failed to find dependency conflicts: {e}")
            raise
    
    async def delete_repository(self, repo_name: str) -> int:
        """Delete a repository and all its related nodes."""
        query = """
        MATCH (r:Repository {name: $repo_name})
        OPTIONAL MATCH (r)-[:CONTAINS]->(f:File)
        OPTIONAL MATCH (r)-[:DEFINES_ARTIFACT]->(a:MavenArtifact)
        DETACH DELETE r, f, a
        RETURN count(r) + count(f) + count(a) as deleted_count
        """
        
        try:
            result = await self.execute_query(query, {"repo_name": repo_name})
            deleted_count = result[0]["deleted_count"] if result else 0
            logger.info(f"Deleted repository {repo_name} and {deleted_count} related nodes")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to delete repository {repo_name}: {e}")
            raise
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get overall database statistics."""
        query = """
        MATCH (r:Repository)
        OPTIONAL MATCH (f:File)
        OPTIONAL MATCH (a:MavenArtifact)
        OPTIONAL MATCH ()-[d:DEPENDS_ON]->()
        RETURN 
            count(DISTINCT r) as total_repositories,
            count(DISTINCT f) as total_files,
            count(DISTINCT a) as total_artifacts,
            count(d) as total_dependencies
        """
        
        try:
            result = await self.execute_query(query)
            return result[0] if result else {}
            
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            raise
    
    # ENHANCED: Migration-specific methods
    
    async def create_business_rule(
        self,
        rule_id: str,
        rule_text: str,
        domain: str,
        complexity: str = "medium",
        rule_type: str = "validation",
        file_path: str = None,
        location: str = None,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Create a business rule node."""
        query = """
        MERGE (br:BusinessRule {id: $rule_id})
        SET br.rule_text = $rule_text,
            br.domain = $domain,
            br.complexity = $complexity,
            br.rule_type = $rule_type,
            br.created_at = datetime(),
            br.updated_at = datetime()
        """
        
        if file_path:
            query += ", br.file_path = $file_path"
        if location:
            query += ", br.location = $location"
            
        # Add metadata
        if metadata:
            for key, value in metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    query += f", br.{key} = ${key}"
        
        query += " RETURN br.id as id"
        
        parameters = {
            "rule_id": rule_id,
            "rule_text": rule_text,
            "domain": domain,
            "complexity": complexity,
            "rule_type": rule_type,
            "file_path": file_path,
            "location": location,
            **(metadata or {})
        }
        
        try:
            result = await self.execute_query(query, parameters)
            logger.info(f"Created business rule: {rule_id}")
            return result[0]["id"] if result else rule_id
        except Exception as e:
            logger.error(f"Failed to create business rule {rule_id}: {e}")
            raise
    
    async def create_struts_action(
        self,
        path: str,
        action_class: str,
        business_purpose: str,
        repo_name: str,
        file_path: str = None,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Create a Struts action node."""
        query = """
        MATCH (r:Repository {name: $repo_name})
        MERGE (sa:StrutsAction {path: $path})
        SET sa.action_class = $action_class,
            sa.business_purpose = $business_purpose,
            sa.created_at = datetime(),
            sa.updated_at = datetime()
        """
        
        if file_path:
            query += ", sa.file_path = $file_path"
            
        # Add metadata
        if metadata:
            for key, value in metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    query += f", sa.{key} = ${key}"
        
        query += """
        MERGE (r)-[:CONTAINS_STRUTS_ACTION]->(sa)
        RETURN sa.path as path
        """
        
        parameters = {
            "repo_name": repo_name,
            "path": path,
            "action_class": action_class,
            "business_purpose": business_purpose,
            "file_path": file_path,
            **(metadata or {})
        }
        
        try:
            result = await self.execute_query(query, parameters)
            logger.info(f"Created Struts action: {path}")
            return result[0]["path"] if result else path
        except Exception as e:
            logger.error(f"Failed to create Struts action {path}: {e}")
            raise
    
    async def create_corba_interface(
        self,
        interface_name: str,
        operations: List[str],
        repo_name: str,
        file_path: str = None,
        inheritance: str = None,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Create a CORBA interface node."""
        query = """
        MATCH (r:Repository {name: $repo_name})
        MERGE (ci:CORBAInterface {name: $interface_name})
        SET ci.operations = $operations,
            ci.created_at = datetime(),
            ci.updated_at = datetime()
        """
        
        if file_path:
            query += ", ci.file_path = $file_path"
        if inheritance:
            query += ", ci.inheritance = $inheritance"
            
        # Add metadata
        if metadata:
            for key, value in metadata.items():
                if isinstance(value, (str, int, float, bool, list)):
                    query += f", ci.{key} = ${key}"
        
        query += """
        MERGE (r)-[:CONTAINS_CORBA_INTERFACE]->(ci)
        RETURN ci.name as name
        """
        
        parameters = {
            "repo_name": repo_name,
            "interface_name": interface_name,
            "operations": operations,
            "file_path": file_path,
            "inheritance": inheritance,
            **(metadata or {})
        }
        
        try:
            result = await self.execute_query(query, parameters)
            logger.info(f"Created CORBA interface: {interface_name}")
            return result[0]["name"] if result else interface_name
        except Exception as e:
            logger.error(f"Failed to create CORBA interface {interface_name}: {e}")
            raise
    
    async def create_jsp_component(
        self,
        component_id: str,
        component_type: str,
        business_purpose: str,
        repo_name: str,
        file_path: str,
        struts_patterns: List[str] = None,
        migration_notes: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> str:
        """Create a JSP component node."""
        query = """
        MATCH (r:Repository {name: $repo_name})
        MERGE (jsp:JSPComponent {id: $component_id})
        SET jsp.component_type = $component_type,
            jsp.business_purpose = $business_purpose,
            jsp.file_path = $file_path,
            jsp.created_at = datetime(),
            jsp.updated_at = datetime()
        """
        
        if struts_patterns:
            query += ", jsp.struts_patterns = $struts_patterns"
        if migration_notes:
            query += ", jsp.migration_notes = $migration_notes"
            
        # Add metadata
        if metadata:
            for key, value in metadata.items():
                if isinstance(value, (str, int, float, bool, list)):
                    query += f", jsp.{key} = ${key}"
        
        query += """
        MERGE (r)-[:CONTAINS_JSP_COMPONENT]->(jsp)
        RETURN jsp.id as id
        """
        
        parameters = {
            "repo_name": repo_name,
            "component_id": component_id,
            "component_type": component_type,
            "business_purpose": business_purpose,
            "file_path": file_path,
            "struts_patterns": struts_patterns,
            "migration_notes": migration_notes,
            **(metadata or {})
        }
        
        try:
            result = await self.execute_query(query, parameters)
            logger.info(f"Created JSP component: {component_id}")
            return result[0]["id"] if result else component_id
        except Exception as e:
            logger.error(f"Failed to create JSP component {component_id}: {e}")
            raise
    
    async def create_business_relationship(
        self,
        source_id: str,
        source_type: str,
        target_id: str,
        target_type: str,
        relationship_type: str,
        metadata: Dict[str, Any] = None
    ):
        """Create relationships between business components."""
        query = f"""
        MATCH (source:{source_type} {{id: $source_id}})
        MATCH (target:{target_type} {{id: $target_id}})
        MERGE (source)-[r:{relationship_type}]->(target)
        SET r.created_at = datetime()
        """
        
        # Add relationship metadata
        if metadata:
            for key, value in metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    query += f", r.{key} = ${key}"
        
        query += " RETURN r"
        
        parameters = {
            "source_id": source_id,
            "target_id": target_id,
            **(metadata or {})
        }
        
        try:
            await self.execute_query(query, parameters)
            logger.debug(f"Created relationship: {source_type}:{source_id} -[{relationship_type}]-> {target_type}:{target_id}")
        except Exception as e:
            logger.error(f"Failed to create business relationship: {e}")
            raise
    
    async def get_migration_analysis(self, repo_name: str) -> Dict[str, Any]:
        """Get comprehensive migration analysis for a repository."""
        query = """
        MATCH (r:Repository {name: $repo_name})
        OPTIONAL MATCH (r)-[:CONTAINS_STRUTS_ACTION]->(sa:StrutsAction)
        OPTIONAL MATCH (r)-[:CONTAINS_CORBA_INTERFACE]->(ci:CORBAInterface)
        OPTIONAL MATCH (r)-[:CONTAINS_JSP_COMPONENT]->(jsp:JSPComponent)
        OPTIONAL MATCH (r)-[:CONTAINS]->(f:File)
        OPTIONAL MATCH (br:BusinessRule)
        WHERE br.file_path STARTS WITH r.path OR EXISTS {
            MATCH (f)-[:IMPLEMENTS_BUSINESS_RULE]->(br)
        }
        
        RETURN 
            r.name as repository,
            count(DISTINCT sa) as struts_actions,
            count(DISTINCT ci) as corba_interfaces,
            count(DISTINCT jsp) as jsp_components,
            count(DISTINCT br) as business_rules,
            collect(DISTINCT f.migration_complexity) as complexity_levels,
            collect(DISTINCT sa.business_purpose) as business_purposes,
            collect(DISTINCT ci.operations) as corba_operations
        """
        
        try:
            result = await self.execute_query(query, {"repo_name": repo_name})
            return result[0] if result else {}
        except Exception as e:
            logger.error(f"Failed to get migration analysis for {repo_name}: {e}")
            raise
    
    async def find_cross_repo_business_dependencies(self, repo_names: List[str] = None) -> List[Dict[str, Any]]:
        """Find business dependencies that cross repository boundaries."""
        base_query = """
        MATCH (repo1:Repository)-[:CONTAINS_STRUTS_ACTION]->(sa1:StrutsAction)
        MATCH (repo2:Repository)-[:CONTAINS_CORBA_INTERFACE]->(ci:CORBAInterface)
        WHERE repo1.name <> repo2.name
        AND EXISTS {
            MATCH (sa1)-[:CALLS_SERVICE]->(ci)
        }
        """
        
        if repo_names:
            base_query += """
            AND repo1.name IN $repo_names
            AND repo2.name IN $repo_names
            """
        
        query = base_query + """
        RETURN 
            repo1.name as source_repo,
            sa1.path as struts_action,
            sa1.business_purpose as business_purpose,
            repo2.name as target_repo,
            ci.name as corba_interface,
            ci.operations as service_operations
        ORDER BY source_repo, target_repo
        """
        
        try:
            result = await self.execute_query(query, {"repo_names": repo_names} if repo_names else {})
            return result
        except Exception as e:
            logger.error(f"Failed to find cross-repo business dependencies: {e}")
            raise