"""
Single-container MVP for Codebase RAG.
Simplified version with ChromaDB + SQLite instead of Neo4j.
"""

import os
import logging
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Import simplified components
from search import CodebaseSearch
from indexer import CodebaseIndexer

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
REPOS_PATH = os.getenv("REPOS_PATH", "/app/repos")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///app/data/codebase.db")

# Initialize FastAPI app
app = FastAPI(
    title="Codebase RAG MVP - Single Container",
    description="Ultra-minimal codebase search with ChromaDB only",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global components
indexer: Optional[CodebaseIndexer] = None
search: Optional[CodebaseSearch] = None
db_connection = None


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


def init_sqlite():
    """Initialize SQLite database for simple repository tracking."""
    conn = sqlite3.connect(DATABASE_URL.replace("sqlite:///", ""))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS repositories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            path TEXT NOT NULL,
            indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            file_count INTEGER DEFAULT 0,
            chunk_count INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    return conn


@app.on_event("startup")
async def startup_event():
    """Initialize components on startup."""
    global indexer, search, db_connection
    
    logger.info("Starting Single-Container Codebase RAG MVP...")
    
    try:
        # Initialize SQLite
        db_connection = init_sqlite()
        
        # Initialize ChromaDB-only indexer
        indexer = CodebaseIndexer(
            chroma_host="localhost",
            chroma_port=8000,
            neo4j_uri=None,  # Disable Neo4j
            maven_enabled=False  # Disable Maven parsing for simplicity
        )
        
        # Initialize search
        search = CodebaseSearch(
            chroma_host="localhost",
            chroma_port=8000,
            neo4j_uri=None  # Disable Neo4j
        )
        
        # Initialize ChromaDB components only
        await indexer.initialize_chromadb_only()
        await search.initialize_chromadb_only()
        
        logger.info("Single-Container MVP started successfully!")
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down Single-Container MVP...")
    if db_connection:
        db_connection.close()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Codebase RAG MVP - Single Container",
        "version": "0.1.0",
        "mode": "single-container",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        status = await search.health_check() if search else False
        
        return {
            "status": "healthy" if status else "unhealthy",
            "mode": "single-container",
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
        
        # Index the repository (ChromaDB only)
        repo_name = request.repo_name or repo_path.name
        result = await indexer.index_repository_simple(str(repo_path), repo_name)
        
        # Update SQLite tracking
        cursor = db_connection.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO repositories (name, path, file_count, chunk_count)
            VALUES (?, ?, ?, ?)
        """, (repo_name, str(repo_path), result.get("files_indexed", 0), result.get("chunks_created", 0)))
        db_connection.commit()
        
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
        results = await search.search_simple(
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
    """Search code using GET method."""
    request = SearchRequest(
        query=q,
        limit=limit,
        similarity_threshold=threshold
    )
    return await search_code(request)


@app.get("/repositories")
async def list_repositories():
    """List indexed repositories."""
    try:
        cursor = db_connection.cursor()
        cursor.execute("SELECT name, path, indexed_at, file_count, chunk_count FROM repositories ORDER BY indexed_at DESC")
        rows = cursor.fetchall()
        
        repositories = [
            {
                "name": row[0],
                "path": row[1], 
                "indexed_at": row[2],
                "file_count": row[3],
                "chunk_count": row[4]
            }
            for row in rows
        ]
        
        return {
            "repositories": repositories,
            "count": len(repositories)
        }
    except Exception as e:
        logger.error(f"Failed to list repositories: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list repositories: {str(e)}")


@app.get("/status")
async def get_status():
    """Get system status and statistics."""
    if not search:
        raise HTTPException(status_code=500, detail="Search not initialized")
    
    try:
        chroma_stats = await search.get_collection_stats()
        
        cursor = db_connection.cursor()
        cursor.execute("SELECT COUNT(*), SUM(file_count), SUM(chunk_count) FROM repositories")
        repo_count, total_files, total_chunks = cursor.fetchone()
        
        return {
            "status": "running",
            "mode": "single-container",
            "chromadb": {
                "total_chunks": chroma_stats.get("total_chunks", total_chunks or 0),
                "host": "localhost",
                "port": 8000
            },
            "repositories": {
                "total_repositories": repo_count or 0,
                "total_files": total_files or 0,
                "total_chunks": total_chunks or 0
            }
        }
    except Exception as e:
        logger.error(f"Failed to get status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


if __name__ == "__main__":
    # Run the application
    uvicorn.run(
        "main-single:app",
        host="0.0.0.0",
        port=8080,
        log_level=LOG_LEVEL.lower(),
        reload=False
    )