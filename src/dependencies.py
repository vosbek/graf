"""
Enhanced Dependency Injection for FastAPI routes with v2.0 support.
"""

from fastapi import HTTPException
from typing import Optional, Union

# Import only non-heavy modules at startup
from .core.neo4j_client import Neo4jClient
# ChromaDB, embedding, and processor imports will be done dynamically

# Global clients - will be set by main.py during startup
chroma_client: Optional[object] = None  # ChromaDBClient
neo4j_client: Optional[Neo4jClient] = None
repository_processor: Optional[object] = None  # RepositoryProcessor or EnhancedRepositoryProcessor
embedding_client: Optional[object] = None  # AsyncEnhancedEmbeddingClient
oracle_client: Optional[object] = None  # OracleDBClient
oracle_analyzer: Optional[object] = None  # OracleDatabaseAnalyzer

# Configuration flags
use_enhanced_processor: bool = True  # Switch to v2.0 processor
use_codebert: bool = True  # Use CodeBERT embeddings


def set_clients(chroma: object,  # ChromaDBClient
                neo4j: Neo4jClient, 
                repo_processor: object,  # RepositoryProcessor or EnhancedRepositoryProcessor
                embedding: Optional[object] = None,  # AsyncEnhancedEmbeddingClient
                oracle: Optional[object] = None,  # OracleDBClient
                oracle_analyzer_instance: Optional[object] = None):  # OracleDatabaseAnalyzer
    """Set the global client instances."""
    global chroma_client, neo4j_client, repository_processor, embedding_client, oracle_client, oracle_analyzer
    chroma_client = chroma
    neo4j_client = neo4j
    repository_processor = repo_processor
    embedding_client = embedding
    oracle_client = oracle
    oracle_analyzer = oracle_analyzer_instance


def get_chroma_client() -> object:  # ChromaDBClient
    """Get ChromaDB client."""
    if not chroma_client:
        raise HTTPException(status_code=503, detail="ChromaDB client not initialized")
    return chroma_client


def get_neo4j_client() -> Neo4jClient:
    """Get Neo4j client."""
    if not neo4j_client:
        raise HTTPException(status_code=503, detail="Neo4j client not initialized")
    return neo4j_client


def get_repository_processor() -> object:  # RepositoryProcessor or EnhancedRepositoryProcessor
    """Get repository processor (v1 or v2)."""
    if not repository_processor:
        raise HTTPException(status_code=503, detail="Repository processor not initialized")
    return repository_processor


def get_embedding_client() -> object:  # AsyncEnhancedEmbeddingClient
    """Get enhanced embedding client."""
    if not embedding_client:
        raise HTTPException(status_code=503, detail="Embedding client not initialized")
    return embedding_client


def get_oracle_client() -> object:  # OracleDBClient
    """Get Oracle database client."""
    if not oracle_client:
        raise HTTPException(status_code=503, detail="Oracle client not initialized")
    return oracle_client


def get_oracle_analyzer() -> object:  # OracleDatabaseAnalyzer
    """Get Oracle database analyzer."""
    if not oracle_analyzer:
        raise HTTPException(status_code=503, detail="Oracle analyzer not initialized")
    return oracle_analyzer


def create_enhanced_clients() -> tuple[object, object]:  # (AsyncEnhancedEmbeddingClient, EnhancedRepositoryProcessor)
    """
    Factory function to create enhanced v2.0 clients.
    
    Returns:
        tuple: (embedding_client, repository_processor)
    """
    # NOTE: This function requires dynamic imports to avoid blocking startup
    # It should only be called after the main app has initialized
    raise RuntimeError("create_enhanced_clients is deprecated - use main.py initialization instead")


def get_system_info() -> dict:
    """Get system information about loaded components."""
    # Safe stats collection - don't call methods that might block
    embedding_stats = None
    if embedding_client:
        try:
            # Only get basic stats that are safe to access
            embedding_stats = {
                "model_type": getattr(embedding_client.config, 'model_type', 'unknown'),
                "model_name": getattr(embedding_client.config, 'model_name', 'unknown'),
                "dimension": getattr(embedding_client.config, 'dimension', 768),
                "device": getattr(embedding_client.config, 'device', 'cpu'),
                "total_requests": getattr(embedding_client, 'total_requests', 0),
                "cache_hits": getattr(embedding_client, 'cache_hits', 0),
                "cache_hit_rate": getattr(embedding_client, 'cache_hits', 0) / max(getattr(embedding_client, 'total_requests', 1), 1) * 100.0,
                "cache_size": len(getattr(embedding_client, 'embedding_cache', {})),
                "average_embedding_time": getattr(embedding_client, 'total_embedding_time', 0.0) / max(getattr(embedding_client, 'total_requests', 1), 1),
                "total_embedding_time": getattr(embedding_client, 'total_embedding_time', 0.0)
            }
        except Exception:
            embedding_stats = {"status": "stats_unavailable"}
    
    return {
        'chroma_client_loaded': chroma_client is not None,
        'neo4j_client_loaded': neo4j_client is not None,
        'repository_processor_loaded': repository_processor is not None,
        'embedding_client_loaded': embedding_client is not None,
        'oracle_client_loaded': oracle_client is not None,
        'oracle_analyzer_loaded': oracle_analyzer is not None,
        'oracle_enabled': oracle_client.enabled if oracle_client else False,
        'processor_type': 'enhanced_v2' if (repository_processor and 'EnhancedRepositoryProcessor' in str(type(repository_processor))) else 'legacy_v1',
        'use_enhanced_processor': use_enhanced_processor,
        'use_codebert': use_codebert,
        'embedding_stats': embedding_stats
    }