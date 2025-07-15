"""
FastAPI application for Codebase RAG system.
Provides RESTful API endpoints for querying, indexing, and managing repositories.
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, HTTPException, Depends, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

from .core.chromadb_client import ChromaDBClient, SearchQuery, SearchResult
from .core.neo4j_client import Neo4jClient
from .services.repository_processor import RepositoryProcessor, RepositoryConfig, RepositoryFilter
from .api.routes import query, index, health, admin
from .api.middleware.auth import AuthMiddleware
from .api.middleware.logging import LoggingMiddleware
from .config.settings import Settings


# Initialize settings
settings = Settings()

# Global clients
chroma_client: Optional[ChromaDBClient] = None
neo4j_client: Optional[Neo4jClient] = None
repository_processor: Optional[RepositoryProcessor] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global chroma_client, neo4j_client, repository_processor
    
    # Startup
    logging.info("Starting Codebase RAG application...")
    
    try:
        # Initialize ChromaDB client
        chroma_client = ChromaDBClient(
            host=settings.chroma_host,
            port=settings.chroma_port
        )
        await chroma_client.initialize()
        
        # Initialize Neo4j client
        neo4j_client = Neo4jClient(
            uri=settings.neo4j_uri,
            username=settings.neo4j_username,
            password=settings.neo4j_password,
            database=settings.neo4j_database
        )
        await neo4j_client.initialize()
        
        # Initialize repository processor
        repository_processor = RepositoryProcessor(
            chroma_client=chroma_client,
            neo4j_client=neo4j_client,
            max_concurrent_repos=settings.max_concurrent_repos
        )
        
        # Store clients in app state
        app.state.chroma_client = chroma_client
        app.state.neo4j_client = neo4j_client
        app.state.repository_processor = repository_processor
        
        logging.info("Application startup completed successfully")
        
        yield
        
    except Exception as e:
        logging.error(f"Application startup failed: {e}")
        raise
    
    finally:
        # Shutdown
        logging.info("Shutting down Codebase RAG application...")
        
        if chroma_client:
            await chroma_client.close()
        
        if neo4j_client:
            await neo4j_client.close()
        
        if repository_processor:
            await repository_processor.cleanup()
        
        logging.info("Application shutdown completed")


# Create FastAPI application
app = FastAPI(
    title="Codebase RAG API",
    description="Advanced RAG system for large-scale codebase analysis",
    version="1.0.0",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(LoggingMiddleware)

if settings.auth_enabled:
    app.add_middleware(AuthMiddleware)

# Include routers
app.include_router(query.router, prefix="/api/v1/query", tags=["Query"])
app.include_router(index.router, prefix="/api/v1/index", tags=["Indexing"])
app.include_router(health.router, prefix="/api/v1/health", tags=["Health"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Codebase RAG API",
        "version": "1.0.0",
        "description": "Advanced RAG system for large-scale codebase analysis",
        "endpoints": {
            "health": "/api/v1/health",
            "query": "/api/v1/query",
            "index": "/api/v1/index",
            "admin": "/api/v1/admin"
        }
    }


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "timestamp": time.time(),
            "path": str(request.url)
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    logging.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "timestamp": time.time(),
            "path": str(request.url)
        }
    )


# Dependency injection
def get_chroma_client() -> ChromaDBClient:
    """Get ChromaDB client."""
    if not chroma_client:
        raise HTTPException(status_code=503, detail="ChromaDB client not initialized")
    return chroma_client


def get_neo4j_client() -> Neo4jClient:
    """Get Neo4j client."""
    if not neo4j_client:
        raise HTTPException(status_code=503, detail="Neo4j client not initialized")
    return neo4j_client


def get_repository_processor() -> RepositoryProcessor:
    """Get repository processor."""
    if not repository_processor:
        raise HTTPException(status_code=503, detail="Repository processor not initialized")
    return repository_processor


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )