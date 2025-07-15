"""
Query API routes for semantic search and graph queries.
"""

import time
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query as QueryParam
from pydantic import BaseModel, Field

from ...core.chromadb_client import ChromaDBClient, SearchQuery, SearchResult
from ...core.neo4j_client import Neo4jClient, GraphQuery
from ...main import get_chroma_client, get_neo4j_client


router = APIRouter()


# Request/Response models
class SemanticSearchRequest(BaseModel):
    """Request model for semantic search."""
    query: str = Field(..., description="Search query text")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum number of results")
    min_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum similarity score")
    repository_filter: Optional[str] = Field(None, description="Filter by repository name")
    language_filter: Optional[str] = Field(None, description="Filter by programming language")
    domain_filter: Optional[str] = Field(None, description="Filter by business domain")
    chunk_type_filter: Optional[str] = Field(None, description="Filter by chunk type")
    include_metadata: bool = Field(default=True, description="Include metadata in results")
    
    class Config:
        schema_extra = {
            "example": {
                "query": "authentication login function",
                "limit": 10,
                "min_score": 0.5,
                "repository_filter": "user-service",
                "language_filter": "python",
                "domain_filter": "authentication"
            }
        }


class GraphQueryRequest(BaseModel):
    """Request model for graph queries."""
    cypher: str = Field(..., description="Cypher query")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Query parameters")
    read_only: bool = Field(default=True, description="Whether query is read-only")
    timeout: int = Field(default=30, ge=1, le=300, description="Query timeout in seconds")
    
    class Config:
        schema_extra = {
            "example": {
                "cypher": "MATCH (r:Repository)-[:CONTAINS]->(c:CodeChunk) WHERE r.name = $repo_name RETURN c.name, c.chunk_type LIMIT 10",
                "parameters": {"repo_name": "user-service"},
                "read_only": True,
                "timeout": 30
            }
        }


class DependencyAnalysisRequest(BaseModel):
    """Request model for dependency analysis."""
    artifact_coordinates: str = Field(..., description="Maven artifact coordinates")
    max_depth: int = Field(default=10, ge=1, le=50, description="Maximum traversal depth")
    include_conflicts: bool = Field(default=True, description="Include dependency conflicts")
    include_vulnerabilities: bool = Field(default=True, description="Include vulnerability information")
    
    class Config:
        schema_extra = {
            "example": {
                "artifact_coordinates": "com.example:user-service:1.0.0",
                "max_depth": 10,
                "include_conflicts": True,
                "include_vulnerabilities": True
            }
        }


class SemanticSearchResponse(BaseModel):
    """Response model for semantic search."""
    results: List[SearchResult]
    total_results: int
    query_time: float
    metadata: Dict[str, Any]
    
    class Config:
        schema_extra = {
            "example": {
                "results": [
                    {
                        "chunk_id": "repo1:abc123",
                        "content": "def authenticate_user(username, password):",
                        "score": 0.85,
                        "metadata": {"language": "python", "chunk_type": "function"},
                        "language": "python",
                        "chunk_type": "function",
                        "name": "authenticate_user",
                        "business_domain": "authentication"
                    }
                ],
                "total_results": 1,
                "query_time": 0.123,
                "metadata": {"cache_hit": False}
            }
        }


@router.post("/semantic", response_model=SemanticSearchResponse)
async def semantic_search(
    request: SemanticSearchRequest,
    chroma_client: ChromaDBClient = Depends(get_chroma_client)
):
    """
    Perform semantic search across codebase.
    
    This endpoint performs vector similarity search to find code chunks
    semantically similar to the query text.
    """
    start_time = time.time()
    
    try:
        # Build search query
        search_query = SearchQuery(
            query=request.query,
            limit=request.limit,
            min_score=request.min_score,
            repository_filter=request.repository_filter,
            language_filter=request.language_filter,
            domain_filter=request.domain_filter,
            chunk_type_filter=request.chunk_type_filter,
            include_metadata=request.include_metadata
        )
        
        # Execute search
        results = await chroma_client.search(search_query)
        
        # Calculate query time
        query_time = time.time() - start_time
        
        # Build response
        response = SemanticSearchResponse(
            results=results,
            total_results=len(results),
            query_time=query_time,
            metadata={
                "cache_hit": False,  # Would be determined by ChromaDB client
                "query_processed": True
            }
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/similar/{chunk_id}")
async def find_similar_chunks(
    chunk_id: str,
    limit: int = QueryParam(default=10, ge=1, le=50),
    min_score: float = QueryParam(default=0.5, ge=0.0, le=1.0),
    chroma_client: ChromaDBClient = Depends(get_chroma_client)
):
    """
    Find chunks similar to a specific chunk.
    
    This endpoint finds code chunks that are semantically similar to a given chunk.
    """
    try:
        # Get the source chunk content
        source_chunk = await chroma_client.collection.get(ids=[chunk_id])
        
        if not source_chunk['documents']:
            raise HTTPException(status_code=404, detail="Chunk not found")
        
        # Use the chunk content as query
        query_content = source_chunk['documents'][0]
        
        # Search for similar chunks
        search_query = SearchQuery(
            query=query_content,
            limit=limit + 1,  # +1 to exclude the source chunk
            min_score=min_score
        )
        
        results = await chroma_client.search(search_query)
        
        # Filter out the source chunk
        filtered_results = [r for r in results if r.chunk_id != chunk_id][:limit]
        
        return {
            "source_chunk_id": chunk_id,
            "similar_chunks": filtered_results,
            "total_results": len(filtered_results)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to find similar chunks: {str(e)}")


@router.post("/graph")
async def graph_query(
    request: GraphQueryRequest,
    neo4j_client: Neo4jClient = Depends(get_neo4j_client)
):
    """
    Execute a Cypher query against the graph database.
    
    This endpoint allows direct querying of the Neo4j graph database
    for complex relationship analysis.
    """
    try:
        # Build graph query
        graph_query = GraphQuery(
            cypher=request.cypher,
            parameters=request.parameters,
            read_only=request.read_only,
            timeout=request.timeout
        )
        
        # Execute query
        result = await neo4j_client.execute_query(graph_query)
        
        return {
            "records": result.records,
            "summary": result.summary,
            "query_time": result.query_time,
            "record_count": len(result.records)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph query failed: {str(e)}")


@router.get("/dependencies/transitive/{artifact_coordinates}")
async def get_transitive_dependencies(
    artifact_coordinates: str,
    max_depth: int = QueryParam(default=10, ge=1, le=50),
    neo4j_client: Neo4jClient = Depends(get_neo4j_client)
):
    """
    Get transitive dependencies for a Maven artifact.
    
    This endpoint returns all transitive dependencies for a given Maven artifact,
    including dependency paths and depth information.
    """
    try:
        dependencies = await neo4j_client.find_transitive_dependencies(
            artifact_coordinates=artifact_coordinates,
            max_depth=max_depth
        )
        
        return {
            "artifact_coordinates": artifact_coordinates,
            "transitive_dependencies": dependencies,
            "total_dependencies": len(dependencies),
            "max_depth_reached": max(dep.get('depth', 0) for dep in dependencies) if dependencies else 0
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get transitive dependencies: {str(e)}")


@router.get("/dependencies/conflicts")
async def get_dependency_conflicts(
    repository_name: Optional[str] = QueryParam(None),
    neo4j_client: Neo4jClient = Depends(get_neo4j_client)
):
    """
    Get dependency conflicts across repositories.
    
    This endpoint returns information about dependency version conflicts,
    optionally filtered by repository.
    """
    try:
        conflicts = await neo4j_client.find_dependency_conflicts(repository_name)
        
        return {
            "repository_name": repository_name,
            "conflicts": conflicts,
            "total_conflicts": len(conflicts),
            "critical_conflicts": len([c for c in conflicts if c.get('severity') == 'critical'])
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get dependency conflicts: {str(e)}")


@router.get("/dependencies/circular")
async def get_circular_dependencies(
    neo4j_client: Neo4jClient = Depends(get_neo4j_client)
):
    """
    Get circular dependencies in the system.
    
    This endpoint identifies circular dependencies in the Maven dependency graph.
    """
    try:
        circular_deps = await neo4j_client.find_circular_dependencies()
        
        return {
            "circular_dependencies": circular_deps,
            "total_cycles": len(circular_deps)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get circular dependencies: {str(e)}")


@router.get("/code/relationships/{chunk_id}")
async def get_code_relationships(
    chunk_id: str,
    neo4j_client: Neo4jClient = Depends(get_neo4j_client)
):
    """
    Get relationships for a code chunk.
    
    This endpoint returns all relationships (calls, inheritance, dependencies)
    for a specific code chunk.
    """
    try:
        relationships = await neo4j_client.find_code_relationships(chunk_id)
        
        if not relationships:
            raise HTTPException(status_code=404, detail="Code chunk not found")
        
        return {
            "chunk_id": chunk_id,
            "relationships": relationships[0] if relationships else {},
            "total_relationships": sum(len(rel) for rel in relationships[0].values()) if relationships else 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get code relationships: {str(e)}")


@router.get("/domains/{domain_name}/dependencies")
async def get_domain_dependencies(
    domain_name: str,
    neo4j_client: Neo4jClient = Depends(get_neo4j_client)
):
    """
    Get dependencies between business domains.
    
    This endpoint returns how a specific business domain depends on other domains.
    """
    try:
        dependencies = await neo4j_client.find_business_domain_dependencies(domain_name)
        
        return {
            "domain_name": domain_name,
            "dependencies": dependencies,
            "total_dependencies": len(dependencies),
            "dependency_count": sum(dep.get('dependency_count', 0) for dep in dependencies)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get domain dependencies: {str(e)}")


@router.get("/artifacts/most-connected")
async def get_most_connected_artifacts(
    limit: int = QueryParam(default=10, ge=1, le=50),
    neo4j_client: Neo4jClient = Depends(get_neo4j_client)
):
    """
    Get most connected Maven artifacts (hub analysis).
    
    This endpoint identifies the most connected artifacts in the dependency graph,
    which are often critical components.
    """
    try:
        artifacts = await neo4j_client.find_most_connected_artifacts(limit)
        
        return {
            "most_connected_artifacts": artifacts,
            "total_artifacts": len(artifacts)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get most connected artifacts: {str(e)}")


@router.get("/repositories/{repository_name}/health")
async def get_repository_health(
    repository_name: str,
    neo4j_client: Neo4jClient = Depends(get_neo4j_client)
):
    """
    Get health analysis for a repository.
    
    This endpoint provides a comprehensive health analysis of a repository,
    including dependency health, code quality, and complexity metrics.
    """
    try:
        health = await neo4j_client.analyze_repository_health(repository_name)
        
        if not health:
            raise HTTPException(status_code=404, detail="Repository not found")
        
        # Calculate health score
        health_score = 100.0
        
        # Deduct points for conflicts
        conflicts = health.get('conflicts_count', 0)
        if conflicts > 0:
            health_score -= min(conflicts * 5, 30)
        
        # Deduct points for complexity
        avg_complexity = health.get('avg_complexity', 0)
        if avg_complexity > 5:
            health_score -= min((avg_complexity - 5) * 5, 20)
        
        # Determine grade
        if health_score >= 90:
            grade = "A"
        elif health_score >= 80:
            grade = "B"
        elif health_score >= 70:
            grade = "C"
        elif health_score >= 60:
            grade = "D"
        else:
            grade = "F"
        
        return {
            "repository_name": repository_name,
            "health_metrics": health,
            "health_score": max(health_score, 0),
            "grade": grade,
            "recommendations": _generate_health_recommendations(health)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get repository health: {str(e)}")


def _generate_health_recommendations(health: Dict[str, Any]) -> List[str]:
    """Generate health recommendations based on metrics."""
    recommendations = []
    
    conflicts = health.get('conflicts_count', 0)
    if conflicts > 5:
        recommendations.append("Resolve dependency conflicts to improve stability")
    
    avg_complexity = health.get('avg_complexity', 0)
    if avg_complexity > 5:
        recommendations.append("Refactor complex code to improve maintainability")
    
    dependencies = health.get('dependencies_count', 0)
    if dependencies > 50:
        recommendations.append("Consider reducing number of dependencies")
    
    if not recommendations:
        recommendations.append("Repository health looks good!")
    
    return recommendations


@router.get("/search/hybrid")
async def hybrid_search(
    query: str = QueryParam(..., description="Search query"),
    semantic_weight: float = QueryParam(default=0.7, ge=0.0, le=1.0),
    keyword_weight: float = QueryParam(default=0.3, ge=0.0, le=1.0),
    limit: int = QueryParam(default=10, ge=1, le=50),
    chroma_client: ChromaDBClient = Depends(get_chroma_client),
    neo4j_client: Neo4jClient = Depends(get_neo4j_client)
):
    """
    Perform hybrid search combining semantic and graph-based results.
    
    This endpoint combines semantic search results with graph-based relationship
    analysis to provide more comprehensive search results.
    """
    try:
        # Semantic search
        semantic_query = SearchQuery(
            query=query,
            limit=limit * 2  # Get more results for merging
        )
        semantic_results = await chroma_client.search(semantic_query)
        
        # Graph-based search for related chunks
        graph_query = GraphQuery(
            cypher="""
            CALL db.index.fulltext.queryNodes('code_search', $query)
            YIELD node, score
            RETURN node.id as chunk_id, node.name as name, node.content as content, score
            LIMIT $limit
            """,
            parameters={"query": query, "limit": limit},
            read_only=True
        )
        graph_result = await neo4j_client.execute_query(graph_query)
        
        # Merge and rank results
        combined_results = []
        
        # Add semantic results with weighted scores
        for result in semantic_results:
            combined_results.append({
                "chunk_id": result.chunk_id,
                "content": result.content,
                "score": result.score * semantic_weight,
                "source": "semantic",
                "metadata": result.metadata
            })
        
        # Add graph results with weighted scores
        for record in graph_result.records:
            combined_results.append({
                "chunk_id": record.get('chunk_id'),
                "content": record.get('content', ''),
                "score": record.get('score', 0) * keyword_weight,
                "source": "graph",
                "metadata": {}
            })
        
        # Sort by combined score and remove duplicates
        seen_ids = set()
        unique_results = []
        for result in sorted(combined_results, key=lambda x: x['score'], reverse=True):
            if result['chunk_id'] not in seen_ids:
                seen_ids.add(result['chunk_id'])
                unique_results.append(result)
        
        return {
            "query": query,
            "results": unique_results[:limit],
            "total_results": len(unique_results),
            "semantic_weight": semantic_weight,
            "keyword_weight": keyword_weight
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hybrid search failed: {str(e)}")


@router.get("/statistics")
async def get_query_statistics(
    chroma_client: ChromaDBClient = Depends(get_chroma_client),
    neo4j_client: Neo4jClient = Depends(get_neo4j_client)
):
    """
    Get query and database statistics.
    
    This endpoint provides statistics about the database contents and query performance.
    """
    try:
        chroma_stats = await chroma_client.get_statistics()
        neo4j_stats = await neo4j_client.get_statistics()
        
        return {
            "chromadb_statistics": chroma_stats,
            "neo4j_statistics": neo4j_stats,
            "timestamp": time.time()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")