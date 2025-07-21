#!/usr/bin/env python3
"""
Start MVP with embedded ChromaDB - Works without external containers
"""

import os
import logging
from pathlib import Path
import chromadb
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
API_HOST = "0.0.0.0"
API_PORT = 8080
REPOS_PATH = "./data/repositories"

# Initialize FastAPI app
app = FastAPI(
    title="Codebase RAG MVP - Embedded",
    description="Minimal MVP with embedded ChromaDB",
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

# Serve static files if frontend exists
frontend_build_path = Path(__file__).parent / "frontend" / "build"
if frontend_build_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_build_path / "static")), name="static")
    app.mount("/", StaticFiles(directory=str(frontend_build_path), html=True), name="frontend")

# Global components
chroma_client = None

class IndexRequest(BaseModel):
    repo_path: str
    repo_name: str = None

class SearchRequest(BaseModel):
    query: str
    limit: int = 10

@app.on_event("startup")
async def startup_event():
    """Initialize embedded ChromaDB."""
    global chroma_client
    
    logger.info("Starting MVP with embedded ChromaDB...")
    
    try:
        # Create data directory
        os.makedirs(REPOS_PATH, exist_ok=True)
        os.makedirs("./data/chroma", exist_ok=True)
        
        # Initialize embedded ChromaDB
        chroma_client = chromadb.PersistentClient(path="./data/chroma")
        
        logger.info("MVP started successfully with embedded ChromaDB!")
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Codebase RAG MVP - Embedded Mode",
        "version": "0.1.0",
        "mode": "embedded",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        collections = chroma_client.list_collections() if chroma_client else []
        
        return {
            "status": "healthy",
            "mode": "embedded",
            "chromadb": "connected",
            "collections": len(collections),
            "repos_path": REPOS_PATH
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
    """Index a local repository (simplified version)."""
    if not chroma_client:
        raise HTTPException(status_code=500, detail="ChromaDB not initialized")
    
    try:
        repo_path = Path(request.repo_path)
        
        if not repo_path.exists():
            raise HTTPException(status_code=404, detail=f"Repository path not found: {request.repo_path}")
        
        if not repo_path.is_dir():
            raise HTTPException(status_code=400, detail=f"Path is not a directory: {request.repo_path}")
        
        repo_name = request.repo_name or repo_path.name
        
        # Get or create collection
        try:
            collection = chroma_client.get_collection(repo_name)
        except:
            collection = chroma_client.create_collection(repo_name)
        
        # Simple file indexing
        files_indexed = 0
        documents = []
        metadatas = []
        ids = []
        
        for file_path in repo_path.rglob("*"):
            if file_path.is_file() and file_path.suffix in ['.java', '.js', '.py', '.xml', '.properties']:
                try:
                    content = file_path.read_text(encoding='utf-8')
                    if len(content) > 0 and len(content) < 50000:  # Skip very large files
                        documents.append(content[:2000])  # First 2000 chars
                        metadatas.append({
                            "file_path": str(file_path.relative_to(repo_path)),
                            "repository": repo_name,
                            "file_type": file_path.suffix,
                            "size": len(content)
                        })
                        ids.append(f"{repo_name}_{files_indexed}")
                        files_indexed += 1
                        
                        if files_indexed >= 100:  # Limit for demo
                            break
                except:
                    continue
        
        # Add to ChromaDB
        if documents:
            collection.add(
                documents=documents,
                metadatas=metadatas, 
                ids=ids
            )
        
        return {
            "status": "success",
            "repository": repo_name,
            "path": str(repo_path),
            "files_indexed": files_indexed,
            "collection_size": collection.count()
        }
        
    except Exception as e:
        logger.error(f"Failed to index repository: {e}")
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")

@app.post("/search")
async def search_code(request: SearchRequest):
    """Search indexed code."""
    if not chroma_client:
        raise HTTPException(status_code=500, detail="ChromaDB not initialized")
    
    try:
        collections = chroma_client.list_collections()
        all_results = []
        
        for collection_info in collections:
            collection = chroma_client.get_collection(collection_info.name)
            results = collection.query(
                query_texts=[request.query],
                n_results=min(request.limit, 10)
            )
            
            for i, doc in enumerate(results['documents'][0]):
                all_results.append({
                    "file_path": results['metadatas'][0][i].get('file_path', 'unknown'),
                    "repository": results['metadatas'][0][i].get('repository', collection_info.name),
                    "content": doc,
                    "score": 1.0 - results['distances'][0][i] if results['distances'][0] else 0.8,
                    "metadata": results['metadatas'][0][i]
                })
        
        # Sort by score and limit
        all_results.sort(key=lambda x: x['score'], reverse=True)
        return all_results[:request.limit]
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/repositories")
async def list_repositories():
    """List available repositories."""
    if not chroma_client:
        raise HTTPException(status_code=500, detail="ChromaDB not initialized")
    
    try:
        collections = chroma_client.list_collections()
        repos = []
        
        for collection_info in collections:
            collection = chroma_client.get_collection(collection_info.name)
            repos.append({
                "name": collection_info.name,
                "document_count": collection.count()
            })
        
        return {
            "repositories": repos,
            "count": len(repos)
        }
    except Exception as e:
        logger.error(f"Failed to list repositories: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list repositories: {str(e)}")

@app.get("/agent/health")
async def agent_health():
    """AI Agent health - fallback mode."""
    return {
        "status": "healthy",
        "agent_initialized": True,
        "fallback_mode": True,
        "aws_available": False,
        "message": "AI Agent running in fallback mode - basic responses available"
    }

@app.post("/agent/ask")
async def ask_agent(request: dict):
    """Simple AI agent fallback responses."""
    question = request.get("question", "")
    
    # Simple pattern matching for common questions
    responses = {
        "payment": "I found payment-related code patterns in your repositories. Check files containing 'payment', 'transaction', or 'billing' for payment processing logic.",
        "authentication": "Authentication patterns typically include login, session management, and security filters. Look for files with 'auth', 'login', 'security', or 'filter' in their names.",
        "migration": "For Struts to GraphQL migration, focus on: 1) Action classes → GraphQL resolvers, 2) Form beans → GraphQL types, 3) Business logic extraction, 4) Database layer modernization.",
        "database": "Database-related code is usually in DAO, repository, or service layers. Look for files with SQL queries, JPA annotations, or database configuration.",
        "endpoints": "Web endpoints in Struts are defined in Action classes and struts-config.xml. Search for 'Action' classes and XML configuration files."
    }
    
    # Find best match
    question_lower = question.lower()
    for keyword, response in responses.items():
        if keyword in question_lower:
            return {
                "answer": response,
                "question": question,
                "mode": "fallback",
                "suggestion": "For more detailed analysis, index your repositories and use the search functionality."
            }
    
    return {
        "answer": "I'm running in fallback mode. I can help with questions about payment processing, authentication, migration planning, database patterns, and endpoint discovery. Try asking about specific topics or use the search function to explore your indexed code.",
        "question": question,
        "mode": "fallback"
    }

if __name__ == "__main__":
    print("🚀 Starting Codebase RAG MVP - Embedded Mode")
    print(f"📊 ChromaDB: Embedded (persistent storage in ./data/chroma)")
    print(f"🌐 Server: http://localhost:{API_PORT}")
    print("📁 Repository storage: ./data/repositories")
    print("\n🎯 Ready to index and analyze your Struts/Java repositories!")
    
    uvicorn.run(
        "start-mvp-embedded:app",
        host=API_HOST,
        port=API_PORT,
        log_level="info",
        reload=False
    )