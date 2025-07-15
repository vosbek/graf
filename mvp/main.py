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
from pydantic import BaseModel

from .indexer import CodebaseIndexer
from .search import CodebaseSearch
from .neo4j_client import Neo4jClient

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "codebase-rag-2024")
MAVEN_ENABLED = os.getenv("MAVEN_ENABLED", "true").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
REPOS_PATH = os.getenv("REPOS_PATH", "/app/repos")

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

# Global components
indexer: Optional[CodebaseIndexer] = None
search: Optional[CodebaseSearch] = None
neo4j_client: Optional[Neo4jClient] = None


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


@app.on_event("startup")
async def startup_event():
    """Initialize components on startup."""
    global indexer, search, neo4j_client
    
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
        
        # Initialize all components
        await indexer.initialize()
        await search.initialize()
        await neo4j_client.initialize()
        
        logger.info("Codebase RAG MVP started successfully with Neo4j and Maven support!")
        
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
    """Health check endpoint."""
    try:
        # Check ChromaDB connection
        status = await search.health_check() if search else False
        
        return {
            "status": "healthy" if status else "unhealthy",
            "chromadb": "connected" if status else "disconnected",
            "repos_path": REPOS_PATH,
            "repos_available": os.path.exists(REPOS_PATH)
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


if __name__ == "__main__":
    # Run the application
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        log_level=LOG_LEVEL.lower(),
        reload=False
    )