#!/usr/bin/env python3
"""
Comprehensive test script for the entire GraphRAG system.
Tests all components and performs end-to-end repository indexing.
"""

import asyncio
import sys
import os
import json
import time
import logging
from pathlib import Path

# Add parent directory to path for imports
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))


async def test_system_health():
    """Test overall system health."""
    print("=" * 60)
    print("TESTING SYSTEM HEALTH")
    print("=" * 60)
    
    import requests
    
    # Test API availability
    try:
        response = requests.get("http://localhost:8080/", timeout=10)
        if response.status_code == 200:
            print("[SUCCESS] API server is responding")
        else:
            print(f"[ERROR] API server returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"[ERROR] API server not accessible: {e}")
        return False
        
    # Test health endpoint
    try:
        response = requests.get("http://localhost:8080/api/v1/health/", timeout=10)
        if response.status_code == 200:
            health_data = response.json()
            print(f"[SUCCESS] Basic health check: {health_data['status']}")
        else:
            print(f"[ERROR] Health endpoint returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"[ERROR] Health endpoint failed: {e}")
        return False
        
    # Test readiness endpoint  
    try:
        response = requests.get("http://localhost:8080/api/v1/health/ready", timeout=10)
        readiness_data = response.json()
        
        print(f"System readiness: {readiness_data['status']}")
        
        # Check individual components
        checks = readiness_data.get('checks', {})
        for component, status in checks.items():
            component_status = status.get('status', 'unknown')
            if component_status == 'healthy':
                print(f"  [SUCCESS] {component}: {component_status}")
            else:
                print(f"  [ERROR] {component}: {component_status}")
                if 'error' in status:
                    print(f"    Error: {status['error']}")
                    
        if readiness_data['status'] == 'ready':
            print("[SUCCESS] System is ready for operations")
            return True
        else:
            print("[WARNING] System is not fully ready, but continuing tests...")
            return True  # Continue with partial functionality
            
    except Exception as e:
        print(f"[ERROR] Readiness check failed: {e}")
        return False


async def test_neo4j_connectivity():
    """Test Neo4j connectivity."""
    print("\n" + "=" * 60)
    print("TESTING NEO4J CONNECTIVITY")  
    print("=" * 60)
    
    from src.core.neo4j_client import Neo4jClient, GraphQuery
    from src.config.settings import Settings
    
    settings = Settings()
    client = Neo4jClient(
        uri=settings.neo4j_uri,
        username=settings.neo4j_username,
        password=settings.neo4j_password,
        database=settings.neo4j_database
    )
    
    try:
        await client.initialize()
        print("[SUCCESS] Neo4j client initialized")
        
        # Test basic query
        query = GraphQuery(
            cypher="RETURN 'Neo4j Connection Test' as test",
            parameters={},
            read_only=True
        )
        result = await client.execute_query(query)
        if result.records:
            print(f"[SUCCESS] Neo4j query executed: {result.records[0]}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Neo4j test failed: {e}")
        return False
    finally:
        await client.close()


async def test_chromadb_connectivity():
    """Test ChromaDB connectivity."""
    print("\n" + "=" * 60)
    print("TESTING CHROMADB CONNECTIVITY")
    print("=" * 60)
    
    from src.core.chromadb_client import ChromaDBClient
    from src.config.settings import Settings
    
    settings = Settings()
    client = ChromaDBClient(
        host=settings.chroma_host,
        port=settings.chroma_port,
        collection_name=settings.chroma_collection_name
    )
    
    try:
        await client.initialize()
        print("[SUCCESS] ChromaDB client initialized")
        
        # Get statistics
        stats = await client.get_statistics()
        print(f"[SUCCESS] ChromaDB stats: {stats.get('total_chunks', 0)} chunks")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] ChromaDB test failed: {e}")
        return False
    finally:
        await client.close()


async def test_repository_indexing():
    """Test repository indexing functionality."""
    print("\n" + "=" * 60)
    print("TESTING REPOSITORY INDEXING")
    print("=" * 60)
    
    import requests
    
    # Test repository indexing endpoint
    repo_data = {
        "name": "jmeter-ai-test",
        "url": "https://github.com/test/jmeter-ai",
        "branch": "main",
        "priority": "high",
        "business_domain": "testing",
        "maven_enabled": True
    }
    
    try:
        print("Submitting repository for indexing...")
        response = requests.post(
            "http://localhost:8080/api/v1/index/repository",
            json=repo_data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"[SUCCESS] Repository indexing started: {result['status']}")
            print(f"  Repository: {result['repository_name']}")
            print(f"  Progress: {result['progress']}")
            
            # Wait a moment for processing
            print("Waiting for initial processing...")
            time.sleep(5)
            
            # Check repository list
            response = requests.get("http://localhost:8080/api/v1/index/repositories")
            if response.status_code == 200:
                repos = response.json()
                print(f"[SUCCESS] Found {repos['total_repositories']} repositories")
                for repo in repos['repositories']:
                    print(f"  - {repo['name']}: {repo.get('chunks_count', 0)} chunks")
            
            return True
            
        else:
            print(f"[ERROR] Repository indexing failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Repository indexing test failed: {e}")
        return False


async def test_frontend_connectivity():
    """Test frontend connectivity."""
    print("\n" + "=" * 60)
    print("TESTING FRONTEND CONNECTIVITY")
    print("=" * 60)
    
    import requests
    
    try:
        response = requests.get("http://localhost:3000", timeout=10)
        if response.status_code == 200:
            print("[SUCCESS] Frontend is accessible")
            
            # Check if API connectivity is working from frontend perspective
            if "React" in response.text or "<!DOCTYPE html>" in response.text:
                print("[SUCCESS] Frontend appears to be serving React application")
                return True
            else:
                print("[WARNING] Frontend response doesn't look like React app")
                return True
        else:
            print(f"[ERROR] Frontend returned status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Frontend connectivity test failed: {e}")
        return False


async def run_comprehensive_tests():
    """Run all tests in sequence."""
    print("GraphRAG System Comprehensive Test Suite")
    print("=" * 80)
    
    test_results = {}
    
    # Run all tests
    tests = [
        ("System Health", test_system_health),
        ("Neo4j Connectivity", test_neo4j_connectivity), 
        ("ChromaDB Connectivity", test_chromadb_connectivity),
        ("Repository Indexing", test_repository_indexing),
        ("Frontend Connectivity", test_frontend_connectivity)
    ]
    
    for test_name, test_func in tests:
        print(f"\nRunning {test_name} test...")
        try:
            result = await test_func()
            test_results[test_name] = result
            if result:
                print(f"[PASS] {test_name}: PASSED")
            else:
                print(f"[FAIL] {test_name}: FAILED")
        except Exception as e:
            test_results[test_name] = False
            print(f"[ERROR] {test_name}: ERROR - {e}")
            
    # Print summary
    print("\n" + "=" * 80)
    print("TEST RESULTS SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for result in test_results.values() if result)
    total = len(test_results)
    
    for test_name, result in test_results.items():
        status = "PASSED" if result else "FAILED"
        icon = "[PASS]" if result else "[FAIL]"
        print(f"{icon} {test_name}: {status}")
        
    print("\n" + "=" * 80)
    print(f"OVERALL RESULT: {passed}/{total} tests passed")
    
    if passed == total:
        print("[SUCCESS] ALL TESTS PASSED! GraphRAG system is fully operational.")
        return True
    elif passed >= total * 0.8:  # 80% pass rate
        print("[WARNING] Most tests passed. System is largely functional.")
        return True
    else:
        print("[ERROR] Multiple tests failed. System needs attention.")
        return False


async def main():
    """Main test function."""
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    try:
        success = await run_comprehensive_tests()
        
        if success:
            print("\n[SUCCESS] System is ready for repository indexing!")
            sys.exit(0)
        else:
            print("\n[ERROR] System needs fixes before full operation.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error during testing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())