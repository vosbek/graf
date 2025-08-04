#!/usr/bin/env python3

"""Minimal FastAPI test to isolate blocking issues."""

import uvicorn
from fastapi import FastAPI
import time

app = FastAPI(title="Minimal Test API")

@app.get("/")
async def root():
    return {"message": "Hello World", "timestamp": time.time()}

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": time.time()}

if __name__ == "__main__":
    print("Starting minimal FastAPI server...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8081,
        workers=1,
        reload=False,
        log_level="info"
    )