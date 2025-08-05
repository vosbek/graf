#!/usr/bin/env python3
"""
Database Cleanup Script for Enhanced Codebase Ingestion
========================================================

This script clears Neo4j and ChromaDB databases to enable clean re-indexing
of repositories with the enhanced business relationship extraction.

Usage:
    python scripts/cleanup-databases.py [options]
    
Options:
    --neo4j-only        Clear only Neo4j database
    --chroma-only       Clear only ChromaDB database  
    --confirm           Skip confirmation prompt (dangerous!)
    --backup            Create backup before clearing
    --dry-run           Show what would be deleted without deleting
    
Examples:
    python scripts/cleanup-databases.py                    # Clear both databases (with confirmation)
    python scripts/cleanup-databases.py --backup           # Backup then clear
    python scripts/cleanup-databases.py --neo4j-only       # Clear only Neo4j
    python scripts/cleanup-databases.py --dry-run          # Preview deletions
"""

import asyncio
import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional

# Add src to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    import chromadb
    from chromadb.config import Settings
    from neo4j import AsyncGraphDatabase
    from src.config.settings import get_settings
except ImportError as e:
    print(f"Import error: {e}")
    print("Please ensure you're running from the project root and dependencies are installed.")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseCleaner:
    """Handles cleanup of Neo4j and ChromaDB databases."""
    
    def __init__(self, settings):
        self.settings = settings
        self.neo4j_driver = None
        self.chroma_client = None
        
    async def initialize(self):
        """Initialize database connections."""
        try:
            # Initialize Neo4j
            self.neo4j_driver = AsyncGraphDatabase.driver(
                self.settings.neo4j_uri,
                auth=(self.settings.neo4j_username, self.settings.neo4j_password)
            )
            
            # Test Neo4j connection
            async with self.neo4j_driver.session() as session:
                await session.run("RETURN 1")
            logger.info("✅ Connected to Neo4j")
            
            # Initialize ChromaDB
            self.chroma_client = chromadb.HttpClient(
                host=self.settings.chroma_host,
                port=self.settings.chroma_port,
                settings=Settings(anonymized_telemetry=False)
            )
            
            # Test ChromaDB connection
            self.chroma_client.heartbeat()
            logger.info("✅ Connected to ChromaDB")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize database connections: {e}")
            raise
    
    async def get_neo4j_stats(self) -> Dict[str, Any]:
        """Get Neo4j database statistics."""
        stats = {}
        try:
            async with self.neo4j_driver.session() as session:
                # Count all nodes by label
                result = await session.run("""
                    CALL db.labels() YIELD label
                    CALL apoc.cypher.run('MATCH (n:' + label + ') RETURN count(n) as count', {}) YIELD value
                    RETURN label, value.count as count
                """)
                
                node_counts = {}
                total_nodes = 0
                async for record in result:
                    label = record["label"]
                    count = record["count"]
                    node_counts[label] = count
                    total_nodes += count
                
                # Count all relationships by type
                result = await session.run("""
                    CALL db.relationshipTypes() YIELD relationshipType
                    CALL apoc.cypher.run('MATCH ()-[r:' + relationshipType + ']->() RETURN count(r) as count', {}) YIELD value
                    RETURN relationshipType, value.count as count
                """)
                
                rel_counts = {}
                total_rels = 0
                async for record in result:
                    rel_type = record["relationshipType"]
                    count = record["count"]
                    rel_counts[rel_type] = count
                    total_rels += count
                
                stats = {
                    "total_nodes": total_nodes,
                    "total_relationships": total_rels,
                    "node_counts": node_counts,
                    "relationship_counts": rel_counts
                }
                
        except Exception as e:
            logger.warning(f"Could not get Neo4j stats (APOC may not be available): {e}")
            # Fallback to basic count
            try:
                async with self.neo4j_driver.session() as session:
                    result = await session.run("MATCH (n) RETURN count(n) as total_nodes")
                    record = await result.single()
                    total_nodes = record["total_nodes"]
                    
                    result = await session.run("MATCH ()-[r]->() RETURN count(r) as total_rels")
                    record = await result.single()
                    total_rels = record["total_rels"]
                    
                    stats = {
                        "total_nodes": total_nodes,
                        "total_relationships": total_rels,
                        "node_counts": {"Unknown": total_nodes},
                        "relationship_counts": {"Unknown": total_rels}
                    }
            except Exception as e2:
                logger.error(f"Failed to get basic Neo4j stats: {e2}")
                stats = {"error": str(e2)}
        
        return stats
    
    def get_chroma_stats(self) -> Dict[str, Any]:
        """Get ChromaDB statistics."""
        try:
            collections = self.chroma_client.list_collections()
            stats = {
                "total_collections": len(collections),
                "collections": {}
            }
            
            total_chunks = 0
            for collection in collections:
                try:
                    count = collection.count()
                    stats["collections"][collection.name] = count
                    total_chunks += count
                except Exception as e:
                    logger.warning(f"Could not get count for collection {collection.name}: {e}")
                    stats["collections"][collection.name] = "unknown"
            
            stats["total_chunks"] = total_chunks
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get ChromaDB stats: {e}")
            return {"error": str(e)}
    
    async def backup_neo4j(self, backup_dir: Path) -> Optional[str]:
        """Create Neo4j backup (export to Cypher file)."""
        try:
            backup_file = backup_dir / f"neo4j_backup_{int(time.time())}.cypher"
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Creating Neo4j backup: {backup_file}")
            
            async with self.neo4j_driver.session() as session:
                # Export all nodes and relationships
                result = await session.run("""
                    CALL apoc.export.cypher.all($file, {format: 'plain'})
                    YIELD file, source, format, nodes, relationships, properties, time, rows, batchSize, batches, done
                    RETURN file, nodes, relationships, time
                """, {"file": str(backup_file)})
                
                record = await result.single()
                if record:
                    logger.info(f"✅ Neo4j backup created: {record['nodes']} nodes, {record['relationships']} relationships")
                    return str(backup_file)
                else:
                    logger.warning("⚠️ Neo4j backup may not have completed properly")
                    return str(backup_file)
                    
        except Exception as e:
            logger.error(f"❌ Failed to create Neo4j backup: {e}")
            logger.info("💡 Continuing without backup (APOC export may not be available)")
            return None
    
    def backup_chroma(self, backup_dir: Path) -> Optional[str]:
        """Create ChromaDB backup (export collections)."""
        try:
            backup_file = backup_dir / f"chroma_backup_{int(time.time())}.json"
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Creating ChromaDB backup: {backup_file}")
            
            collections = self.chroma_client.list_collections()
            backup_data = {"collections": {}}
            
            for collection in collections:
                try:
                    # Get all data from collection
                    data = collection.get(include=["documents", "metadatas", "embeddings"])
                    backup_data["collections"][collection.name] = {
                        "ids": data["ids"],
                        "documents": data["documents"],
                        "metadatas": data["metadatas"],
                        "count": len(data["ids"])
                    }
                    # Note: Embeddings are large, skipping for backup size
                    logger.info(f"Backed up collection '{collection.name}': {len(data['ids'])} chunks")
                except Exception as e:
                    logger.warning(f"Failed to backup collection {collection.name}: {e}")
            
            import json
            with open(backup_file, 'w') as f:
                json.dump(backup_data, f, indent=2)
            
            logger.info(f"✅ ChromaDB backup created: {backup_file}")
            return str(backup_file)
            
        except Exception as e:
            logger.error(f"❌ Failed to create ChromaDB backup: {e}")
            return None
    
    async def clear_neo4j(self, dry_run: bool = False) -> Dict[str, Any]:
        """Clear Neo4j database."""
        stats_before = await self.get_neo4j_stats()
        
        if dry_run:
            logger.info("🔍 DRY RUN: Would delete from Neo4j:")
            logger.info(f"  - {stats_before.get('total_nodes', 0)} nodes")
            logger.info(f"  - {stats_before.get('total_relationships', 0)} relationships")
            if 'node_counts' in stats_before:
                for label, count in stats_before['node_counts'].items():
                    logger.info(f"    • {label}: {count} nodes")
            return {"dry_run": True, "stats_before": stats_before}
        
        try:
            async with self.neo4j_driver.session() as session:
                logger.info("🗑️  Clearing Neo4j database...")
                
                # Delete all relationships first
                await session.run("MATCH ()-[r]->() DELETE r")
                logger.info("✅ Deleted all relationships")
                
                # Delete all nodes
                await session.run("MATCH (n) DELETE n")
                logger.info("✅ Deleted all nodes")
                
                # Recreate schema constraints and indexes
                logger.info("🔧 Recreating schema...")
                
                # Import the Neo4j client to get schema creation
                try:
                    from src.core.neo4j_client import Neo4jClient
                    temp_client = Neo4jClient(
                        self.settings.neo4j_uri,
                        self.settings.neo4j_username, 
                        self.settings.neo4j_password
                    )
                    await temp_client.initialize()
                    await temp_client.create_schema()
                    await temp_client.close()
                    logger.info("✅ Schema recreated")
                except Exception as e:
                    logger.warning(f"⚠️ Could not recreate schema automatically: {e}")
                    logger.info("💡 You may need to restart the application to recreate schema")
            
            stats_after = await self.get_neo4j_stats()
            logger.info("✅ Neo4j database cleared successfully")
            
            return {
                "success": True,
                "stats_before": stats_before,
                "stats_after": stats_after
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to clear Neo4j database: {e}")
            return {"success": False, "error": str(e)}
    
    def clear_chroma(self, dry_run: bool = False) -> Dict[str, Any]:
        """Clear ChromaDB database."""
        stats_before = self.get_chroma_stats()
        
        if dry_run:
            logger.info("🔍 DRY RUN: Would delete from ChromaDB:")
            logger.info(f"  - {stats_before.get('total_collections', 0)} collections")
            logger.info(f"  - {stats_before.get('total_chunks', 0)} total chunks")
            if 'collections' in stats_before:
                for name, count in stats_before['collections'].items():
                    logger.info(f"    • {name}: {count} chunks")
            return {"dry_run": True, "stats_before": stats_before}
        
        try:
            logger.info("🗑️  Clearing ChromaDB database...")
            
            collections = self.chroma_client.list_collections()
            deleted_collections = []
            
            for collection in collections:
                try:
                    self.chroma_client.delete_collection(collection.name)
                    deleted_collections.append(collection.name)
                    logger.info(f"✅ Deleted collection: {collection.name}")
                except Exception as e:
                    logger.error(f"❌ Failed to delete collection {collection.name}: {e}")
            
            # Recreate the main collection
            try:
                self.chroma_client.create_collection(
                    name=self.settings.chroma_collection_name,
                    metadata={"description": "Enhanced codebase RAG collection"}
                )
                logger.info(f"✅ Recreated collection: {self.settings.chroma_collection_name}")
            except Exception as e:
                logger.warning(f"⚠️ Could not recreate main collection: {e}")
            
            stats_after = self.get_chroma_stats()
            logger.info("✅ ChromaDB database cleared successfully")
            
            return {
                "success": True,
                "deleted_collections": deleted_collections,
                "stats_before": stats_before,
                "stats_after": stats_after
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to clear ChromaDB database: {e}")
            return {"success": False, "error": str(e)}
    
    async def close(self):
        """Close database connections."""
        if self.neo4j_driver:
            await self.neo4j_driver.close()


async def main():
    parser = argparse.ArgumentParser(
        description="Clear Neo4j and ChromaDB databases for clean re-indexing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument("--neo4j-only", action="store_true", help="Clear only Neo4j database")
    parser.add_argument("--chroma-only", action="store_true", help="Clear only ChromaDB database")
    parser.add_argument("--confirm", action="store_true", help="Skip confirmation prompt (DANGEROUS!)")
    parser.add_argument("--backup", action="store_true", help="Create backup before clearing")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without deleting")
    
    args = parser.parse_args()
    
    # Load settings
    settings = get_settings()
    
    # Initialize cleaner
    cleaner = DatabaseCleaner(settings)
    
    try:
        await cleaner.initialize()
        
        # Get current statistics
        logger.info("📊 Current database statistics:")
        
        neo4j_stats = await cleaner.get_neo4j_stats()
        if not args.chroma_only:
            logger.info(f"Neo4j: {neo4j_stats.get('total_nodes', 0)} nodes, {neo4j_stats.get('total_relationships', 0)} relationships")
        
        chroma_stats = cleaner.get_chroma_stats()
        if not args.neo4j_only:
            logger.info(f"ChromaDB: {chroma_stats.get('total_collections', 0)} collections, {chroma_stats.get('total_chunks', 0)} chunks")
        
        # Confirmation prompt
        if not args.confirm and not args.dry_run:
            print("\n" + "="*60)
            print("⚠️  WARNING: This will permanently delete all data!")
            print("="*60)
            
            if not args.neo4j_only:
                print(f"ChromaDB: {chroma_stats.get('total_chunks', 0)} chunks in {chroma_stats.get('total_collections', 0)} collections")
            if not args.chroma_only:
                print(f"Neo4j: {neo4j_stats.get('total_nodes', 0)} nodes, {neo4j_stats.get('total_relationships', 0)} relationships")
            
            print("\nThis action cannot be undone!")
            if args.backup:
                print("(Backups will be created first)")
            
            response = input("\nAre you sure you want to continue? (type 'yes' to confirm): ")
            if response.lower() != 'yes':
                print("❌ Operation cancelled")
                return
        
        # Create backups if requested
        if args.backup and not args.dry_run:
            backup_dir = Path("backups")
            logger.info("💾 Creating backups...")
            
            if not args.chroma_only:
                await cleaner.backup_neo4j(backup_dir)
            if not args.neo4j_only:
                cleaner.backup_chroma(backup_dir)
        
        # Clear databases
        results = {}
        
        if not args.chroma_only:
            logger.info("\n🗑️  Clearing Neo4j...")
            results["neo4j"] = await cleaner.clear_neo4j(dry_run=args.dry_run)
        
        if not args.neo4j_only:
            logger.info("\n🗑️  Clearing ChromaDB...")
            results["chroma"] = cleaner.clear_chroma(dry_run=args.dry_run)
        
        # Summary
        if args.dry_run:
            logger.info("\n✅ Dry run completed - no data was actually deleted")
        else:
            logger.info("\n✅ Database cleanup completed!")
            logger.info("💡 You can now re-index repositories with the enhanced ingestion pipeline")
        
        return results
        
    except KeyboardInterrupt:
        logger.info("\n❌ Operation cancelled by user")
    except Exception as e:
        logger.error(f"❌ Cleanup failed: {e}")
        raise
    finally:
        await cleaner.close()


if __name__ == "__main__":
    asyncio.run(main())