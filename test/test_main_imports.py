#!/usr/bin/env python3

import time

print("Testing imports from main.py one by one...")

start = time.time()
print("Importing Neo4j client...")
try:
    from src.core.neo4j_client import Neo4jClient
    print(f"Neo4j client imported in {time.time() - start:.2f}s")
except Exception as e:
    print(f"Neo4j import failed: {e}")

start = time.time()
print("Importing logging config...")
try:
    from src.core.logging_config import setup_logging, log_api_request, get_logger
    print(f"Logging config imported in {time.time() - start:.2f}s")
except Exception as e:
    print(f"Logging config import failed: {e}")

start = time.time()
print("Importing embedding config...")
try:
    from src.core.embedding_config import create_embedding_client
    print(f"Embedding config imported in {time.time() - start:.2f}s")
except Exception as e:
    print(f"Embedding config import failed: {e}")

start = time.time()
print("Importing repository processors...")
try:
    from src.services.repository_processor import RepositoryProcessor, RepositoryConfig, RepositoryFilter
    from src.services.repository_processor_v2 import EnhancedRepositoryProcessor
    print(f"Repository processors imported in {time.time() - start:.2f}s")
except Exception as e:
    print(f"Repository processors import failed: {e}")

start = time.time()
print("Importing API routes...")
try:
    from src.api.routes import health, query, index, admin
    print(f"API routes imported in {time.time() - start:.2f}s")
except Exception as e:
    print(f"API routes import failed: {e}")

start = time.time()
print("Importing settings...")
try:
    from src.config.settings import Settings
    print(f"Settings imported in {time.time() - start:.2f}s")
except Exception as e:
    print(f"Settings import failed: {e}")

start = time.time()
print("Importing dependencies...")
try:
    from src import dependencies
    print(f"Dependencies imported in {time.time() - start:.2f}s")
except Exception as e:
    print(f"Dependencies import failed: {e}")

print("Import test completed!")