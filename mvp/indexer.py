"""
Enhanced codebase indexer for MVP.
Processes local repositories, creates embeddings in ChromaDB, and analyzes Maven dependencies in Neo4j.
"""

import os
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import hashlib

import chromadb
from chromadb.config import Settings
import tree_sitter_languages
import magic
import chardet

from .neo4j_client import Neo4jClient
from .maven_parser import MavenParser

logger = logging.getLogger(__name__)


class CodebaseIndexer:
    """Enhanced indexer for local codebases with Maven support."""
    
    def __init__(
        self, 
        chroma_host: str = "localhost", 
        chroma_port: int = 8000,
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_username: str = "neo4j",
        neo4j_password: str = "codebase-rag-2024",
        maven_enabled: bool = True
    ):
        self.chroma_host = chroma_host
        self.chroma_port = chroma_port
        self.client = None
        self.collection = None
        
        # Neo4j client for graph relationships
        self.neo4j_client = Neo4jClient(neo4j_uri, neo4j_username, neo4j_password)
        
        # Maven parser for dependency analysis
        self.maven_enabled = maven_enabled
        self.maven_parser = MavenParser() if maven_enabled else None
        
        # Supported file extensions
        self.supported_extensions = {
            '.py': 'python',
            '.js': 'javascript', 
            '.ts': 'typescript',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
            '.cpp': 'cpp',
            '.c': 'c',
            '.h': 'c',
            '.hpp': 'cpp',
            '.cs': 'c_sharp',
            '.rb': 'ruby',
            '.php': 'php',
            '.md': 'markdown',
            '.txt': 'text',
            '.json': 'json',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.xml': 'xml',
            '.html': 'html',
            '.css': 'css',
            '.sql': 'sql',
            '.sh': 'bash',
            '.dockerfile': 'dockerfile',
            # Struts/Legacy web framework support
            '.jsp': 'jsp',
            '.tag': 'jsp',
            '.tagx': 'jsp',
            '.properties': 'properties',
            '.ftl': 'freemarker',
            '.vm': 'velocity'
        }
        
        # Directories to exclude
        self.exclude_dirs = {
            'node_modules', '__pycache__', '.git', 'target', 'build', 
            'dist', '.vscode', '.idea', 'venv', 'env', '.env'
        }
        
        # File size limit (1MB)
        self.max_file_size = 1024 * 1024
        
        # Chunk settings
        self.chunk_size = 1000
        self.chunk_overlap = 200
    
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
                logger.info("Connected to existing ChromaDB collection")
            except:
                self.collection = self.client.create_collection(
                    name="codebase_chunks",
                    metadata={"description": "Codebase RAG MVP collection"}
                )
                logger.info("Created new ChromaDB collection")
            
            # Initialize Neo4j
            await self.neo4j_client.initialize()
            logger.info("Neo4j client initialized")
                
        except Exception as e:
            logger.error(f"Failed to initialize clients: {e}")
            raise
    
    async def index_repository(self, repo_path: str, repo_name: str) -> Dict[str, Any]:
        """Index a local repository with Maven analysis."""
        if not self.collection:
            raise Exception("ChromaDB collection not initialized")
        
        start_time = time.time()
        files_processed = 0
        chunks_created = 0
        maven_artifacts = 0
        maven_dependencies = 0
        
        logger.info(f"Starting to index repository: {repo_name} at {repo_path}")
        
        try:
            # Create repository node in Neo4j
            await self.neo4j_client.create_repository(repo_name, repo_path)
            
            # Process Maven dependencies if enabled
            if self.maven_enabled and self.maven_parser:
                maven_stats = await self._process_maven_dependencies(repo_path, repo_name)
                maven_artifacts = maven_stats.get("artifacts", 0)
                maven_dependencies = maven_stats.get("dependencies", 0)
            
            # Walk through repository files
            for file_path in self._walk_repository(repo_path):
                try:
                    # Process file for ChromaDB
                    file_chunks = await self._process_file(file_path, repo_name, repo_path)
                    
                    if file_chunks:
                        # Add chunks to ChromaDB
                        await self._add_chunks_to_db(file_chunks)
                        chunks_created += len(file_chunks)
                    
                    # Add file to Neo4j graph
                    await self._add_file_to_graph(file_path, repo_name, repo_path)
                    
                    files_processed += 1
                    
                    if files_processed % 10 == 0:
                        logger.info(f"Processed {files_processed} files, created {chunks_created} chunks")
                        
                except Exception as e:
                    logger.warning(f"Failed to process file {file_path}: {e}")
                    continue
            
            processing_time = time.time() - start_time
            
            logger.info(f"Completed indexing {repo_name}: {files_processed} files, {chunks_created} chunks, {maven_artifacts} Maven artifacts, {maven_dependencies} dependencies in {processing_time:.2f}s")
            
            return {
                "files_indexed": files_processed,
                "chunks_created": chunks_created,
                "maven_artifacts": maven_artifacts,
                "maven_dependencies": maven_dependencies,
                "processing_time": processing_time
            }
            
        except Exception as e:
            logger.error(f"Failed to index repository {repo_name}: {e}")
            raise
    
    def _walk_repository(self, repo_path: str) -> List[Path]:
        """Walk through repository and return supported files."""
        repo_path = Path(repo_path)
        files = []
        
        for file_path in repo_path.rglob("*"):
            # Skip directories
            if not file_path.is_file():
                continue
            
            # Skip excluded directories
            if any(excluded in file_path.parts for excluded in self.exclude_dirs):
                continue
            
            # Check file extension
            if file_path.suffix.lower() not in self.supported_extensions:
                continue
            
            # Check file size
            try:
                if file_path.stat().st_size > self.max_file_size:
                    logger.debug(f"Skipping large file: {file_path}")
                    continue
            except OSError:
                continue
            
            files.append(file_path)
        
        logger.info(f"Found {len(files)} supported files in {repo_path}")
        return files
    
    async def _process_file(self, file_path: Path, repo_name: str, repo_root: str) -> List[Dict[str, Any]]:
        """Process a single file and create chunks."""
        try:
            # Read file content
            content = self._read_file_content(file_path)
            if not content:
                return []
            
            # Get relative path
            relative_path = file_path.relative_to(repo_root)
            
            # Get file extension and language
            extension = file_path.suffix.lower()
            language = self.supported_extensions.get(extension, 'text')
            
            # Create chunks
            chunks = self._create_chunks(content, str(relative_path), language)
            
            # Prepare chunk data
            chunk_data = []
            for i, chunk in enumerate(chunks):
                chunk_id = f"{repo_name}:{relative_path}:{i}"
                
                metadata = {
                    "repository": repo_name,
                    "file_path": str(relative_path),
                    "language": language,
                    "chunk_index": i,
                    "file_size": len(content),
                    "chunk_size": len(chunk)
                }
                
                chunk_data.append({
                    "id": chunk_id,
                    "content": chunk,
                    "metadata": metadata
                })
            
            return chunk_data
            
        except Exception as e:
            logger.error(f"Failed to process file {file_path}: {e}")
            return []
    
    def _read_file_content(self, file_path: Path) -> Optional[str]:
        """Read file content with encoding detection."""
        try:
            # First try to read as binary to detect encoding
            with open(file_path, 'rb') as f:
                raw_data = f.read()
            
            # Detect encoding
            detected = chardet.detect(raw_data)
            encoding = detected.get('encoding', 'utf-8')
            
            # If confidence is too low, try common encodings
            if detected.get('confidence', 0) < 0.7:
                for enc in ['utf-8', 'latin-1', 'cp1252']:
                    try:
                        content = raw_data.decode(enc)
                        return content
                    except UnicodeDecodeError:
                        continue
                return None
            
            # Decode with detected encoding
            try:
                content = raw_data.decode(encoding)
                return content
            except UnicodeDecodeError:
                # Fallback to utf-8 with error handling
                content = raw_data.decode('utf-8', errors='ignore')
                return content
                
        except Exception as e:
            logger.warning(f"Failed to read file {file_path}: {e}")
            return None
    
    def _create_chunks(self, content: str, file_path: str, language: str) -> List[str]:
        """Create chunks from file content."""
        # Simple chunking by lines for MVP
        lines = content.split('\n')
        chunks = []
        current_chunk = []
        current_size = 0
        
        for line in lines:
            line_size = len(line)
            
            # If adding this line would exceed chunk size, start new chunk
            if current_size + line_size > self.chunk_size and current_chunk:
                # Join current chunk
                chunk_text = '\n'.join(current_chunk)
                if chunk_text.strip():  # Only add non-empty chunks
                    chunks.append(chunk_text)
                
                # Start new chunk with overlap
                overlap_lines = current_chunk[-self.chunk_overlap//50:] if len(current_chunk) > self.chunk_overlap//50 else []
                current_chunk = overlap_lines + [line]
                current_size = sum(len(l) for l in current_chunk)
            else:
                current_chunk.append(line)
                current_size += line_size
        
        # Add final chunk
        if current_chunk:
            chunk_text = '\n'.join(current_chunk)
            if chunk_text.strip():
                chunks.append(chunk_text)
        
        # If no chunks were created, create one from the entire content
        if not chunks and content.strip():
            chunks.append(content[:self.chunk_size])
        
        return chunks
    
    async def _add_chunks_to_db(self, chunks: List[Dict[str, Any]]):
        """Add chunks to ChromaDB."""
        if not chunks:
            return
        
        try:
            # Prepare data for ChromaDB
            ids = [chunk["id"] for chunk in chunks]
            documents = [chunk["content"] for chunk in chunks]
            metadatas = [chunk["metadata"] for chunk in chunks]
            
            # Add to collection
            self.collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
            
        except Exception as e:
            logger.error(f"Failed to add chunks to ChromaDB: {e}")
            raise
    
    async def _process_maven_dependencies(self, repo_path: str, repo_name: str) -> Dict[str, Any]:
        """Process Maven dependencies for a repository."""
        try:
            # Find POM files
            pom_files = self.maven_parser.find_pom_files(repo_path)
            if not pom_files:
                logger.info(f"No POM files found in {repo_name}")
                return {"artifacts": 0, "dependencies": 0}
            
            # Build dependency tree
            dependency_tree = self.maven_parser.build_dependency_tree(pom_files)
            
            artifacts_created = 0
            dependencies_created = 0
            
            # Create Maven artifacts in Neo4j
            for artifact_id, artifact_data in dependency_tree['artifacts'].items():
                try:
                    # Get relative path for POM file
                    pom_path = str(Path(artifact_data['file_path']).relative_to(repo_path))
                    
                    await self.neo4j_client.create_maven_artifact(
                        group_id=artifact_data['group_id'],
                        artifact_id=artifact_data['artifact_id'],
                        version=artifact_data['version'],
                        repo_name=repo_name,
                        file_path=pom_path,
                        metadata={
                            'packaging': artifact_data.get('packaging', 'jar'),
                            'name': artifact_data.get('name', ''),
                            'description': artifact_data.get('description', '')
                        }
                    )
                    artifacts_created += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to create Maven artifact {artifact_id}: {e}")
            
            # Create dependencies
            for dep in dependency_tree['dependencies']:
                try:
                    await self.neo4j_client.create_dependency(
                        from_artifact=dep['from_artifact'],
                        to_group_id=dep['to_group_id'],
                        to_artifact_id=dep['to_artifact_id'],
                        to_version=dep['to_version'],
                        scope=dep['scope'],
                        optional=dep['optional'],
                        metadata={
                            'managed': dep.get('managed', False)
                        }
                    )
                    dependencies_created += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to create dependency: {e}")
            
            logger.info(f"Processed Maven dependencies for {repo_name}: {artifacts_created} artifacts, {dependencies_created} dependencies")
            
            return {
                "artifacts": artifacts_created,
                "dependencies": dependencies_created,
                "pom_files": len(pom_files)
            }
            
        except Exception as e:
            logger.error(f"Failed to process Maven dependencies for {repo_name}: {e}")
            return {"artifacts": 0, "dependencies": 0}
    
    async def _add_file_to_graph(self, file_path: Path, repo_name: str, repo_root: str):
        """Add file information to Neo4j graph."""
        try:
            # Get relative path and file info
            relative_path = str(file_path.relative_to(repo_root))
            extension = file_path.suffix.lower()
            language = self.supported_extensions.get(extension, 'unknown')
            
            # File metadata
            stat = file_path.stat()
            metadata = {
                'file_size': stat.st_size,
                'extension': extension,
                'last_modified': stat.st_mtime
            }
            
            await self.neo4j_client.create_file(
                repo_name=repo_name,
                file_path=relative_path,
                language=language,
                metadata=metadata
            )
            
        except Exception as e:
            logger.warning(f"Failed to add file {file_path} to graph: {e}")

    async def delete_repository(self, repo_name: str) -> Dict[str, Any]:
        """Delete all chunks and graph data for a repository."""
        chunks_deleted = 0
        graph_nodes_deleted = 0
        
        try:
            # Delete from ChromaDB
            if self.collection:
                results = self.collection.get(
                    where={"repository": repo_name}
                )
                
                if results["ids"]:
                    self.collection.delete(
                        where={"repository": repo_name}
                    )
                    chunks_deleted = len(results["ids"])
            
            # Delete from Neo4j
            graph_nodes_deleted = await self.neo4j_client.delete_repository(repo_name)
            
            logger.info(f"Deleted repository {repo_name}: {chunks_deleted} chunks, {graph_nodes_deleted} graph nodes")
            
            return {
                "chunks_deleted": chunks_deleted,
                "graph_nodes_deleted": graph_nodes_deleted
            }
            
        except Exception as e:
            logger.error(f"Failed to delete repository {repo_name}: {e}")
            raise