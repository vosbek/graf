#!/usr/bin/env python3
"""
Minimal FastAPI test without any complex initialization or middleware
"""

from fastapi import FastAPI
import uvicorn

# Create the most basic FastAPI app possible
app = FastAPI()

@app.get("/")
def root():
    return {"message": "Minimal API working"}

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8083)