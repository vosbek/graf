"""
MVP FastAPI application for Codebase RAG system.
Simplified version for local development and testing.
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import boto3

from indexer import CodebaseIndexer
from search import CodebaseSearch
from neo4j_client import Neo4jClient
from struts_parser import StrutsParser
from agents import AgentService

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration from environment variables
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "codebase-rag-2024")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
MAVEN_ENABLED = os.getenv("MAVEN_ENABLED", "true").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
REPOS_PATH = os.getenv("REPOS_PATH", "./data/repositories")
APP_ENV = os.getenv("APP_ENV", "development")
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8080"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
MAX_CONCURRENT_REPOS = int(os.getenv("MAX_CONCURRENT_REPOS", "10"))
AI_AGENT_ENABLED = os.getenv("AI_AGENT_ENABLED", "true").lower() == "true"
AWS_REQUIRED = os.getenv("AWS_REQUIRED", "false").lower() == "true"

# Initialize FastAPI app
app = FastAPI(
    title="Codebase RAG MVP",
    description="Minimal viable product for codebase search and analysis",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (React frontend)
frontend_build_path = Path(__file__).parent.parent / "frontend" / "build"
if frontend_build_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_build_path / "static")), name="static")
    app.mount("/", StaticFiles(directory=str(frontend_build_path), html=True), name="frontend")

# Global components
indexer: Optional[CodebaseIndexer] = None
search: Optional[CodebaseSearch] = None
neo4j_client: Optional[Neo4jClient] = None
struts_parser: Optional[StrutsParser] = None


async def _validate_aws_credentials(agent_instance) -> Dict[str, Any]:
    """
    Validate AWS credentials and agent initialization status.
    
    Returns:
        Dict with agent_mode, credentials_valid, and reason
    """
    import boto3
    from botocore.exceptions import NoCredentialsError, ClientError
    
    status = {
        "agent_mode": "failed",
        "credentials_valid": False,
        "reason": "Unknown"
    }
    
    try:
        # Check if agent has AWS Strands available
        if not agent_instance:
            status["reason"] = "Agent instance not created"
            return status
            
        if not agent_instance.agent:
            # Agent is in fallback mode - check why
            
            # First check if AWS credentials exist
            try:
                # Try multiple credential sources
                session = boto3.Session()
                credentials = session.get_credentials()
                
                if not credentials:
                    status["agent_mode"] = "fallback"
                    status["reason"] = "No AWS credentials found (check .env file or aws configure)"
                    return status
                
                # Test if credentials are valid
                sts = boto3.client('sts')
                identity = sts.get_caller_identity()
                
                status["credentials_valid"] = True
                
                # Check if Bedrock is accessible (needed for Strands)
                try:
                    bedrock = boto3.client('bedrock', region_name='us-east-1')
                    bedrock.list_foundation_models()
                    
                    # Credentials are valid and Bedrock accessible, but agent still failed
                    status["agent_mode"] = "fallback" 
                    status["reason"] = "AWS credentials valid but Strands library not available (pip install strands-agents)"
                    
                except Exception as bedrock_error:
                    status["agent_mode"] = "fallback"
                    if "AccessDenied" in str(bedrock_error):
                        status["reason"] = "AWS credentials valid but missing Bedrock permissions"
                    else:
                        status["reason"] = f"Bedrock service unavailable: {str(bedrock_error)[:100]}"
                
            except NoCredentialsError:
                status["agent_mode"] = "fallback"
                status["reason"] = "No AWS credentials configured"
                
            except ClientError as e:
                status["agent_mode"] = "fallback"
                if e.response['Error']['Code'] == 'AccessDenied':
                    status["reason"] = "AWS credentials invalid or expired"
                else:
                    status["reason"] = f"AWS credential error: {e.response['Error']['Code']}"
                    
            except Exception as e:
                status["agent_mode"] = "fallback"
                status["reason"] = f"AWS credential validation failed: {str(e)[:100]}"
                
        else:
            # Agent initialized successfully with AWS
            status["agent_mode"] = "aws"
            status["credentials_valid"] = True
            status["reason"] = "AWS Strands agent initialized successfully"
            
    except Exception as e:
        status["reason"] = f"Validation error: {str(e)[:100]}"
        
    return status


# Request/Response models
class IndexRequest(BaseModel):
    repo_path: str
    repo_name: Optional[str] = None


class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    similarity_threshold: float = 0.7


class SearchResult(BaseModel):
    file_path: str
    content: str
    score: float
    metadata: Dict[str, Any]


class AgentRequest(BaseModel):
    question: str
    repository: Optional[str] = None


class AgentResponse(BaseModel):
    answer: str
    question: str
    repository: Optional[str] = None


@app.on_event("startup")
async def startup_event():
    """Initialize components on startup."""
    global indexer, search, neo4j_client, struts_parser
    
    logger.info("Starting Codebase RAG MVP with Neo4j and Maven support...")
    
    try:
        # Initialize indexer with Neo4j and Maven support
        indexer = CodebaseIndexer(
            chroma_host=CHROMA_HOST,
            chroma_port=CHROMA_PORT,
            neo4j_uri=NEO4J_URI,
            neo4j_username=NEO4J_USERNAME,
            neo4j_password=NEO4J_PASSWORD,
            maven_enabled=MAVEN_ENABLED
        )
        
        # Initialize search
        search = CodebaseSearch(
            chroma_host=CHROMA_HOST,
            chroma_port=CHROMA_PORT,
            neo4j_uri=NEO4J_URI,
            neo4j_username=NEO4J_USERNAME,
            neo4j_password=NEO4J_PASSWORD
        )
        
        # Initialize Neo4j client for direct queries
        neo4j_client = Neo4jClient(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)
        
        # Initialize Struts parser
        struts_parser = StrutsParser()
        
        # Initialize all components
        await indexer.initialize()
        await search.initialize()
        await neo4j_client.initialize()
        
        # Initialize AI Agent for natural language queries
        agent_instance = AgentService.initialize(
            neo4j_client=neo4j_client,
            chromadb_client=indexer.client,  # ChromaDB client from indexer
            search_client=search
        )
        
        # Validate AWS credentials and agent initialization
        aws_status = await _validate_aws_credentials(agent_instance)
        
        if aws_status["agent_mode"] == "aws":
            logger.info("🎉 Codebase RAG MVP started successfully with FULL AI Agent and AWS Strands support!")
        elif aws_status["agent_mode"] == "fallback":
            if AWS_REQUIRED:
                logger.error("❌ STARTUP FAILED: AWS credentials are REQUIRED but missing/invalid")
                logger.error(f"   Reason: {aws_status['reason']}")
                logger.error("   Set AWS_REQUIRED=false in .env to allow fallback mode")
                logger.error("   Or configure AWS credentials (see .aws-credentials.template)")
                raise ValueError(f"AWS credentials required but unavailable: {aws_status['reason']}")
            else:
                logger.warning("⚠️  Codebase RAG MVP started in FALLBACK MODE - AWS credentials missing/invalid")
                logger.warning(f"   Reason: {aws_status['reason']}")
                logger.warning("   AI Agent will provide basic responses only")
                logger.warning("   For full functionality, configure AWS credentials (see .aws-credentials.template)")
                logger.warning("   To require AWS credentials, set AWS_REQUIRED=true in .env")
        else:
            logger.error("❌ AI Agent failed to initialize - check configuration")
            if AWS_REQUIRED:
                raise ValueError("AI Agent initialization failed and AWS is required")
            
        logger.info("✅ Core services (ChromaDB, Neo4j, Search) are fully functional")
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down Codebase RAG MVP...")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Codebase RAG MVP",
        "version": "0.1.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint with AWS credential status."""
    try:
        # Check ChromaDB connection
        chromadb_status = await search.health_check() if search else False
        
        # Check AWS credential status
        agent = AgentService.get_agent()
        aws_status = await _validate_aws_credentials(agent) if agent else {
            "agent_mode": "not_initialized",
            "credentials_valid": False,
            "reason": "Agent service not initialized"
        }
        
        overall_status = "healthy" if chromadb_status else "unhealthy"
        
        return {
            "status": overall_status,
            "chromadb": "connected" if chromadb_status else "disconnected",
            "neo4j": "connected" if neo4j_client else "not_initialized",
            "ai_agent": {
                "mode": aws_status["agent_mode"],
                "aws_credentials_valid": aws_status["credentials_valid"],
                "status_reason": aws_status["reason"]
            },
            "repos_path": REPOS_PATH,
            "repos_available": os.path.exists(REPOS_PATH),
            "ai_agent_enabled": AI_AGENT_ENABLED
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )


@app.post("/index")
async def index_repository(request: IndexRequest):
    """Index a local repository."""
    if not indexer:
        raise HTTPException(status_code=500, detail="Indexer not initialized")
    
    try:
        repo_path = Path(request.repo_path)
        
        # Validate repository path
        if not repo_path.exists():
            raise HTTPException(status_code=404, detail=f"Repository path not found: {request.repo_path}")
        
        if not repo_path.is_dir():
            raise HTTPException(status_code=400, detail=f"Path is not a directory: {request.repo_path}")
        
        # Index the repository
        repo_name = request.repo_name or repo_path.name
        result = await indexer.index_repository(str(repo_path), repo_name)
        
        return {
            "status": "success",
            "repository": repo_name,
            "path": str(repo_path),
            "files_indexed": result.get("files_indexed", 0),
            "chunks_created": result.get("chunks_created", 0),
            "processing_time": result.get("processing_time", 0)
        }
        
    except Exception as e:
        logger.error(f"Failed to index repository: {e}")
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")


@app.post("/search", response_model=List[SearchResult])
async def search_code(request: SearchRequest):
    """Search indexed code."""
    if not search:
        raise HTTPException(status_code=500, detail="Search not initialized")
    
    try:
        results = await search.search(
            query=request.query,
            limit=request.limit,
            similarity_threshold=request.similarity_threshold
        )
        
        return [
            SearchResult(
                file_path=result["file_path"],
                content=result["content"],
                score=result["score"],
                metadata=result.get("metadata", {})
            )
            for result in results
        ]
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.get("/search")
async def search_code_get(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=100, description="Number of results"),
    threshold: float = Query(0.7, ge=0.0, le=1.0, description="Similarity threshold")
):
    """Search code using GET method (for easy browser testing)."""
    request = SearchRequest(
        query=q,
        limit=limit,
        similarity_threshold=threshold
    )
    return await search_code(request)


@app.get("/repositories")
async def list_repositories():
    """List available repositories."""
    if not search:
        raise HTTPException(status_code=500, detail="Search not initialized")
    
    try:
        repos = await search.list_repositories()
        return {
            "repositories": repos,
            "count": len(repos)
        }
    except Exception as e:
        logger.error(f"Failed to list repositories: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list repositories: {str(e)}")


@app.get("/repositories/{repo_name}/stats")
async def get_repository_stats(repo_name: str):
    """Get statistics for a specific repository."""
    if not search:
        raise HTTPException(status_code=500, detail="Search not initialized")
    
    try:
        stats = await search.get_repository_stats(repo_name)
        return stats
    except Exception as e:
        logger.error(f"Failed to get repository stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get repository stats: {str(e)}")


@app.delete("/repositories/{repo_name}")
async def delete_repository(repo_name: str):
    """Delete a repository from the index."""
    if not indexer:
        raise HTTPException(status_code=500, detail="Indexer not initialized")
    
    try:
        result = await indexer.delete_repository(repo_name)
        return {
            "status": "success",
            "repository": repo_name,
            "chunks_deleted": result.get("chunks_deleted", 0)
        }
    except Exception as e:
        logger.error(f"Failed to delete repository: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete repository: {str(e)}")


@app.get("/status")
async def get_status():
    """Get system status and statistics."""
    if not search or not neo4j_client:
        raise HTTPException(status_code=500, detail="Components not initialized")
    
    try:
        chroma_stats = await search.get_collection_stats()
        repos = await search.list_repositories()
        neo4j_stats = await neo4j_client.get_collection_stats()
        
        return {
            "status": "running",
            "chromadb": {
                "total_chunks": chroma_stats.get("total_chunks", 0),
                "host": CHROMA_HOST,
                "port": CHROMA_PORT
            },
            "neo4j": {
                "total_repositories": neo4j_stats.get("total_repositories", 0),
                "total_files": neo4j_stats.get("total_files", 0),
                "total_artifacts": neo4j_stats.get("total_artifacts", 0),
                "total_dependencies": neo4j_stats.get("total_dependencies", 0),
                "uri": NEO4J_URI
            },
            "maven_enabled": MAVEN_ENABLED,
            "repositories": repos
        }
    except Exception as e:
        logger.error(f"Failed to get status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


# Maven-specific endpoints
@app.get("/maven/dependencies/{group_id}/{artifact_id}/{version}")
async def get_maven_dependencies(
    group_id: str,
    artifact_id: str,
    version: str,
    transitive: bool = Query(True, description="Include transitive dependencies"),
    max_depth: int = Query(3, ge=1, le=10, description="Maximum dependency depth")
):
    """Get Maven dependencies for an artifact."""
    if not neo4j_client:
        raise HTTPException(status_code=500, detail="Neo4j not initialized")
    
    try:
        artifact_full_id = f"{group_id}:{artifact_id}:{version}"
        dependencies = await neo4j_client.get_maven_dependencies(
            artifact_id=artifact_full_id,
            max_depth=max_depth,
            include_transitive=transitive
        )
        
        return {
            "artifact": {
                "group_id": group_id,
                "artifact_id": artifact_id,
                "version": version
            },
            "dependencies": dependencies,
            "transitive": transitive,
            "max_depth": max_depth,
            "total_dependencies": len(dependencies)
        }
        
    except Exception as e:
        logger.error(f"Failed to get Maven dependencies: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get dependencies: {str(e)}")


@app.get("/maven/conflicts")
async def get_dependency_conflicts(
    repository: Optional[str] = Query(None, description="Filter by repository")
):
    """Find conflicting Maven dependencies."""
    if not neo4j_client:
        raise HTTPException(status_code=500, detail="Neo4j not initialized")
    
    try:
        conflicts = await neo4j_client.find_dependency_conflicts(repo_name=repository)
        
        return {
            "conflicts": conflicts,
            "total_conflicts": len(conflicts),
            "repository": repository
        }
        
    except Exception as e:
        logger.error(f"Failed to find dependency conflicts: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to find conflicts: {str(e)}")


@app.get("/graph/repository/{repo_name}")
async def get_repository_graph(repo_name: str):
    """Get graph information for a repository."""
    if not neo4j_client:
        raise HTTPException(status_code=500, detail="Neo4j not initialized")
    
    try:
        stats = await neo4j_client.get_repository_stats(repo_name)
        
        return {
            "repository": repo_name,
            "graph_stats": stats
        }
        
    except Exception as e:
        logger.error(f"Failed to get repository graph: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get graph data: {str(e)}")


@app.get("/graph/repository/{repo_name}/visualization")
async def get_repository_graph_visualization(repo_name: str):
    """Get graph visualization data for a repository."""
    if not neo4j_client:
        raise HTTPException(status_code=500, detail="Neo4j not initialized")
    
    try:
        # Get nodes and relationships for visualization
        nodes_query = """
        MATCH (n)
        WHERE n.repository = $repo_name OR n.name = $repo_name
        RETURN 
            id(n) as id,
            labels(n)[0] as type,
            n.name as name,
            n.repository as repository,
            n.path as path,
            n.language as language,
            n.size as size,
            n.version as version,
            n.groupId as groupId,
            n.artifactId as artifactId
        LIMIT 100
        """
        
        relationships_query = """
        MATCH (n)-[r]->(m)
        WHERE (n.repository = $repo_name OR n.name = $repo_name) 
           OR (m.repository = $repo_name OR m.name = $repo_name)
        RETURN 
            id(n) as source_id,
            id(m) as target_id,
            type(r) as relationship_type,
            r.weight as weight
        LIMIT 200
        """
        
        nodes_result = await neo4j_client.execute_query(nodes_query, {"repo_name": repo_name})
        relationships_result = await neo4j_client.execute_query(relationships_query, {"repo_name": repo_name})
        
        # Format for frontend visualization
        graph_data = {
            "nodes": nodes_result,
            "edges": relationships_result,
            "repository": repo_name,
            "node_count": len(nodes_result),
            "edge_count": len(relationships_result)
        }
        
        return graph_data
        
    except Exception as e:
        logger.error(f"Failed to get repository graph visualization: {e}")
        # Return sample data if Neo4j query fails
        return {
            "nodes": [],
            "edges": [],
            "repository": repo_name,
            "node_count": 0,
            "edge_count": 0,
            "sample_mode": True
        }


@app.get("/graph/query")
async def execute_graph_query(
    cypher: str = Query(..., description="Cypher query to execute"),
    read_only: bool = Query(True, description="Execute as read-only query")
):
    """Execute a custom Cypher query (for advanced users)."""
    if not neo4j_client:
        raise HTTPException(status_code=500, detail="Neo4j not initialized")
    
    try:
        # Basic safety check for read-only queries
        if read_only and any(keyword in cypher.upper() for keyword in ['CREATE', 'DELETE', 'SET', 'REMOVE', 'MERGE']):
            raise HTTPException(status_code=400, detail="Query contains write operations but read_only=True")
        
        results = await neo4j_client.execute_query(cypher)
        
        return {
            "query": cypher,
            "results": results,
            "count": len(results)
        }
        
    except Exception as e:
        logger.error(f"Failed to execute graph query: {e}")
        raise HTTPException(status_code=500, detail=f"Query execution failed: {str(e)}")



# Struts-specific endpoints for legacy application migration
@app.post("/struts/analyze")
async def analyze_struts_repository(request: IndexRequest):
    """Analyze a Struts application repository for migration planning."""
    if not struts_parser:
        raise HTTPException(status_code=500, detail="Struts parser not initialized")
    
    try:
        repo_path = Path(request.repo_path)
        
        # Validate repository path
        if not repo_path.exists():
            raise HTTPException(status_code=404, detail=f"Repository path not found: {request.repo_path}")
        
        # Analyze Struts application
        repo_name = request.repo_name or repo_path.name
        analysis = struts_parser.analyze_struts_application(str(repo_path))
        
        return {
            "status": "success",
            "repository": repo_name,
            "analysis": analysis
        }
        
    except Exception as e:
        logger.error(f"Failed to analyze Struts repository: {e}")
        raise HTTPException(status_code=500, detail=f"Struts analysis failed: {str(e)}")


@app.get("/struts/actions")
async def get_struts_actions(
    repository: Optional[str] = Query(None, description="Filter by repository")
):
    """Get all Struts actions discovered in indexed repositories."""
    if not search:
        raise HTTPException(status_code=500, detail="Search not initialized")
    
    try:
        # Search for Struts Action classes
        query = "extends Action execute method ActionForward"
        if repository:
            query += f" repository:{repository}"
        
        results = await search.search(
            query=query,
            limit=100,
            similarity_threshold=0.6
        )
        
        # Process results to extract action information
        actions = []
        for result in results:
            if "Action" in result["file_path"] and ".java" in result["file_path"]:
                actions.append({
                    "file_path": result["file_path"],
                    "class_name": Path(result["file_path"]).stem,
                    "score": result["score"],
                    "content_preview": result["content"][:200] + "..."
                })
        
        return {
            "actions": actions,
            "total": len(actions),
            "repository": repository
        }
        
    except Exception as e:
        logger.error(f"Failed to get Struts actions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get actions: {str(e)}")


@app.get("/struts/migration-plan/{repository}")
async def generate_migration_plan(repository: str):
    """Generate a GraphQL migration plan for a Struts repository."""
    if not search or not struts_parser:
        raise HTTPException(status_code=500, detail="Required components not initialized")
    
    try:
        # Analyze business logic patterns
        business_logic_query = "business logic validation calculate process transform"
        business_results = await search.search(
            query=f"{business_logic_query} repository:{repository}",
            limit=50,
            similarity_threshold=0.6
        )
        
        # Analyze data models
        data_model_query = "data model DTO bean entity form"
        data_results = await search.search(
            query=f"{data_model_query} repository:{repository}",
            limit=50,
            similarity_threshold=0.6
        )
        
        # Generate migration suggestions
        migration_plan = {
            "repository": repository,
            "analysis_summary": {
                "business_logic_components": len(business_results),
                "data_models_found": len(data_results)
            },
            "graphql_suggestions": {
                "recommended_types": [],
                "recommended_queries": [],
                "recommended_mutations": []
            },
            "migration_steps": [
                "1. Analyze discovered business logic components",
                "2. Design GraphQL schema from data models", 
                "3. Map Struts actions to GraphQL operations",
                "4. Implement resolvers with extracted business logic",
                "5. Test migration incrementally"
            ]
        }
        
        # Extract suggested GraphQL types from data models
        for result in data_results[:10]:
            file_name = Path(result["file_path"]).stem
            if "Form" in file_name or "DTO" in file_name or "Bean" in file_name:
                type_name = file_name.replace("Form", "").replace("DTO", "").replace("Bean", "")
                if type_name:
                    migration_plan["graphql_suggestions"]["recommended_types"].append(type_name)
        
        return migration_plan
        
    except Exception as e:
        logger.error(f"Failed to generate migration plan: {e}")
        raise HTTPException(status_code=500, detail=f"Migration plan generation failed: {str(e)}")


@app.get("/search/legacy-patterns")
async def search_legacy_patterns(
    pattern: str = Query(..., description="Legacy pattern to search for (struts, hibernate, jsp, etc.)"),
    repository: Optional[str] = Query(None, description="Filter by repository"),
    limit: int = Query(20, ge=1, le=100, description="Number of results")
):
    """Enhanced search for common legacy code patterns."""
    if not search:
        raise HTTPException(status_code=500, detail="Search not initialized")
    
    try:
        # Define pattern-specific search queries
        pattern_queries = {
            "struts": "struts action form jsp extends Action ActionForm",
            "hibernate": "hibernate entity annotation @Entity @Table Session",
            "jsp": "jsp scriptlet taglib html:form bean:write logic:iterate",
            "spring": "spring bean @Component @Service @Repository @Autowired",
            "ejb": "EJB @Stateless @Entity @Remote @Local",
            "servlet": "servlet HttpServlet doGet doPost",
            "validation": "validation validate error message required",
            "database": "database connection sql query prepared statement",
            "configuration": "configuration properties xml config settings"
        }
        
        # Get query for pattern or use the pattern itself
        query = pattern_queries.get(pattern.lower(), pattern)
        if repository:
            query += f" repository:{repository}"
        
        results = await search.search(
            query=query,
            limit=limit,
            similarity_threshold=0.5
        )
        
        # Categorize results by file type
        categorized_results = {
            "java_files": [],
            "config_files": [],
            "jsp_files": [],
            "other_files": []
        }
        
        for result in results:
            file_path = result["file_path"]
            result_data = {
                "file_path": file_path,
                "score": result["score"],
                "content_preview": result["content"][:300] + "..."
            }
            
            if file_path.endswith('.java'):
                categorized_results["java_files"].append(result_data)
            elif any(file_path.endswith(ext) for ext in ['.xml', '.properties', '.yml', '.yaml']):
                categorized_results["config_files"].append(result_data)
            elif any(file_path.endswith(ext) for ext in ['.jsp', '.tag', '.tagx']):
                categorized_results["jsp_files"].append(result_data)
            else:
                categorized_results["other_files"].append(result_data)
        
        return {
            "pattern": pattern,
            "repository": repository,
            "total_results": len(results),
            "results": categorized_results,
            "available_patterns": list(pattern_queries.keys())
        }
        
    except Exception as e:
        logger.error(f"Failed to search legacy patterns: {e}")
        raise HTTPException(status_code=500, detail=f"Legacy pattern search failed: {str(e)}")


# AI Agent endpoint for natural language queries
@app.post("/agent/ask", response_model=AgentResponse)
async def ask_agent(request: AgentRequest):
    """
    Ask the AI agent questions about your Struts codebase in natural language.
    
    The agent can help you understand your application, find business logic,
    analyze dependencies, and plan your migration to modern architecture.
    
    Example questions:
    - "What are all the payment processing endpoints?"
    - "Show me the user authentication business logic" 
    - "How complex would it be to migrate the order management system?"
    - "What security patterns are used in this application?"
    """
    agent = AgentService.get_agent()
    if not agent:
        raise HTTPException(status_code=500, detail="AI Agent not initialized")
    
    try:
        # Add repository context to question if provided
        question = request.question
        if request.repository:
            question += f" (focus on repository: {request.repository})"
        
        # Get answer from the AI agent
        answer = await agent.ask(question)
        
        return AgentResponse(
            answer=answer,
            question=request.question,
            repository=request.repository
        )
        
    except Exception as e:
        logger.error(f"Agent query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Agent query failed: {str(e)}")


@app.get("/agent/capabilities")
async def get_agent_capabilities():
    """Get information about what the AI agent can help you with."""
    agent = AgentService.get_agent()
    if not agent:
        raise HTTPException(status_code=500, detail="AI Agent not initialized")
    
    try:
        capabilities = agent.get_capabilities()
        return capabilities
        
    except Exception as e:
        logger.error(f"Failed to get agent capabilities: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get capabilities: {str(e)}")


@app.get("/agent/health")
async def check_agent_health():
    """Check the health status of the AI agent and its dependencies."""
    agent = AgentService.get_agent()
    if not agent:
        return {
            "status": "unhealthy",
            "agent_initialized": False,
            "error": "Agent not initialized"
        }
    
    try:
        health = await agent.health_check()
        overall_status = "healthy" if all(health.values()) else "unhealthy"
        
        return {
            "status": overall_status,
            **health
        }
        
    except Exception as e:
        logger.error(f"Agent health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


if __name__ == "__main__":
    # Run the application with environment configuration
    uvicorn.run(
        "main:app",
        host=API_HOST,
        port=API_PORT,
        log_level=LOG_LEVEL.lower(),
        reload=(APP_ENV == "development")
    )