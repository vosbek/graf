#!/usr/bin/env python3
"""
Script to fix ChromaDB collection issues by force-recreating collections.
"""

import asyncio
import sys
import os
import logging
from pathlib import Path

# Add parent directory to path for imports
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

import chromadb
from src.config.settings import Settings


async def fix_chromadb():
    """Force recreate ChromaDB collections."""
    
    print("Fixing ChromaDB Collection Issues...")
    
    # Initialize settings
    settings = Settings()
    print(f"ChromaDB Host: {settings.chroma_host}")
    print(f"ChromaDB Port: {settings.chroma_port}")
    print(f"ChromaDB Collection: {settings.chroma_collection_name}")
    
    try:
        # Connect directly to ChromaDB
        print("\nConnecting to ChromaDB...")
        client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port
        )
        
        # List all collections
        print("\nListing all collections...")
        collections = client.list_collections()
        print(f"Found {len(collections)} collections:")
        for collection in collections:
            print(f"  - {collection.name} (UUID: {collection.id})")
            
        # Delete all collections with our collection name
        print(f"\nDeleting collections with name '{settings.chroma_collection_name}'...")
        deleted_count = 0
        for collection in collections:
            if collection.name == settings.chroma_collection_name:
                try:
                    client.delete_collection(name=collection.name)
                    print(f"  [SUCCESS] Deleted collection: {collection.name} (UUID: {collection.id})")
                    deleted_count += 1
                except Exception as e:
                    print(f"  [ERROR] Failed to delete collection {collection.name}: {e}")
                    
        if deleted_count == 0:
            print(f"  No collections with name '{settings.chroma_collection_name}' found to delete")
            
        # List collections again to confirm deletion
        print("\nListing collections after deletion...")
        collections = client.list_collections()
        print(f"Found {len(collections)} collections:")
        for collection in collections:
            print(f"  - {collection.name} (UUID: {collection.id})")
            
        # Create a fresh collection
        print(f"\nCreating fresh collection '{settings.chroma_collection_name}'...")
        try:
            from chromadb.utils import embedding_functions
            
            embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
            
            new_collection = client.create_collection(
                name=settings.chroma_collection_name,
                embedding_function=embedding_function,
                metadata={"hnsw:space": "cosine"}
            )
            
            print(f"  [SUCCESS] Created collection: {new_collection.name} (UUID: {new_collection.id})")
            
            # Test the collection
            count = new_collection.count()
            print(f"  [SUCCESS] Collection health check passed. Document count: {count}")
            
        except Exception as e:
            print(f"  [ERROR] Failed to create collection: {e}")
            return False
            
        print("\n[SUCCESS] ChromaDB fix completed!")
        return True
        
    except Exception as e:
        print(f"[ERROR] ChromaDB fix failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main function."""
    print("=" * 60)
    print("ChromaDB Collection Fix Script")
    print("=" * 60)
    
    try:
        success = await fix_chromadb()
        
        if success:
            print("\n[SUCCESS] ChromaDB has been fixed!")
            print("You can now restart the API server.")
            sys.exit(0)
        else:
            print("\n[ERROR] ChromaDB fix failed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\nFix interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())