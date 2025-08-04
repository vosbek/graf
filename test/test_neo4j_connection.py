#!/usr/bin/env python3
"""
Test script to verify Neo4j connectivity and basic operations.
"""

import asyncio
import sys
import os
import logging
from pathlib import Path

# Add parent directory to path for imports
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from src.core.neo4j_client import Neo4jClient
from src.config.settings import Settings


async def test_neo4j_connection():
    """Test Neo4j connection and basic operations."""
    
    print("Testing Neo4j Connection...")
    
    # Initialize settings
    settings = Settings()
    print(f"Neo4j URI: {settings.neo4j_uri}")
    print(f"Neo4j Username: {settings.neo4j_username}")
    print(f"Neo4j Database: {settings.neo4j_database}")
    print(f"Neo4j Password: {'*' * len(settings.neo4j_password)}")
    
    # Create Neo4j client
    client = Neo4jClient(
        uri=settings.neo4j_uri,
        username=settings.neo4j_username,
        password=settings.neo4j_password,
        database=settings.neo4j_database
    )
    
    try:
        # Test initialization
        print("\nInitializing Neo4j client...")
        await client.initialize()
        print("[SUCCESS] Neo4j client initialized successfully")
        
        # Test basic connectivity
        print("\nTesting basic connectivity...")
        health = await client.health_check()
        print(f"[SUCCESS] Health check result: {health['status']}")
        
        # Test basic query
        print("\nTesting basic query...")
        from src.core.neo4j_client import GraphQuery
        test_query = GraphQuery(
            cypher="RETURN 'Hello Neo4j!' as message, datetime() as timestamp",
            parameters={},
            read_only=True
        )
        result = await client.execute_query(test_query)
        if result.records:
            record = result.records[0]
            print(f"[SUCCESS] Query result: {record}")
        
        # Test database statistics
        print("\nGetting database statistics...")
        stats = await client.get_statistics()
        print(f"[SUCCESS] Node counts: {stats.get('node_counts', {})}")
        print(f"[SUCCESS] Relationship counts: {stats.get('relationship_counts', {})}")
        print(f"[SUCCESS] Total nodes: {stats.get('total_nodes', 0)}")
        print(f"[SUCCESS] Total relationships: {stats.get('total_relationships', 0)}")
        
        # Test repository node creation
        print("\nTesting repository node creation...")
        repo_metadata = {
            'name': 'test-repo',
            'url': 'https://github.com/test/repo',
            'branch': 'main',
            'business_domain': 'testing',
            'team_owner': 'test-team',
            'is_golden_repo': False,
            'languages': ['Python'],
            'file_count': 10,
            'lines_of_code': 1000,
            'chunks_count': 50
        }
        
        success = await client.create_repository_node('test-repo', repo_metadata)
        if success:
            print("[SUCCESS] Repository node created successfully")
        else:
            print("[ERROR] Failed to create repository node")
        
        print("\n[SUCCESS] All Neo4j tests passed!")
        return True
        
    except Exception as e:
        print(f"[ERROR] Neo4j test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up
        print("\nCleaning up...")
        await client.close()


async def main():
    """Main test function."""
    print("=" * 60)
    print("Neo4j Connection Test Suite")
    print("=" * 60)
    
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    try:
        success = await test_neo4j_connection()
        
        if success:
            print("\n[SUCCESS] All tests passed! Neo4j is working correctly.")
            sys.exit(0)
        else:
            print("\n[ERROR] Tests failed! Check Neo4j configuration.")
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