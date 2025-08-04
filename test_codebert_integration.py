#!/usr/bin/env python3
"""
Test script to verify CodeBERT integration without full API startup.
This validates our core integration changes.
"""

import asyncio
import sys
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_codebert_integration():
    """Test CodeBERT embedding generation and ChromaDB integration."""
    
    print("🧪 Testing CodeBERT Integration...")
    
    # Test 1: Import and create CodeBERT client
    try:
        from src.core.embedding_config import create_embedding_client, create_chromadb_embedding_function
        print("✅ Successfully imported CodeBERT components")
        
        # Create embedding client
        embedding_client = create_embedding_client(
            model_type="codebert",
            device="cpu",  # Force CPU for testing
            use_cache=True,
            lazy_init=True
        )
        print("✅ Successfully created CodeBERT embedding client")
        
        # Test embedding generation
        test_code = "def hello_world():\n    print('Hello, World!')\n    return True"
        embeddings = await embedding_client.encode(test_code)
        
        print(f"✅ Generated embeddings with shape: {embeddings.shape}")
        print(f"✅ Embedding dimension: {embeddings.shape[0] if len(embeddings.shape) == 1 else embeddings.shape[1]}")
        
        # Verify it's 768 dimensions (CodeBERT)
        dim = embeddings.shape[0] if len(embeddings.shape) == 1 else embeddings.shape[1]
        if dim == 768:
            print("✅ Correct CodeBERT dimension (768)")
        else:
            print(f"❌ Wrong dimension: expected 768, got {dim}")
            
        # Test ChromaDB embedding function adapter
        chroma_func = create_chromadb_embedding_function(embedding_client)
        print("✅ Successfully created ChromaDB embedding function")
        
        # Test ChromaDB function interface
        result = chroma_func([test_code])
        print(f"✅ ChromaDB function returned: {type(result)} with {len(result)} embeddings")
        print(f"✅ First embedding type: {type(result[0])}, length: {len(result[0])}")
        
        if len(result[0]) == 768:
            print("✅ ChromaDB function returns correct 768-d vectors")
        else:
            print(f"❌ ChromaDB function wrong dimension: {len(result[0])}")
            
        # Test health check
        health = await embedding_client.health_check()
        print(f"✅ Health check: {health['status']} - {health.get('dimension', 'unknown')}d")
        
        # Get statistics
        stats = embedding_client.get_statistics()
        print(f"✅ Model: {stats['model_name']} on {stats['device']}")
        
        print("\n🎉 CodeBERT Integration Test PASSED!")
        return True
        
    except Exception as e:
        print(f"❌ CodeBERT Integration Test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_chromadb_connection():
    """Test ChromaDB connection separately."""
    
    print("\n🔌 Testing ChromaDB Connection...")
    
    try:
        import chromadb
        
        # Try to connect to ChromaDB server
        client = chromadb.HttpClient(host="localhost", port=8000)
        
        # Test basic operations
        heartbeat = client.heartbeat()
        print(f"✅ ChromaDB heartbeat: {heartbeat}")
        
        print("✅ ChromaDB Connection Test PASSED!")
        return True
        
    except Exception as e:
        print(f"❌ ChromaDB Connection Test FAILED: {e}")
        return False

async def main():
    """Run all tests."""
    
    print("🚀 Starting GraphRAG Integration Tests\n")
    
    # Test CodeBERT integration
    codebert_ok = await test_codebert_integration()
    
    # Test ChromaDB connection
    chromadb_ok = await test_chromadb_connection()
    
    print(f"\n📊 Test Results:")
    print(f"   CodeBERT Integration: {'✅ PASS' if codebert_ok else '❌ FAIL'}")
    print(f"   ChromaDB Connection:  {'✅ PASS' if chromadb_ok else '❌ FAIL'}")
    
    if codebert_ok and chromadb_ok:
        print("\n🎉 All tests PASSED! System ready for full integration.")
        return 0
    else:
        print("\n💥 Some tests FAILED. Check the errors above.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)