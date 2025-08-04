#!/usr/bin/env python3
"""
Test script to verify ChromaDB connectivity and fix collection issues.
"""

import asyncio
import sys
import os
import logging
from pathlib import Path

# Add parent directory to path for imports
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from src.core.chromadb_client import ChromaDBClient
from src.config.settings import Settings


async def test_chromadb_connection():
    """Test ChromaDB connection and collection management."""
    
    print("Testing ChromaDB Connection...")
    
    # Initialize settings
    settings = Settings()
    print(f"ChromaDB Host: {settings.chroma_host}")
    print(f"ChromaDB Port: {settings.chroma_port}")
    print(f"ChromaDB Collection: {settings.chroma_collection_name}")
    
    # Create ChromaDB client
    client = ChromaDBClient(
        host=settings.chroma_host,
        port=settings.chroma_port,
        collection_name=settings.chroma_collection_name
    )
    
    try:
        # Test initialization
        print("\nInitializing ChromaDB client...")
        await client.initialize()
        print("[SUCCESS] ChromaDB client initialized successfully")
        
        # Test basic connectivity
        print("\nTesting basic connectivity...")
        health = await client.health_check()
        print(f"[SUCCESS] Health check result: {health['status']}")
        
        # List collections
        print("\nListing collections...")
        try:
            # Use direct client access to list collections
            if hasattr(client, '_client') and client._client:
                collections = client._client.list_collections()
                print(f"[SUCCESS] Collections found: {[col.name for col in collections]}")
                
                # Check if our collection exists
                collection_exists = any(col.name == settings.chroma_collection_name for col in collections)
                print(f"[INFO] Collection '{settings.chroma_collection_name}' exists: {collection_exists}")
                
                if not collection_exists:
                    print(f"[INFO] Creating collection '{settings.chroma_collection_name}'...")
                    await client.initialize()  # This should create the collection
                    print(f"[SUCCESS] Collection created")
            else:
                print("[ERROR] ChromaDB client not properly initialized")
                
        except Exception as e:
            print(f"[ERROR] Failed to list collections: {e}")
        
        # Test collection operations
        print("\nTesting collection operations...")
        try:
            # Try to get collection info
            if hasattr(client, 'collection') and client.collection:
                count = client.collection.count()
                print(f"[SUCCESS] Collection document count: {count}")
            else:
                print("[ERROR] Collection not available")
                
        except Exception as e:
            print(f"[ERROR] Failed collection operations: {e}")
        
        # Test statistics
        print("\nGetting statistics...")
        try:
            stats = await client.get_statistics()
            print(f"[SUCCESS] Total chunks: {stats.get('total_chunks', 0)}")
            print(f"[SUCCESS] Performance metrics: {stats.get('performance_metrics', {})}")
        except Exception as e:
            print(f"[ERROR] Failed to get statistics: {e}")
        
        print("\n[SUCCESS] ChromaDB tests completed!")
        return True
        
    except Exception as e:
        print(f"[ERROR] ChromaDB test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up
        print("\nCleaning up...")
        try:
            await client.close()
        except Exception as e:
            print(f"[WARN] Cleanup error: {e}")


async def main():
    """Main test function."""
    print("=" * 60)
    print("ChromaDB Connection Test Suite")
    print("=" * 60)
    
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    try:
        success = await test_chromadb_connection()
        
        if success:
            print("\n[SUCCESS] ChromaDB tests completed!")
            sys.exit(0)
        else:
            print("\n[ERROR] ChromaDB tests failed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())