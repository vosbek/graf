#!/usr/bin/env python3
"""
Test script to verify CodeBERT setup and dependencies.
Run this after installing requirements to ensure everything works.
"""

import sys
import asyncio
from pathlib import Path

def test_imports():
    """Test that all required packages can be imported."""
    print("Testing imports...")
    
    try:
        import torch
        import transformers
        import numpy as np
        import fastapi
        import uvicorn
        import pydantic
        import chromadb
        import neo4j
        print("[OK] All core packages imported successfully")
        return True
    except Exception as e:
        print(f"[ERROR] Import failed: {e}")
        return False

def test_codebert():
    """Test CodeBERT model loading and embedding generation."""
    print("Testing CodeBERT...")
    
    try:
        from transformers import AutoModel, AutoTokenizer
        import torch
        
        model_name = "microsoft/codebert-base"
        print(f"Loading {model_name}...")
        
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModel.from_pretrained(model_name)
        
        # Test embedding generation
        test_code = "def fibonacci(n): return n if n <= 1 else fibonacci(n-1) + fibonacci(n-2)"
        inputs = tokenizer(test_code, return_tensors="pt", padding=True, truncation=True)
        
        with torch.no_grad():
            outputs = model(**inputs)
            embedding = outputs.last_hidden_state[:, 0, :].numpy()
        
        print(f"[OK] Generated embedding with shape: {embedding.shape}")
        print(f"[OK] Embedding dimension: {embedding.shape[1]} (expected: 768)")
        
        assert embedding.shape[1] == 768, f"Expected 768 dimensions, got {embedding.shape[1]}"
        return True
        
    except Exception as e:
        print(f"[ERROR] CodeBERT test failed: {e}")
        return False

def test_app_config():
    """Test application configuration."""
    print("Testing app configuration...")
    
    try:
        # Add src to path
        sys.path.insert(0, str(Path(__file__).parent / "src"))
        
        from config.settings import settings
        from core.embedding_config import EmbeddingConfig, AsyncEnhancedEmbeddingClient
        
        print(f"[OK] Embedding model: {settings.embedding_model}")
        print(f"[OK] Embedding dimension: {settings.embedding_dimension}")
        print(f"[OK] Neo4j URI: {settings.neo4j_uri}")
        print(f"[OK] ChromaDB host: {settings.chroma_host}:{settings.chroma_port}")
        
        # Test embedding config
        config = EmbeddingConfig()
        print(f"[OK] EmbeddingConfig created with model: {config.model_name}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] App config test failed: {e}")
        return False

async def test_async_embedding():
    """Test async embedding client."""
    print("Testing async embedding client...")
    
    try:
        sys.path.insert(0, str(Path(__file__).parent / "src"))
        
        from core.embedding_config import AsyncEnhancedEmbeddingClient, EmbeddingConfig
        
        config = EmbeddingConfig(lazy_init=True)
        client = AsyncEnhancedEmbeddingClient(config)
        
        # Test health check
        health = await client.health_check()
        print(f"[OK] Health check status: {health.get('status', 'unknown')}")
        
        # Test embedding generation
        test_code = "class Example: pass"
        embedding = await client.encode(test_code)
        
        print(f"[OK] Async embedding generated with shape: {embedding.shape}")
        # Single text input returns 1D array of 768 dimensions
        if len(embedding.shape) == 1:
            assert embedding.shape[0] == 768, f"Expected 768 dimensions, got {embedding.shape[0]}"
        else:
            assert embedding.shape[1] == 768, f"Expected 768 dimensions, got {embedding.shape[1]}"
        
        # Cleanup
        client.close()
        return True
        
    except Exception as e:
        print(f"[ERROR] Async embedding test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 50)
    print("CodeBERT Setup Verification")
    print("=" * 50)
    
    tests = [
        ("Imports", test_imports),
        ("CodeBERT", test_codebert),
        ("App Config", test_app_config),
    ]
    
    passed = 0
    total = len(tests)
    
    for name, test_func in tests:
        print(f"\n--- {name} Test ---")
        try:
            if test_func():
                print(f"[PASS] {name} test completed successfully")
                passed += 1
            else:
                print(f"[FAIL] {name} test failed")
        except Exception as e:
            print(f"[FAIL] {name} test failed with exception: {e}")
    
    # Test async functionality
    print(f"\n--- Async Embedding Test ---")
    try:
        if asyncio.run(test_async_embedding()):
            print("[PASS] Async embedding test completed successfully")
            passed += 1
            total += 1
        else:
            print("[FAIL] Async embedding test failed")
            total += 1
    except Exception as e:
        print(f"[FAIL] Async embedding test failed with exception: {e}")
        total += 1
    
    print("\n" + "=" * 50)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("[SUCCESS] All tests passed! Your CodeBERT setup is ready.")
        return 0
    else:
        print("[WARNING] Some tests failed. Check the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())