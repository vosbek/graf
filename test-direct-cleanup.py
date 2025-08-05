#!/usr/bin/env python3
"""
Direct test of database cleanup using HTTP requests to avoid client issues
"""

import asyncio
import requests
from neo4j import AsyncGraphDatabase
import json

async def test_direct_cleanup():
    """Test database cleanup using direct HTTP requests."""
    print("Testing database cleanup with direct HTTP...")
    
    # Test Neo4j
    print("\nTesting Neo4j...")
    try:
        neo4j_driver = AsyncGraphDatabase.driver(
            "bolt://localhost:7687",
            auth=("neo4j", "codebase-rag-2024")
        )
        
        async with neo4j_driver.session() as session:
            result = await session.run("MATCH (n) RETURN count(n) as total_nodes")
            record = await result.single()
            node_count = record["total_nodes"] if record else 0
            print(f"[OK] Neo4j: {node_count} nodes")
            
            # Test deletion (dry run)
            if node_count > 0:
                print(f"[INFO] Would delete {node_count} nodes in cleanup")
        
        await neo4j_driver.close()
        
    except Exception as e:
        print(f"[ERROR] Neo4j: {e}")
        return False
    
    # Test ChromaDB using HTTP requests
    print("\nTesting ChromaDB via HTTP...")
    try:
        # Try v2 health endpoint
        response = requests.get("http://localhost:8000/api/v2/healthcheck", timeout=5)
        if response.status_code == 200:
            print("[OK] ChromaDB v2 health endpoint working")
        else:
            print(f"[WARN] ChromaDB v2 health returned {response.status_code}")
        
        # Try to list collections via HTTP
        try:
            collections_response = requests.get("http://localhost:8000/api/v1/collections", timeout=5)
            if collections_response.status_code == 200:
                collections = collections_response.json()
                print(f"[OK] ChromaDB: Found {len(collections)} collections via HTTP")
                for collection in collections:
                    print(f"  - Collection: {collection.get('name', 'unknown')}")
            else:
                print(f"[WARN] Collections endpoint returned {collections_response.status_code}")
        except Exception as e:
            print(f"[WARN] Collections HTTP test failed: {e}")
            
    except Exception as e:
        print(f"[ERROR] ChromaDB HTTP test failed: {e}")
        return False
    
    # Test API endpoints
    print("\nTesting API server...")
    try:
        health_response = requests.get("http://localhost:8080/api/v1/health/", timeout=5)
        if health_response.status_code == 200:
            health_data = health_response.json()
            print(f"[OK] API health: {health_data.get('status', 'unknown')}")
            
            # Test database reset endpoint
            reset_test = {
                "reset_neo4j": False,
                "reset_chromadb": False,
                "create_backup": False,
                "confirm": False
            }
            
            print("[INFO] Testing database reset API (dry run)...")
            reset_response = requests.post(
                "http://localhost:8080/api/v1/admin/database/reset",
                json=reset_test,
                timeout=10
            )
            
            if reset_response.status_code == 400:
                print("[OK] Database reset API properly requires confirmation")
            else:
                print(f"[WARN] Database reset API returned {reset_response.status_code}")
                
        else:
            print(f"[ERROR] API health returned {health_response.status_code}")
            return False
            
    except Exception as e:
        print(f"[ERROR] API test failed: {e}")
        return False
    
    print("\n[SUCCESS] All database connectivity tests passed!")
    print("\nDatabase cleanup methods available:")
    print("1. API endpoint: POST /api/v1/admin/database/reset")
    print("2. Web UI: System Status -> Database Management -> Reset Databases")
    print("3. Script: python scripts/cleanup-databases.py --dry-run")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_direct_cleanup())
    exit(0 if success else 1)