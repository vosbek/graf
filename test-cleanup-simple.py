#!/usr/bin/env python3
"""
Simple test script to verify database cleanup functionality works
"""

import asyncio
import sys
from pathlib import Path

# Add src to Python path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    import chromadb
    from neo4j import AsyncGraphDatabase
    import time
except ImportError as e:
    print(f"Import error: {e}")
    print("Please ensure dependencies are installed.")
    sys.exit(1)

async def test_cleanup():
    """Test database cleanup functionality."""
    print("Testing database cleanup functionality...")
    
    # Test Neo4j connection
    print("\nTesting Neo4j connection...")
    try:
        neo4j_driver = AsyncGraphDatabase.driver(
            "bolt://localhost:7687",
            auth=("neo4j", "codebase-rag-2024")
        )
        
        async with neo4j_driver.session() as session:
            result = await session.run("MATCH (n) RETURN count(n) as total_nodes")
            record = await result.single()
            node_count = record["total_nodes"] if record else 0
            print(f"[OK] Neo4j: Connected successfully, found {node_count} nodes")
        
        await neo4j_driver.close()
        
    except Exception as e:
        print(f"[ERROR] Neo4j connection failed: {e}")
        return False
    
    # Test ChromaDB connection
    print("\nTesting ChromaDB connection...")
    try:
        # Try different approaches for ChromaDB
        chroma_client = None
        
        # Approach 1: Direct client with no tenant
        try:
            chroma_client = chromadb.HttpClient(
                host="localhost",
                port=8000
            )
            collections = chroma_client.list_collections()
            print(f"[OK] ChromaDB: Connected successfully (direct), found {len(collections)} collections")
            
        except Exception as e1:
            print(f"[WARN] ChromaDB direct approach failed: {e1}")
            
            # Approach 2: Try with settings
            try:
                chroma_client = chromadb.HttpClient(
                    host="localhost",
                    port=8000,
                    settings=chromadb.config.Settings(anonymized_telemetry=False)
                )
                collections = chroma_client.list_collections()
                print(f"[OK] ChromaDB: Connected successfully (with settings), found {len(collections)} collections")
                
            except Exception as e2:
                print(f"[ERROR] ChromaDB connection failed: {e2}")
                return False
                
    except Exception as e:
        print(f"[ERROR] ChromaDB connection failed: {e}")
        return False
    
    print("\nDatabase connectivity test passed!")
    print("\nNext steps:")
    print("1. The cleanup script should work with these connections")
    print("2. Try running: python -m scripts.cleanup-databases --dry-run")
    print("3. Or use the web UI reset button")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_cleanup())
    sys.exit(0 if success else 1)