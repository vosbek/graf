"""
ChromaDB client with semantic search optimization for codebase RAG.
Implements high-performance vector search with intelligent chunking and metadata filtering.
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Tuple, Union, Any
from dataclasses import dataclass, field
from contextlib import asynccontextmanager

import chromadb
import numpy as np
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer

from ..processing.code_chunker import EnhancedChunk
from ..processing.tree_sitter_parser import SupportedLanguage


@dataclass
class SearchResult:
    """Result from semantic search."""
    chunk_id: str
    content: str
    score: float
    metadata: Dict[str, Any]
    language: str
    chunk_type: str
    name: Optional[str] = None
    file_path: Optional[str] = None
    business_domain: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'chunk_id': self.chunk_id,
            'content': self.content,
            'score': self.score,
            'metadata': self.metadata,
            'language': self.language,
            'chunk_type': self.chunk_type,
            'name': self.name,
            'file_path': self.file_path,
            'business_domain': self.business_domain
        }


@dataclass
class SearchQuery:
    """Search query with filters and parameters."""
    query: str
    filters: Dict[str, Any] = field(default_factory=dict)
    limit: int = 10
    min_score: float = 0.0
    include_metadata: bool = True
    repository_filter: Optional[str] = None
    language_filter: Optional[str] = None
    domain_filter: Optional[str] = None
    chunk_type_filter: Optional[str] = None


@dataclass
class EmbeddingConfig:
    """Configuration for embedding generation."""
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    dimension: int = 384
    batch_size: int = 32
    max_length: int = 512
    normalize_embeddings: bool = True
    device: str = "cpu"


class ChromaDBClient:
    """High-performance ChromaDB client with semantic search optimization."""
    
    def __init__(self, 
                 host: str = "localhost",
                 port: int = 8000,
                 embedding_config: EmbeddingConfig = None,
                 collection_name: str = "codebase_chunks"):
        
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.embedding_config = embedding_config or EmbeddingConfig()
        
        # Initialize logging
        self.logger = logging.getLogger(__name__)
        
        # Initialize client and embedding model
        self.client = None
        self.collection = None
        self.embedding_model = None
        
        # Performance metrics
        self.query_count = 0
        self.total_query_time = 0.0
        self.cache_hits = 0
        
        # Query cache
        self.query_cache: Dict[str, Tuple[List[SearchResult], float]] = {}
        self.cache_ttl = 300  # 5 minutes
        
        # Batch processing
        self.batch_queue = []
        self.batch_size = 100
        
    async def initialize(self):
        """Initialize ChromaDB client and embedding model."""
        try:
            # Initialize ChromaDB client
            self.client = chromadb.HttpClient(
                host=self.host,
                port=self.port,
                settings=Settings(
                    chroma_db_impl="duckdb+parquet",
                    persist_directory="./data/chroma",
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Initialize embedding model
            self.embedding_model = SentenceTransformer(
                self.embedding_config.model_name,
                device=self.embedding_config.device
            )
            
            # Create or get collection
            self.collection = await self._get_or_create_collection()
            
            self.logger.info(f"ChromaDB client initialized successfully with {self.collection.count()} documents")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize ChromaDB client: {e}")
            raise
    
    async def _get_or_create_collection(self):
        """Get or create ChromaDB collection with optimized settings."""
        try:
            # Try to get existing collection
            collection = self.client.get_collection(
                name=self.collection_name,
                embedding_function=self._get_embedding_function()
            )
            
            self.logger.info(f"Retrieved existing collection: {self.collection_name}")
            return collection
            
        except Exception:
            # Create new collection
            collection = self.client.create_collection(
                name=self.collection_name,
                embedding_function=self._get_embedding_function(),
                metadata={
                    "hnsw:space": "cosine",
                    "hnsw:M": 32,  # Higher M for better recall
                    "hnsw:ef_construction": 400,  # Higher ef for better quality
                    "hnsw:ef_search": 200,  # Balanced search performance
                    "hnsw:batch_size": 1000,
                    "hnsw:num_threads": 4
                }
            )
            
            self.logger.info(f"Created new collection: {self.collection_name}")
            return collection
    
    def _get_embedding_function(self):
        """Get embedding function for ChromaDB."""
        return embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=self.embedding_config.model_name,
            device=self.embedding_config.device,
            normalize_embeddings=self.embedding_config.normalize_embeddings
        )
    
    async def add_chunks(self, chunks: List[EnhancedChunk], repository_name: str) -> bool:
        """Add enhanced chunks to ChromaDB."""
        try:
            if not chunks:
                return True
            
            # Prepare data for ChromaDB
            ids = []
            documents = []
            metadatas = []
            
            for chunk in chunks:
                # Create unique ID
                chunk_id = f"{repository_name}:{chunk.chunk.id}"
                ids.append(chunk_id)
                
                # Prepare document for embedding
                document = self._prepare_document_for_embedding(chunk)
                documents.append(document)
                
                # Prepare metadata
                metadata = self._prepare_metadata(chunk, repository_name)
                metadatas.append(metadata)
            
            # Add to collection in batches
            batch_size = self.batch_size
            for i in range(0, len(ids), batch_size):
                batch_ids = ids[i:i + batch_size]
                batch_docs = documents[i:i + batch_size]
                batch_metadata = metadatas[i:i + batch_size]
                
                await self._add_batch(batch_ids, batch_docs, batch_metadata)
            
            self.logger.info(f"Added {len(chunks)} chunks from repository {repository_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to add chunks: {e}")
            return False
    
    async def _add_batch(self, ids: List[str], documents: List[str], metadatas: List[Dict]):
        """Add a batch of documents to ChromaDB."""
        try:
            self.collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
        except Exception as e:
            self.logger.error(f"Failed to add batch: {e}")
            raise
    
    def _prepare_document_for_embedding(self, chunk: EnhancedChunk) -> str:
        """Prepare document content for optimal embedding."""
        parts = []
        
        # Add chunk type and name
        if chunk.chunk.name:
            parts.append(f"{chunk.chunk.chunk_type}: {chunk.chunk.name}")
        else:
            parts.append(f"{chunk.chunk.chunk_type}")
        
        # Add business domain
        if chunk.business_domain:
            parts.append(f"Domain: {chunk.business_domain}")
        
        # Add docstring if available
        if chunk.chunk.docstring:
            parts.append(f"Documentation: {chunk.chunk.docstring}")
        
        # Add context (limited to avoid overwhelming the embedding)
        if chunk.context_before:
            context_lines = chunk.context_before.split('\n')[-2:]  # Last 2 lines
            if context_lines:
                parts.append(f"Context: {' '.join(context_lines)}")
        
        # Add main content (truncated if too long)
        content = chunk.chunk.content
        max_content_length = self.embedding_config.max_length - len('\n'.join(parts)) - 100
        if len(content) > max_content_length:
            content = content[:max_content_length] + "..."
        
        parts.append(f"Code: {content}")
        
        # Add imports if relevant
        if chunk.chunk.imports:
            imports_str = ', '.join(chunk.chunk.imports[:5])  # Limit to first 5 imports
            parts.append(f"Imports: {imports_str}")
        
        return '\n'.join(parts)
    
    def _prepare_metadata(self, chunk: EnhancedChunk, repository_name: str) -> Dict[str, Any]:
        """Prepare metadata for ChromaDB storage."""
        metadata = {
            # Basic chunk information
            'repository': repository_name,
            'chunk_id': chunk.chunk.id,
            'chunk_type': chunk.chunk.chunk_type,
            'language': chunk.chunk.language.value,
            'name': chunk.chunk.name or "",
            'file_path': chunk.chunk.id.split(':')[0] if ':' in chunk.chunk.id else "",
            
            # Location information
            'start_line': chunk.chunk.start_line,
            'end_line': chunk.chunk.end_line,
            'line_count': chunk.chunk.end_line - chunk.chunk.start_line + 1,
            
            # Quality metrics
            'complexity_score': chunk.chunk.complexity_score,
            'importance_score': chunk.importance_score,
            'has_docstring': chunk.chunk.docstring is not None,
            
            # Business context
            'business_domain': chunk.business_domain or "",
            
            # Content features
            'has_error_handling': 'try' in chunk.chunk.content.lower() or 'catch' in chunk.chunk.content.lower(),
            'has_async': 'async' in chunk.chunk.content.lower() or 'await' in chunk.chunk.content.lower(),
            'has_database': any(keyword in chunk.chunk.content.lower() for keyword in ['query', 'select', 'insert', 'update', 'delete']),
            'has_api': any(keyword in chunk.chunk.content.lower() for keyword in ['request', 'response', 'http', 'api']),
            
            # Relationships
            'has_dependencies': len(chunk.chunk.dependencies) > 0,
            'related_chunks_count': len(chunk.related_chunks),
            
            # Timestamp
            'indexed_at': int(time.time())
        }
        
        # Add import information
        if chunk.chunk.imports:
            metadata['imports'] = json.dumps(chunk.chunk.imports[:10])  # Store first 10 imports
        
        # Add annotations if available
        if chunk.chunk.annotations:
            metadata['annotations'] = json.dumps(chunk.chunk.annotations)
        
        return metadata
    
    async def search(self, query: SearchQuery) -> List[SearchResult]:
        """Perform semantic search with optimization."""
        start_time = time.time()
        
        try:
            # Check cache first
            cache_key = self._generate_cache_key(query)
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                self.cache_hits += 1
                return cached_result
            
            # Build ChromaDB query
            chroma_query = await self._build_chroma_query(query)
            
            # Execute search
            results = self.collection.query(**chroma_query)
            
            # Process results
            search_results = self._process_search_results(results, query)
            
            # Cache results
            self._cache_result(cache_key, search_results)
            
            # Update metrics
            query_time = time.time() - start_time
            self.query_count += 1
            self.total_query_time += query_time
            
            self.logger.debug(f"Search completed in {query_time:.3f}s, found {len(search_results)} results")
            
            return search_results
            
        except Exception as e:
            self.logger.error(f"Search failed: {e}")
            raise
    
    async def _build_chroma_query(self, query: SearchQuery) -> Dict[str, Any]:
        """Build ChromaDB query parameters."""
        chroma_query = {
            'query_texts': [query.query],
            'n_results': query.limit,
            'include': ['documents', 'metadatas', 'distances'] if query.include_metadata else ['documents', 'distances']
        }
        
        # Build where clause from filters
        where_clause = {}
        
        if query.repository_filter:
            where_clause['repository'] = query.repository_filter
        
        if query.language_filter:
            where_clause['language'] = query.language_filter
        
        if query.domain_filter:
            where_clause['business_domain'] = query.domain_filter
        
        if query.chunk_type_filter:
            where_clause['chunk_type'] = query.chunk_type_filter
        
        # Add custom filters
        for key, value in query.filters.items():
            where_clause[key] = value
        
        if where_clause:
            chroma_query['where'] = where_clause
        
        return chroma_query
    
    def _process_search_results(self, results: Dict, query: SearchQuery) -> List[SearchResult]:
        """Process ChromaDB results into SearchResult objects."""
        search_results = []
        
        if not results['ids'] or not results['ids'][0]:
            return search_results
        
        ids = results['ids'][0]
        documents = results['documents'][0]
        distances = results['distances'][0]
        metadatas = results.get('metadatas', [[]])[0]
        
        for i, chunk_id in enumerate(ids):
            # Calculate similarity score (ChromaDB returns distances, we want similarity)
            distance = distances[i]
            score = max(0.0, 1.0 - distance)  # Convert distance to similarity
            
            # Skip results below minimum score
            if score < query.min_score:
                continue
            
            # Extract metadata
            metadata = metadatas[i] if metadatas and i < len(metadatas) else {}
            
            # Create search result
            search_result = SearchResult(
                chunk_id=chunk_id,
                content=documents[i],
                score=score,
                metadata=metadata,
                language=metadata.get('language', 'unknown'),
                chunk_type=metadata.get('chunk_type', 'unknown'),
                name=metadata.get('name'),
                file_path=metadata.get('file_path'),
                business_domain=metadata.get('business_domain')
            )
            
            search_results.append(search_result)
        
        return search_results
    
    def _generate_cache_key(self, query: SearchQuery) -> str:
        """Generate cache key for query."""
        key_parts = [
            query.query,
            str(query.limit),
            str(query.min_score),
            query.repository_filter or "",
            query.language_filter or "",
            query.domain_filter or "",
            query.chunk_type_filter or "",
            json.dumps(query.filters, sort_keys=True)
        ]
        
        return hashlib.md5('|'.join(key_parts).encode()).hexdigest()
    
    def _get_cached_result(self, cache_key: str) -> Optional[List[SearchResult]]:
        """Get cached search result if valid."""
        if cache_key in self.query_cache:
            results, timestamp = self.query_cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                return results
            else:
                # Remove expired cache entry
                del self.query_cache[cache_key]
        
        return None
    
    def _cache_result(self, cache_key: str, results: List[SearchResult]):
        """Cache search results."""
        self.query_cache[cache_key] = (results, time.time())
        
        # Simple cache cleanup - remove oldest entries if cache is too large
        if len(self.query_cache) > 1000:
            oldest_key = min(self.query_cache.keys(), key=lambda k: self.query_cache[k][1])
            del self.query_cache[oldest_key]
    
    async def update_chunk(self, chunk: EnhancedChunk, repository_name: str) -> bool:
        """Update an existing chunk in ChromaDB."""
        try:
            chunk_id = f"{repository_name}:{chunk.chunk.id}"
            
            # Check if chunk exists
            try:
                existing = self.collection.get(ids=[chunk_id])
                if not existing['ids']:
                    # Chunk doesn't exist, add it
                    return await self.add_chunks([chunk], repository_name)
            except Exception:
                # Chunk doesn't exist, add it
                return await self.add_chunks([chunk], repository_name)
            
            # Update existing chunk
            document = self._prepare_document_for_embedding(chunk)
            metadata = self._prepare_metadata(chunk, repository_name)
            
            self.collection.update(
                ids=[chunk_id],
                documents=[document],
                metadatas=[metadata]
            )
            
            self.logger.debug(f"Updated chunk {chunk_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update chunk: {e}")
            return False
    
    async def delete_chunks(self, chunk_ids: List[str], repository_name: str) -> bool:
        """Delete chunks from ChromaDB."""
        try:
            # Prefix chunk IDs with repository name
            full_ids = [f"{repository_name}:{chunk_id}" for chunk_id in chunk_ids]
            
            # Delete in batches
            batch_size = 100
            for i in range(0, len(full_ids), batch_size):
                batch_ids = full_ids[i:i + batch_size]
                
                try:
                    self.collection.delete(ids=batch_ids)
                except Exception as e:
                    self.logger.warning(f"Failed to delete batch {i//batch_size + 1}: {e}")
            
            self.logger.info(f"Deleted {len(chunk_ids)} chunks from repository {repository_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete chunks: {e}")
            return False
    
    async def delete_repository(self, repository_name: str) -> bool:
        """Delete all chunks from a repository."""
        try:
            # Query all chunks for this repository
            results = self.collection.get(
                where={'repository': repository_name},
                include=['documents']
            )
            
            if results['ids']:
                self.collection.delete(ids=results['ids'])
                self.logger.info(f"Deleted {len(results['ids'])} chunks from repository {repository_name}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete repository {repository_name}: {e}")
            return False
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get ChromaDB statistics."""
        try:
            total_count = self.collection.count()
            
            # Get repository distribution
            all_metadata = self.collection.get(include=['metadatas'])
            repository_counts = {}
            language_counts = {}
            domain_counts = {}
            
            for metadata in all_metadata.get('metadatas', []):
                if metadata:
                    repo = metadata.get('repository', 'unknown')
                    repository_counts[repo] = repository_counts.get(repo, 0) + 1
                    
                    lang = metadata.get('language', 'unknown')
                    language_counts[lang] = language_counts.get(lang, 0) + 1
                    
                    domain = metadata.get('business_domain', 'unknown')
                    if domain:
                        domain_counts[domain] = domain_counts.get(domain, 0) + 1
            
            # Calculate performance metrics
            avg_query_time = self.total_query_time / max(self.query_count, 1)
            cache_hit_rate = self.cache_hits / max(self.query_count, 1)
            
            return {
                'total_chunks': total_count,
                'repository_distribution': repository_counts,
                'language_distribution': language_counts,
                'domain_distribution': domain_counts,
                'performance_metrics': {
                    'total_queries': self.query_count,
                    'average_query_time': avg_query_time,
                    'cache_hit_rate': cache_hit_rate,
                    'cache_size': len(self.query_cache)
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get statistics: {e}")
            return {}
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on ChromaDB."""
        health = {
            'status': 'healthy',
            'timestamp': time.time(),
            'checks': {}
        }
        
        try:
            # Check collection access
            count = self.collection.count()
            health['checks']['collection_access'] = {
                'status': 'pass',
                'document_count': count
            }
            
            # Check embedding model
            test_embedding = self.embedding_model.encode("test")
            health['checks']['embedding_model'] = {
                'status': 'pass',
                'dimension': len(test_embedding),
                'model_name': self.embedding_config.model_name
            }
            
            # Check query performance
            start_time = time.time()
            test_query = SearchQuery(query="test", limit=1)
            await self.search(test_query)
            query_time = time.time() - start_time
            
            health['checks']['query_performance'] = {
                'status': 'pass' if query_time < 1.0 else 'warn',
                'query_time': query_time
            }
            
        except Exception as e:
            health['status'] = 'unhealthy'
            health['error'] = str(e)
            self.logger.error(f"Health check failed: {e}")
        
        return health
    
    async def optimize_collection(self):
        """Optimize ChromaDB collection performance."""
        try:
            # This would trigger any optimization routines
            # ChromaDB handles most optimizations automatically
            self.logger.info("Collection optimization completed")
            
        except Exception as e:
            self.logger.error(f"Collection optimization failed: {e}")
    
    async def close(self):
        """Close ChromaDB client and cleanup resources."""
        try:
            # Clear caches
            self.query_cache.clear()
            
            # Close embedding model
            if hasattr(self.embedding_model, 'close'):
                self.embedding_model.close()
            
            self.logger.info("ChromaDB client closed successfully")
            
        except Exception as e:
            self.logger.error(f"Error closing ChromaDB client: {e}")
    
    @asynccontextmanager
    async def transaction(self):
        """Context manager for batch operations."""
        try:
            yield self
        except Exception as e:
            self.logger.error(f"Transaction failed: {e}")
            raise
        finally:
            # Cleanup if needed
            pass


# Utility functions for advanced search patterns

async def hybrid_search(client: ChromaDBClient, 
                       semantic_query: str, 
                       keyword_filters: Dict[str, Any],
                       limit: int = 10) -> List[SearchResult]:
    """Perform hybrid semantic + keyword search."""
    # Semantic search
    semantic_results = await client.search(SearchQuery(
        query=semantic_query,
        limit=limit * 2,  # Get more results for filtering
        filters=keyword_filters
    ))
    
    # Additional keyword filtering on results
    filtered_results = []
    for result in semantic_results:
        if _matches_keywords(result.content, keyword_filters):
            filtered_results.append(result)
        
        if len(filtered_results) >= limit:
            break
    
    return filtered_results


def _matches_keywords(content: str, keyword_filters: Dict[str, Any]) -> bool:
    """Check if content matches keyword filters."""
    content_lower = content.lower()
    
    for key, value in keyword_filters.items():
        if key == 'required_keywords':
            if not all(keyword.lower() in content_lower for keyword in value):
                return False
        elif key == 'excluded_keywords':
            if any(keyword.lower() in content_lower for keyword in value):
                return False
    
    return True


async def multi_repository_search(client: ChromaDBClient,
                                 query: str,
                                 repositories: List[str],
                                 limit_per_repo: int = 5) -> Dict[str, List[SearchResult]]:
    """Search across multiple repositories with per-repository limits."""
    results = {}
    
    for repo in repositories:
        repo_results = await client.search(SearchQuery(
            query=query,
            repository_filter=repo,
            limit=limit_per_repo
        ))
        results[repo] = repo_results
    
    return results


async def domain_aware_search(client: ChromaDBClient,
                             query: str,
                             preferred_domains: List[str],
                             limit: int = 10) -> List[SearchResult]:
    """Search with domain preference weighting."""
    all_results = []
    
    # Search each preferred domain
    for domain in preferred_domains:
        domain_results = await client.search(SearchQuery(
            query=query,
            domain_filter=domain,
            limit=limit
        ))
        
        # Boost scores for preferred domains
        for result in domain_results:
            result.score *= 1.2  # 20% boost for preferred domains
        
        all_results.extend(domain_results)
    
    # Search without domain filter for additional results
    general_results = await client.search(SearchQuery(
        query=query,
        limit=limit * 2
    ))
    
    # Filter out results already in preferred domains
    preferred_domain_ids = {result.chunk_id for result in all_results}
    for result in general_results:
        if result.chunk_id not in preferred_domain_ids:
            all_results.append(result)
    
    # Sort by score and return top results
    all_results.sort(key=lambda x: x.score, reverse=True)
    return all_results[:limit]