"""
Query API routes for semantic search and graph queries.
"""

import time
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query as QueryParam
from pydantic import BaseModel, Field

# Heavy imports removed - will use dynamic imports when needed
from ...core.neo4j_client import Neo4jClient, GraphQuery
from ...core.multi_repo_schema import RepositoryMetadata, BusinessOperationMetadata, BusinessFlowMetadata, RelationshipType
from ...dependencies import get_chroma_client, get_neo4j_client


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


class MultiRepoAnalysisRequest(BaseModel):
    """Request model for multi-repository analysis."""
    repository_names: List[str] = Field(..., description="List of repository names to analyze")
    analysis_type: str = Field(..., description="Type of cross-repository analysis")
    include_business_flows: bool = Field(default=True, description="Include business flow analysis")
    include_dependencies: bool = Field(default=True, description="Include dependency analysis")
    include_migration_impact: bool = Field(default=False, description="Include migration impact analysis")
    
    class Config:
        schema_extra = {
            "example": {
                "repository_names": ["user-service", "payment-service", "order-service"],
                "analysis_type": "business_flows",
                "include_business_flows": True,
                "include_dependencies": True,
                "include_migration_impact": False
            }
        }


class RepositorySelectionRequest(BaseModel):
    """Request model for repository selection and scoping."""
    selected_repositories: List[str] = Field(..., description="Selected repository names")
    business_domains: Optional[List[str]] = Field(None, description="Filter by business domains")
    exclude_repositories: Optional[List[str]] = Field(None, description="Repositories to exclude")
    max_repositories: int = Field(default=100, ge=1, le=100, description="Maximum repositories to include")
    
    class Config:
        schema_extra = {
            "example": {
                "selected_repositories": ["user-service", "payment-service"],
                "business_domains": ["authentication", "payment"],
                "exclude_repositories": ["legacy-service"],
                "max_repositories": 50
            }
        }


class SemanticSearchResponse(BaseModel):
    """Response model for semantic search."""
    results: List[Dict[str, Any]]  # SearchResult objects as dicts
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
    chroma_client: object = Depends(get_chroma_client)  # ChromaDBClient
):
    """
    Perform semantic search across codebase.
    
    This endpoint performs vector similarity search to find code chunks
    semantically similar to the query text.
    """
    start_time = time.time()
    
    try:
        # Dynamically import SearchQuery to avoid blocking startup
        import importlib
        chromadb_module = importlib.import_module('.core.chromadb_client', package='src')
        SearchQuery = chromadb_module.SearchQuery
        
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
        
        # Convert results to dicts for response
        results_dicts = [result.to_dict() if hasattr(result, 'to_dict') else dict(result) for result in results]
        
        # Build response
        response = SemanticSearchResponse(
            results=results_dicts,
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
    chroma_client: object = Depends(get_chroma_client)  # ChromaDBClient
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

    Always return a JSON body (diagnostics on failure) to aid troubleshooting.
    """
    try:
        # Build graph query
        graph_query = GraphQuery(
            cypher=request.cypher,
            parameters=request.parameters or {},
            read_only=request.read_only,
            timeout=request.timeout
        )
        # Execute query
        result = await neo4j_client.execute_query(graph_query)
        records = getattr(result, "records", []) or []
        return {
            "records": records,
            "summary": getattr(result, "summary", {"query_type": "r", "counters": {}, "notifications": []}),
            "query_time": float(getattr(result, "query_time", 0.0)),
            "record_count": len(records)
        }
    except HTTPException:
        # Preserve explicit HTTPExceptions as-is
        raise
    except Exception as e:
        import traceback
        return {
            "records": [],
            "summary": {"query_type": "r", "counters": {}, "notifications": []},
            "query_time": 0.0,
            "record_count": 0,
            "diagnostics": {
                "status": "query_failed",
                "message": f"Graph query failed: {str(e)}",
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc()
            }
        }


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
    chroma_client: object = Depends(get_chroma_client),  # ChromaDBClient
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
    chroma_client: object = Depends(get_chroma_client),  # ChromaDBClient
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


# Multi-repository analysis endpoints

@router.post("/multi-repo/analyze")
async def analyze_multiple_repositories(
    request: MultiRepoAnalysisRequest,
    neo4j_client: Neo4jClient = Depends(get_neo4j_client)
):
    """
    Perform cross-repository analysis.
    
    Analyzes business flows, dependencies, and relationships across multiple repositories.
    """
    try:
        analysis_results = {}
        
        if request.include_business_flows:
            business_flows = await neo4j_client.find_business_flows_for_repositories(
                request.repository_names
            )
            analysis_results['business_flows'] = business_flows
        
        if request.include_dependencies:
            dependencies = await neo4j_client.find_cross_repository_dependencies(
                request.repository_names
            )
            analysis_results['cross_repo_dependencies'] = dependencies
            
            shared_operations = await neo4j_client.find_shared_business_operations(
                request.repository_names
            )
            analysis_results['shared_business_operations'] = shared_operations
        
        if request.include_migration_impact:
            migration_impact = await neo4j_client.analyze_migration_impact(
                request.repository_names
            )
            analysis_results['migration_impact'] = migration_impact
        
        # Get integration points
        integration_points = await neo4j_client.find_integration_points(
            request.repository_names
        )
        analysis_results['integration_points'] = integration_points
        
        return {
            "repository_names": request.repository_names,
            "analysis_type": request.analysis_type,
            "analysis_results": analysis_results,
            "repository_count": len(request.repository_names),
            "summary": _generate_multi_repo_summary(analysis_results)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Multi-repository analysis failed: {str(e)}")


@router.get("/multi-repo/repositories")
async def get_available_repositories(
    business_domain: Optional[str] = QueryParam(None),
    framework: Optional[str] = QueryParam(None),
    team_owner: Optional[str] = QueryParam(None),
    neo4j_client: Neo4jClient = Depends(get_neo4j_client)
):
    """
    Get list of available repositories with filtering options.
    
    Supports filtering by business domain, framework, and team ownership.
    """
    try:
        cypher = """
        MATCH (r:Repository)
        """
        
        conditions = []
        parameters = {}
        
        if business_domain:
            conditions.append("$business_domain IN r.business_domains")
            parameters['business_domain'] = business_domain
        
        if framework:
            conditions.append("r.framework = $framework")
            parameters['framework'] = framework
        
        if team_owner:
            conditions.append("r.team_owner = $team_owner")
            parameters['team_owner'] = team_owner
        
        if conditions:
            cypher += " WHERE " + " AND ".join(conditions)
        
        cypher += """
        RETURN r.name as name,
               r.business_domains as business_domains,
               r.framework as framework,
               r.team_owner as team_owner,
               r.size_loc as size_loc,
               r.complexity_score as complexity_score,
               r.provides_services as provides_services,
               r.consumes_services as consumes_services
        ORDER BY r.name
        """
        
        query = GraphQuery(cypher=cypher, parameters=parameters)
        result = await neo4j_client.execute_query(query)
        
        return {
            "repositories": result.records,
            "total_count": len(result.records),
            "filters_applied": {
                "business_domain": business_domain,
                "framework": framework,
                "team_owner": team_owner
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get repositories: {str(e)}")


@router.post("/multi-repo/business-flows")
async def get_business_flows_for_repositories(
    request: RepositorySelectionRequest,
    neo4j_client: Neo4jClient = Depends(get_neo4j_client)
):
    """
    Get business flows that span the selected repositories.
    
    Returns business flows with migration planning information.
    """
    try:
        # Apply repository filtering
        selected_repos = _apply_repository_filters(
            request.selected_repositories,
            request.business_domains,
            request.exclude_repositories,
            request.max_repositories
        )
        
        business_flows = await neo4j_client.find_business_flows_for_repositories(selected_repos)
        
        return {
            "selected_repositories": selected_repos,
            "business_flows": business_flows,
            "total_flows": len(business_flows),
            "high_value_flows": len([f for f in business_flows if f.get('business_value') == 'high']),
            "migration_recommendations": _generate_migration_recommendations(business_flows)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get business flows: {str(e)}")


@router.post("/multi-repo/dependencies/cross-repo")
async def get_cross_repository_dependencies(
    request: RepositorySelectionRequest,
    neo4j_client: Neo4jClient = Depends(get_neo4j_client)
):
    """
    Get dependencies between selected repositories.
    
    Analyzes cross-repository dependency relationships and strength.
    """
    try:
        selected_repos = _apply_repository_filters(
            request.selected_repositories,
            request.business_domains,
            request.exclude_repositories,
            request.max_repositories
        )
        
        dependencies = await neo4j_client.find_cross_repository_dependencies(selected_repos)
        
        # Analyze dependency strength and criticality
        critical_deps = [d for d in dependencies if d.get('criticality') == 'critical']
        high_deps = [d for d in dependencies if d.get('criticality') == 'high']
        
        return {
            "selected_repositories": selected_repos,
            "cross_repo_dependencies": dependencies,
            "total_dependencies": len(dependencies),
            "critical_dependencies": len(critical_deps),
            "high_dependencies": len(high_deps),
            "dependency_graph": _build_dependency_graph(dependencies),
            "recommendations": _generate_dependency_recommendations(dependencies)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cross-repository dependencies: {str(e)}")


@router.post("/multi-repo/migration-impact")
async def analyze_cross_repository_migration_impact(
    request: RepositorySelectionRequest,
    neo4j_client: Neo4jClient = Depends(get_neo4j_client),
    chroma_client: object = Depends(get_chroma_client),
):
    """
    Analyze migration impact across selected repositories.

    STANDARDIZED: Returns the canonical multi-repo migration plan schema
    (plan_scope, summary, cross_repo, slices, graphql, roadmap, diagnostics).
    """
    try:
        selected_repos = _apply_repository_filters(
            request.selected_repositories,
            request.business_domains,
            request.exclude_repositories,
            request.max_repositories
        )

        # Delegate to centralized planner service to avoid drift with GET /api/v1/migration-plan
        from ...services.migration_planner import MultiRepoPlanner  # single source of truth

        planner = MultiRepoPlanner(neo4j_client=neo4j_client, chroma_client=chroma_client)
        plan = await planner.plan_multi_repo(selected_repos)

        # Return canonical schema directly
        return plan

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Failed to analyze migration impact: {str(e)}")


@router.get("/multi-repo/integration-points")
async def get_integration_points_for_repositories(
    repository_names: List[str] = QueryParam(...),
    neo4j_client: Neo4jClient = Depends(get_neo4j_client)
):
    """
    Get integration points for specified repositories.
    
    Identifies external system integrations and data sensitivity.
    """
    try:
        integration_points = await neo4j_client.find_integration_points(repository_names)
        
        # Group by data sensitivity
        high_sensitivity = [i for i in integration_points if i.get('data_sensitivity') == 'high']
        medium_sensitivity = [i for i in integration_points if i.get('data_sensitivity') == 'medium']
        
        return {
            "repository_names": repository_names,
            "integration_points": integration_points,
            "total_integrations": len(integration_points),
            "high_sensitivity_count": len(high_sensitivity),
            "medium_sensitivity_count": len(medium_sensitivity),
            "integration_summary": _summarize_integrations(integration_points)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get integration points: {str(e)}")


# Helper functions for multi-repository analysis

def _apply_repository_filters(selected_repos: List[str], 
                            business_domains: Optional[List[str]],
                            exclude_repos: Optional[List[str]],
                            max_repos: int) -> List[str]:
    """Apply filtering logic to repository selection."""
    filtered_repos = selected_repos.copy()
    
    if exclude_repos:
        filtered_repos = [r for r in filtered_repos if r not in exclude_repos]
    
    # Apply max limit
    if len(filtered_repos) > max_repos:
        filtered_repos = filtered_repos[:max_repos]
    
    return filtered_repos


def _generate_multi_repo_summary(analysis_results: Dict[str, Any]) -> Dict[str, Any]:
    """Generate summary of multi-repository analysis."""
    summary = {
        "total_business_flows": len(analysis_results.get('business_flows', [])),
        "total_dependencies": len(analysis_results.get('cross_repo_dependencies', [])),
        "total_integrations": len(analysis_results.get('integration_points', [])),
        "shared_operations": len(analysis_results.get('shared_business_operations', []))
    }
    
    if 'migration_impact' in analysis_results:
        summary['migration_affected_flows'] = len(analysis_results['migration_impact'])
    
    return summary


def _generate_migration_recommendations(business_flows: List[Dict[str, Any]]) -> List[str]:
    """Generate migration recommendations based on business flows."""
    recommendations = []
    
    high_value_flows = [f for f in business_flows if f.get('business_value') == 'high']
    if high_value_flows:
        recommendations.append(f"Prioritize {len(high_value_flows)} high-value business flows for migration")
    
    low_risk_flows = [f for f in business_flows if f.get('risk_level') == 'low']
    if low_risk_flows:
        recommendations.append(f"Consider starting with {len(low_risk_flows)} low-risk flows")
    
    return recommendations


def _generate_dependency_recommendations(dependencies: List[Dict[str, Any]]) -> List[str]:
    """Generate recommendations for cross-repository dependencies."""
    recommendations = []
    
    critical_deps = [d for d in dependencies if d.get('criticality') == 'critical']
    if critical_deps:
        recommendations.append(f"Address {len(critical_deps)} critical dependencies before migration")
    
    return recommendations


def _build_dependency_graph(dependencies: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build dependency graph structure."""
    nodes = set()
    edges = []
    
    for dep in dependencies:
        source = dep.get('source_name')
        target = dep.get('target_name')
        if source and target:
            nodes.add(source)
            nodes.add(target)
            edges.append({
                'source': source,
                'target': target,
                'strength': dep.get('strength', 'medium'),
                'criticality': dep.get('criticality', 'medium')
            })
    
    return {
        'nodes': list(nodes),
        'edges': edges,
        'node_count': len(nodes),
        'edge_count': len(edges)
    }


def _generate_migration_sequence(migration_impact: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generate recommended migration sequence."""
    # Sort by migration order and risk level
    sorted_flows = sorted(
        migration_impact,
        key=lambda x: (x.get('migration_order', 999), x.get('risk_level') == 'low')
    )
    
    return [
        {
            'name': flow.get('name'),
            'order': flow.get('migration_order'),
            'effort_weeks': flow.get('estimated_effort_weeks'),
            'risk_level': flow.get('risk_level')
        }
        for flow in sorted_flows
    ]


def _assess_migration_risks(migration_impact: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Assess overall migration risks."""
    high_risk = len([f for f in migration_impact if f.get('risk_level') == 'high'])
    medium_risk = len([f for f in migration_impact if f.get('risk_level') == 'medium'])
    low_risk = len([f for f in migration_impact if f.get('risk_level') == 'low'])
    
    total_flows = len(migration_impact)
    overall_risk = "low"
    
    if total_flows > 0:
        if high_risk / total_flows > 0.3:
            overall_risk = "high"
        elif (high_risk + medium_risk) / total_flows > 0.5:
            overall_risk = "medium"
    
    return {
        "overall_risk": overall_risk,
        "high_risk_flows": high_risk,
        "medium_risk_flows": medium_risk,
        "low_risk_flows": low_risk,
        "risk_distribution": {
            "high": high_risk,
            "medium": medium_risk,
            "low": low_risk
        }
    }


def _summarize_integrations(integration_points: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Summarize integration points by type and sensitivity."""
    integration_types = {}
    sensitivity_levels = {}
    
    for integration in integration_points:
        int_type = integration.get('integration_type', 'unknown')
        sensitivity = integration.get('data_sensitivity', 'unknown')
        
        integration_types[int_type] = integration_types.get(int_type, 0) + 1
        sensitivity_levels[sensitivity] = sensitivity_levels.get(sensitivity, 0) + 1
    
    return {
        "integration_types": integration_types,
        "sensitivity_levels": sensitivity_levels,
        "most_common_type": max(integration_types, key=integration_types.get) if integration_types else None,
        "highest_sensitivity_count": sensitivity_levels.get('high', 0)
    }