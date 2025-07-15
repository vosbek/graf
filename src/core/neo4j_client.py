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
            
            self.logger.info("Neo4j client initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Neo4j client: {e}")
            raise
    
    async def _verify_connectivity(self):
        """Verify Neo4j connectivity."""
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("RETURN 1 as test")
                record = result.single()
                if record["test"] != 1:
                    raise Exception("Connectivity test failed")
                    
        except Exception as e:
            raise Exception(f"Neo4j connectivity verification failed: {e}")
    
    async def execute_query(self, query: GraphQuery) -> GraphQueryResult:
        """Execute a Cypher query."""
        start_time = time.time()
        
        try:
            # Check cache for read-only queries
            if query.read_only:
                cache_key = self._generate_cache_key(query)
                cached_result = self._get_cached_result(cache_key)
                if cached_result:
                    return cached_result
            
            # Execute query
            with self.driver.session(database=self.database) as session:
                if query.read_only:
                    result = session.run(query.cypher, query.parameters)
                else:
                    result = session.write_transaction(
                        lambda tx: tx.run(query.cypher, query.parameters)
                    )
                
                # Process results
                records = []
                for record in result:
                    records.append(dict(record))
                
                summary = {
                    'query_type': result.summary().query_type,
                    'counters': dict(result.summary().counters),
                    'notifications': [str(n) for n in result.summary().notifications]
                }
                
                query_time = time.time() - start_time
                
                query_result = GraphQueryResult(
                    records=records,
                    summary=summary,
                    query_time=query_time
                )
                
                # Cache read-only results
                if query.read_only:
                    self._cache_result(cache_key, query_result)
                
                # Update metrics
                self.query_count += 1
                self.total_query_time += query_time
                
                return query_result
                
        except Exception as e:
            self.logger.error(f"Query execution failed: {e}")
            raise
    
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
        
        # Process node counts
        node_counts = {}
        for record in result.records:
            labels = record['labels']
            count = record['count']
            for label in labels:
                node_counts[label] = node_counts.get(label, 0) + count
        
        # Get relationship counts
        rel_query = GraphQuery(
            cypher="""
            MATCH ()-[r]->()
            RETURN type(r) as relationship_type, count(*) as count
            ORDER BY count DESC
            """,
            read_only=True
        )
        
        rel_result = await self.execute_query(rel_query)
        relationship_counts = {record['relationship_type']: record['count'] for record in rel_result.records}
        
        return {
            'node_counts': node_counts,
            'relationship_counts': relationship_counts,
            'total_nodes': sum(node_counts.values()),
            'total_relationships': sum(relationship_counts.values()),
            'performance_metrics': {
                'total_queries': self.query_count,
                'average_query_time': self.total_query_time / max(self.query_count, 1),
                'cache_size': len(self.query_cache)
            }
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on Neo4j database."""
        health = {
            'status': 'healthy',
            'timestamp': time.time(),
            'checks': {}
        }
        
        try:
            # Check basic connectivity
            query = GraphQuery(cypher="RETURN 1 as test", read_only=True)
            result = await self.execute_query(query)
            
            if result.records and result.records[0]['test'] == 1:
                health['checks']['connectivity'] = {'status': 'pass'}
            else:
                health['checks']['connectivity'] = {'status': 'fail'}
                health['status'] = 'unhealthy'
            
            # Check query performance
            start_time = time.time()
            perf_query = GraphQuery(
                cypher="MATCH (n) RETURN count(n) as total_nodes LIMIT 1",
                read_only=True
            )
            await self.execute_query(perf_query)
            query_time = time.time() - start_time
            
            health['checks']['query_performance'] = {
                'status': 'pass' if query_time < 1.0 else 'warn',
                'query_time': query_time
            }
            
        except Exception as e:
            health['status'] = 'unhealthy'
            health['error'] = str(e)
            self.logger.error(f"Health check failed: {e}")
        
        return health
    
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
        """Context manager for Neo4j transactions."""
        session = self.driver.session(database=self.database)
        tx = await session.begin_transaction()
        
        try:
            yield tx
            await tx.commit()
        except Exception as e:
            await tx.rollback()
            raise
        finally:
            await session.close()


# Utility functions for common graph operations

async def find_shortest_path(client: Neo4jClient, 
                           start_node: str, 
                           end_node: str,
                           relationship_type: str = None) -> List[Dict[str, Any]]:
    """Find shortest path between two nodes."""
    cypher = """
    MATCH (start {id: $start_id}), (end {id: $end_id})
    MATCH path = shortestPath((start)-[*]->(end))
    """
    
    if relationship_type:
        cypher = cypher.replace("[*]", f"[:{relationship_type}*]")
    
    cypher += """
    RETURN path,
           length(path) as path_length,
           [node in nodes(path) | node.id] as node_ids,
           [rel in relationships(path) | type(rel)] as relationship_types
    """
    
    query = GraphQuery(
        cypher=cypher,
        parameters={'start_id': start_node, 'end_id': end_node}
    )
    
    result = await client.execute_query(query)
    return result.records


async def find_influential_nodes(client: Neo4jClient, 
                               node_label: str,
                               relationship_type: str,
                               limit: int = 10) -> List[Dict[str, Any]]:
    """Find most influential nodes using PageRank algorithm."""
    query = GraphQuery(
        cypher="""
        CALL gds.pageRank.stream({
            nodeProjection: $node_label,
            relationshipProjection: $relationship_type,
            maxIterations: 20,
            dampingFactor: 0.85
        })
        YIELD nodeId, score
        RETURN gds.util.asNode(nodeId).id as node_id,
               gds.util.asNode(nodeId).name as name,
               score
        ORDER BY score DESC
        LIMIT $limit
        """,
        parameters={
            'node_label': node_label,
            'relationship_type': relationship_type,
            'limit': limit
        }
    )
    
    result = await client.execute_query(query)
    return result.records


async def detect_communities(client: Neo4jClient,
                           node_label: str,
                           relationship_type: str) -> List[Dict[str, Any]]:
    """Detect communities in the graph using Louvain algorithm."""
    query = GraphQuery(
        cypher="""
        CALL gds.louvain.stream({
            nodeProjection: $node_label,
            relationshipProjection: $relationship_type,
            maxIterations: 10,
            tolerance: 0.0001
        })
        YIELD nodeId, communityId
        RETURN communityId,
               collect(gds.util.asNode(nodeId).id) as community_members,
               count(*) as community_size
        ORDER BY community_size DESC
        """,
        parameters={
            'node_label': node_label,
            'relationship_type': relationship_type
        }
    )
    
    result = await client.execute_query(query)
    return result.records