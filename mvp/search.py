"""
Enhanced codebase search for MVP.
Provides semantic search capabilities using ChromaDB and graph queries with Neo4j.
"""

import logging
from typing import List, Dict, Any, Optional

import chromadb
from chromadb.config import Settings

from neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


class CodebaseSearch:
    """Enhanced search interface for indexed codebases with graph capabilities."""
    
    def __init__(
        self, 
        chroma_host: str = "localhost", 
        chroma_port: int = 8000,
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_username: str = "neo4j",
        neo4j_password: str = "codebase-rag-2024"
    ):
        self.chroma_host = chroma_host
        self.chroma_port = chroma_port
        self.client = None
        self.collection = None
        
        # Neo4j client for graph queries
        self.neo4j_client = Neo4jClient(neo4j_uri, neo4j_username, neo4j_password)
    
    async def initialize(self):
        """Initialize ChromaDB and Neo4j connections."""
        try:
            # Initialize ChromaDB
            self.client = chromadb.HttpClient(
                host=self.chroma_host,
                port=self.chroma_port,
                settings=Settings(anonymized_telemetry=False)
            )
            
            # Get or create collection
            try:
                self.collection = self.client.get_collection(name="codebase_chunks")
                logger.info("Connected to ChromaDB collection for search")
            except:
                # Collection doesn't exist, create it
                self.collection = self.client.create_collection(
                    name="codebase_chunks",
                    metadata={"description": "Codebase RAG MVP collection"}
                )
                logger.info("Created new ChromaDB collection for search")
            
            # Initialize Neo4j
            await self.neo4j_client.initialize()
            logger.info("Neo4j client initialized for search")
                
        except Exception as e:
            logger.error(f"Failed to initialize search clients: {e}")
            raise
    
    async def search(
        self, 
        query: str, 
        limit: int = 10, 
        similarity_threshold: float = 0.7,
        repository: Optional[str] = None,
        language: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for code chunks similar to the query."""
        if not self.collection:
            raise Exception("ChromaDB collection not initialized")
        
        try:
            # Prepare where clause for filtering
            where_clause = {}
            if repository:
                where_clause["repository"] = repository
            if language:
                where_clause["language"] = language
            
            # Perform search
            results = self.collection.query(
                query_texts=[query],
                n_results=limit,
                where=where_clause if where_clause else None
            )
            
            # Process results
            search_results = []
            if results["documents"] and results["documents"][0]:
                for i in range(len(results["documents"][0])):
                    # Calculate similarity score (ChromaDB returns distance, convert to similarity)
                    distance = results["distances"][0][i]
                    similarity = 1 - distance  # Convert distance to similarity
                    
                    # Filter by similarity threshold
                    if similarity < similarity_threshold:
                        continue
                    
                    result = {
                        "id": results["ids"][0][i],
                        "content": results["documents"][0][i],
                        "score": similarity,
                        "file_path": results["metadatas"][0][i].get("file_path", ""),
                        "metadata": results["metadatas"][0][i]
                    }
                    search_results.append(result)
            
            logger.info(f"Search for '{query}' returned {len(search_results)} results")
            return search_results
            
        except Exception as e:
            logger.error(f"Search failed for query '{query}': {e}")
            raise
    
    async def list_repositories(self) -> List[str]:
        """List all indexed repositories."""
        if not self.collection:
            raise Exception("ChromaDB collection not initialized")
        
        try:
            # Get all metadata to extract unique repositories
            results = self.collection.get()
            
            repositories = set()
            if results["metadatas"]:
                for metadata in results["metadatas"]:
                    repo = metadata.get("repository")
                    if repo:
                        repositories.add(repo)
            
            return sorted(list(repositories))
            
        except Exception as e:
            logger.error(f"Failed to list repositories: {e}")
            raise
    
    async def get_repository_stats(self, repo_name: str) -> Dict[str, Any]:
        """Get statistics for a specific repository."""
        if not self.collection:
            raise Exception("ChromaDB collection not initialized")
        
        try:
            # Get repository chunks
            results = self.collection.get(
                where={"repository": repo_name}
            )
            
            if not results["metadatas"]:
                return {
                    "repository": repo_name,
                    "total_chunks": 0,
                    "files": [],
                    "languages": {}
                }
            
            # Analyze metadata
            files = set()
            languages = {}
            total_size = 0
            
            for metadata in results["metadatas"]:
                # Count files
                file_path = metadata.get("file_path")
                if file_path:
                    files.add(file_path)
                
                # Count languages
                language = metadata.get("language", "unknown")
                languages[language] = languages.get(language, 0) + 1
                
                # Sum file sizes
                chunk_size = metadata.get("chunk_size", 0)
                if isinstance(chunk_size, (int, float)):
                    total_size += chunk_size
            
            return {
                "repository": repo_name,
                "total_chunks": len(results["metadatas"]),
                "total_files": len(files),
                "total_size": total_size,
                "files": sorted(list(files)),
                "languages": languages
            }
            
        except Exception as e:
            logger.error(f"Failed to get repository stats for {repo_name}: {e}")
            raise
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get overall collection statistics."""
        if not self.collection:
            raise Exception("ChromaDB collection not initialized")
        
        try:
            # Get collection info
            results = self.collection.get()
            
            total_chunks = len(results["ids"]) if results["ids"] else 0
            
            # Count repositories and languages
            repositories = set()
            languages = {}
            
            if results["metadatas"]:
                for metadata in results["metadatas"]:
                    repo = metadata.get("repository")
                    if repo:
                        repositories.add(repo)
                    
                    language = metadata.get("language", "unknown")
                    languages[language] = languages.get(language, 0) + 1
            
            return {
                "total_chunks": total_chunks,
                "total_repositories": len(repositories),
                "repositories": sorted(list(repositories)),
                "languages": languages
            }
            
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            raise
    
    async def health_check(self) -> bool:
        """Check if ChromaDB connection is healthy."""
        try:
            if not self.client:
                return False
            
            # Try to access the collection
            if self.collection:
                # Simple query to test connection
                self.collection.count()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    async def get_similar_files(self, file_path: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Find files similar to the given file."""
        if not self.collection:
            raise Exception("ChromaDB collection not initialized")
        
        try:
            # Get the content of the specified file
            results = self.collection.get(
                where={"file_path": file_path}
            )
            
            if not results["documents"] or not results["documents"]:
                return []
            
            # Use the first chunk as query
            query_content = results["documents"][0]
            
            # Search for similar content
            similar_results = self.collection.query(
                query_texts=[query_content],
                n_results=limit + 10,  # Get more results to filter out the same file
                where={"file_path": {"$ne": file_path}}  # Exclude the original file
            )
            
            # Process and group by file
            file_scores = {}
            if similar_results["documents"] and similar_results["documents"][0]:
                for i in range(len(similar_results["documents"][0])):
                    metadata = similar_results["metadatas"][0][i]
                    other_file = metadata.get("file_path")
                    
                    if other_file and other_file != file_path:
                        distance = similar_results["distances"][0][i]
                        similarity = 1 - distance
                        
                        if other_file not in file_scores or similarity > file_scores[other_file]["score"]:
                            file_scores[other_file] = {
                                "file_path": other_file,
                                "score": similarity,
                                "repository": metadata.get("repository"),
                                "language": metadata.get("language")
                            }
            
            # Sort by score and return top results
            similar_files = sorted(
                file_scores.values(), 
                key=lambda x: x["score"], 
                reverse=True
            )[:limit]
            
            return similar_files
            
        except Exception as e:
            logger.error(f"Failed to find similar files for {file_path}: {e}")
            raise