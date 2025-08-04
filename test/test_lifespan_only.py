#!/usr/bin/env python3

"""Test FastAPI with just the lifespan function to see if it's blocking."""

import asyncio
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI

print("Creating lifespan function...")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Test lifespan function."""
    print("=== LIFESPAN STARTUP: Starting ===")
    
    # Simple background task
    async def background_task():
        print("=== BACKGROUND: Task starting ===")
        await asyncio.sleep(1)  # Simulate some work
        print("=== BACKGROUND: Task complete ===")
    
    print("=== LIFESPAN: Creating background task ===")
    task = asyncio.create_task(background_task())
    print("=== LIFESPAN: Background task created, yielding ===")
    
    yield
    
    print("=== LIFESPAN SHUTDOWN: Starting ===")

print("Creating FastAPI app...")
app = FastAPI(title="Lifespan Test", lifespan=lifespan)

@app.get("/")
async def root():
    return {"message": "lifespan test", "status": "ok"}

if __name__ == "__main__":
    print("Starting server...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8082,
        workers=1,
        reload=False,
        log_level="info"
    )