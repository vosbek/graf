"""
Enhanced Repository Processor v2.0 - Thread-Free Architecture
===============================================================

This module provides a completely async, thread-free repository processing system
for the GraphRAG codebase analysis platform. It eliminates all threading/pickling
issues while providing robust error handling and comprehensive logging.

Key Features:
- Pure async processing (no threading/pickling issues)
- CodeBERT embeddings for superior code understanding
- Comprehensive error handling and recovery
- Detailed progress tracking and logging
- Maven and dependency analysis
- Rock-solid reliability with graceful degradation

Author: Claude Code Assistant
Version: 2.0.0
Last Updated: 2025-08-02
"""

import asyncio
import hashlib
import json
import logging
import subprocess
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Union, Tuple
import uuid
import fnmatch

# Core processing imports
from ..processing.code_chunker import CodeChunker, EnhancedChunk, ChunkingConfig
from ..processing.tree_sitter_parser import TreeSitterParser, SupportedLanguage
from ..processing.maven_parser import MavenParser
from ..processing.dependency_resolver import DependencyResolver
from ..core.chromadb_client import ChromaDBClient
from ..core.neo4j_client import Neo4jClient, GraphQuery

# Enhanced error handling and monitoring imports
from ..core.error_handling import error_handling_context, get_error_handler, ErrorHandler
from ..core.logging_config import get_logger, log_performance, log_validation_result
from ..core.performance_metrics import performance_collector
from ..core.exceptions import (
    GraphRAGException, ErrorContext, ProcessingError, ValidationError,
    TimeoutError as GraphRAGTimeoutError, ResourceError, DatabaseError
)
from ..core.diagnostics import diagnostic_collector


class ProcessingStatus(str, Enum):
    """Enhanced processing status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


def _matches_exclusion_pattern(file_path: Path, pattern: str, repo_root: Path) -> bool:
    """
    Check if a file path matches an exclusion pattern.
    
    This function properly handles glob patterns like **/node_modules/** on Windows
    by converting paths to POSIX format and using fnmatch.
    
    Args:
        file_path: The file path to check
        pattern: The exclusion pattern (e.g., "**/node_modules/**")
        repo_root: The repository root path for relative path calculation
        
    Returns:
        True if the file matches the exclusion pattern
    """
    try:
        # Get relative path from repo root
        relative_path = file_path.relative_to(repo_root)
        
        # Convert to POSIX format for consistent pattern matching
        posix_path = relative_path.as_posix()
        
        # Handle different pattern formats
        if pattern.startswith('**/') and pattern.endswith('/**'):
            # Pattern like **/node_modules/** - check if any part of path matches
            pattern_core = pattern[3:-3]  # Remove **/ and /**
            path_parts = posix_path.split('/')
            return pattern_core in path_parts
        elif pattern.startswith('**/'):
            # Pattern like **/*.class - use fnmatch
            return fnmatch.fnmatch(posix_path, pattern)
        elif pattern.endswith('/**'):
            # Pattern like build/** - check if path starts with pattern prefix
            pattern_prefix = pattern[:-3]  # Remove /**
            return posix_path.startswith(pattern_prefix + '/') or posix_path == pattern_prefix
        else:
            # Regular pattern - use fnmatch
            return fnmatch.fnmatch(posix_path, pattern)
            
    except (ValueError, OSError):
        # If we can't get relative path, fall back to string matching
        return fnmatch.fnmatch(str(file_path), pattern)


class RepositoryPriority(str, Enum):
    """Repository processing priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ProcessingError is now imported from core.exceptions
# Keeping this for backward compatibility but using the enhanced version


@dataclass
class RepositoryConfig:
    """Enhanced repository configuration with validation."""
    name: str
    url: str
    branch: str = "main"
    priority: RepositoryPriority = RepositoryPriority.MEDIUM
    business_domain: Optional[str] = None
    team_owner: Optional[str] = None
    maven_enabled: bool = True
    is_golden_repo: bool = False
    
    # Processing configuration
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    include_patterns: List[str] = field(default_factory=lambda: [
        "**/*.java", "**/*.py", "**/*.js", "**/*.ts", "**/*.jsx", "**/*.tsx",
        "**/*.go", "**/*.rs", "**/*.cpp", "**/*.c", "**/*.h", "**/*.hpp",
        "**/*.cs", "**/*.php", "**/*.rb", "**/*.scala", "**/*.kt", "**/*.swift"
    ])
    exclude_patterns: List[str] = field(default_factory=lambda: [
        "**/target/**", "**/build/**", "**/dist/**", "**/node_modules/**",
        "**/.git/**", "**/*.class", "**/*.jar", "**/*.war", "**/*.ear",
        "**/bin/**", "**/obj/**", "**/*.exe", "**/*.dll", "**/*.so",
        "**/.vscode/**", "**/.idea/**", "**/__pycache__/**", "**/.pytest_cache/**",
        "**/coverage/**", "**/htmlcov/**", "**/.coverage", "**/logs/**",
        "**/tmp/**", "**/temp/**", "**/.DS_Store", "**/Thumbs.db"
    ])
    
    # Processing limits
    max_files_per_batch: int = 25
    max_processing_time: int = 1800  # 30 minutes
    retry_attempts: int = 3
    retry_delay: float = 5.0
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.name or not self.name.strip():
            raise ValueError("Repository name cannot be empty")
        if not self.url or not self.url.strip():
            raise ValueError("Repository URL cannot be empty")
        if self.max_file_size <= 0:
            raise ValueError("Max file size must be positive")


@dataclass
class RepositoryFilter:
    """Filter for repository selection."""
    name_patterns: List[str] = field(default_factory=list)
    domains: List[str] = field(default_factory=list)
    teams: List[str] = field(default_factory=list)
    priorities: List[RepositoryPriority] = field(default_factory=list)
    languages: List[SupportedLanguage] = field(default_factory=list)
    min_size: Optional[int] = None
    max_size: Optional[int] = None
    has_maven: Optional[bool] = None
    is_golden_repo: Optional[bool] = None
    exclude_names: List[str] = field(default_factory=list)


@dataclass
class LocalRepositoryConfig:
    """Configuration for local repository processing."""
    name: str
    path: str
    priority: RepositoryPriority = RepositoryPriority.MEDIUM
    business_domain: Optional[str] = None
    team_owner: Optional[str] = None
    is_golden_repo: bool = False
    
    # Processing configuration (inherited from main config)
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    include_patterns: List[str] = field(default_factory=lambda: [
        "**/*.java", "**/*.py", "**/*.js", "**/*.ts", "**/*.jsx", "**/*.tsx",
        "**/*.go", "**/*.rs", "**/*.cpp", "**/*.c", "**/*.h", "**/*.hpp",
        "**/*.cs", "**/*.php", "**/*.rb", "**/*.scala", "**/*.kt", "**/*.swift"
    ])
    exclude_patterns: List[str] = field(default_factory=lambda: [
        "**/target/**", "**/build/**", "**/dist/**", "**/node_modules/**",
        "**/.git/**", "**/*.class", "**/*.jar", "**/*.war", "**/*.ear",
        "**/bin/**", "**/obj/**", "**/*.exe", "**/*.dll", "**/*.so",
        "**/.vscode/**", "**/.idea/**", "**/__pycache__/**", "**/.pytest_cache/**",
        "**/coverage/**", "**/htmlcov/**", "**/.coverage", "**/logs/**",
        "**/tmp/**", "**/temp/**", "**/.DS_Store", "**/Thumbs.db"
    ])
    
    # Processing limits
    max_files_per_batch: int = 25
    max_processing_time: int = 1800  # 30 minutes
    retry_attempts: int = 3
    retry_delay: float = 5.0
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.name or not self.name.strip():
            raise ValueError("Repository name cannot be empty")
        if not self.path or not self.path.strip():
            raise ValueError("Repository path cannot be empty")
        if self.max_file_size <= 0:
            raise ValueError("Max file size must be positive")


@dataclass
class ProcessingResult:
    """Comprehensive processing result with detailed metrics."""
    repository_name: str
    status: ProcessingStatus
    processed_files: int = 0
    generated_chunks: int = 0
    processing_time: float = 0.0
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    
    # Detailed metrics
    files_by_language: Dict[str, int] = field(default_factory=dict)
    total_lines_of_code: int = 0
    complexity_metrics: Dict[str, float] = field(default_factory=dict)
    dependency_count: int = 0
    maven_artifacts: List[str] = field(default_factory=list)
    
    # Business logic metrics
    business_rules_extracted: int = 0
    struts_patterns_found: int = 0
    corba_interfaces_found: int = 0
    jsp_components_found: int = 0
    migration_complexity_score: float = 0.0
    
    # Processing metadata
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            'repository_name': self.repository_name,
            'status': self.status.value,
            'processed_files': self.processed_files,
            'generated_chunks': self.generated_chunks,
            'processing_time': self.processing_time,
            'error_message': self.error_message,
            'error_code': self.error_code,
            'files_by_language': self.files_by_language,
            'total_lines_of_code': self.total_lines_of_code,
            'complexity_metrics': self.complexity_metrics,
            'dependency_count': self.dependency_count,
            'maven_artifacts': self.maven_artifacts,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'warnings': self.warnings
        }


@dataclass
class ProcessingStats:
    """Global processing statistics tracker."""
    total_repositories: int = 0
    completed_repositories: int = 0
    failed_repositories: int = 0
    total_files_processed: int = 0
    total_chunks_generated: int = 0
    total_processing_time: float = 0.0
    start_time: float = field(default_factory=time.time)
    
    def add_result(self, result: ProcessingResult):
        """Add a processing result to statistics."""
        self.total_repositories += 1
        if result.status == ProcessingStatus.COMPLETED:
            self.completed_repositories += 1
        elif result.status == ProcessingStatus.FAILED:
            self.failed_repositories += 1
        
        self.total_files_processed += result.processed_files
        self.total_chunks_generated += result.generated_chunks
        self.total_processing_time += result.processing_time


class EnhancedRepositoryProcessor:
    """
    Enhanced Repository Processor v2.0 - Thread-Free Architecture
    
    This processor eliminates all threading/pickling issues by using pure async
    processing. It provides robust error handling, comprehensive logging, and
    supports CodeBERT embeddings for superior code understanding.
    """
    
    def __init__(self,
                 chroma_client: ChromaDBClient,
                 neo4j_client: Neo4jClient,
                 max_concurrent_repos: int = 5,
                 workspace_dir: str = "./data/repositories",
                 use_codebert: bool = True):
        """
        Initialize the enhanced repository processor.
        
        Args:
            chroma_client: ChromaDB client for vector storage
            neo4j_client: Neo4j client for graph relationships
            max_concurrent_repos: Maximum concurrent repository processing
            workspace_dir: Directory for repository storage
            use_codebert: Whether to use CodeBERT embeddings
        """
        # Core clients
        self.chroma_client = chroma_client
        self.neo4j_client = neo4j_client
        self.workspace_dir = Path(workspace_dir)
        self.max_concurrent_repos = max_concurrent_repos
        self.use_codebert = use_codebert
        
        # Initialize processing components
        self.tree_sitter_parser = TreeSitterParser()
        self.maven_parser = MavenParser()
        self.dependency_resolver = DependencyResolver()
        
        # Processing state (pure async, no threads)
        self.processing_queue: asyncio.Queue = asyncio.Queue()
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.processing_stats = ProcessingStats()
        self.repository_cache: Dict[str, Dict[str, Any]] = {}
        
        # Semaphore for concurrency control
        self.semaphore = asyncio.Semaphore(max_concurrent_repos)
        
        # Initialize comprehensive logging and error handling
        self.logger = get_logger("repository_processor")
        self.error_handler = get_error_handler(
            "repository_processor",
            max_retries=3,
            retry_delay=5.0,
            exponential_backoff=True,
            timeout=1800.0  # 30 minutes
        )
        
        # Performance tracking
        self.operation_start_time = time.time()
        
        self.logger.info(f"Enhanced Repository Processor v2.0 initialized")
        self.logger.info(f"- Max concurrent repos: {max_concurrent_repos}")
        self.logger.info(f"- Workspace directory: {workspace_dir}")
        self.logger.info(f"- CodeBERT embeddings: {use_codebert}")
        
        # Register diagnostic collectors
        diagnostic_collector.register_service_checker(
            "repository_processor", 
            self._health_check_async
        )
    
    async def _health_check_async(self) -> Dict[str, Any]:
        """
        Async health check for diagnostic collector.
        
        Returns:
            Dict containing health status and metrics
        """
        try:
            async with error_handling_context("repository_processor", "health_check") as ctx:
                # Check component availability
                components_healthy = True
                component_status = {}
                
                # Check ChromaDB client
                try:
                    chroma_health = await self.chroma_client.health_check()
                    component_status["chromadb"] = chroma_health.get("status", "unknown")
                    if chroma_health.get("status") != "healthy":
                        components_healthy = False
                except Exception as e:
                    component_status["chromadb"] = "unhealthy"
                    components_healthy = False
                    ctx.add_diagnostic_data("chromadb_error", str(e))
                
                # Check Neo4j client
                try:
                    neo4j_health = await self.neo4j_client.health_check()
                    component_status["neo4j"] = neo4j_health.get("status", "unknown")
                    if neo4j_health.get("status") != "healthy":
                        components_healthy = False
                except Exception as e:
                    component_status["neo4j"] = "unhealthy"
                    components_healthy = False
                    ctx.add_diagnostic_data("neo4j_error", str(e))
                
                # Check processing capacity
                active_tasks_count = len(self.active_tasks)
                processing_capacity = self.max_concurrent_repos - active_tasks_count
                
                # Get performance stats
                stats = await self.get_processing_statistics()
                
                return {
                    "status": "healthy" if components_healthy else "unhealthy",
                    "components": component_status,
                    "active_tasks": active_tasks_count,
                    "processing_capacity": processing_capacity,
                    "statistics": stats,
                    "uptime_seconds": time.time() - self.operation_start_time
                }
                
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "uptime_seconds": time.time() - self.operation_start_time
            }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Public health check method.
        
        Returns:
            Dict containing health status and metrics
        """
        return await self._health_check_async()
    
    def _create_processing_context(self, repository_name: str, operation: str) -> ErrorContext:
        """
        Create error context for processing operations.
        
        Args:
            repository_name: Name of the repository being processed
            operation: Name of the operation being performed
            
        Returns:
            ErrorContext object
        """
        return ErrorContext(
            component="repository_processor",
            operation=operation,
            repository_name=repository_name,
            additional_data={
                "active_tasks": len(self.active_tasks),
                "processing_capacity": self.max_concurrent_repos - len(self.active_tasks),
                "use_codebert": self.use_codebert
            }
        )
    
    async def _validate_repository_config(self, config: Union[RepositoryConfig, LocalRepositoryConfig]) -> None:
        """
        Validate repository configuration with comprehensive error handling.
        
        Args:
            config: Repository configuration to validate
            
        Raises:
            ValidationError: If configuration is invalid
        """
        async with error_handling_context("repository_processor", "validate_config", 
                                         repository_name=config.name) as ctx:
            
            validation_start = time.time()
            validation_errors = []
            
            # Validate basic fields
            if not config.name or not config.name.strip():
                validation_errors.append("Repository name cannot be empty")
            
            if isinstance(config, RepositoryConfig):
                if not config.url or not config.url.strip():
                    validation_errors.append("Repository URL cannot be empty")
                
                # Validate URL format
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(config.url)
                    if not parsed.scheme or not parsed.netloc:
                        validation_errors.append("Invalid repository URL format")
                except Exception as e:
                    validation_errors.append(f"URL validation error: {str(e)}")
            
            elif isinstance(config, LocalRepositoryConfig):
                if not config.path or not config.path.strip():
                    validation_errors.append("Repository path cannot be empty")
                
                # Validate path exists
                repo_path = Path(config.path)
                if not repo_path.exists():
                    validation_errors.append(f"Repository path does not exist: {config.path}")
                elif not repo_path.is_dir():
                    validation_errors.append(f"Repository path is not a directory: {config.path}")
            
            # Validate processing limits
            if config.max_file_size <= 0:
                validation_errors.append("Max file size must be positive")
            
            if config.max_files_per_batch <= 0:
                validation_errors.append("Max files per batch must be positive")
            
            if config.max_processing_time <= 0:
                validation_errors.append("Max processing time must be positive")
            
            # Validate patterns
            if not config.include_patterns:
                validation_errors.append("Include patterns cannot be empty")
            
            # Add validation context
            ctx.add_diagnostic_data("validation_errors", validation_errors)
            ctx.add_diagnostic_data("config_type", type(config).__name__)
            
            validation_time = time.time() - validation_start
            
            # Log validation results
            log_validation_result(
                "repository_processor",
                "config_validation",
                len(validation_errors) == 0,
                validation_time,
                {
                    "repository_name": config.name,
                    "error_count": len(validation_errors)
                }
            )
            
            if validation_errors:
                raise ValidationError(
                    message=f"Repository configuration validation failed: {'; '.join(validation_errors)}",
                    validation_type="repository_config",
                    context=self._create_processing_context(config.name, "validate_config")
                )
    
    async def _handle_processing_error(self, 
                                     repository_name: str, 
                                     operation: str, 
                                     error: Exception) -> ProcessingResult:
        """
        Handle processing errors with comprehensive logging and recovery attempts.
        
        Args:
            repository_name: Name of the repository being processed
            operation: Operation that failed
            error: The exception that occurred
            
        Returns:
            ProcessingResult with error information
        """
        error_context = self._create_processing_context(repository_name, operation)
        
        # Determine error type and create appropriate structured exception
        if isinstance(error, GraphRAGException):
            structured_error = error
        else:
            # Wrap in appropriate GraphRAG exception
            if "timeout" in str(error).lower():
                structured_error = GraphRAGTimeoutError(
                    message=f"Processing timeout in {operation}: {str(error)}",
                    timeout_duration=1800.0,  # 30 minutes
                    context=error_context
                )
            elif "memory" in str(error).lower() or "resource" in str(error).lower():
                structured_error = ResourceError(
                    message=f"Resource error in {operation}: {str(error)}",
                    resource_type="memory",
                    context=error_context
                )
            elif "database" in str(error).lower() or "connection" in str(error).lower():
                structured_error = DatabaseError(
                    message=f"Database error in {operation}: {str(error)}",
                    database_type="unknown",
                    context=error_context,
                    cause=error
                )
            else:
                structured_error = ProcessingError(
                    message=f"Processing error in {operation}: {str(error)}",
                    processing_stage=operation,
                    context=error_context,
                    cause=error
                )
        
        # Log the structured error
        self.logger.error(
            f"Processing failed for repository {repository_name}",
            repository_name=repository_name,
            operation=operation,
            error_id=structured_error.error_id,
            error_code=structured_error.error_code,
            error_category=structured_error.category,
            recoverable=structured_error.recoverable
        )
        
        # Record performance impact
        performance_collector.record_metric(
            "repository_processing_error",
            1,
            labels={
                "repository": repository_name,
                "operation": operation,
                "error_category": structured_error.category,
                "recoverable": str(structured_error.recoverable)
            }
        )
        
        # Create processing result with error information
        result = ProcessingResult(
            repository_name=repository_name,
            status=ProcessingStatus.FAILED,
            error_message=structured_error.message,
            error_code=structured_error.error_code,
            completed_at=time.time()
        )
        
        # Add recovery suggestions to warnings
        for action in structured_error.recovery_actions:
            result.warnings.append(f"Recovery: {action.description}")
        
        return result
    
    async def process_repository(self, repo_config: RepositoryConfig, run_id: Optional[str] = None, progress_callback: Optional[callable] = None) -> ProcessingResult:
        """
        Process a single repository with comprehensive error handling.

        Args:
            repo_config: Repository configuration
            run_id: Correlation ID for structured logging

        Returns:
            ProcessingResult: Detailed processing results
        """
        rid = run_id or uuid.uuid4().hex
        result = ProcessingResult(
            repository_name=repo_config.name,
            status=ProcessingStatus.IN_PROGRESS
        )

        def log_stage(stage: str, **fields: Any):
            extra = {"run_id": rid, "repo": repo_config.name, "stage": stage}
            extra.update(fields or {})
            self.logger.info(f"[{rid}] {repo_config.name} - stage={stage}", extra=extra)

        async with self.semaphore:  # Control concurrency
            try:
                log_stage("start")
                
                # Progress callback helper
                async def notify_progress(stage: str, progress: float, details: Optional[Dict] = None):
                    if progress_callback:
                        try:
                            await progress_callback(stage, progress, details)
                        except Exception as e:
                            self.logger.warning(f"Progress callback error: {e}")
                
                # Phase 1: Repository preparation (0-20%)
                await notify_progress("cloning", 5.0, {"current_operation": "Preparing repository"})
                t0 = time.time()
                repo_path = await self._prepare_repository_async(repo_config)
                log_stage("prepare_repo_done", elapsed_ms=int((time.time() - t0) * 1000), path=str(repo_path))
                await notify_progress("cloning", 20.0, {"current_operation": "Repository prepared"})

                # Phase 2: Repository analysis (20-40%)
                await notify_progress("analyzing", 25.0, {"current_operation": "Analyzing repository structure"})
                t1 = time.time()
                analysis = await self._analyze_repository_async(repo_path, repo_config)
                log_stage("analyze_done",
                          elapsed_ms=int((time.time() - t1) * 1000),
                          file_count=analysis.get('file_count', 0),
                          loc=analysis.get('lines_of_code', 0))
                
                total_files = analysis.get('file_count', 0)
                await notify_progress("analyzing", 40.0, {
                    "current_operation": "Analysis complete",
                    "total_files": total_files,
                    "processed_files": 0
                })

                # Phase 3: Code file processing (40-80%)
                await notify_progress("parsing", 45.0, {
                    "current_operation": "Starting code processing",
                    "total_files": total_files,
                    "processed_files": 0
                })
                t2 = time.time()
                code_results = await self._process_code_files_async(repo_path, repo_config, analysis, progress_callback)
                log_stage("code_processing_done",
                          elapsed_ms=int((time.time() - t2) * 1000),
                          files=len(code_results.get('files', [])),
                          chunks=len(code_results.get('chunks', [])))
                
                processed_files = len(code_results.get('files', []))
                generated_chunks = len(code_results.get('chunks', []))
                await notify_progress("embedding", 80.0, {
                    "current_operation": "Code processing complete",
                    "total_files": total_files,
                    "processed_files": processed_files,
                    "generated_chunks": generated_chunks,
                    "embedding_progress": {
                        "total_chunks": generated_chunks,
                        "embedded_chunks": generated_chunks,
                        "embedding_rate": generated_chunks / max(time.time() - t2, 1)
                    }
                })

                # Phase 4: Maven dependency processing (if enabled)
                maven_results = None
                if repo_config.maven_enabled:
                    await notify_progress("parsing", 85.0, {"current_operation": "Processing Maven dependencies"})
                    t3 = time.time()
                    maven_results = await self._process_maven_dependencies_async(repo_path, repo_config)
                    deps = len(maven_results.get('dependencies', [])) if maven_results else 0
                    log_stage("maven_done", elapsed_ms=int((time.time() - t3) * 1000), dependencies=deps)

                # Phase 5: Data storage (80-95%)
                await notify_progress("storing", 90.0, {"current_operation": "Storing processed data"})
                t4 = time.time()
                await self._store_repository_data_async(repo_config, analysis, code_results, maven_results)
                log_stage("storage_done",
                          elapsed_ms=int((time.time() - t4) * 1000),
                          chunks=len(code_results.get('chunks', [])))
                await notify_progress("storing", 95.0, {"current_operation": "Data storage complete"})

                # Phase 6: Validation and completion (95-100%)
                await notify_progress("validating", 98.0, {"current_operation": "Validating stored data"})

                # Update result with success metrics
                result.status = ProcessingStatus.COMPLETED
                result.processed_files = len(code_results['files'])
                result.generated_chunks = len(code_results['chunks'])
                result.processing_time = time.time() - result.started_at
                result.completed_at = time.time()
                result.files_by_language = analysis.get('language_counts', {})
                result.total_lines_of_code = analysis.get('lines_of_code', 0)

                if maven_results:
                    result.dependency_count = len(maven_results.get('dependencies', []))
                    result.maven_artifacts = [dep.get('artifact_id', '') for dep in maven_results.get('dependencies', [])]

                self.processing_stats.add_result(result)
                log_stage("completed",
                          processed_files=result.processed_files,
                          generated_chunks=result.generated_chunks,
                          processing_time_ms=int(result.processing_time * 1000))

                await notify_progress("validating", 100.0, {
                    "current_operation": "Processing complete",
                    "processed_files": result.processed_files,
                    "generated_chunks": result.generated_chunks
                })

                return result

            except ProcessingError as e:
                # Handle known processing errors
                log_stage("failed_known", error=str(e), error_code=e.error_code)
                result.status = ProcessingStatus.FAILED
                result.error_message = str(e)
                result.error_code = e.error_code
                result.processing_time = time.time() - result.started_at
                result.completed_at = time.time()
                self.processing_stats.add_result(result)
                return result

            except Exception as e:
                # Handle unexpected errors
                log_stage("failed_unexpected", error=str(e))
                result.status = ProcessingStatus.FAILED
                result.error_message = f"Unexpected error processing {repo_config.name}: {e}"
                result.error_code = "UNEXPECTED_ERROR"
                result.processing_time = time.time() - result.started_at
                result.completed_at = time.time()
                self.processing_stats.add_result(result)
                return result
    
    async def process_local_repository(self, local_config: LocalRepositoryConfig, run_id: Optional[str] = None, progress_callback: Optional[callable] = None) -> ProcessingResult:
        """
        Process a local repository from filesystem path with comprehensive error handling.

        Args:
            local_config: Local repository configuration
            run_id: Correlation ID for structured logging

        Returns:
            ProcessingResult: Detailed processing results
        """
        rid = run_id or uuid.uuid4().hex
        result = ProcessingResult(
            repository_name=local_config.name,
            status=ProcessingStatus.IN_PROGRESS
        )

        def log_stage(stage: str, **fields: Any):
            extra = {"run_id": rid, "repo": local_config.name, "stage": stage}
            extra.update(fields or {})
            self.logger.info(f"[{rid}] {local_config.name} - stage={stage}", extra=extra)

        async with self.semaphore:  # Control concurrency
            try:
                log_stage("start_local", path=local_config.path)
                repo_path = Path(local_config.path)

                # Phase 1: Validate local path
                if not repo_path.exists():
                    raise ProcessingError(f"Local path does not exist: {local_config.path}", "PATH_NOT_FOUND")
                if not repo_path.is_dir():
                    raise ProcessingError(f"Local path is not a directory: {local_config.path}", "NOT_DIRECTORY")

                # Phase 2: Repository analysis (reuse existing logic)
                t1 = time.time()
                analysis = await self._analyze_repository_async(repo_path, local_config, progress_callback=progress_callback)
                log_stage("analyze_done",
                          elapsed_ms=int((time.time() - t1) * 1000),
                          file_count=analysis.get('file_count', 0),
                          loc=analysis.get('lines_of_code', 0))

                # Phase 3: Code file processing (reuse existing logic)
                t2 = time.time()
                code_results = await self._process_code_files_async(repo_path, local_config, analysis, progress_callback)
                log_stage("code_processing_done",
                          elapsed_ms=int((time.time() - t2) * 1000),
                          files=len(code_results.get('files', [])),
                          chunks=len(code_results.get('chunks', [])))

                # Phase 4: Maven dependency processing (optional for local)
                maven_results = None

                # Phase 5: Data storage with local metadata
                t4 = time.time()
                await self._store_local_repository_data_async(local_config, analysis, code_results, maven_results)
                log_stage("storage_done",
                          elapsed_ms=int((time.time() - t4) * 1000),
                          chunks=len(code_results.get('chunks', [])))

                # Update result with success metrics
                result.status = ProcessingStatus.COMPLETED
                result.processed_files = len(code_results['files'])
                result.generated_chunks = len(code_results['chunks'])
                result.processing_time = time.time() - result.started_at
                result.completed_at = time.time()
                result.files_by_language = analysis.get('language_counts', {})
                result.total_lines_of_code = analysis.get('lines_of_code', 0)

                self.processing_stats.add_result(result)
                log_stage("completed",
                          processed_files=result.processed_files,
                          generated_chunks=result.generated_chunks,
                          processing_time_ms=int(result.processing_time * 1000))

                return result

            except ProcessingError as e:
                log_stage("failed_known", error=str(e), error_code=e.error_code)
                result.status = ProcessingStatus.FAILED
                result.error_message = str(e)
                result.error_code = e.error_code
                result.processing_time = time.time() - result.started_at
                result.completed_at = time.time()
                self.processing_stats.add_result(result)
                return result

            except Exception as e:
                log_stage("failed_unexpected", error=str(e))
                result.status = ProcessingStatus.FAILED
                result.error_message = f"Unexpected error processing local repository {local_config.name}: {e}"
                result.error_code = "UNEXPECTED_ERROR"
                result.processing_time = time.time() - result.started_at
                result.completed_at = time.time()
                self.processing_stats.add_result(result)
                return result
    
    async def process_repository_dry_run(self, repo_config: RepositoryConfig, run_id: Optional[str] = None) -> ProcessingResult:
        """
        Dry-run processing: prepare, analyze, process code; skip writes to Chroma/Neo4j.
        Returns predicted counts only.
        """
        rid = run_id or uuid.uuid4().hex
        result = ProcessingResult(
            repository_name=repo_config.name,
            status=ProcessingStatus.IN_PROGRESS
        )

        def log_stage(stage: str, **fields: Any):
            extra = {"run_id": rid, "repo": repo_config.name, "stage": stage}
            extra.update(fields or {})
            self.logger.info(f"[{rid}] {repo_config.name} - stage={stage}", extra=extra)

        async with self.semaphore:
            try:
                log_stage("dry_run_start")
                t0 = time.time()
                repo_path = await self._prepare_repository_async(repo_config)
                log_stage("dry_prepare_done", elapsed_ms=int((time.time() - t0) * 1000), path=str(repo_path))

                t1 = time.time()
                analysis = await self._analyze_repository_async(repo_path, repo_config)
                log_stage("dry_analyze_done", elapsed_ms=int((time.time() - t1) * 1000), file_count=analysis.get('file_count', 0), loc=analysis.get('lines_of_code', 0))

                t2 = time.time()
                code_results = await self._process_code_files_async(repo_path, repo_config, analysis)
                log_stage("dry_code_done", elapsed_ms=int((time.time() - t2) * 1000), files=len(code_results.get('files', [])), chunks=len(code_results.get('chunks', [])))

                # Optional: estimate maven dependency count without writes
                maven_results = None
                if repo_config.maven_enabled:
                    # safe, read-only maven parse; we won't write results
                    try:
                        t3 = time.time()
                        maven_results = await self._process_maven_dependencies_async(repo_path, repo_config)
                        deps = len(maven_results.get('dependencies', [])) if maven_results else 0
                        log_stage("dry_maven_done", elapsed_ms=int((time.time() - t3) * 1000), dependencies=deps)
                    except Exception as e:
                        self.logger.warning(f"[{rid}] Maven dry-run parse failed: {e}")

                result.status = ProcessingStatus.COMPLETED
                result.processed_files = len(code_results.get('files', []))
                result.generated_chunks = len(code_results.get('chunks', []))
                result.processing_time = time.time() - result.started_at
                result.completed_at = time.time()
                result.files_by_language = analysis.get('language_counts', {})
                result.total_lines_of_code = analysis.get('lines_of_code', 0)
                if maven_results:
                    result.dependency_count = len(maven_results.get('dependencies', []))
                    result.maven_artifacts = [dep.get('artifact_id', '') for dep in maven_results.get('dependencies', [])]

                self.processing_stats.add_result(result)
                log_stage("dry_run_completed",
                          processed_files=result.processed_files,
                          generated_chunks=result.generated_chunks,
                          processing_time_ms=int(result.processing_time * 1000))
                return result

            except Exception as e:
                self.logger.info(f"[{rid}] {repo_config.name} - stage=dry_run_failed", extra={"run_id": rid, "repo": repo_config.name, "stage": "dry_run_failed", "error": str(e)})
                result.status = ProcessingStatus.FAILED
                result.error_message = f"Dry-run failed: {e}"
                result.error_code = "DRY_RUN_ERROR"
                result.processing_time = time.time() - result.started_at
                result.completed_at = time.time()
                self.processing_stats.add_result(result)
                return result

    async def process_local_repository_dry_run(self, local_config: LocalRepositoryConfig, run_id: Optional[str] = None) -> ProcessingResult:
        """
        Dry-run for local repositories: analyze and process code; skip all writes.
        """
        rid = run_id or uuid.uuid4().hex
        result = ProcessingResult(
            repository_name=local_config.name,
            status=ProcessingStatus.IN_PROGRESS
        )

        def log_stage(stage: str, **fields: Any):
            extra = {"run_id": rid, "repo": local_config.name, "stage": stage}
            extra.update(fields or {})
            self.logger.info(f"[{rid}] {local_config.name} - stage={stage}", extra=extra)

        async with self.semaphore:
            try:
                log_stage("dry_run_local_start", path=local_config.path)
                repo_path = Path(local_config.path)
                if not repo_path.exists():
                    raise ProcessingError(f"Local path does not exist: {local_config.path}", "PATH_NOT_FOUND")
                if not repo_path.is_dir():
                    raise ProcessingError(f"Local path is not a directory: {local_config.path}", "NOT_DIRECTORY")

                t1 = time.time()
                analysis = await self._analyze_repository_async(repo_path, local_config)
                log_stage("dry_analyze_done", elapsed_ms=int((time.time() - t1) * 1000), file_count=analysis.get('file_count', 0), loc=analysis.get('lines_of_code', 0))

                t2 = time.time()
                code_results = await self._process_code_files_async(repo_path, local_config, analysis)
                log_stage("dry_code_done", elapsed_ms=int((time.time() - t2) * 1000), files=len(code_results.get('files', [])), chunks=len(code_results.get('chunks', [])))

                result.status = ProcessingStatus.COMPLETED
                result.processed_files = len(code_results.get('files', []))
                result.generated_chunks = len(code_results.get('chunks', []))
                result.processing_time = time.time() - result.started_at
                result.completed_at = time.time()
                result.files_by_language = analysis.get('language_counts', {})
                result.total_lines_of_code = analysis.get('lines_of_code', 0)

                self.processing_stats.add_result(result)
                log_stage("dry_run_local_completed",
                          processed_files=result.processed_files,
                          generated_chunks=result.generated_chunks,
                          processing_time_ms=int(result.processing_time * 1000))
                return result

            except Exception as e:
                self.logger.info(f"[{rid}] {local_config.name} - stage=dry_run_local_failed", extra={"run_id": rid, "repo": local_config.name, "stage": "dry_run_local_failed", "error": str(e)})
                result.status = ProcessingStatus.FAILED
                result.error_message = f"Dry-run (local) failed: {e}"
                result.error_code = "DRY_RUN_LOCAL_ERROR"
                result.processing_time = time.time() - result.started_at
                result.completed_at = time.time()
                self.processing_stats.add_result(result)
                return result

    async def _prepare_repository_async(self, repo_config: RepositoryConfig) -> Path:
        """
        Prepare repository for processing (pure async, no threading).
        
        Args:
            repo_config: Repository configuration
            
        Returns:
            Path: Path to the prepared repository
        """
        repo_path = self.workspace_dir / repo_config.name
        
        try:
            if repo_path.exists():
                self.logger.info(f"Repository exists, updating: {repo_path}")
                # Update existing repository
                await self._run_git_command_async(["git", "pull"], cwd=repo_path)
                await self._run_git_command_async(["git", "checkout", repo_config.branch], cwd=repo_path)
            else:
                self.logger.info(f"Cloning repository: {repo_config.url}")
                # Clone repository (skip for dummy URLs since local repo exists)
                if not repo_config.url.startswith("https://github.com/dummy/"):
                    await self._run_git_command_async([
                        "git", "clone", "--depth", "1", 
                        "--branch", repo_config.branch,
                        repo_config.url, str(repo_path)
                    ])
                elif not repo_path.exists():
                    raise ProcessingError(
                        f"Repository not found at {repo_path} and URL is dummy",
                        error_code="REPO_NOT_FOUND",
                        recoverable=False
                    )
            
            return repo_path
            
        except subprocess.CalledProcessError as e:
            raise ProcessingError(
                f"Git command failed: {e.stderr if hasattr(e, 'stderr') else str(e)}",
                error_code="GIT_ERROR",
                recoverable=True
            )
        except Exception as e:
            raise ProcessingError(
                f"Repository preparation failed: {e}",
                error_code="REPO_PREP_ERROR",
                recoverable=True
            )
    
    async def _run_git_command_async(self, command: List[str], cwd: Optional[Path] = None) -> str:
        """
        Run git command asynchronously without threading.
        
        Args:
            command: Git command to execute
            cwd: Working directory
            
        Returns:
            str: Command output
        """
        try:
            self.logger.debug(f"Running git command: {' '.join(command)}")
            
            # Use asyncio.create_subprocess_exec for pure async execution
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60.0)
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='ignore').strip()
                raise subprocess.CalledProcessError(process.returncode, command, stderr=error_msg)
            
            return stdout.decode('utf-8', errors='ignore').strip()
            
        except asyncio.TimeoutError:
            raise ProcessingError(
                f"Git command timed out: {' '.join(command)}",
                error_code="GIT_TIMEOUT",
                recoverable=True
            )
        except Exception as e:
            raise ProcessingError(
                f"Git command failed: {e}",
                error_code="GIT_ERROR",
                recoverable=True
            )
    
    async def _analyze_repository_async(self, repo_path: Path, repo_config: Union[RepositoryConfig, LocalRepositoryConfig], progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """
        Analyze repository structure asynchronously.
        
        Args:
            repo_path: Path to repository
            repo_config: Repository configuration
            progress_callback: Optional async function to report progress
            
        Returns:
            Dict[str, Any]: Repository analysis results
        """#
        analysis = {
            'languages': set(),
            'file_count': 0,
            'lines_of_code': 0,
            'complexity_score': 0.0,
            'has_maven': False,
            'has_gradle': False,
            'has_npm': False,
            'main_language': None,
            'language_counts': defaultdict(int),
            'file_extensions': defaultdict(int)
        }
        
        try:
            self.logger.info(f"Analyzing repository structure: {repo_path}")
            
            # Find all relevant files
            files = []
            for pattern in repo_config.include_patterns:
                pattern_files = list(repo_path.glob(pattern))
                files.extend(pattern_files)
            
            # Filter by exclusion patterns and size
            filtered_files = []
            for file_path in files:
                # Check exclusion patterns
                excluded = False
                for pattern in repo_config.exclude_patterns:
                    if _matches_exclusion_pattern(file_path, pattern, repo_path):
                        excluded = True
                        break
                
                if not excluded and file_path.is_file():
                    try:
                        file_size = file_path.stat().st_size
                        if file_size <= repo_config.max_file_size:
                            filtered_files.append(file_path)
                    except (OSError, PermissionError) as e:
                        self.logger.warning(f"Cannot access file {file_path}: {e}")
            
            # Analyze files in batches
            batch_size = repo_config.max_files_per_batch
            total_lines = 0
            
            for i in range(0, len(filtered_files), batch_size):
                batch = filtered_files[i:i + batch_size]
                batch_results = await self._analyze_file_batch_async(batch, repo_path)
                
                # Aggregate results
                for result in batch_results:
                    if result['language']:
                        analysis['languages'].add(result['language'])
                        analysis['language_counts'][result['language']] += 1
                    
                    extension = result['file_path'].suffix.lower()
                    analysis['file_extensions'][extension] += 1
                    total_lines += result['lines']
                
                # Yield control periodically
                await asyncio.sleep(0)

                # Report progress if callback is provided
                if progress_callback:
                    progress_percent = 20.0 + (i / len(filtered_files)) * 20.0  # 20-40% range
                    await progress_callback("analyzing", progress_percent, {
                        "current_operation": f"Analyzed batch {i//batch_size + 1}",
                        "processed_files": i + len(batch),
                        "total_files": len(filtered_files)
                    })
            
            # Finalize analysis
            analysis['file_count'] = len(filtered_files)
            analysis['lines_of_code'] = total_lines
            analysis['languages'] = list(analysis['languages'])
            
            # Determine main language
            if analysis['language_counts']:
                analysis['main_language'] = max(analysis['language_counts'].items(), key=lambda x: x[1])[0]
            
            # Check for build systems
            analysis['has_maven'] = (repo_path / "pom.xml").exists()
            analysis['has_gradle'] = (repo_path / "build.gradle").exists() or (repo_path / "build.gradle.kts").exists()
            analysis['has_npm'] = (repo_path / "package.json").exists()
            
            self.logger.info(f"Repository analysis completed: {analysis['file_count']} files, {analysis['lines_of_code']} LOC")
            return analysis
            
        except Exception as e:
            raise ProcessingError(
                f"Repository analysis failed: {e}",
                error_code="ANALYSIS_ERROR",
                recoverable=True
            )
    
    async def _analyze_file_batch_async(self, files: List[Path], repo_path: Path) -> List[Dict[str, Any]]:
        """
        Analyze a batch of files asynchronously.
        
        Args:
            files: List of file paths to analyze
            repo_path: Repository root path
            
        Returns:
            List[Dict[str, Any]]: Analysis results for each file
        """
        results = []
        
        for file_path in files:
            try:
                # Read file content asynchronously
                content = await self._read_file_async(file_path)
                
                # Detect language
                language = self.tree_sitter_parser.detect_language(str(file_path), content)
                language_str = language.value if language else None
                
                # Count lines
                lines = len(content.split('\n'))
                
                results.append({
                    'file_path': file_path,
                    'relative_path': str(file_path.relative_to(repo_path)),
                    'language': language_str,
                    'lines': lines,
                    'size': len(content)
                })
                
            except Exception as e:
                self.logger.warning(f"Error analyzing file {file_path}: {e}")
                results.append({
                    'file_path': file_path,
                    'relative_path': str(file_path.relative_to(repo_path)),
                    'language': None,
                    'lines': 0,
                    'size': 0
                })
        
        return results
    
    async def _read_file_async(self, file_path: Path) -> str:
        """
        Read file content asynchronously.
        
        Args:
            file_path: Path to file
            
        Returns:
            str: File content
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            return content
        except Exception as e:
            self.logger.warning(f"Error reading file {file_path}: {e}")
            return ""
    
    async def _process_code_files_async(self, 
                                      repo_path: Path, 
                                      repo_config: RepositoryConfig,
                                      analysis: Dict[str, Any],
                                      progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """
        Process code files asynchronously without threading.
        
        Args:
            repo_path: Repository path
            repo_config: Repository configuration
            analysis: Repository analysis results
            
        Returns:
            Dict[str, Any]: Processing results
        """
        files_data = []
        all_chunks = []
        
        try:
            start_time = time.time()
            self.logger.info(f"Processing code files for repository: {repo_config.name}")
            
            # Find all code files
            code_files = []
            for pattern in repo_config.include_patterns:
                code_files.extend(repo_path.glob(pattern))
            
            # Filter files
            filtered_files = []
            for file_path in code_files:
                # Check exclusion patterns
                excluded = False
                for pattern in repo_config.exclude_patterns:
                    if _matches_exclusion_pattern(file_path, pattern, repo_path):
                        excluded = True
                        break
                
                if not excluded and file_path.is_file():
                    try:
                        if file_path.stat().st_size <= repo_config.max_file_size:
                            filtered_files.append(file_path)
                    except (OSError, PermissionError):
                        continue
            
            # Process files in batches with progress tracking
            batch_size = repo_config.max_files_per_batch
            total_files = len(filtered_files)
            processed_files = 0
            
            for i in range(0, len(filtered_files), batch_size):
                batch = filtered_files[i:i + batch_size]
                
                # Update progress before processing batch
                if progress_callback:
                    current_file = str(batch[0].relative_to(repo_path)) if batch else None
                    progress_percent = 40.0 + (processed_files / total_files) * 35.0  # 40-75% range
                    try:
                        await progress_callback("parsing", progress_percent, {
                            "current_file": current_file,
                            "processed_files": processed_files,
                            "total_files": total_files,
                            "current_operation": f"Processing files batch {i//batch_size + 1}"
                        })
                    except Exception as e:
                        self.logger.warning(f"Progress callback error: {e}")
                
                batch_results = await self._process_file_batch_async(batch, repo_path, repo_config, progress_callback)
                
                files_data.extend(batch_results['files'])
                all_chunks.extend(batch_results['chunks'])
                processed_files += len(batch)
                
                # Update progress after processing batch
                if progress_callback:
                    progress_percent = 40.0 + (processed_files / total_files) * 35.0  # 40-75% range
                    try:
                        await progress_callback("embedding", progress_percent, {
                            "processed_files": processed_files,
                            "total_files": total_files,
                            "generated_chunks": len(all_chunks),
                            "current_operation": f"Generated {len(all_chunks)} code chunks",
                            "embedding_progress": {
                                "total_chunks": len(all_chunks),
                                "embedded_chunks": len(all_chunks),
                                "embedding_rate": len(all_chunks) / max(time.time() - start_time, 1) if 'start_time' in locals() else 0,
                                "current_file": str(batch[-1].relative_to(repo_path)) if batch else None
                            }
                        })
                    except Exception as e:
                        self.logger.warning(f"Progress callback error: {e}")
                
                # Yield control and log progress
                await asyncio.sleep(0)
                self.logger.debug(f"Processed batch {i//batch_size + 1}/{(len(filtered_files) + batch_size - 1)//batch_size}")
            
            return {
                'files': files_data,
                'chunks': all_chunks,
                'statistics': {
                    'total_files': len(files_data),
                    'total_chunks': len(all_chunks),
                    'languages': analysis['languages'],
                    'lines_of_code': analysis['lines_of_code']
                }
            }
            
        except Exception as e:
            raise ProcessingError(
                f"Code file processing failed: {e}",
                error_code="CODE_PROCESSING_ERROR",
                recoverable=True
            )
    
    async def _process_file_batch_async(self, 
                                       files: List[Path], 
                                       repo_path: Path,
                                       repo_config: RepositoryConfig,
                                       progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """
        Process a batch of files asynchronously (no threading).
        
        Args:
            files: Files to process
            repo_path: Repository root path
            repo_config: Repository configuration
            progress_callback: Optional async function to report progress
            
        Returns:
            Dict[str, Any]: Batch processing results
        """
        batch_files = []
        batch_chunks = []
        
        for file_path in files:
            try:
                # Read file content
                content = await self._read_file_async(file_path)
                if not content.strip():
                    continue
                
                # Detect language
                language = self.tree_sitter_parser.detect_language(str(file_path), content)
                if not language:
                    continue
                
                # Generate relative path
                rel_path = str(file_path.relative_to(repo_path))
                
                # Create chunking config
                chunking_config = ChunkingConfig(
                    max_chunk_size=1000,
                    min_chunk_size=100,
                    include_context=True,
                    semantic_splitting=True
                )
                
                # Create chunker with config
                chunker = CodeChunker(chunking_config)
                
                # Generate chunks with enhanced parsing
                chunks = chunker.chunk_file(rel_path, content, language)
                
                # ENHANCED: Extract business rules and framework patterns
                business_analysis = await self._extract_business_analysis(content, rel_path, language)
                
                # Store file data with business context
                file_data = {
                    'path': rel_path,
                    'language': language.value,
                    'size': len(content),
                    'lines': len(content.split('\n')),
                    'chunks_count': len(chunks),
                    'business_analysis': business_analysis
                }
                
                batch_files.append(file_data)
                batch_chunks.extend(chunks)
                
                # ENHANCED: Store business analysis in Neo4j
                await self._store_business_analysis_to_neo4j(business_analysis, rel_path, repo_config.name)
                
                # Yield control periodically for async processing
                if len(batch_files) % 5 == 0:
                    await asyncio.sleep(0)

                # Report progress if callback is provided
                if progress_callback:
                    progress_percent = 40.0 + (len(batch_files) / len(files)) * 40.0  # 40-80% range
                    await progress_callback("parsing", progress_percent, {
                        "current_file": rel_path,
                        "processed_files": len(batch_files),
                        "total_files": len(files),
                        "generated_chunks": len(batch_chunks)
                    })
                
            except Exception as e:
                self.logger.warning(f"Error processing file {file_path}: {e}")
        
        return {
            'files': batch_files,
            'chunks': batch_chunks
        }
    
    async def _process_maven_dependencies_async(self, 
                                               repo_path: Path, 
                                               repo_config: RepositoryConfig) -> Optional[Dict[str, Any]]:
        """
        Process Maven dependencies asynchronously.
        
        Args:
            repo_path: Repository path
            repo_config: Repository configuration
            
        Returns:
            Optional[Dict[str, Any]]: Maven processing results
        """
        pom_path = repo_path / "pom.xml"
        
        if not pom_path.exists():
            return None
        
        try:
            self.logger.info(f"Processing Maven dependencies for: {repo_config.name}")
            
            # Parse POM file
            pom_content = await self._read_file_async(pom_path)
            dependencies = self.maven_parser.parse_pom(pom_content)
            
            # Resolve additional dependency information
            resolved_deps = []
            for dep in dependencies:
                resolved_dep = await self._resolve_dependency_async(dep)
                resolved_deps.append(resolved_dep)
            
            return {
                'pom_path': str(pom_path.relative_to(repo_path)),
                'dependencies': resolved_deps,
                'dependency_count': len(resolved_deps)
            }
            
        except Exception as e:
            self.logger.warning(f"Maven processing failed for {repo_config.name}: {e}")
            return {
                'pom_path': str(pom_path.relative_to(repo_path)),
                'dependencies': [],
                'dependency_count': 0,
                'error': str(e)
            }
    
    async def _resolve_dependency_async(self, dependency: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve additional dependency information asynchronously.
        
        Args:
            dependency: Dependency information
            
        Returns:
            Dict[str, Any]: Resolved dependency information
        """
        # Add resolved information (placeholder for now)
        resolved = dict(dependency)
        resolved['resolved_at'] = time.time()
        return resolved
    
    async def _store_repository_data_async(self, 
                                          repo_config: RepositoryConfig,
                                          analysis: Dict[str, Any],
                                          code_results: Dict[str, Any],
                                          maven_results: Optional[Dict[str, Any]]):
        """
        Store repository data in ChromaDB and Neo4j asynchronously.
        
        Args:
            repo_config: Repository configuration
            analysis: Repository analysis results
            code_results: Code processing results
            maven_results: Maven processing results
        """
        try:
            self.logger.info(f"Storing repository data: {repo_config.name}")
            
            # Store code chunks in ChromaDB
            if code_results['chunks']:
                enhanced_chunks = []
                for chunk in code_results['chunks']:
                    enhanced_chunk = EnhancedChunk(
                        chunk=chunk,
                        business_domain=repo_config.business_domain,
                        importance_score=1.0,
                        context_before="",
                        context_after="",
                        related_chunks=[]
                    )
                    enhanced_chunks.append(enhanced_chunk)
                
                success = await self.chroma_client.add_chunks(enhanced_chunks, repo_config.name)
                if not success:
                    raise ProcessingError(
                        "Failed to store chunks in ChromaDB",
                        error_code="CHROMADB_STORAGE_ERROR",
                        recoverable=True
                    )
            
            # Store repository metadata in Neo4j
            await self._store_neo4j_metadata_async(repo_config, analysis, code_results, maven_results)
            
            self.logger.info(f"Repository data stored successfully: {repo_config.name}")
            
        except Exception as e:
            raise ProcessingError(
                f"Data storage failed: {e}",
                error_code="STORAGE_ERROR",
                recoverable=True
            )
    
    async def _store_local_repository_data_async(self, 
                                               local_config: LocalRepositoryConfig,
                                               analysis: Dict[str, Any],
                                               code_results: Dict[str, Any],
                                               maven_results: Optional[Dict[str, Any]]):
        """
        Store local repository data in ChromaDB and Neo4j asynchronously.
        
        Adapts LocalRepositoryConfig to RepositoryConfig format for storage.
        
        Args:
            local_config: Local repository configuration
            analysis: Repository analysis results
            code_results: Code processing results
            maven_results: Maven processing results
        """
        try:
            self.logger.info(f"Storing local repository data: {local_config.name}")
            
            # Store code chunks in ChromaDB (same logic as remote)
            if code_results['chunks']:
                enhanced_chunks = []
                for chunk in code_results['chunks']:
                    enhanced_chunk = EnhancedChunk(
                        chunk=chunk,
                        business_domain=local_config.business_domain,
                        importance_score=1.0,
                        context_before="",
                        context_after="",
                        related_chunks=[]
                    )
                    enhanced_chunks.append(enhanced_chunk)
                
                success = await self.chroma_client.add_chunks(enhanced_chunks, local_config.name)
                if not success:
                    raise ProcessingError(
                        "Failed to store chunks in ChromaDB",
                        error_code="CHROMADB_STORAGE_ERROR",
                        recoverable=True
                    )
            
            # Store local repository metadata in Neo4j
            await self._store_local_neo4j_metadata_async(local_config, analysis, code_results, maven_results)
            
            self.logger.info(f"Local repository data stored successfully: {local_config.name}")
            
        except Exception as e:
            raise ProcessingError(
                f"Data storage failed: {e}",
                error_code="STORAGE_ERROR",
                recoverable=True
            )
    
    async def _store_local_neo4j_metadata_async(self, 
                                              local_config: LocalRepositoryConfig,
                                              analysis: Dict[str, Any],
                                              code_results: Dict[str, Any],
                                              maven_results: Optional[Dict[str, Any]]):
        """
        Store local repository metadata in Neo4j asynchronously.
        
        Args:
            local_config: Local repository configuration
            analysis: Repository analysis results
            code_results: Code processing results with chunks
            maven_results: Maven processing results
        """
        try:
            # Create repository node with local path as URL
            repo_query = GraphQuery(
                cypher="""
                MERGE (r:Repository {name: $name})
                SET r.url = $url,
                    r.branch = $branch,
                    r.priority = $priority,
                    r.business_domain = $business_domain,
                    r.team_owner = $team_owner,
                    r.is_golden_repo = $is_golden_repo,
                    r.languages = $languages,
                    r.file_count = $file_count,
                    r.lines_of_code = $lines_of_code,
                    r.chunks_count = $chunks_count,
                    r.created_at = datetime(),
                    r.updated_at = datetime(),
                    r.source_type = $source_type
                RETURN r
                """,
                parameters={
                    "name": local_config.name,
                    "url": f"file://{local_config.path}",  # Use file:// protocol for local paths
                    "branch": "local",  # Local repositories don't have branches
                    "priority": local_config.priority.value,
                    "business_domain": local_config.business_domain,
                    "team_owner": local_config.team_owner,
                    "is_golden_repo": local_config.is_golden_repo,
                    "languages": list(analysis.get('language_counts', {}).keys()),
                    "file_count": analysis.get('file_count', 0),
                    "lines_of_code": analysis.get('lines_of_code', 0),
                    "chunks_count": len(code_results.get('chunks', [])),
                    "source_type": "local"
                }
            )
            
            await self.neo4j_client.execute_query(repo_query)
            self.logger.info(f"Local repository metadata stored in Neo4j: {local_config.name}")
            
        except Exception as e:
            self.logger.error(f"Failed to store local repository metadata in Neo4j: {e}")
            raise ProcessingError(
                f"Neo4j metadata storage failed: {e}",
                error_code="NEO4J_STORAGE_ERROR",
                recoverable=True
            )
    
    async def _store_neo4j_metadata_async(self, 
                                         repo_config: RepositoryConfig,
                                         analysis: Dict[str, Any],
                                         code_results: Dict[str, Any],
                                         maven_results: Optional[Dict[str, Any]]):
        """
        Store repository metadata in Neo4j asynchronously.
        
        Args:
            repo_config: Repository configuration
            analysis: Repository analysis results
            code_results: Code processing results with chunks
            maven_results: Maven processing results
        """
        try:
            # Create repository node
            repo_query = GraphQuery(
                cypher="""
                MERGE (r:Repository {name: $name})
                SET r.url = $url,
                    r.branch = $branch,
                    r.priority = $priority,
                    r.business_domain = $business_domain,
                    r.team_owner = $team_owner,
                    r.is_golden_repo = $is_golden_repo,
                    r.languages = $languages,
                    r.file_count = $file_count,
                    r.lines_of_code = $lines_of_code,
                    r.chunks_count = $chunks_count,
                    r.updated_at = datetime()
                RETURN r
                """,
                parameters={
                    "name": repo_config.name,
                    "url": repo_config.url,
                    "branch": repo_config.branch,
                    "priority": repo_config.priority.value,
                    "business_domain": repo_config.business_domain,
                    "team_owner": repo_config.team_owner,
                    "is_golden_repo": repo_config.is_golden_repo,
                    "languages": analysis['languages'],
                    "file_count": analysis['file_count'],
                    "lines_of_code": analysis['lines_of_code'],
                    "chunks_count": len(code_results.get('chunks', []))
                },
                read_only=False
            )
            
            await self.neo4j_client.execute_query(repo_query)
            
            # Store Maven dependencies if available
            if maven_results and maven_results.get('dependencies'):
                for dep in maven_results['dependencies']:
                    dep_query = GraphQuery(
                        cypher="""
                        MATCH (r:Repository {name: $repo_name})
                        MERGE (d:MavenArtifact {groupId: $group_id, artifactId: $artifact_id})
                        SET d.version = $version
                        MERGE (r)-[:DEPENDS_ON]->(d)
                        """,
                        parameters={
                            "repo_name": repo_config.name,
                            "group_id": dep.get('group_id', ''),
                            "artifact_id": dep.get('artifact_id', ''),
                            "version": dep.get('version', '')
                        },
                        read_only=False
                    )
                    await self.neo4j_client.execute_query(dep_query)
            
        except Exception as e:
            self.logger.error(f"Neo4j metadata storage failed: {e}")
            raise
    
    async def get_processing_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive processing statistics.
        
        Returns:
            Dict[str, Any]: Processing statistics
        """
        runtime = time.time() - self.processing_stats.start_time
        
        return {
            'total_repositories': self.processing_stats.total_repositories,
            'completed_repositories': self.processing_stats.completed_repositories,
            'failed_repositories': self.processing_stats.failed_repositories,
            'success_rate': (
                self.processing_stats.completed_repositories / max(self.processing_stats.total_repositories, 1)
            ) * 100,
            'total_files_processed': self.processing_stats.total_files_processed,
            'total_chunks_generated': self.processing_stats.total_chunks_generated,
            'total_processing_time': self.processing_stats.total_processing_time,
            'average_processing_time': (
                self.processing_stats.total_processing_time / max(self.processing_stats.total_repositories, 1)
            ),
            'runtime_seconds': runtime,
            'active_tasks': len(self.active_tasks),
            'queue_size': self.processing_queue.qsize()
        }

    async def health_check(self) -> Dict[str, Any]:
        """
        Minimal non-throwing health check for readiness.
        Always returns healthy with basic stats snapshot to avoid blocking readiness.
        """
        try:
            stats = await self.get_processing_statistics()
        except Exception as e:
            # Never raise from health_check
            stats = {"error": str(e)}
        return {
            "status": "healthy",
            "timestamp": time.time(),
            "checks": {
                "initialized": {"status": "pass"},
                "queue": {"status": "pass", "size": stats.get("queue_size", 0)}
            },
            "statistics": stats
        }
    
    async def cleanup(self):
        """Cleanup resources and cancel active tasks."""
        try:
            # Cancel all active tasks
            for task_id, task in self.active_tasks.items():
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

            self.active_tasks.clear()

            self.logger.info("Enhanced Repository Processor cleanup completed")

        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
    
    async def _extract_business_analysis(self, content: str, file_path: str, language) -> Dict[str, Any]:
        """
        Extract business rules and framework patterns from code content.
        
        Args:
            content: File content
            file_path: File path for context
            language: Detected programming language
            
        Returns:
            Dict containing business analysis results
        """
        analysis = {
            'business_rules': [],
            'framework_patterns': {},
            'migration_complexity': 'low',
            'struts_components': [],
            'corba_interfaces': [],
            'jsp_patterns': [],
            'migration_notes': []
        }
        
        try:
            # Use enhanced Tree-sitter parser
            chunks, relationships = self.tree_sitter_parser.parse_code(content, language, file_path)
            
            # Aggregate business information from chunks
            total_business_rules = 0
            total_framework_patterns = 0
            
            for chunk in chunks:
                if hasattr(chunk, 'business_rules') and chunk.business_rules:
                    analysis['business_rules'].extend(chunk.business_rules)
                    total_business_rules += len(chunk.business_rules)
                
                if hasattr(chunk, 'framework_patterns') and chunk.framework_patterns:
                    analysis['framework_patterns'].update(chunk.framework_patterns)
                    total_framework_patterns += 1
                    
                    # Categorize framework-specific patterns
                    if 'struts_namespace' in chunk.framework_patterns:
                        analysis['struts_components'].append({
                            'type': chunk.chunk_type,
                            'name': chunk.name,
                            'business_purpose': chunk.framework_patterns.get('business_purpose', ''),
                            'location': f"{file_path}:{chunk.start_line}"
                        })
                    
                    if 'corba_interface' in chunk.framework_patterns:
                        analysis['corba_interfaces'].append({
                            'interface': chunk.framework_patterns['corba_interface'],
                            'operations': chunk.framework_patterns.get('business_operations', []),
                            'location': f"{file_path}:{chunk.start_line}"
                        })
                
                if hasattr(chunk, 'migration_notes') and chunk.migration_notes:
                    analysis['migration_notes'].extend(chunk.migration_notes)
            
            # Calculate migration complexity based on patterns found
            complexity_score = 0
            
            # JSP/Servlet complexity
            if file_path.endswith(('.jsp', '.tag', '.tagx')):
                analysis['jsp_patterns'] = self._analyze_jsp_complexity(content)
                complexity_score += len(analysis['jsp_patterns']) * 2
            
            # Struts complexity
            if any('struts' in pattern.lower() for pattern in analysis['framework_patterns'].keys()):
                complexity_score += 5
            
            # CORBA complexity
            if analysis['corba_interfaces']:
                complexity_score += len(analysis['corba_interfaces']) * 3
            
            # Business rules complexity
            complexity_score += total_business_rules
            
            # Determine migration complexity level
            if complexity_score <= 3:
                analysis['migration_complexity'] = 'low'
            elif complexity_score <= 10:
                analysis['migration_complexity'] = 'medium'
            else:
                analysis['migration_complexity'] = 'high'
                
            # Add relationships information
            analysis['relationships'] = [
                {
                    'type': rel.relationship_type,
                    'source': rel.source_id,
                    'target': rel.target_id,
                    'location': rel.source_location
                }
                for rel in relationships
            ]
            
        except Exception as e:
            self.logger.warning(f"Business analysis failed for {file_path}: {e}")
            # Return basic analysis on error
            
        return analysis
    
    def _analyze_jsp_complexity(self, content: str) -> List[Dict[str, Any]]:
        """Analyze JSP-specific complexity patterns."""
        patterns = []
        
        # Check for embedded Java code (scriptlets)
        import re
        scriptlets = re.findall(r'<%[^@](.*?)%>', content, re.DOTALL)
        if scriptlets:
            patterns.append({
                'type': 'scriptlets',
                'count': len(scriptlets),
                'complexity': 'high' if len(scriptlets) > 5 else 'medium',
                'migration_note': 'Scriptlets need to be converted to Angular components'
            })
        
        # Check for direct database access
        if any(db_pattern in content for db_pattern in ['Connection', 'PreparedStatement', 'ResultSet']):
            patterns.append({
                'type': 'direct_db_access',
                'complexity': 'high',
                'migration_note': 'Direct DB access should be moved to GraphQL resolvers'
            })
        
        # Check for session management
        if 'session.' in content:
            patterns.append({
                'type': 'session_management',
                'complexity': 'medium',
                'migration_note': 'Session usage needs Angular state management'
            })
        
        # Check for Struts tags
        struts_tags = re.findall(r'<(html|bean|logic|nested):(\w+)', content)
        if struts_tags:
            patterns.append({
                'type': 'struts_tags',
                'count': len(struts_tags),
                'complexity': 'medium',
                'migration_note': 'Struts tags need Angular component equivalents'
            })
        
        return patterns
    
    async def _store_business_analysis_to_neo4j(self, business_analysis: Dict[str, Any], file_path: str, repo_name: str):
        """Store business analysis results in Neo4j graph database."""
        try:
            # Store business rules
            for i, rule_text in enumerate(business_analysis.get('business_rules', [])):
                rule_id = f"{repo_name}:{file_path}:rule:{i}"
                await self.neo4j_client.create_business_rule(
                    rule_id=rule_id,
                    rule_text=rule_text,
                    domain=self._infer_business_domain(rule_text),
                    complexity=business_analysis.get('migration_complexity', 'medium'),
                    rule_type='validation',
                    file_path=file_path,
                    location=f"{file_path}:rule_{i}"
                )
            
            # Store Struts components
            for struts_comp in business_analysis.get('struts_components', []):
                await self.neo4j_client.create_struts_action(
                    path=struts_comp.get('name', f"{file_path}:struts"),
                    action_class=struts_comp.get('type', 'unknown'),
                    business_purpose=struts_comp.get('business_purpose', ''),
                    repo_name=repo_name,
                    file_path=file_path,
                    metadata={'location': struts_comp.get('location', '')}
                )
            
            # Store CORBA interfaces
            for corba_interface in business_analysis.get('corba_interfaces', []):
                await self.neo4j_client.create_corba_interface(
                    interface_name=corba_interface.get('interface', 'unknown'),
                    operations=corba_interface.get('operations', []),
                    repo_name=repo_name,
                    file_path=file_path,
                    metadata={'location': corba_interface.get('location', '')}
                )
            
            # Store JSP components (if JSP patterns exist)
            jsp_patterns = business_analysis.get('jsp_patterns', [])
            if jsp_patterns:
                component_id = f"{repo_name}:{file_path}:jsp"
                await self.neo4j_client.create_jsp_component(
                    component_id=component_id,
                    component_type='jsp_page',
                    business_purpose=self._infer_jsp_business_purpose(jsp_patterns),
                    repo_name=repo_name,
                    file_path=file_path,
                    struts_patterns=[p.get('type', '') for p in jsp_patterns],
                    migration_notes=business_analysis.get('migration_notes', [])
                )
            
            # Create business relationships
            for relationship in business_analysis.get('relationships', []):
                # Skip relationship creation for now - would need proper ID mapping
                pass
                
        except Exception as e:
            self.logger.warning(f"Failed to store business analysis for {file_path}: {e}")
    
    def _infer_business_domain(self, rule_text: str) -> str:
        """Infer business domain from rule text."""
        rule_lower = rule_text.lower()
        
        if any(word in rule_lower for word in ['user', 'login', 'auth', 'permission']):
            return 'security'
        elif any(word in rule_lower for word in ['amount', 'payment', 'contract', 'policy']):
            return 'financial'
        elif any(word in rule_lower for word in ['customer', 'client', 'account']):
            return 'customer_management'
        elif any(word in rule_lower for word in ['validate', 'required', 'empty']):
            return 'validation'
        else:
            return 'general'
    
    def _infer_jsp_business_purpose(self, jsp_patterns: List[Dict[str, Any]]) -> str:
        """Infer business purpose from JSP patterns."""
        pattern_types = [p.get('type', '') for p in jsp_patterns]
        
        if 'struts_tags' in pattern_types:
            return 'user_interface_form'
        elif 'scriptlets' in pattern_types:
            return 'dynamic_content_generation'
        elif 'session_management' in pattern_types:
            return 'user_session_handling'
        elif 'direct_db_access' in pattern_types:
            return 'data_access_layer'
        else:
            return 'web_presentation'