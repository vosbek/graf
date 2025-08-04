#!/usr/bin/env python3
"""
Simple test API to verify FastAPI is working without complex initialization.
"""

from fastapi import FastAPI
import uvicorn

# Create a simple FastAPI app without any middleware or complex startup
app = FastAPI(title="Simple Test API")

@app.get("/test")
async def test_endpoint():
    """Simple test endpoint."""
    return {"status": "ok", "message": "Simple API is working"}

@app.get("/health")
async def health():
    """Simple health check."""
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, workers=1)