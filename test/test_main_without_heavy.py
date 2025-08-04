#!/usr/bin/env python3

"""Test main application imports without the heavy ones."""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, HTTPException, Depends, Query, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

# Import the non-heavy modules
print("Importing Neo4j client...")
from src.core.neo4j_client import Neo4jClient

print("Importing logging config...")
from src.core.logging_config import setup_logging, log_api_request, get_logger

print("Importing settings...")
from src.config.settings import Settings

print("Importing dependencies...")
from src import dependencies

print("All imports complete, creating test app...")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Test lifespan function."""
    print("=== LIFESPAN STARTUP: Starting ===")
    
    async def background_init():
        print("=== BACKGROUND: Init starting ===")
        # Just test Neo4j connection
        settings = Settings()
        neo4j_client = Neo4jClient(
            uri=settings.neo4j_uri,
            username=settings.neo4j_username,
            password=settings.neo4j_password,
            database=settings.neo4j_database
        )
        print("=== BACKGROUND: Neo4j client created ===")
        try:
            await neo4j_client.initialize()
            print("=== BACKGROUND: Neo4j initialized successfully ===")
        except Exception as e:
            print(f"=== BACKGROUND: Neo4j failed: {e} ===")
        
        app.state.ready = True
        print("=== BACKGROUND: Init complete ===")
    
    task = asyncio.create_task(background_init())
    print("=== LIFESPAN: Background task created, yielding ===")
    
    yield
    
    print("=== LIFESPAN SHUTDOWN: Starting ===")

# Initialize settings and logging
settings = Settings()
logger = setup_logging(
    log_level=settings.log_level,
    component="test-api",
    enable_console=True,
    enable_file=True
)

# Create FastAPI application
app = FastAPI(
    title="Test Codebase RAG API",
    description="Test without heavy imports",
    version="1.0.0",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Test Codebase RAG API",
        "version": "1.0.0",
        "status": "ok",
        "ready": getattr(app.state, 'ready', False)
    }

@app.get("/health")
async def health():
    """Health endpoint."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "ready": getattr(app.state, 'ready', False)
    }

if __name__ == "__main__":
    print("Starting test server...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8083,
        workers=1,
        reload=False,
        log_level="info"
    )