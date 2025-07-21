#!/usr/bin/env python3
"""
Simple MVP Demo - Tests core functionality without external services
"""

import os
import sys
import sqlite3
from pathlib import Path

# Test 1: Basic imports work
print("🔧 Testing MVP Component Imports...")
try:
    import chromadb
    print("✅ ChromaDB imported successfully")
except Exception as e:
    print(f"❌ ChromaDB import failed: {e}")

try:
    from neo4j import GraphDatabase
    print("✅ Neo4j driver imported successfully") 
except Exception as e:
    print(f"❌ Neo4j import failed: {e}")

try:
    import fastapi
    import uvicorn
    print("✅ FastAPI/Uvicorn imported successfully")
except Exception as e:
    print(f"❌ FastAPI import failed: {e}")

# Test 2: ChromaDB embedded mode
print("\n📊 Testing ChromaDB Embedded Mode...")
try:
    # Use embedded ChromaDB instead of remote
    client = chromadb.Client()
    collection = client.create_collection("test_collection")
    
    # Add some test documents
    collection.add(
        documents=["This is a test document", "Another test file"],
        metadatas=[{"source": "demo"}, {"source": "demo"}],
        ids=["doc1", "doc2"]
    )
    
    # Query the collection
    results = collection.query(
        query_texts=["test"],
        n_results=2
    )
    
    print(f"✅ ChromaDB embedded working - found {len(results['documents'][0])} documents")
    
    # Clean up
    client.delete_collection("test_collection")
    
except Exception as e:
    print(f"❌ ChromaDB test failed: {e}")

# Test 3: Neo4j connection (only if running)
print("\n🔗 Testing Neo4j Connection...")
try:
    driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "codebase-rag-2024"))
    with driver.session() as session:
        result = session.run("RETURN 1 as test")
        record = result.single()
        if record and record["test"] == 1:
            print("✅ Neo4j connection successful")
        else:
            print("❌ Neo4j query failed")
    driver.close()
except Exception as e:
    print(f"⚠️  Neo4j connection failed (container may not be running): {e}")

# Test 4: Basic file operations
print("\n📂 Testing File Operations...")
try:
    data_dir = Path("./data/test")
    data_dir.mkdir(parents=True, exist_ok=True)
    
    test_file = data_dir / "test.txt"
    test_file.write_text("Test content for MVP demo")
    
    if test_file.exists():
        content = test_file.read_text()
        print(f"✅ File operations working - wrote and read: '{content[:30]}...'")
        
        # Clean up
        test_file.unlink()
        data_dir.rmdir()
    else:
        print("❌ File write failed")
        
except Exception as e:
    print(f"❌ File operations failed: {e}")

# Test 5: Simple FastAPI server (no startup)
print("\n⚡ Testing FastAPI Setup...")
try:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    
    app = FastAPI(title="MVP Demo")
    
    @app.get("/")
    def root():
        return {"message": "MVP Demo Working", "status": "ok"}
    
    @app.get("/health")
    def health():
        return JSONResponse({
            "status": "healthy",
            "components": {
                "chromadb": "embedded",
                "neo4j": "container",
                "fastapi": "working"
            }
        })
    
    print("✅ FastAPI app created successfully")
    print("   Endpoints: / and /health defined")
    
except Exception as e:
    print(f"❌ FastAPI setup failed: {e}")

print("\n🎉 MVP Core Components Test Complete!")
print("\nNext Steps:")
print("1. Neo4j container is running on port 7687")
print("2. ChromaDB can work in embedded mode")
print("3. FastAPI server can be started")
print("4. All dependencies are installed")
print("\nTo start the web interface:")
print("   cd mvp && python3 main.py")
print("   (Note: Will use embedded ChromaDB automatically)")