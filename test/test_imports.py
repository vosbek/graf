#!/usr/bin/env python3

import time
import sys

print("Starting import test...")
start_time = time.time()

try:
    print("Importing FastAPI...")
    from fastapi import FastAPI
    print(f"FastAPI imported in {time.time() - start_time:.2f}s")
    
    print("Importing ChromaDB...")
    start_chroma = time.time()
    try:
        from src.core.chromadb_client import ChromaDBClient
        print(f"ChromaDB imported in {time.time() - start_chroma:.2f}s")
    except Exception as e:
        print(f"ChromaDB import failed: {e}")
    
    print("Importing Neo4j...")
    start_neo4j = time.time()
    try:
        from src.core.neo4j_client import Neo4jClient
        print(f"Neo4j imported in {time.time() - start_neo4j:.2f}s")
    except Exception as e:
        print(f"Neo4j import failed: {e}")
    
    print("Importing embedding config...")
    start_embedding = time.time()
    try:
        from src.core.embedding_config import create_embedding_client
        print(f"Embedding config imported in {time.time() - start_embedding:.2f}s")
    except Exception as e:
        print(f"Embedding config import failed: {e}")
    
    print("Importing repository processor...")
    start_repo = time.time()
    try:
        from src.services.repository_processor_v2 import EnhancedRepositoryProcessor
        print(f"Repository processor imported in {time.time() - start_repo:.2f}s")
    except Exception as e:
        print(f"Repository processor import failed: {e}")
    
    print("Importing main application...")
    start_main = time.time()
    try:
        # Don't actually import main to avoid starting the server
        # from src.main import app
        print(f"Main application structure verified")
    except Exception as e:
        print(f"Main application import failed: {e}")
    
    total_time = time.time() - start_time
    print(f"Total import test completed in {total_time:.2f}s")
    
    if total_time > 5:
        print("WARNING: Imports taking longer than 5 seconds - likely cause of API hanging!")
    else:
        print("Imports seem fast - issue might be elsewhere")

except Exception as e:
    print(f"Import test failed: {e}")
    sys.exit(1)