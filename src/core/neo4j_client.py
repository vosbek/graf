"""
Neo4j client for graph database operations and relationship management.
Handles complex graph queries, business logic relationships, and dependency analysis.
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from contextlib import asynccontextmanager

from neo4j import GraphDatabase, Driver, Session, Transaction
from neo4j.exceptions import ServiceUnavailable, TransientError

from ..processing.code_chunker import EnhancedChunk
from ..processing.maven_parser import MavenDependency, PomFile
from ..processing.dependency_resolver import ResolvedDependency, DependencyConflict
from .multi_repo_schema import (
    MultiRepoSchemaManager, RepositoryMetadata, BusinessOperationMetadata, 
    BusinessFlowMetadata, NodeType, RelationshipType, initialize_multi_repo_schema
)


@dataclass
class GraphNode:
    """Represents a node in the graph database."""
    id: str
    labels: List[str]
    properties: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'labels': self.labels,
            'properties': self.properties
        }


@dataclass
class GraphRelationship:
    """Represents a relationship in the graph database."""
    start_node: str
    end_node: str
    type: str
    properties: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'start_node': self.start_node,
            'end_node': self.end_node,
            'type': self.type,
            'properties': self.properties
        }


@dataclass
class GraphQuery:
    """Represents a Cypher query with parameters."""
    cypher: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    read_only: bool = True
    timeout: int = 30


@dataclass
class GraphQueryResult:
    """Result from a graph query."""
    records: List[Dict[str, Any]]
    summary: Dict[str, Any]
    query_time: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'records': self.records,
            'summary': self.summary,
            'query_time': self.query_time
        }


class Neo4jClient:
    """High-performance Neo4j client for graph operations."""
    
    def __init__(self,
                 uri: str = "bolt://localhost:7687",
                 username: str = "neo4j",
                 password: str = "password",
                 database: str = "neo4j"):
        
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        
        # Initialize logging
        self.logger = logging.getLogger(__name__)
        
        # Driver and connection
        self.driver: Optional[Driver] = None
        
        # Performance metrics
        self.query_count = 0
        self.total_query_time = 0.0
        self.connection_pool_size = 10
        
        # Query cache
        self.query_cache: Dict[str, Tuple[GraphQueryResult, float]] = {}
        self.cache_ttl = 300  # 5 minutes
        
        # Batch operations
        self.batch_size = 1000
        
        # Multi-repository schema manager
        self.schema_manager = None

        # Recovery/backoff state
        self._last_reconnect_ts: float = 0.0
        self._reconnect_backoff_sec: float = 1.0
        self._reconnect_backoff_max_sec: float = 8.0
        
    async def initialize(self):
        """Initialize Neo4j driver and connection."""
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password),
                max_connection_pool_size=self.connection_pool_size,
                connection_timeout=30,
                max_transaction_retry_time=15
            )
            
            # Verify connectivity
            await self._verify_connectivity()
            
            # Initialize multi-repository schema
            self.schema_manager = MultiRepoSchemaManager()
            await self._initialize_multi_repo_schema()
            
            self.logger.info("Neo4j client initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Neo4j client: {e}")
            raise
    
    async def _verify_connectivity(self):
        """Verify Neo4j connectivity."""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._sync_connectivity_check)
            if result != 1:
                raise Exception("Connectivity test failed")
        except Exception as e:
            raise Exception(f"Neo4j connectivity verification failed: {e}")
    
    def _sync_connectivity_check(self):
        """Synchronous connectivity check to run in thread pool."""
        if self.driver is None:
            raise RuntimeError("Neo4j driver is not initialized")
        with self.driver.session(database=self.database) as session:
            result = session.run("RETURN 1 as test")
            record = result.single()
            return record["test"]
    
    async def _initialize_multi_repo_schema(self):
        """Initialize multi-repository schema in Neo4j."""
        try:
            cypher_statements = self.schema_manager.generate_schema_cypher()
            
            for statement in cypher_statements:
                query = GraphQuery(cypher=statement, read_only=False)
                await self.execute_query(query)
                self.logger.debug(f"Executed schema statement: {statement[:100]}...")
            
            self.logger.info("Multi-repository schema initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize multi-repository schema: {e}")
            raise
    
    async def execute_query(self, query: GraphQuery) -> GraphQueryResult:
        """Execute a Cypher query with recovery on defunct/transient failures."""
        start_time = time.time()
        # Prepare cache early
        cache_key = None
        if query.read_only:
            cache_key = self._generate_cache_key(query)
            cached = self._get_cached_result(cache_key)
            if cached:
                return cached

        attempts = 0
        last_exc: Optional[Exception] = None

        while attempts < 2:
            try:
                loop = asyncio.get_event_loop()
                records, summary = await loop.run_in_executor(None, self._sync_execute_query, query)
                qtime = time.time() - start_time
                result = GraphQueryResult(records=records, summary=summary, query_time=qtime)
                if query.read_only and cache_key:
                    self._cache_result(cache_key, result)
                self.query_count += 1
                self.total_query_time += qtime
                return result
            except Exception as e:
                last_exc = e
                msg = str(e).lower()
                is_defunct = ("defunct connection" in msg) or isinstance(e, ServiceUnavailable) or isinstance(e, TransientError)
                self.logger.error(f"Neo4j execute_query failed (attempt {attempts+1}): {e}")
                if is_defunct and attempts == 0:
                    try:
                        await self._reconnect_driver()
                        attempts += 1
                        continue
                    except Exception as re:
                        self.logger.error(f"Neo4j reconnect failed: {re}")
                        break
                break

        raise last_exc if last_exc else RuntimeError("Neo4j execute_query failed without exception")
    
    def _sync_execute_query(self, query: GraphQuery):
        """Synchronous query execution to run in thread pool."""
        if self.driver is None:
            raise RuntimeError("Neo4j driver is not initialized")
        with self.driver.session(database=self.database) as session:
            if query.read_only:
                result = session.run(query.cypher, query.parameters)
                records = [dict(record) for record in result]
                result_summary = result.consume()
                summary = {
                    'query_type': result_summary.query_type,
                    'counters': result_summary.counters,
                    'notifications': [str(n) for n in (result_summary.notifications or [])]
                }
                return records, summary
            else:
                def write_work(tx: Transaction):
                    result = tx.run(query.cypher, query.parameters)
                    records = [dict(record) for record in result]
                    result_summary = result.consume()
                    summary = {
                        'query_type': result_summary.query_type,
                        'counters': result_summary.counters,
                        'notifications': [str(n) for n in (result_summary.notifications or [])]
                    }
                    return records, summary
                records, summary = session.write_transaction(write_work)
                return records, summary
    
    def _generate_cache_key(self, query: GraphQuery) -> str:
        """Generate cache key for query."""
        import hashlib
        content = f"{query.cypher}:{json.dumps(query.parameters, sort_keys=True)}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _get_cached_result(self, cache_key: str) -> Optional[GraphQueryResult]:
        """Get cached query result if valid."""
        if cache_key in self.query_cache:
            result, timestamp = self.query_cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                return result
            else:
                del self.query_cache[cache_key]
        return None
    
    def _cache_result(self, cache_key: str, result: GraphQueryResult):
        """Cache query result."""
        self.query_cache[cache_key] = (result, time.time())
        
        # Simple cache cleanup
        if len(self.query_cache) > 1000:
            oldest_key = min(self.query_cache.keys(), key=lambda k: self.query_cache[k][1])
            del self.query_cache[oldest_key]
    
    async def create_repository_node(self, repository_name: str, metadata: Dict[str, Any]) -> bool:
        """Create a repository node."""
        try:
            query = GraphQuery(
                cypher="""
                MERGE (r:Repository {name: $name})
                SET r += $metadata
                SET r.updated_at = datetime()
                RETURN r
                """,
                parameters={
                    'name': repository_name,
                    'metadata': metadata
                },
                read_only=False
            )
            
            await self.execute_query(query)
            self.logger.debug(f"Created repository node: {repository_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create repository node: {e}")
            return False
    
    async def create_code_chunks(self, chunks: List[EnhancedChunk], repository_name: str) -> bool:
        """Create code chunk nodes and relationships."""
        try:
            # Process chunks in batches
            for i in range(0, len(chunks), self.batch_size):
                batch = chunks[i:i + self.batch_size]
                await self._create_chunk_batch(batch, repository_name)
            
            self.logger.info(f"Created {len(chunks)} code chunks for repository {repository_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create code chunks: {e}")
            return False
    
    async def _create_chunk_batch(self, chunks: List[EnhancedChunk], repository_name: str):
        """Create a batch of code chunks."""
        chunk_data = []
        
        for chunk in chunks:
            chunk_data.append({
                'id': chunk.chunk.id,
                'content': chunk.chunk.content,
                'chunk_type': chunk.chunk.chunk_type,
                'language': chunk.chunk.language.value,
                'name': chunk.chunk.name,
                'start_line': chunk.chunk.start_line,
                'end_line': chunk.chunk.end_line,
                'complexity_score': chunk.chunk.complexity_score,
                'importance_score': chunk.importance_score,
                'business_domain': chunk.business_domain,
                'docstring': chunk.chunk.docstring,
                'annotations': json.dumps(chunk.chunk.annotations) if chunk.chunk.annotations else None,
                'imports': json.dumps(chunk.chunk.imports) if chunk.chunk.imports else None,
                'dependencies': json.dumps(chunk.chunk.dependencies) if chunk.chunk.dependencies else None,
                'repository': repository_name
            })
        
        query = GraphQuery(
            cypher="""
            UNWIND $chunks as chunk
            MERGE (repo:Repository {name: chunk.repository})
            MERGE (c:CodeChunk {id: chunk.id})
            SET c += chunk
            SET c.updated_at = datetime()
            MERGE (repo)-[:CONTAINS]->(c)
            
            // Create domain relationship if exists
            FOREACH (domain IN CASE WHEN chunk.business_domain IS NOT NULL THEN [chunk.business_domain] ELSE [] END |
                MERGE (d:Domain {name: domain})
                MERGE (c)-[:BELONGS_TO]->(d)
            )
            """,
            parameters={'chunks': chunk_data},
            read_only=False
        )
        
        await self.execute_query(query)
    
    async def create_maven_dependencies(self, pom: PomFile, resolved_deps: List[ResolvedDependency]) -> bool:
        """Create Maven dependency nodes and relationships."""
        try:
            # Create POM node
            await self._create_pom_node(pom)
            
            # Create dependency nodes
            for dep in resolved_deps:
                await self._create_dependency_node(dep, pom.coordinates.coordinates)
            
            self.logger.info(f"Created Maven dependencies for {pom.coordinates.coordinates}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create Maven dependencies: {e}")
            return False
    
    async def _create_pom_node(self, pom: PomFile):
        """Create POM file node."""
        query = GraphQuery(
            cypher="""
            MERGE (p:PomFile {file_path: $file_path})
            SET p.group_id = $group_id
            SET p.artifact_id = $artifact_id
            SET p.version = $version
            SET p.coordinates = $coordinates
            SET p.packaging = $packaging
            SET p.name = $name
            SET p.description = $description
            SET p.properties = $properties
            SET p.licenses = $licenses
            SET p.developers = $developers
            SET p.scm_url = $scm_url
            SET p.updated_at = datetime()
            
            MERGE (artifact:MavenArtifact {coordinates: $coordinates})
            SET artifact.group_id = $group_id
            SET artifact.artifact_id = $artifact_id
            SET artifact.version = $version
            SET artifact.packaging = $packaging
            SET artifact.name = $name
            SET artifact.description = $description
            SET artifact.updated_at = datetime()
            
            MERGE (p)-[:DEFINES_ARTIFACT]->(artifact)
            RETURN p, artifact
            """,
            parameters={
                'file_path': pom.file_path,
                'group_id': pom.coordinates.group_id,
                'artifact_id': pom.coordinates.artifact_id,
                'version': pom.coordinates.version,
                'coordinates': pom.coordinates.coordinates,
                'packaging': pom.packaging.value,
                'name': pom.name,
                'description': pom.description,
                'properties': json.dumps(pom.properties),
                'licenses': json.dumps(pom.licenses),
                'developers': json.dumps(pom.developers),
                'scm_url': pom.scm_url
            },
            read_only=False
        )
        
        await self.execute_query(query)
    
    async def _create_dependency_node(self, dep: ResolvedDependency, parent_coordinates: str):
        """Create dependency node and relationship."""
        query = GraphQuery(
            cypher="""
            MERGE (parent:MavenArtifact {coordinates: $parent_coordinates})
            MERGE (dep:MavenArtifact {coordinates: $dep_coordinates})
            SET dep.group_id = $group_id
            SET dep.artifact_id = $artifact_id
            SET dep.version = $selected_version
            SET dep.scope = $scope
            SET dep.is_optional = $is_optional
            SET dep.conflict_resolution = $conflict_resolution
            SET dep.updated_at = datetime()
            
            MERGE (parent)-[r:DEPENDS_ON]->(dep)
            SET r.scope = $scope
            SET r.is_optional = $is_optional
            SET r.conflict_resolution = $conflict_resolution
            SET r.excluded_versions = $excluded_versions
            SET r.dependency_paths = $dependency_paths
            SET r.updated_at = datetime()
            
            RETURN parent, dep, r
            """,
            parameters={
                'parent_coordinates': parent_coordinates,
                'dep_coordinates': dep.coordinates,
                'group_id': dep.dependency.coordinates.group_id,
                'artifact_id': dep.dependency.coordinates.artifact_id,
                'selected_version': dep.selected_version,
                'scope': dep.dependency.coordinates.scope.value,
                'is_optional': dep.dependency.is_optional,
                'conflict_resolution': dep.conflict_resolution.value if dep.conflict_resolution else None,
                'excluded_versions': json.dumps(dep.excluded_versions),
                'dependency_paths': json.dumps([str(path) for path in dep.dependency_paths])
            },
            read_only=False
        )
        
        await self.execute_query(query)
    
    async def create_dependency_conflicts(self, conflicts: List[DependencyConflict]) -> bool:
        """Create dependency conflict nodes."""
        try:
            conflict_data = []
            
            for conflict in conflicts:
                conflict_data.append({
                    'conflict_id': conflict.conflict_id,
                    'artifact_ga': conflict.artifact_ga,
                    'conflicting_versions': conflict.conflicting_versions,
                    'resolution_strategy': conflict.resolution_strategy.value,
                    'resolved_version': conflict.resolved_version,
                    'severity': conflict.severity.value,
                    'resolution_rationale': conflict.resolution_rationale,
                    'impact_analysis': json.dumps(conflict.impact_analysis)
                })
            
            query = GraphQuery(
                cypher="""
                UNWIND $conflicts as conflict
                MERGE (c:DependencyConflict {conflict_id: conflict.conflict_id})
                SET c += conflict
                SET c.updated_at = datetime()
                
                // Link to affected artifacts
                WITH c, conflict
                UNWIND conflict.conflicting_versions as version
                MATCH (artifact:MavenArtifact)
                WHERE artifact.group_id + ':' + artifact.artifact_id = conflict.artifact_ga
                  AND artifact.version = version
                MERGE (c)-[:AFFECTS]->(artifact)
                """,
                parameters={'conflicts': conflict_data},
                read_only=False
            )
            
            await self.execute_query(query)
            self.logger.info(f"Created {len(conflicts)} dependency conflicts")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create dependency conflicts: {e}")
            return False
    
    async def find_transitive_dependencies(self, artifact_coordinates: str, max_depth: int = 10) -> List[Dict[str, Any]]:
        """Find all transitive dependencies for an artifact."""
        query = GraphQuery(
            cypher="""
            MATCH (root:MavenArtifact {coordinates: $coordinates})
            CALL apoc.path.expandConfig(root, {
                relationshipFilter: "DEPENDS_ON>",
                labelFilter: "MavenArtifact",
                uniqueness: "NODE_GLOBAL",
                maxLevel: $max_depth,
                bfs: true
            }) YIELD path
            WITH path, length(path) as depth
            WHERE depth > 0
            RETURN 
                nodes(path)[-1].coordinates as coordinates,
                nodes(path)[-1].group_id as group_id,
                nodes(path)[-1].artifact_id as artifact_id,
                nodes(path)[-1].version as version,
                depth,
                [rel in relationships(path) | rel.scope] as scope_chain
            ORDER BY depth, coordinates
            """,
            parameters={
                'coordinates': artifact_coordinates,
                'max_depth': max_depth
            }
        )
        
        result = await self.execute_query(query)
        return result.records
    
    async def find_circular_dependencies(self) -> List[Dict[str, Any]]:
        """Find circular dependencies in the dependency graph."""
        query = GraphQuery(
            cypher="""
            MATCH (a:MavenArtifact)-[:DEPENDS_ON*]->(b:MavenArtifact)-[:DEPENDS_ON*]->(a)
            WHERE a.coordinates < b.coordinates  // Avoid duplicates
            RETURN a.coordinates as artifact1, b.coordinates as artifact2
            """,
            read_only=True
        )
        
        result = await self.execute_query(query)
        return result.records
    
    async def find_dependency_conflicts(self, repository_name: str = None) -> List[Dict[str, Any]]:
        """Find dependency conflicts, optionally filtered by repository."""
        cypher = """
        MATCH (conflict:DependencyConflict)
        """
        
        if repository_name:
            cypher += """
            MATCH (conflict)-[:AFFECTS]->(artifact:MavenArtifact)
            MATCH (artifact)<-[:DEFINES_ARTIFACT]-(pom:PomFile)
            MATCH (pom)<-[:HAS_POM]-(repo:Repository {name: $repository_name})
            """
        
        cypher += """
        RETURN conflict.conflict_id as conflict_id,
               conflict.artifact_ga as artifact_ga,
               conflict.conflicting_versions as conflicting_versions,
               conflict.resolution_strategy as resolution_strategy,
               conflict.resolved_version as resolved_version,
               conflict.severity as severity,
               conflict.resolution_rationale as resolution_rationale,
               conflict.impact_analysis as impact_analysis
        ORDER BY conflict.severity DESC, conflict.artifact_ga
        """
        
        query = GraphQuery(
            cypher=cypher,
            parameters={'repository_name': repository_name} if repository_name else {}
        )
        
        result = await self.execute_query(query)
        return result.records
    
    async def find_code_relationships(self, chunk_id: str) -> List[Dict[str, Any]]:
        """Find relationships for a code chunk."""
        query = GraphQuery(
            cypher="""
            MATCH (c:CodeChunk {id: $chunk_id})
            OPTIONAL MATCH (c)-[r1:CALLS]->(called:CodeChunk)
            OPTIONAL MATCH (caller:CodeChunk)-[r2:CALLS]->(c)
            OPTIONAL MATCH (c)-[r3:INHERITS]->(parent:CodeChunk)
            OPTIONAL MATCH (child:CodeChunk)-[r4:INHERITS]->(c)
            OPTIONAL MATCH (c)-[r5:BELONGS_TO]->(domain:Domain)
            OPTIONAL MATCH (c)-[r6:DEPENDS_ON]->(dep:CodeChunk)
            
            RETURN 
                c as chunk,
                collect(DISTINCT {type: 'calls', target: called.id, name: called.name}) as calls,
                collect(DISTINCT {type: 'called_by', source: caller.id, name: caller.name}) as called_by,
                collect(DISTINCT {type: 'inherits', target: parent.id, name: parent.name}) as inherits,
                collect(DISTINCT {type: 'inherited_by', source: child.id, name: child.name}) as inherited_by,
                collect(DISTINCT {type: 'domain', target: domain.name}) as domains,
                collect(DISTINCT {type: 'depends_on', target: dep.id, name: dep.name}) as dependencies
            """,
            parameters={'chunk_id': chunk_id}
        )
        
        result = await self.execute_query(query)
        return result.records
    
    async def find_business_domain_dependencies(self, domain_name: str) -> List[Dict[str, Any]]:
        """Find dependencies between business domains."""
        query = GraphQuery(
            cypher="""
            MATCH (domain:Domain {name: $domain_name})
            MATCH (domain)<-[:BELONGS_TO]-(chunk:CodeChunk)
            MATCH (chunk)-[:DEPENDS_ON]->(dep_chunk:CodeChunk)
            MATCH (dep_chunk)-[:BELONGS_TO]->(dep_domain:Domain)
            WHERE dep_domain.name <> domain.name
            
            RETURN dep_domain.name as dependent_domain,
                   count(*) as dependency_count,
                   collect(DISTINCT chunk.name) as source_chunks,
                   collect(DISTINCT dep_chunk.name) as target_chunks
            ORDER BY dependency_count DESC
            """,
            parameters={'domain_name': domain_name}
        )
        
        result = await self.execute_query(query)
        return result.records
    
    async def find_most_connected_artifacts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Find most connected Maven artifacts (hub analysis)."""
        query = GraphQuery(
            cypher="""
            MATCH (artifact:MavenArtifact)
            OPTIONAL MATCH (artifact)-[:DEPENDS_ON]->(dep:MavenArtifact)
            OPTIONAL MATCH (dependent:MavenArtifact)-[:DEPENDS_ON]->(artifact)
            
            WITH artifact,
                 count(DISTINCT dep) as dependencies_count,
                 count(DISTINCT dependent) as dependents_count
            
            RETURN artifact.coordinates as coordinates,
                   artifact.group_id as group_id,
                   artifact.artifact_id as artifact_id,
                   artifact.version as version,
                   dependencies_count,
                   dependents_count,
                   dependencies_count + dependents_count as total_connections
            ORDER BY total_connections DESC
            LIMIT $limit
            """,
            parameters={'limit': limit}
        )
        
        result = await self.execute_query(query)
        return result.records
    
    async def analyze_repository_health(self, repository_name: str) -> Dict[str, Any]:
        """Analyze the health of a repository's dependencies."""
        query = GraphQuery(
            cypher="""
            MATCH (repo:Repository {name: $repository_name})
            MATCH (repo)-[:CONTAINS]->(chunk:CodeChunk)
            OPTIONAL MATCH (chunk)-[:BELONGS_TO]->(domain:Domain)
            
            // Get Maven artifacts for this repository
            MATCH (repo)-[:HAS_POM]->(pom:PomFile)-[:DEFINES_ARTIFACT]->(artifact:MavenArtifact)
            OPTIONAL MATCH (artifact)-[:DEPENDS_ON]->(dep:MavenArtifact)
            
            // Get conflicts
            OPTIONAL MATCH (conflict:DependencyConflict)-[:AFFECTS]->(artifact)
            
            RETURN 
                count(DISTINCT chunk) as total_chunks,
                count(DISTINCT domain) as domains_count,
                count(DISTINCT dep) as dependencies_count,
                count(DISTINCT conflict) as conflicts_count,
                avg(chunk.complexity_score) as avg_complexity,
                avg(chunk.importance_score) as avg_importance
            """,
            parameters={'repository_name': repository_name}
        )
        
        result = await self.execute_query(query)
        if result.records:
            return result.records[0]
        return {}
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get Neo4j database statistics."""
        query = GraphQuery(
            cypher="""
            MATCH (n)
            RETURN
                labels(n) as labels,
                count(*) as count
            ORDER BY count DESC
            """,
            read_only=True
        )
        result = await self.execute_query(query)
        node_counts: Dict[str, int] = {}
        for record in result.records:
            labels = record['labels']
            count = record['count']
            for label in labels:
                node_counts[label] = node_counts.get(label, 0) + count
        rel_query = GraphQuery(
            cypher="""
            MATCH ()-[r]->()
            RETURN type(r) as relationship_type, count(*) as count
            ORDER BY count DESC
            """,
            read_only=True
        )
        rel_result = await self.execute_query(rel_query)
        relationship_counts = {
            record['relationship_type']: record['count'] for record in rel_result.records
        }
        return {
            'node_counts': node_counts,
            'relationship_counts': relationship_counts,
            'total_nodes': sum(node_counts.values()),
            'total_relationships': sum(relationship_counts.values()),
            'performance_metrics': {
                'total_queries': self.query_count,
                'average_query_time': self.total_query_time / max(self.query_count, 1),
                'cache_size': len(self.query_cache),
            },
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check with retry/reconnect on transient failures."""
        async def _probe() -> Dict[str, Any]:
            health = {'status': 'healthy', 'checks': {}}
            # Connectivity
            r = await self.execute_query(GraphQuery(cypher="RETURN 1 as test", read_only=True))
            if not (r.records and r.records[0].get('test') == 1):
                health['checks']['connectivity'] = {'status': 'fail'}
                health['status'] = 'unhealthy'
            else:
                health['checks']['connectivity'] = {'status': 'pass'}
            # Perf
            t0 = time.time()
            pr = await self.execute_query(GraphQuery(cypher="MATCH (n) RETURN count(n) as total_nodes LIMIT 1", read_only=True))
            qtime = time.time() - t0
            total_nodes = int(pr.records[0].get('total_nodes', 0)) if pr.records else 0
            health['checks']['query_performance'] = {
                'status': 'pass' if qtime < 1.0 else 'warn',
                'query_time': qtime,
                'total_nodes_sample': total_nodes
            }
            # Version info (best-effort)
            try:
                vr = await self.execute_query(GraphQuery(
                    cypher="CALL dbms.components() YIELD name, versions RETURN name, versions LIMIT 1",
                    read_only=True
                ))
                if vr.records:
                    rec = vr.records[0]
                    health['checks']['version'] = {
                        "name": rec.get("name"),
                        "version": (rec.get("versions") or [None])[0]
                    }
            except Exception as ver_e:
                health['checks']['version'] = {"error": str(ver_e)}
            return health

        try:
            h = await _probe()
            if h.get('status') == 'healthy':
                h['timestamp'] = time.time()
                return h
            # One reconnect + re-probe if unhealthy
            await self._reconnect_driver()
            h2 = await _probe()
            h2['timestamp'] = time.time()
            return h2
        except Exception as e:
            # As a last resort, try reconnect once more and re-probe
            msg = str(e).lower()
            if ("defunct connection" in msg) or isinstance(e, ServiceUnavailable) or isinstance(e, TransientError):
                try:
                    await self._reconnect_driver()
                    h3 = await _probe()
                    h3['timestamp'] = time.time()
                    return h3
                except Exception as e2:
                    self.logger.error(f"Neo4j health reconnection failed: {e2}")
            self.logger.error(f"Health check failed: {e}")
            return {'status': 'unhealthy', 'timestamp': time.time(), 'error': str(e), 'checks': {}}
    
    # =========================
    # Database-aware operations
    # =========================
    async def count_tables(self, repositories: List[str]) -> int:
        """
        Strict count of Table nodes associated to provided repositories.
        Requires repo→DB linkage via READS_FROM/WRITES_TO/CONTAINS edges.
        """
        if not repositories:
            raise ValueError("count_tables requires at least one repository")
        cypher = """
        UNWIND $repos as repoName
        MATCH (r:Repository {name: repoName})
        OPTIONAL MATCH (r)-[:READS_FROM|WRITES_TO]->(t:Table)
        WITH r, collect(DISTINCT t) as t1
        OPTIONAL MATCH (r)-[:CONTAINS]->(:Schema)-[:CONTAINS]->(t2:Table)
        WITH t1 + collect(DISTINCT t2) as allTables
        WITH [x IN allTables WHERE x IS NOT NULL] as tbls
        RETURN size(apoc.coll.toSet(tbls)) as total
        """
        query = GraphQuery(cypher=cypher, parameters={'repos': repositories})
        result = await self.execute_query(query)
        if not result.records:
            raise RuntimeError("count_tables failed to retrieve results")
        return int(result.records[0]['total'])
    
    async def count_views(self, repositories: List[str]) -> int:
        """Strict count of View nodes for the given repositories."""
        if not repositories:
            raise ValueError("count_views requires at least one repository")
        cypher = """
        UNWIND $repos as repoName
        MATCH (r:Repository {name: repoName})
        OPTIONAL MATCH (r)-[:READS_FROM]->(v:View)
        OPTIONAL MATCH (r)-[:CONTAINS]->(:Schema)-[:CONTAINS]->(v2:View)
        WITH collect(DISTINCT v) + collect(DISTINCT v2) as vs
        WITH [x IN vs WHERE x IS NOT NULL] as views
        RETURN size(apoc.coll.toSet(views)) as total
        """
        query = GraphQuery(cypher=cypher, parameters={'repos': repositories})
        result = await self.execute_query(query)
        if not result.records:
            raise RuntimeError("count_views failed to retrieve results")
        return int(result.records[0]['total'])
    
    async def count_procedures(self, repositories: List[str]) -> int:
        """Strict count of Procedure nodes for the given repositories."""
        if not repositories:
            raise ValueError("count_procedures requires at least one repository")
        cypher = """
        UNWIND $repos as repoName
        MATCH (r:Repository {name: repoName})
        OPTIONAL MATCH (r)-[:CALLS_DB_PROC]->(p:Procedure)
        OPTIONAL MATCH (r)-[:CONTAINS]->(:Schema)-[:CONTAINS]->(p2:Procedure)
        WITH collect(DISTINCT p) + collect(DISTINCT p2) as ps
        WITH [x IN ps WHERE x IS NOT NULL] as procs
        RETURN size(apoc.coll.toSet(procs)) as total
        """
        query = GraphQuery(cypher=cypher, parameters={'repos': repositories})
        result = await self.execute_query(query)
        if not result.records:
            raise RuntimeError("count_procedures failed to retrieve results")
        return int(result.records[0]['total'])
    
    async def count_triggers(self, repositories: List[str]) -> int:
        """Strict count of Trigger nodes attached to tables for the given repositories."""
        if not repositories:
            raise ValueError("count_triggers requires at least one repository")
        cypher = """
        UNWIND $repos as repoName
        MATCH (r:Repository {name: repoName})
        OPTIONAL MATCH (r)-[:CONTAINS]->(:Schema)-[:CONTAINS]->(:Table)<-[:ATTACHED_TO]-(t:Trigger)
        WITH collect(DISTINCT t) as ts
        WITH [x IN ts WHERE x IS NOT NULL] as triggers
        RETURN size(apoc.coll.toSet(triggers)) as total
        """
        query = GraphQuery(cypher=cypher, parameters={'repos': repositories})
        result = await self.execute_query(query)
        if not result.records:
            raise RuntimeError("count_triggers failed to retrieve results")
        return int(result.records[0]['total'])
    
    async def find_shared_db_artifacts(self, repositories: List[str]) -> List[Dict[str, Any]]:
        """
        Find DB artifacts (tables/views) used by more than one repository in the set.
        """
        if not repositories:
            raise ValueError("find_shared_db_artifacts requires at least one repository")
        cypher = """
        UNWIND $repos as repoName
        MATCH (r:Repository {name: repoName})
        OPTIONAL MATCH (r)-[:READS_FROM|WRITES_TO]->(obj:Table)
        WITH obj, collect(DISTINCT r.name) as reposUsed
        WHERE size(reposUsed) > 1 AND obj IS NOT NULL
        RETURN obj.name as artifact, reposUsed as repos, 'Table' as type
        UNION
        UNWIND $repos as repoName
        MATCH (r:Repository {name: repoName})
        OPTIONAL MATCH (r)-[:READS_FROM]->(obj:View)
        WITH obj, collect(DISTINCT r.name) as reposUsed
        WHERE size(reposUsed) > 1 AND obj IS NOT NULL
        RETURN obj.name as artifact, reposUsed as repos, 'View' as type
        ORDER BY artifact
        """
        query = GraphQuery(cypher=cypher, parameters={'repos': repositories})
        result = await self.execute_query(query)
        return result.records
     
    async def upsert_db_objects(self, payload: Dict[str, Any]) -> None:
         """
         Upsert Database/Schema/Table/View/Column/Procedure/Function/Package/Trigger and relationships.
         Strict mode: any failure raises; no partial silent success.
         Expected payload keys: database, schemas, tables, views, procedures, functions, packages, triggers, fks
         """
         start = time.time()
         try:
             # Upsert Database
             db = payload.get('database')
             if not db or 'name' not in db:
                 raise ValueError("payload.database with name is required")
             q_db = GraphQuery(
                 cypher="""
                 MERGE (d:Database {name: $name})
                 SET d += apoc.map.clean($props, [], [NULL])
                 """,
                 parameters={'name': db['name'], 'props': {k: v for k, v in db.items() if k != 'name'}},
                 read_only=False
             )
             await self.execute_query(q_db)
             
             # Upsert Schemas
             schemas = payload.get('schemas', [])
             if schemas:
                 q_schema = GraphQuery(
                     cypher="""
                     UNWIND $schemas as s
                     MATCH (d:Database {name: $db})
                     MERGE (sc:Schema {name: s.name})
                     SET sc.owner = s.owner
                     MERGE (d)-[:CONTAINS]->(sc)
                     """,
                     parameters={'db': db['name'], 'schemas': schemas},
                     read_only=False
                 )
                 await self.execute_query(q_schema)
             
             # Upsert Tables and Columns
             tables = payload.get('tables', [])
             if tables:
                 q_tables = GraphQuery(
                     cypher="""
                     UNWIND $tables as t
                     MATCH (sc:Schema {name: t.schema})
                     MERGE (tb:Table {name: t.name})
                     SET tb.pk = t.pk, tb.row_count = t.row_count, tb.last_analyzed = t.last_analyzed
                     MERGE (sc)-[:CONTAINS]->(tb)
                     
                     WITH t, tb
                     UNWIND coalesce(t.columns, []) as col
                     MERGE (c:Column {name: col.name})
                     SET c.data_type = col.data_type,
                         c.nullable = col.nullable,
                         c.default = col.default,
                         c.sensitive = col.sensitive,
                         c.comment = col.comment
                     MERGE (tb)-[:CONTAINS]->(c)
                     """,
                     parameters={'tables': tables},
                     read_only=False
                 )
                 await self.execute_query(q_tables)
             
             # Upsert Views
             views = payload.get('views', [])
             if views:
                 q_views = GraphQuery(
                     cypher="""
                     UNWIND $views as v
                     MATCH (sc:Schema {name: v.schema})
                     MERGE (vw:View {name: v.name})
                     SET vw.definition_hash = v.definition_hash
                     MERGE (sc)-[:CONTAINS]->(vw)
                     WITH v, vw
                     UNWIND coalesce(v.derives_from, []) as base
                     MATCH (t:Table {name: base}) OR (t:View {name: base})
                     MERGE (vw)-[:DERIVES_FROM]->(t)
                     """,
                     parameters={'views': views},
                     read_only=False
                 )
                 await self.execute_query(q_views)
             
             # Upsert Procedures / Functions / Packages
             procs = payload.get('procedures', [])
             if procs:
                 q_procs = GraphQuery(
                     cypher="""
                     UNWIND $procedures as p
                     MATCH (sc:Schema {name: p.schema})
                     MERGE (pr:Procedure {name: p.name})
                     SET pr.language = p.language,
                         pr.deterministic = p.deterministic,
                         pr.authz_enforced = p.authz_enforced
                     MERGE (sc)-[:CONTAINS]->(pr)
                     """,
                     parameters={'procedures': procs},
                     read_only=False
                 )
                 await self.execute_query(q_procs)
             
             funcs = payload.get('functions', [])
             if funcs:
                 q_funcs = GraphQuery(
                     cypher="""
                     UNWIND $functions as f
                     MATCH (sc:Schema {name: f.schema})
                     MERGE (fn:Function {name: f.name})
                     SET fn.language = f.language,
                         fn.deterministic = f.deterministic
                     MERGE (sc)-[:CONTAINS]->(fn)
                     """,
                     parameters={'functions': funcs},
                     read_only=False
                 )
                 await self.execute_query(q_funcs)
             
             packages = payload.get('packages', [])
             if packages:
                 q_pkgs = GraphQuery(
                     cypher="""
                     UNWIND $packages as p
                     MATCH (sc:Schema {name: p.schema})
                     MERGE (pkg:Package {name: p.name})
                     MERGE (sc)-[:CONTAINS]->(pkg)
                     """,
                     parameters={'packages': packages},
                     read_only=False
                 )
                 await self.execute_query(q_pkgs)
             
             # Upsert Triggers
             triggers = payload.get('triggers', [])
             if triggers:
                 q_trg = GraphQuery(
                     cypher="""
                     UNWIND $triggers as t
                     MATCH (sc:Schema {name: t.schema})-[:CONTAINS]->(tb:Table {name: t.table})
                     MERGE (tr:Trigger {name: t.name})
                     SET tr.event = t.event, tr.timing = t.timing, tr.enabled = coalesce(t.enabled, true)
                     MERGE (tr)-[:ATTACHED_TO]->(tb)
                     """,
                     parameters={'triggers': triggers},
                     read_only=False
                 )
                 await self.execute_query(q_trg)
             
             # Foreign Keys
             fks = payload.get('fks', [])
             if fks:
                 q_fk = GraphQuery(
                     cypher="""
                     UNWIND $fks as fk
                     MATCH (src:Table {name: fk.source})
                     MATCH (tgt:Table {name: fk.target})
                     MERGE (src)-[:FK_REF]->(tgt)
                     """,
                     parameters={'fks': fks},
                     read_only=False
                 )
                 await self.execute_query(q_fk)
             
             self.logger.info("DB objects upsert completed", extra={'elapsed_ms': int((time.time() - start) * 1000)})
         
         except Exception as e:
             self.logger.error(f"DB objects upsert failed: {e}")
             raise

    # Multi-repository operations

    async def create_enhanced_repository_node(self, metadata: RepositoryMetadata) -> bool:
        """Create repository node with enhanced multi-repo metadata."""
        try:
            cypher = self.schema_manager.create_repository_node_cypher(metadata)
            query = GraphQuery(
                cypher=cypher,
                parameters={
                    'name': metadata.name,
                    'url': metadata.url,
                    'language': metadata.language,
                    'framework': metadata.framework,
                    'business_domains': metadata.business_domains,
                    'size_loc': metadata.size_loc,
                    'complexity_score': metadata.complexity_score,
                    'last_modified': metadata.last_modified,
                    'team_owner': metadata.team_owner,
                    'deployment_environment': metadata.deployment_environment,
                    'depends_on_repos': metadata.depends_on_repos,
                    'provides_services': metadata.provides_services,
                    'consumes_services': metadata.consumes_services,
                    'shared_artifacts': metadata.shared_artifacts
                },
                read_only=False
            )
            
            await self.execute_query(query)
            self.logger.info(f"Created enhanced repository node: {metadata.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create enhanced repository node: {e}")
            return False
     
    async def create_business_operation_node(self, metadata: BusinessOperationMetadata) -> bool:
        """Create business operation node."""
        try:
            cypher = self.schema_manager.create_business_operation_cypher(metadata)
            query = GraphQuery(
                cypher=cypher,
                parameters={
                    'name': metadata.name,
                    'business_domain': metadata.business_domain,
                    'operation_type': metadata.operation_type,
                    'customer_facing': metadata.customer_facing,
                    'financial_impact': metadata.financial_impact,
                    'data_sensitivity': metadata.data_sensitivity,
                    'implementing_repositories': metadata.implementing_repositories,
                    'coordinating_operations': metadata.coordinating_operations,
                    'migration_complexity': metadata.migration_complexity,
                    'migration_priority': metadata.migration_priority
                },
                read_only=False
            )
            
            await self.execute_query(query)
            self.logger.info(f"Created business operation node: {metadata.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create business operation node: {e}")
            return False
    
    async def create_business_flow_node(self, metadata: BusinessFlowMetadata) -> bool:
        """Create business flow node spanning repositories."""
        try:
            cypher = self.schema_manager.create_business_flow_cypher(metadata)
            query = GraphQuery(
                cypher=cypher,
                parameters={
                    'name': metadata.name,
                    'description': metadata.description,
                    'flow_type': metadata.flow_type,
                    'repositories_involved': metadata.repositories_involved,
                    'business_value': metadata.business_value,
                    'user_impact': metadata.user_impact,
                    'compliance_requirements': metadata.compliance_requirements,
                    'migration_order': metadata.migration_order,
                    'estimated_effort_weeks': metadata.estimated_effort_weeks,
                    'risk_level': metadata.risk_level,
                    'dependencies': metadata.dependencies
                },
                read_only=False
            )
            
            await self.execute_query(query)
            self.logger.info(f"Created business flow node: {metadata.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create business flow node: {e}")
            return False
    
    async def create_cross_repository_relationship(self, 
                                                 source_repo: str, 
                                                 target_repo: str,
                                                 relationship_type: RelationshipType,
                                                 properties: Dict[str, Any]) -> bool:
        """Create cross-repository relationship."""
        try:
            cypher = self.schema_manager.create_cross_repo_relationship_cypher(
                source_repo, target_repo, relationship_type, properties
            )
            
            params = {
                'source_repo': source_repo,
                'target_repo': target_repo,
                **properties
            }
            
            query = GraphQuery(cypher=cypher, parameters=params, read_only=False)
            await self.execute_query(query)
            self.logger.info(f"Created cross-repo relationship: {source_repo} -> {target_repo}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create cross-repo relationship: {e}")
            return False
    
    async def find_business_flows_for_repositories(self, repository_names: List[str]) -> List[Dict[str, Any]]:
        """Find business flows that involve the specified repositories."""
        queries = self.schema_manager.get_cross_repo_analysis_queries()
        query = GraphQuery(
            cypher=queries['find_business_flows_for_repos'],
            parameters={'repository_names': repository_names}
        )
        
        result = await self.execute_query(query)
        return result.records
    
    async def find_cross_repository_dependencies(self, repository_names: List[str]) -> List[Dict[str, Any]]:
        """Find dependencies between repositories."""
        queries = self.schema_manager.get_cross_repo_analysis_queries()
        query = GraphQuery(
            cypher=queries['find_cross_repo_dependencies'],
            parameters={'repository_names': repository_names}
        )
        
        result = await self.execute_query(query)
        return result.records
    
    async def find_shared_business_operations(self, repository_names: List[str]) -> List[Dict[str, Any]]:
        """Find business operations implemented across multiple repositories."""
        queries = self.schema_manager.get_cross_repo_analysis_queries()
        query = GraphQuery(
            cypher=queries['find_shared_business_operations'],
            parameters={'repository_names': repository_names}
        )
        
        result = await self.execute_query(query)
        return result.records
    
    async def analyze_migration_impact(self, repository_names: List[str]) -> List[Dict[str, Any]]:
        """Analyze migration impact across repositories."""
        queries = self.schema_manager.get_cross_repo_analysis_queries()
        query = GraphQuery(
            cypher=queries['analyze_migration_impact'],
            parameters={'repository_names': repository_names}
        )
        
        result = await self.execute_query(query)
        return result.records
    
    async def find_integration_points(self, repository_names: List[str]) -> List[Dict[str, Any]]:
        """Find integration points for repositories."""
        queries = self.schema_manager.get_cross_repo_analysis_queries()
        query = GraphQuery(
            cypher=queries['find_integration_points'],
            parameters={'repository_names': repository_names}
        )
        
        result = await self.execute_query(query)
        return result.records

    async def close(self):
        """Close Neo4j driver and cleanup resources."""
        try:
            if self.driver:
                await self.driver.close()
            
            # Clear caches
            self.query_cache.clear()
            
            self.logger.info("Neo4j client closed successfully")
            
        except Exception as e:
            self.logger.error(f"Error closing Neo4j client: {e}")
    
    @asynccontextmanager
    async def transaction(self):
        """Context manager for Neo4j transactions with recovery."""
        if self.driver is None:
            raise RuntimeError("Neo4j driver is not initialized")
        session = self.driver.session(database=self.database)
        tx = await session.begin_transaction()
        try:
            yield tx
            await tx.commit()
        except Exception as e:
            await tx.rollback()
            msg = str(e).lower()
            if ("defunct connection" in msg) or isinstance(e, ServiceUnavailable) or isinstance(e, TransientError):
                try:
                    await self._reconnect_driver()
                except Exception:
                    pass
            raise
        finally:
            await session.close()