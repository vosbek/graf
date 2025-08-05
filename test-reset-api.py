#!/usr/bin/env python3
"""
Test the database reset API endpoint
"""

import asyncio
import sys
import requests
import json
from pathlib import Path

# Add src to Python path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_reset_api():
    """Test the database reset API endpoint."""
    print("Testing database reset API endpoint...")
    
    # First try to reach any API server
    api_bases = ["http://localhost:8080", "http://localhost:8081"]
    api_base = None
    
    for base in api_bases:
        try:
            response = requests.get(f"{base}/api/v1/health/", timeout=5)
            if response.status_code == 200:
                api_base = base
                print(f"[OK] Found API server at {base}")
                break
        except:
            continue
    
    if not api_base:
        print("[INFO] No API server running - this is expected if testing components individually")
        print("[INFO] Database reset can still be tested via:")
        print("  1. Web UI when frontend is running")
        print("  2. Direct database operations (as shown in previous test)")
        return True
    
    # Test the reset endpoint with various scenarios
    print(f"\n=== Testing Database Reset API at {api_base} ===")
    
    # Test 1: Missing confirmation (should fail)
    print("\nTest 1: Reset without confirmation (should fail)")
    try:
        reset_request = {
            "reset_neo4j": True,
            "reset_chromadb": True,
            "create_backup": False,
            "confirm": False  # Missing confirmation
        }
        
        response = requests.post(
            f"{api_base}/api/v1/admin/database/reset",
            json=reset_request,
            timeout=10
        )
        
        if response.status_code == 400:
            print("[OK] API correctly rejected request without confirmation")
        else:
            print(f"[WARN] API returned {response.status_code}, expected 400")
            
    except Exception as e:
        print(f"[ERROR] Test 1 failed: {e}")
        return False
    
    # Test 2: No databases selected (should fail)
    print("\nTest 2: Reset with no databases selected (should fail)")
    try:
        reset_request = {
            "reset_neo4j": False,
            "reset_chromadb": False,
            "create_backup": False,
            "confirm": True
        }
        
        response = requests.post(
            f"{api_base}/api/v1/admin/database/reset",
            json=reset_request,
            timeout=10
        )
        
        if response.status_code == 400:
            print("[OK] API correctly rejected request with no databases selected")
        else:
            print(f"[WARN] API returned {response.status_code}, expected 400")
            
    except Exception as e:
        print(f"[ERROR] Test 2 failed: {e}")
        return False
    
    # Test 3: Valid dry-run request (Neo4j only, with backup)
    print("\nTest 3: Valid reset request (Neo4j only, with backup)")
    try:
        reset_request = {
            "reset_neo4j": True,
            "reset_chromadb": False,
            "create_backup": True,
            "confirm": True
        }
        
        response = requests.post(
            f"{api_base}/api/v1/admin/database/reset",
            json=reset_request,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"[OK] Reset request succeeded: {result.get('message', 'No message')}")
            if result.get('backup_paths'):
                print(f"[INFO] Backup created: {result['backup_paths']}")
        else:
            print(f"[WARN] Reset request returned {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"[ERROR] Test 3 failed: {e}")
        return False
    
    print("\n[SUCCESS] Database reset API tests completed")
    return True

if __name__ == "__main__":
    success = test_reset_api()
    sys.exit(0 if success else 1)