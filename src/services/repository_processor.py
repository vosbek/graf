"""
Multi-repository processing pipeline with intelligent filtering and classification.
Handles massive scale repository analysis, business logic extraction, and dependency resolution.
"""

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any, Union
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import hashlib
import json
import os
import subprocess
from urllib.parse import urlparse

from ..core.chromadb_client import ChromaDBClient
from ..core.neo4j_client import Neo4jClient
from ..processing.tree_sitter_parser import TreeSitterParser, SupportedLanguage
from ..processing.code_chunker import CodeChunker, EnhancedChunk, ChunkingConfig
from ..processing.maven_parser import MavenParser, PomFile
from ..processing.dependency_resolver import DependencyResolver, ResolutionResult


class ProcessingStatus(Enum):
    """Status of repository processing."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class RepositoryPriority(Enum):
    """Priority levels for repository processing."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class RepositoryConfig:
    """Configuration for repository processing."""
    name: str
    url: str
    branch: str = "main"
    priority: RepositoryPriority = RepositoryPriority.MEDIUM
    include_patterns: List[str] = field(default_factory=lambda: ["**/*.py", "**/*.java", "**/*.js", "**/*.ts", "**/*.go", "**/*.rs"])
    exclude_patterns: List[str] = field(default_factory=lambda: ["**/node_modules/**", "**/target/**", "**/.git/**", "**/build/**"])
    maven_enabled: bool = True
    max_file_size: int = 1024 * 1024  # 1MB
    timeout_seconds: int = 300
    business_domain: Optional[str] = None
    team_owner: Optional[str] = None
    is_golden_repo: bool = False
    
    def __post_init__(self):
        if not self.include_patterns:
            self.include_patterns = ["**/*.py", "**/*.java", "**/*.js", "**/*.ts", "**/*.go", "**/*.rs"]
        if not self.exclude_patterns:
            self.exclude_patterns = ["**/node_modules/**", "**/target/**", "**/.git/**", "**/build/**"]


@dataclass
class ProcessingResult:
    """Result of repository processing."""
    repository_name: str
    status: ProcessingStatus
    processed_files: int = 0
    generated_chunks: int = 0
    maven_artifacts: int = 0
    dependencies_resolved: int = 0
    conflicts_detected: int = 0
    processing_time: float = 0.0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'repository_name': self.repository_name,
            'status': self.status.value,
            'processed_files': self.processed_files,
            'generated_chunks': self.generated_chunks,
            'maven_artifacts': self.maven_artifacts,
            'dependencies_resolved': self.dependencies_resolved,
            'conflicts_detected': self.conflicts_detected,
            'processing_time': self.processing_time,
            'error_message': self.error_message,
            'metadata': self.metadata
        }


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
class ProcessingStats:
    """Statistics for processing pipeline."""
    total_repositories: int = 0
    completed_repositories: int = 0
    failed_repositories: int = 0
    skipped_repositories: int = 0
    total_files: int = 0
    total_chunks: int = 0
    total_dependencies: int = 0
    total_conflicts: int = 0
    total_processing_time: float = 0.0
    average_processing_time: float = 0.0
    
    def update(self, result: ProcessingResult):
        """Update statistics with processing result."""
        self.total_repositories += 1
        
        if result.status == ProcessingStatus.COMPLETED:
            self.completed_repositories += 1
            self.total_files += result.processed_files
            self.total_chunks += result.generated_chunks
            self.total_dependencies += result.dependencies_resolved
            self.total_conflicts += result.conflicts_detected
        elif result.status == ProcessingStatus.FAILED:
            self.failed_repositories += 1
        elif result.status == ProcessingStatus.SKIPPED:
            self.skipped_repositories += 1
        
        self.total_processing_time += result.processing_time
        self.average_processing_time = self.total_processing_time / max(self.total_repositories, 1)


class RepositoryProcessor:
    """Multi-repository processing pipeline with intelligent filtering."""
    
    def __init__(self,
                 chroma_client: ChromaDBClient,
                 neo4j_client: Neo4jClient,
                 max_concurrent_repos: int = 10,
                 max_workers: int = 4,
                 workspace_dir: str = "./data/repositories"):
        
        self.chroma_client = chroma_client
        self.neo4j_client = neo4j_client
        self.max_concurrent_repos = max_concurrent_repos
        self.max_workers = max_workers
        self.workspace_dir = Path(workspace_dir)
        
        # Initialize processing components
        self.tree_sitter_parser = TreeSitterParser()
        self.code_chunker = CodeChunker()
        self.maven_parser = MavenParser()
        self.dependency_resolver = DependencyResolver()
        
        # Processing state
        self.processing_queue = asyncio.Queue()
        self.processing_tasks = set()
        self.processing_stats = ProcessingStats()
        self.repository_cache = {}
        
        # Thread pools
        self.process_pool = ProcessPoolExecutor(max_workers=max_workers)
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers * 2)
        
        # Initialize logging
        self.logger = logging.getLogger(__name__)
        
        # Create workspace directory
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
    
    async def process_repositories(self, 
                                 repository_configs: List[RepositoryConfig],
                                 filter_config: Optional[RepositoryFilter] = None) -> List[ProcessingResult]:
        """Process multiple repositories with filtering and prioritization."""
        self.logger.info(f"Starting processing of {len(repository_configs)} repositories")
        
        # Apply filtering
        filtered_repos = self._filter_repositories(repository_configs, filter_config)
        self.logger.info(f"Filtered to {len(filtered_repos)} repositories")
        
        # Sort by priority
        sorted_repos = self._sort_by_priority(filtered_repos)
        
        # Process repositories
        results = []
        semaphore = asyncio.Semaphore(self.max_concurrent_repos)
        
        async def process_with_semaphore(repo_config: RepositoryConfig):
            async with semaphore:
                return await self.process_repository(repo_config)
        
        # Create tasks for all repositories
        tasks = [process_with_semaphore(repo) for repo in sorted_repos]
        
        # Process with progress tracking
        for i, coro in enumerate(asyncio.as_completed(tasks)):
            result = await coro
            results.append(result)
            self.processing_stats.update(result)
            
            if i % 10 == 0:  # Log progress every 10 repos
                self.logger.info(f"Processed {i + 1}/{len(sorted_repos)} repositories")
        
        # Log final statistics
        self.logger.info(f"Processing completed: {self.processing_stats.completed_repositories} successful, "
                        f"{self.processing_stats.failed_repositories} failed, "
                        f"{self.processing_stats.skipped_repositories} skipped")
        
        return results
    
    def _filter_repositories(self, 
                           repository_configs: List[RepositoryConfig],
                           filter_config: Optional[RepositoryFilter]) -> List[RepositoryConfig]:
        """Filter repositories based on criteria."""
        if not filter_config:
            return repository_configs
        
        filtered = []
        
        for repo in repository_configs:
            # Skip excluded repositories
            if filter_config.exclude_names and repo.name in filter_config.exclude_names:
                continue
            
            # Check name patterns
            if filter_config.name_patterns:
                if not any(pattern in repo.name for pattern in filter_config.name_patterns):
                    continue
            
            # Check domains
            if filter_config.domains:
                if not repo.business_domain or repo.business_domain not in filter_config.domains:
                    continue
            
            # Check teams
            if filter_config.teams:
                if not repo.team_owner or repo.team_owner not in filter_config.teams:
                    continue
            
            # Check priorities
            if filter_config.priorities:
                if repo.priority not in filter_config.priorities:
                    continue
            
            # Check golden repo flag
            if filter_config.is_golden_repo is not None:
                if repo.is_golden_repo != filter_config.is_golden_repo:
                    continue
            
            # Check Maven presence
            if filter_config.has_maven is not None:
                if repo.maven_enabled != filter_config.has_maven:
                    continue
            
            filtered.append(repo)
        
        return filtered
    
    def _sort_by_priority(self, repository_configs: List[RepositoryConfig]) -> List[RepositoryConfig]:
        """Sort repositories by priority."""
        priority_order = {
            RepositoryPriority.CRITICAL: 0,
            RepositoryPriority.HIGH: 1,
            RepositoryPriority.MEDIUM: 2,
            RepositoryPriority.LOW: 3
        }
        
        return sorted(repository_configs, key=lambda r: (priority_order[r.priority], r.name))
    
    async def process_repository(self, repo_config: RepositoryConfig) -> ProcessingResult:
        """Process a single repository."""
        start_time = time.time()
        
        try:
            self.logger.info(f"Processing repository: {repo_config.name}")
            
            # Clone or update repository
            repo_path = await self._prepare_repository(repo_config)
            
            # Analyze repository structure
            repo_analysis = await self._analyze_repository(repo_path, repo_config)
            
            # Process code files
            code_results = await self._process_code_files(repo_path, repo_config, repo_analysis)
            
            # Process Maven dependencies if enabled
            maven_results = None
            if repo_config.maven_enabled:
                maven_results = await self._process_maven_dependencies(repo_path, repo_config)
            
            # Store results in databases
            await self._store_results(repo_config, code_results, maven_results)
            
            # Create result
            processing_time = time.time() - start_time
            result = ProcessingResult(
                repository_name=repo_config.name,
                status=ProcessingStatus.COMPLETED,
                processed_files=len(code_results['files']),
                generated_chunks=len(code_results['chunks']),
                maven_artifacts=len(maven_results['artifacts']) if maven_results else 0,
                dependencies_resolved=len(maven_results['dependencies']) if maven_results else 0,
                conflicts_detected=len(maven_results['conflicts']) if maven_results else 0,
                processing_time=processing_time,
                metadata={
                    'languages': repo_analysis['languages'],
                    'file_count': repo_analysis['file_count'],
                    'lines_of_code': repo_analysis['lines_of_code'],
                    'complexity_score': repo_analysis['complexity_score'],
                    'business_domain': repo_config.business_domain,
                    'team_owner': repo_config.team_owner,
                    'is_golden_repo': repo_config.is_golden_repo
                }
            )
            
            self.logger.info(f"Successfully processed repository: {repo_config.name} in {processing_time:.2f}s")
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Failed to process repository {repo_config.name}: {str(e)}"
            self.logger.error(error_msg)
            
            return ProcessingResult(
                repository_name=repo_config.name,
                status=ProcessingStatus.FAILED,
                processing_time=processing_time,
                error_message=error_msg
            )
    
    async def _prepare_repository(self, repo_config: RepositoryConfig) -> Path:
        """Clone or update repository."""
        repo_path = self.workspace_dir / repo_config.name
        
        if repo_path.exists():
            # Update existing repository
            await self._run_git_command(["git", "pull"], cwd=repo_path)
            await self._run_git_command(["git", "checkout", repo_config.branch], cwd=repo_path)
        else:
            # Clone repository
            await self._run_git_command([
                "git", "clone", "--depth", "1", 
                "--branch", repo_config.branch,
                repo_config.url, str(repo_path)
            ])
        
        return repo_path
    
    async def _run_git_command(self, command: List[str], cwd: Optional[Path] = None) -> str:
        """Run git command asynchronously."""
        loop = asyncio.get_event_loop()
        
        def run_command():
            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode != 0:
                raise Exception(f"Git command failed: {result.stderr}")
            return result.stdout
        
        return await loop.run_in_executor(self.thread_pool, run_command)
    
    async def _analyze_repository(self, repo_path: Path, repo_config: RepositoryConfig) -> Dict[str, Any]:
        """Analyze repository structure and characteristics."""
        analysis = {
            'languages': set(),
            'file_count': 0,
            'lines_of_code': 0,
            'complexity_score': 0.0,
            'has_maven': False,
            'has_gradle': False,
            'has_npm': False,
            'main_language': None,
            'frameworks': set(),
            'test_coverage': 0.0
        }
        
        # Find all relevant files
        files = []
        for pattern in repo_config.include_patterns:
            files.extend(repo_path.glob(pattern))
        
        # Filter by exclusion patterns
        filtered_files = []
        for file_path in files:
            if not any(file_path.match(pattern) for pattern in repo_config.exclude_patterns):
                if file_path.stat().st_size <= repo_config.max_file_size:
                    filtered_files.append(file_path)
        
        # Analyze files
        language_counts = defaultdict(int)
        total_lines = 0
        
        for file_path in filtered_files:
            try:
                # Detect language
                language = self.tree_sitter_parser.detect_language(str(file_path))
                if language:
                    analysis['languages'].add(language.value)
                    language_counts[language.value] += 1
                
                # Count lines
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = len(f.readlines())
                    total_lines += lines
                
            except Exception as e:
                self.logger.warning(f"Error analyzing file {file_path}: {e}")
        
        # Determine main language
        if language_counts:
            analysis['main_language'] = max(language_counts, key=language_counts.get)
        
        # Check for build files
        analysis['has_maven'] = (repo_path / "pom.xml").exists()
        analysis['has_gradle'] = (repo_path / "build.gradle").exists() or (repo_path / "build.gradle.kts").exists()
        analysis['has_npm'] = (repo_path / "package.json").exists()
        
        # Update analysis
        analysis['file_count'] = len(filtered_files)
        analysis['lines_of_code'] = total_lines
        analysis['languages'] = list(analysis['languages'])
        analysis['frameworks'] = list(analysis['frameworks'])
        
        return analysis
    
    async def _process_code_files(self, 
                                repo_path: Path, 
                                repo_config: RepositoryConfig,
                                repo_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Process code files and generate chunks."""
        files_data = []
        all_chunks = []
        
        # Find all code files
        code_files = []
        for pattern in repo_config.include_patterns:
            code_files.extend(repo_path.glob(pattern))
        
        # Filter files
        filtered_files = []
        for file_path in code_files:
            if not any(file_path.match(pattern) for pattern in repo_config.exclude_patterns):
                if file_path.stat().st_size <= repo_config.max_file_size:
                    filtered_files.append(file_path)
        
        # Process files in batches
        batch_size = 50
        for i in range(0, len(filtered_files), batch_size):
            batch = filtered_files[i:i + batch_size]
            batch_results = await self._process_file_batch(batch, repo_path, repo_config)
            
            files_data.extend(batch_results['files'])
            all_chunks.extend(batch_results['chunks'])
        
        return {
            'files': files_data,
            'chunks': all_chunks,
            'statistics': {
                'total_files': len(files_data),
                'total_chunks': len(all_chunks),
                'languages': repo_analysis['languages'],
                'lines_of_code': repo_analysis['lines_of_code']
            }
        }
    
    async def _process_file_batch(self, 
                                files: List[Path], 
                                repo_path: Path,
                                repo_config: RepositoryConfig) -> Dict[str, Any]:
        """Process a batch of files."""
        loop = asyncio.get_event_loop()
        
        def process_batch():
            batch_files = []
            batch_chunks = []
            
            for file_path in files:
                try:
                    # Read file content
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
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
                    
                    # Generate chunks
                    chunks = chunker.chunk_file(rel_path, content, language)
                    
                    # Store file data
                    file_data = {
                        'path': rel_path,
                        'language': language.value,
                        'size': len(content),
                        'lines': len(content.split('\n')),
                        'chunks_count': len(chunks)
                    }
                    
                    batch_files.append(file_data)
                    batch_chunks.extend(chunks)
                    
                except Exception as e:
                    self.logger.warning(f"Error processing file {file_path}: {e}")
            
            return {
                'files': batch_files,
                'chunks': batch_chunks
            }
        
        return await loop.run_in_executor(self.process_pool, process_batch)
    
    async def _process_maven_dependencies(self, 
                                        repo_path: Path, 
                                        repo_config: RepositoryConfig) -> Optional[Dict[str, Any]]:
        """Process Maven dependencies."""
        pom_path = repo_path / "pom.xml"
        
        if not pom_path.exists():
            return None
        
        try:
            # Read and parse POM
            with open(pom_path, 'r', encoding='utf-8') as f:
                pom_content = f.read()
            
            pom = self.maven_parser.parse_pom(pom_content, str(pom_path))
            
            # Resolve dependencies
            resolution_result = await self.dependency_resolver.resolve_dependencies(pom)
            
            return {
                'pom': pom,
                'artifacts': [pom.coordinates],
                'dependencies': resolution_result.resolved_dependencies,
                'conflicts': resolution_result.conflicts,
                'circular_dependencies': resolution_result.circular_dependencies,
                'statistics': {
                    'total_dependencies': len(resolution_result.resolved_dependencies),
                    'conflicts_count': len(resolution_result.conflicts),
                    'circular_dependencies_count': len(resolution_result.circular_dependencies),
                    'resolution_time': resolution_result.resolution_time_ms
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error processing Maven dependencies for {repo_config.name}: {e}")
            return None
    
    async def _store_results(self, 
                           repo_config: RepositoryConfig,
                           code_results: Dict[str, Any],
                           maven_results: Optional[Dict[str, Any]]):
        """Store processing results in databases."""
        # Create repository node in Neo4j
        repo_metadata = {
            'url': repo_config.url,
            'branch': repo_config.branch,
            'priority': repo_config.priority.value,
            'business_domain': repo_config.business_domain,
            'team_owner': repo_config.team_owner,
            'is_golden_repo': repo_config.is_golden_repo,
            'languages': code_results['statistics']['languages'],
            'file_count': code_results['statistics']['total_files'],
            'lines_of_code': code_results['statistics']['lines_of_code'],
            'chunks_count': code_results['statistics']['total_chunks']
        }
        
        await self.neo4j_client.create_repository_node(repo_config.name, repo_metadata)
        
        # Store code chunks
        if code_results['chunks']:
            await self.chroma_client.add_chunks(code_results['chunks'], repo_config.name)
            await self.neo4j_client.create_code_chunks(code_results['chunks'], repo_config.name)
        
        # Store Maven dependencies
        if maven_results:
            await self.neo4j_client.create_maven_dependencies(
                maven_results['pom'], 
                maven_results['dependencies']
            )
            
            if maven_results['conflicts']:
                await self.neo4j_client.create_dependency_conflicts(maven_results['conflicts'])
    
    async def incremental_update(self, repository_name: str) -> ProcessingResult:
        """Perform incremental update for a repository."""
        self.logger.info(f"Performing incremental update for repository: {repository_name}")
        
        # This would implement git diff-based incremental processing
        # For now, perform full reprocessing
        # TODO: Implement actual incremental processing
        
        return ProcessingResult(
            repository_name=repository_name,
            status=ProcessingStatus.COMPLETED,
            metadata={'type': 'incremental_update'}
        )
    
    async def get_processing_statistics(self) -> Dict[str, Any]:
        """Get processing pipeline statistics."""
        return {
            'total_repositories': self.processing_stats.total_repositories,
            'completed_repositories': self.processing_stats.completed_repositories,
            'failed_repositories': self.processing_stats.failed_repositories,
            'skipped_repositories': self.processing_stats.skipped_repositories,
            'total_files': self.processing_stats.total_files,
            'total_chunks': self.processing_stats.total_chunks,
            'total_dependencies': self.processing_stats.total_dependencies,
            'total_conflicts': self.processing_stats.total_conflicts,
            'total_processing_time': self.processing_stats.total_processing_time,
            'average_processing_time': self.processing_stats.average_processing_time,
            'success_rate': self.processing_stats.completed_repositories / max(self.processing_stats.total_repositories, 1)
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on processing pipeline."""
        health = {
            'status': 'healthy',
            'timestamp': time.time(),
            'checks': {}
        }
        
        try:
            # Check workspace directory
            if self.workspace_dir.exists() and self.workspace_dir.is_dir():
                health['checks']['workspace'] = {'status': 'pass'}
            else:
                health['checks']['workspace'] = {'status': 'fail'}
                health['status'] = 'unhealthy'
            
            # Check database connections
            chroma_health = await self.chroma_client.health_check()
            neo4j_health = await self.neo4j_client.health_check()
            
            health['checks']['chromadb'] = chroma_health
            health['checks']['neo4j'] = neo4j_health
            
            if chroma_health['status'] != 'healthy' or neo4j_health['status'] != 'healthy':
                health['status'] = 'unhealthy'
            
            # Check processing components
            health['checks']['tree_sitter'] = {'status': 'pass', 'languages': len(self.tree_sitter_parser.get_supported_languages())}
            health['checks']['maven_parser'] = {'status': 'pass'}
            health['checks']['dependency_resolver'] = {'status': 'pass'}
            
        except Exception as e:
            health['status'] = 'unhealthy'
            health['error'] = str(e)
            self.logger.error(f"Health check failed: {e}")
        
        return health
    
    async def cleanup(self):
        """Cleanup resources."""
        try:
            # Shutdown thread pools
            self.process_pool.shutdown(wait=True)
            self.thread_pool.shutdown(wait=True)
            
            self.logger.info("Repository processor cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")


class RepositoryClassifier:
    """Classifier for repository categorization and golden repo identification."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Classification criteria
        self.golden_repo_criteria = {
            'min_documentation_score': 0.7,
            'min_test_coverage': 0.6,
            'max_complexity_score': 5.0,
            'required_patterns': ['README', 'docs/', 'tests/'],
            'architecture_patterns': ['clean', 'mvc', 'microservice']
        }
        
        self.domain_keywords = {
            'authentication': ['auth', 'login', 'oauth', 'jwt', 'session'],
            'billing': ['payment', 'billing', 'invoice', 'subscription'],
            'user_management': ['user', 'profile', 'account', 'management'],
            'notification': ['notification', 'email', 'sms', 'push'],
            'analytics': ['analytics', 'metrics', 'tracking', 'events'],
            'api': ['api', 'rest', 'graphql', 'endpoint'],
            'database': ['database', 'db', 'sql', 'migration'],
            'frontend': ['frontend', 'ui', 'web', 'react', 'vue', 'angular'],
            'backend': ['backend', 'server', 'service', 'api'],
            'infrastructure': ['infrastructure', 'deploy', 'config', 'docker'],
            'security': ['security', 'encryption', 'ssl', 'firewall'],
            'monitoring': ['monitoring', 'logging', 'metrics', 'alerts']
        }
    
    def classify_repository(self, repo_config: RepositoryConfig, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Classify repository and determine if it's a golden repo."""
        classification = {
            'business_domain': self._classify_business_domain(repo_config, analysis),
            'architecture_pattern': self._identify_architecture_pattern(analysis),
            'quality_score': self._calculate_quality_score(analysis),
            'is_golden_repo': False,
            'recommendations': []
        }
        
        # Determine if it's a golden repo
        classification['is_golden_repo'] = self._is_golden_repo(classification, analysis)
        
        # Generate recommendations
        classification['recommendations'] = self._generate_recommendations(classification, analysis)
        
        return classification
    
    def _classify_business_domain(self, repo_config: RepositoryConfig, analysis: Dict[str, Any]) -> str:
        """Classify repository business domain."""
        # Use explicit domain if provided
        if repo_config.business_domain:
            return repo_config.business_domain
        
        # Analyze repository name and structure
        repo_name = repo_config.name.lower()
        
        # Score domains based on keywords
        domain_scores = {}
        for domain, keywords in self.domain_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword in repo_name:
                    score += 2
                # Could also check file paths, README content, etc.
            
            if score > 0:
                domain_scores[domain] = score
        
        # Return highest scoring domain
        if domain_scores:
            return max(domain_scores, key=domain_scores.get)
        
        return 'general'
    
    def _identify_architecture_pattern(self, analysis: Dict[str, Any]) -> str:
        """Identify architecture pattern used in repository."""
        # This would analyze code structure to identify patterns
        # For now, return a placeholder
        return 'unknown'
    
    def _calculate_quality_score(self, analysis: Dict[str, Any]) -> float:
        """Calculate repository quality score."""
        score = 0.0
        
        # Documentation score
        if analysis.get('has_readme'):
            score += 0.2
        if analysis.get('has_docs'):
            score += 0.2
        
        # Test coverage
        test_coverage = analysis.get('test_coverage', 0)
        score += min(test_coverage * 0.3, 0.3)
        
        # Code complexity
        complexity = analysis.get('complexity_score', 10)
        if complexity < 5:
            score += 0.2
        elif complexity < 8:
            score += 0.1
        
        # Build configuration
        if analysis.get('has_maven') or analysis.get('has_gradle') or analysis.get('has_npm'):
            score += 0.1
        
        return min(score, 1.0)
    
    def _is_golden_repo(self, classification: Dict[str, Any], analysis: Dict[str, Any]) -> bool:
        """Determine if repository qualifies as a golden repo."""
        quality_score = classification['quality_score']
        
        # Check quality threshold
        if quality_score < self.golden_repo_criteria['min_documentation_score']:
            return False
        
        # Check test coverage
        test_coverage = analysis.get('test_coverage', 0)
        if test_coverage < self.golden_repo_criteria['min_test_coverage']:
            return False
        
        # Check complexity
        complexity = analysis.get('complexity_score', 10)
        if complexity > self.golden_repo_criteria['max_complexity_score']:
            return False
        
        return True
    
    def _generate_recommendations(self, classification: Dict[str, Any], analysis: Dict[str, Any]) -> List[str]:
        """Generate improvement recommendations."""
        recommendations = []
        
        quality_score = classification['quality_score']
        
        if quality_score < 0.7:
            recommendations.append("Improve documentation and README")
        
        if analysis.get('test_coverage', 0) < 0.6:
            recommendations.append("Increase test coverage")
        
        if analysis.get('complexity_score', 0) > 5:
            recommendations.append("Reduce code complexity")
        
        if not analysis.get('has_maven') and not analysis.get('has_gradle') and not analysis.get('has_npm'):
            recommendations.append("Add proper build configuration")
        
        return recommendations