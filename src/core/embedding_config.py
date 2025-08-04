"""
Async CodeBERT Embedding Architecture for Code Analysis
========================================================

Production-ready async CodeBERT implementation with worker pool architecture.
NO FALLBACKS - CodeBERT must work or the system fails fast.

Features:
- Async CodeBERT with dedicated worker pool (non-blocking)
- NO FALLBACKS - rock solid CodeBERT or failure
- Lazy initialization to prevent API blocking
- Concurrent request handling with thread pool
- Production-ready scalable architecture

Author: Claude Code Assistant
Version: 2.1.0 - Async Production Architecture
Last Updated: 2025-08-02
"""

import logging
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional, List, Union
import torch
from transformers import AutoModel, AutoTokenizer
import numpy as np


class EmbeddingModelType(str, Enum):
    """Supported embedding model types - CodeBERT only."""
    CODEBERT = "codebert"


@dataclass
class EmbeddingConfig:
    """Enhanced embedding configuration with code-specific optimizations."""
    
    # Model configuration
    model_type: EmbeddingModelType = EmbeddingModelType.CODEBERT
    model_name: str = "microsoft/codebert-base"
    
    # Model parameters
    dimension: int = 768  # CodeBERT dimension
    max_length: int = 512
    batch_size: int = 32
    device: str = "cpu"  # Will auto-detect GPU if available
    
    # Performance settings
    normalize_embeddings: bool = True
    use_cache: bool = True
    cache_size: int = 10000
    
    # Async/Threading parameters (Production Architecture)
    max_workers: int = 4
    lazy_init: bool = True  # Initialize CodeBERT only when first needed
    embedding_timeout: float = 30.0  # Timeout for embedding operations
    
    # Code-specific settings
    include_docstrings: bool = True
    include_comments: bool = True
    include_imports: bool = True
    code_preprocessing: bool = True
    
    def __post_init__(self):
        """Post-initialization configuration."""
        # Auto-detect device
        if self.device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Adjust dimension based on model
        if self.model_type == EmbeddingModelType.CODEBERT:
            self.dimension = 768
        elif self.model_name == "sentence-transformers/all-MiniLM-L6-v2":
            self.dimension = 384


class AsyncEnhancedEmbeddingClient:
    """
    Async CodeBERT embedding client with worker pool architecture.
    NO FALLBACKS - Production-ready scalable design.
    """
    
    def __init__(self, config: EmbeddingConfig = None):
        """
        Initialize the async embedding client with lazy loading.
        
        Args:
            config: Embedding configuration
        """
        self.config = config or EmbeddingConfig()
        self.logger = logging.getLogger(__name__)
        
        # Model instances (lazy loaded)
        self.primary_model = None
        self.tokenizer = None
        self._model_initialized = False
        
        # Async infrastructure
        self.executor = ThreadPoolExecutor(max_workers=self.config.max_workers)
        self._init_lock = asyncio.Lock()
        
        # Performance tracking
        self.embedding_cache: Dict[str, np.ndarray] = {}
        self.cache_hits = 0
        self.total_requests = 0
        self.total_embedding_time = 0.0
        
        self.logger.info(f"Async CodeBERT client created - lazy_init={self.config.lazy_init}")
        
        # Initialize immediately if not lazy  
        if not self.config.lazy_init:
            # Note: In real async context, would use asyncio.create_task(self._ensure_model_initialized())
            self.logger.info("Non-lazy initialization - will initialize on first use")
    
    async def _ensure_model_initialized(self):
        """Ensure CodeBERT model is initialized (lazy loading)."""
        if self._model_initialized:
            return
            
        async with self._init_lock:
            if self._model_initialized:  # Double-check after acquiring lock
                return
                
            try:
                self.logger.info("Lazy loading CodeBERT model...")
                
                if self.config.model_type != EmbeddingModelType.CODEBERT:
                    raise ValueError(f"Only CodeBERT is supported. Got: {self.config.model_type}")
                
                # Run CodeBERT initialization in thread pool to avoid blocking
                await asyncio.to_thread(self._initialize_codebert)
                
                self._model_initialized = True
                self.logger.info("CodeBERT model lazy-loaded successfully")
                
            except Exception as e:
                self.logger.error(f"CodeBERT lazy initialization failed: {e}")
                raise RuntimeError(f"CodeBERT must work - no fallbacks allowed: {e}")
    
    def _initialize_codebert(self):
        """Initialize CodeBERT model for code understanding."""
        try:
            self.logger.info("Initializing CodeBERT model...")
            
            # Load CodeBERT model and tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(self.config.model_name)
            self.primary_model = AutoModel.from_pretrained(self.config.model_name)
            
            # Move to device
            if self.config.device != "cpu":
                self.primary_model = self.primary_model.to(self.config.device)
            
            self.primary_model.eval()  # Set to evaluation mode
            
            self.logger.info(f"CodeBERT model loaded successfully on {self.config.device}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize CodeBERT: {e}")
            raise
    
    
    
    
    async def encode(self, texts: Union[str, List[str]], **kwargs) -> np.ndarray:
        """
        Generate embeddings for text(s) with async worker pool architecture.
        
        Args:
            texts: Input text(s) to embed
            **kwargs: Additional encoding parameters
            
        Returns:
            np.ndarray: Generated embeddings
        """
        # Ensure model is initialized (lazy loading)
        await self._ensure_model_initialized()
        
        start_time = time.time()
        self.total_requests += 1
        
        try:
            # Handle single text
            if isinstance(texts, str):
                texts = [texts]
            
            # Check cache
            if self.config.use_cache:
                cached_embeddings = []
                uncached_texts = []
                uncached_indices = []
                
                for i, text in enumerate(texts):
                    cache_key = self._get_cache_key(text)
                    if cache_key in self.embedding_cache:
                        cached_embeddings.append((i, self.embedding_cache[cache_key]))
                        self.cache_hits += 1
                    else:
                        uncached_texts.append(text)
                        uncached_indices.append(i)
                
                # Generate embeddings for uncached texts using async thread pool
                if uncached_texts:
                    new_embeddings = await asyncio.wait_for(
                        asyncio.to_thread(self._generate_embeddings, uncached_texts, **kwargs),
                        timeout=self.config.embedding_timeout
                    )
                    
                    # Cache new embeddings
                    for text, embedding in zip(uncached_texts, new_embeddings):
                        cache_key = self._get_cache_key(text)
                        self._cache_embedding(cache_key, embedding)
                    
                    # Combine cached and new embeddings
                    all_embeddings = [None] * len(texts)
                    
                    # Place cached embeddings
                    for original_idx, embedding in cached_embeddings:
                        all_embeddings[original_idx] = embedding
                    
                    # Place new embeddings
                    for i, embedding in enumerate(new_embeddings):
                        original_idx = uncached_indices[i]
                        all_embeddings[original_idx] = embedding
                    
                    result = np.array(all_embeddings)
                else:
                    # All embeddings were cached
                    result = np.array([emb for _, emb in sorted(cached_embeddings)])
            else:
                # No caching
                result = self._generate_embeddings(texts, **kwargs)
            
            # Track performance
            self.total_embedding_time += time.time() - start_time
            
            return result[0] if len(result) == 1 and isinstance(kwargs.get('texts'), str) else result
            
        except asyncio.TimeoutError:
            self.logger.error(f"CodeBERT embedding generation timed out after {self.config.embedding_timeout}s")
            raise RuntimeError(f"CodeBERT embedding timeout - increase embedding_timeout in config")
        except Exception as e:
            self.logger.error(f"CodeBERT embedding generation failed: {e}")
            raise RuntimeError(f"CodeBERT must work - no fallbacks: {e}")
    
    def _generate_embeddings(self, texts: List[str], **kwargs) -> np.ndarray:
        """
        Generate embeddings using the configured model.
        
        Args:
            texts: List of texts to embed
            **kwargs: Additional parameters
            
        Returns:
            np.ndarray: Generated embeddings
        """
        if self.config.model_type != EmbeddingModelType.CODEBERT:
            raise ValueError("Only CodeBERT is supported - no fallbacks")
        return self._generate_codebert_embeddings(texts)
    
    def _generate_codebert_embeddings(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings using CodeBERT.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            np.ndarray: Generated embeddings
        """
        embeddings = []
        
        # Process in batches
        for i in range(0, len(texts), self.config.batch_size):
            batch_texts = texts[i:i + self.config.batch_size]
            
            # Preprocess code if enabled
            if self.config.code_preprocessing:
                batch_texts = [self._preprocess_code(text) for text in batch_texts]
            
            # Tokenize
            inputs = self.tokenizer(
                batch_texts,
                padding=True,
                truncation=True,
                max_length=self.config.max_length,
                return_tensors="pt"
            )
            
            # Move to device
            if self.config.device != "cpu":
                inputs = {k: v.to(self.config.device) for k, v in inputs.items()}
            
            # Generate embeddings
            with torch.no_grad():
                outputs = self.primary_model(**inputs)
                # Use CLS token embedding
                batch_embeddings = outputs.last_hidden_state[:, 0, :].cpu().numpy()
            
            embeddings.extend(batch_embeddings)
        
        embeddings = np.array(embeddings)
        
        # Normalize if requested
        if self.config.normalize_embeddings:
            embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        
        return embeddings
    
    def _preprocess_code(self, code: str) -> str:
        """
        Preprocess code for better embedding quality.
        
        Args:
            code: Raw code text
            
        Returns:
            str: Preprocessed code
        """
        # Basic preprocessing for code
        lines = code.split('\n')
        processed_lines = []
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Include/exclude based on configuration
            if not self.config.include_comments and (line.startswith('//') or line.startswith('#')):
                continue
            
            processed_lines.append(line)
        
        return '\n'.join(processed_lines)
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        import hashlib
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def _cache_embedding(self, key: str, embedding: np.ndarray):
        """Cache embedding with size limit."""
        if len(self.embedding_cache) >= self.config.cache_size:
            # Remove oldest entry (simple FIFO)
            oldest_key = next(iter(self.embedding_cache))
            del self.embedding_cache[oldest_key]
        
        self.embedding_cache[key] = embedding
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get embedding client statistics."""
        cache_hit_rate = self.cache_hits / max(self.total_requests, 1)
        avg_time = self.total_embedding_time / max(self.total_requests, 1)
        
        return {
            'model_type': self.config.model_type.value,
            'model_name': self.config.model_name,
            'dimension': self.config.dimension,
            'device': self.config.device,
            'total_requests': self.total_requests,
            'cache_hits': self.cache_hits,
            'cache_hit_rate': cache_hit_rate,
            'cache_size': len(self.embedding_cache),
            'average_embedding_time': avg_time,
            'total_embedding_time': self.total_embedding_time
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform async health check on embedding client."""
        try:
            # Test embedding generation
            test_embedding = await self.encode("test code function")
            
            return {
                'status': 'healthy',
                'model_loaded': self.primary_model is not None,
                'dimension': len(test_embedding),
                'device': self.config.device,
                'cache_enabled': self.config.use_cache,
                'statistics': self.get_statistics()
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'model_loaded': False
            }
    
    def clear_cache(self):
        """Clear embedding cache."""
        self.embedding_cache.clear()
        self.logger.info("Embedding cache cleared")
    
    def close(self):
        """Cleanup resources."""
        try:
            self.clear_cache()
            
            # Clear models
            self.primary_model = None
            self.tokenizer = None
            
            self.logger.info("Embedding client closed successfully")
            
        except Exception as e:
            self.logger.error(f"Error closing embedding client: {e}")


# ChromaDB Embedding Function Adapter for CodeBERT
class CodeBERTChromaEmbeddingFunction:
    """
    ChromaDB embedding function adapter for AsyncEnhancedEmbeddingClient.
    Implements ChromaDB's embedding function interface while using our CodeBERT client.
    """
    
    def __init__(self, embedding_client: AsyncEnhancedEmbeddingClient):
        """
        Initialize the ChromaDB adapter.
        
        Args:
            embedding_client: The async CodeBERT embedding client
        """
        self.embedding_client = embedding_client
        self.logger = logging.getLogger(__name__)
        # ChromaDB requires these attributes
        self.name = "codebert-embedding-function"
        self.model_name = "microsoft/codebert-base"
        
    def __call__(self, input: Union[str, List[str]]) -> List[List[float]]:
        """
        ChromaDB embedding function interface (synchronous).
        
        Args:
            input: Text or list of texts to embed
            
        Returns:
            List[List[float]]: Embeddings as list of float lists (768-d for CodeBERT)
        """
        try:
            # Handle both single string and list inputs
            if isinstance(input, str):
                texts = [input]
                single_input = True
            else:
                texts = input
                single_input = False
            
            # Use different approach depending on whether we're in an event loop
            try:
                # If this does not raise, we are inside a running loop
                loop = asyncio.get_running_loop()
                # Schedule coroutine safely on the running loop and wait synchronously
                future = asyncio.run_coroutine_threadsafe(self._get_embeddings_async(texts), loop)
                embeddings = future.result()
            except RuntimeError:
                # No running event loop, safe to block with asyncio.run
                embeddings = asyncio.run(self._get_embeddings_async(texts))
            
            # Validate dimensions
            if embeddings.shape[1] != 768:
                raise RuntimeError(f"CodeBERT embedding dimension mismatch: expected 768, got {embeddings.shape[1]}")
            
            # Convert to list of lists of floats (ChromaDB requirement)
            result = embeddings.tolist()
            
            # Return single embedding as list for single input
            if single_input:
                return [result[0]]
            else:
                return result
                
        except Exception as e:
            self.logger.error(f"CodeBERT embedding generation failed: {e}")
            raise RuntimeError(f"CodeBERT must work - no fallbacks: {e}")
    
    async def _get_embeddings_async(self, texts: List[str]) -> np.ndarray:
        """
        Async helper to get embeddings using our CodeBERT client.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            np.ndarray: Embeddings array
        """
        return await self.embedding_client.encode(texts)
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        ChromaDB interface for embedding multiple documents.
        
        Args:
            texts: List of document texts
            
        Returns:
            List[List[float]]: Document embeddings
        """
        return self(texts)
    
    def embed_query(self, text: str) -> List[float]:
        """
        ChromaDB interface for embedding a single query.
        
        Args:
            text: Query text
            
        Returns:
            List[float]: Query embedding
        """
        result = self(text)
        return result[0]  # Return single embedding list


# Factory function for easy instantiation
def create_embedding_client(model_type: str = "codebert", **kwargs) -> AsyncEnhancedEmbeddingClient:
    """
    Factory function to create async embedding client with sensible defaults.
    
    Args:
        model_type: Type of model to use (only "codebert" supported)
        **kwargs: Additional configuration parameters
        
    Returns:
        AsyncEnhancedEmbeddingClient: Configured async embedding client
    """
    config = EmbeddingConfig(
        model_type=EmbeddingModelType(model_type),
        **kwargs
    )
    
    return AsyncEnhancedEmbeddingClient(config)


def create_chromadb_embedding_function(embedding_client: AsyncEnhancedEmbeddingClient) -> CodeBERTChromaEmbeddingFunction:
    """
    Factory function to create ChromaDB-compatible embedding function using CodeBERT.
    
    Args:
        embedding_client: The async CodeBERT embedding client
        
    Returns:
        CodeBERTChromaEmbeddingFunction: ChromaDB-compatible embedding function
    """
    return CodeBERTChromaEmbeddingFunction(embedding_client)