#!/usr/bin/env python3
"""
MVP Verification Script
Tests all critical components to ensure they'll work before starting the full application.
"""

import os
import sys
import asyncio
import logging
import traceback
from pathlib import Path

# Add MVP directory to path
mvp_path = Path(__file__).parent / "mvp"
sys.path.insert(0, str(mvp_path))

# Test results
test_results = []

def test_result(name: str, success: bool, error: str = None):
    """Record a test result."""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} {name}")
    if error and not success:
        print(f"   Error: {error}")
    test_results.append((name, success, error))

def test_imports():
    """Test all critical imports."""
    print("\n🧪 Testing Critical Imports...")
    
    try:
        import main
        test_result("FastAPI main module", True)
    except Exception as e:
        test_result("FastAPI main module", False, str(e))
    
    try:
        from indexer import CodebaseIndexer
        test_result("CodebaseIndexer import", True)
    except Exception as e:
        test_result("CodebaseIndexer import", False, str(e))
    
    try:
        from search import CodebaseSearch  
        test_result("CodebaseSearch import", True)
    except Exception as e:
        test_result("CodebaseSearch import", False, str(e))
    
    try:
        from neo4j_client import Neo4jClient
        test_result("Neo4jClient import", True)
    except Exception as e:
        test_result("Neo4jClient import", False, str(e))
    
    try:
        from struts_parser import StrutsParser
        test_result("StrutsParser import", True)
    except Exception as e:
        test_result("StrutsParser import", False, str(e))

    try:
        from agents.struts_agent import StrutsMigrationAgent, AgentService
        test_result("AI Agent import", True)
    except Exception as e:
        test_result("AI Agent import", False, str(e))

def test_dependencies():
    """Test external dependencies."""
    print("\n🧪 Testing External Dependencies...")
    
    # Test ChromaDB
    try:
        import chromadb
        test_result("ChromaDB", True)
    except Exception as e:
        test_result("ChromaDB", False, str(e))
    
    # Test Neo4j
    try:
        import neo4j
        test_result("Neo4j Driver", True)
    except Exception as e:
        test_result("Neo4j Driver", False, str(e))
    
    # Test FastAPI
    try:
        import fastapi
        import uvicorn
        test_result("FastAPI/Uvicorn", True)
    except Exception as e:
        test_result("FastAPI/Uvicorn", False, str(e))
    
    # Test AI Agent (optional)
    try:
        import strands
        test_result("AWS Strands (Optional)", True)
    except Exception as e:
        test_result("AWS Strands (Optional - Fallback Available)", True, "Will use fallback mode")
    
    # Test other critical deps
    for dep in ['pandas', 'numpy', 'sentence_transformers']:
        try:
            __import__(dep)
            test_result(dep, True)
        except Exception as e:
            test_result(dep, False, str(e))

async def test_component_initialization():
    """Test component initialization without connections."""
    print("\n🧪 Testing Component Initialization...")
    
    try:
        from neo4j_client import Neo4jClient
        client = Neo4jClient("bolt://localhost:7687", "neo4j", "test")
        test_result("Neo4jClient creation", True)
    except Exception as e:
        test_result("Neo4jClient creation", False, str(e))
    
    try:
        from struts_parser import StrutsParser
        parser = StrutsParser()
        test_result("StrutsParser creation", True)
    except Exception as e:
        test_result("StrutsParser creation", False, str(e))
    
    try:
        from agents.struts_agent import StrutsMigrationAgent
        # Try to create agent (might fail on AWS but should not crash)
        agent = StrutsMigrationAgent(None, None, None)
        test_result("AI Agent creation", True)
    except Exception as e:
        test_result("AI Agent creation", False, str(e))

def test_frontend_build_requirements():
    """Test frontend build requirements."""
    print("\n🧪 Testing Frontend Build Requirements...")
    
    frontend_path = Path(__file__).parent / "frontend"
    
    # Check if package.json exists
    package_json = frontend_path / "package.json"
    test_result("Frontend package.json exists", package_json.exists())
    
    # Check if public directory exists
    public_dir = frontend_path / "public"
    test_result("Frontend public directory", public_dir.exists())
    
    # Check if src directory exists  
    src_dir = frontend_path / "src"
    test_result("Frontend src directory", src_dir.exists())
    
    # Check critical frontend files
    critical_files = [
        "src/App.js",
        "src/index.js", 
        "src/services/ApiService.js",
        "src/components/Dashboard.js"
    ]
    
    for file_path in critical_files:
        full_path = frontend_path / file_path
        test_result(f"Frontend {file_path}", full_path.exists())

def check_environment():
    """Check environment setup."""
    print("\n🧪 Testing Environment Setup...")
    
    # Check Python version
    python_version = sys.version_info
    python_ok = python_version >= (3, 8)
    test_result(f"Python {python_version.major}.{python_version.minor}", python_ok, 
                "Need Python 3.8+" if not python_ok else None)
    
    # Check environment variables (optional)
    env_vars = [
        ("CHROMA_HOST", "localhost"),
        ("NEO4J_URI", "bolt://localhost:7687"),
        ("REPOS_PATH", "./data/repositories")
    ]
    
    for var, default in env_vars:
        value = os.getenv(var, default)
        test_result(f"Environment {var}", True, f"Using: {value}")

def print_summary():
    """Print test summary."""
    print("\n" + "="*60)
    print("🎯 MVP VERIFICATION SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, success, _ in test_results if success)
    total = len(test_results)
    
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED - MVP is ready to run!")
        print("\nNext steps:")
        print("1. ./start-mvp-with-ui.sh")
        print("2. Open http://localhost:8080") 
        print("3. Index some repositories")
        print("4. Start analyzing!")
    else:
        print(f"\n⚠️  {total - passed} issues found - check errors above")
        print("\nCritical failures will prevent startup:")
        
        for name, success, error in test_results:
            if not success and "Optional" not in name:
                print(f"  ❌ {name}: {error}")

def main():
    """Run all verification tests."""
    print("🚀 Starting MVP Verification...")
    print("This will test all components without starting services.")
    
    try:
        check_environment()
        test_dependencies() 
        test_imports()
        asyncio.run(test_component_initialization())
        test_frontend_build_requirements()
        print_summary()
        
        # Return exit code
        failed = any(not success for name, success, _ in test_results if "Optional" not in (name or ""))
        return 0 if not failed else 1
        
    except Exception as e:
        print(f"\n💥 Verification failed with exception: {e}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())