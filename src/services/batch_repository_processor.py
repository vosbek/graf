"""
Batch Repository Processing System for Enterprise Scale
======================================================

Handles batch processing of 50-100 repositories with optimized performance,
error recovery, progress tracking, and resource management for enterprise
legacy migration analysis.

Key Features:
- Concurrent processing with resource limits
- Progress tracking and resumability  
- Error isolation and recovery
- Memory management for large batches
- Performance optimization
- Status reporting and monitoring
"""

import asyncio
import logging
import time
import json
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Set
import statistics
import psutil

from .repository_processor_v2 import RepositoryProcessor
from .cross_repository_analyzer import CrossRepositoryAnalyzer
from ..core.neo4j_client import Neo4jClient
from ..core.chromadb_client import ChromaDBClient


logger = logging.getLogger(__name__)


class ProcessingStatus(Enum):
    """Repository processing status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress" 
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class RepositoryBatchItem:
    """Single repository item in batch processing."""
    repo_name: str
    repo_path: str
    priority: int = 5  # 1-10, 10 is highest priority
    status: ProcessingStatus = ProcessingStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    processing_time: Optional[float] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    components_found: int = 0
    business_rules_found: int = 0
    relationships_created: int = 0
    file_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchProcessingStats:
    """Statistics for batch processing operation."""
    total_repositories: int
    completed_repositories: int
    failed_repositories: int
    skipped_repositories: int
    total_processing_time: float
    average_processing_time: float
    total_components: int
    total_business_rules: int
    total_relationships: int
    memory_peak_mb: float
    cpu_usage_avg: float
    throughput_repos_per_hour: float
    error_rate: float


@dataclass
class BatchProcessingResult:
    """Complete batch processing results."""
    batch_id: str
    start_time: datetime
    end_time: datetime
    repositories: List[RepositoryBatchItem]
    stats: BatchProcessingStats
    errors: List[str]
    performance_insights: List[str]
    recommendations: List[str]


class BatchRepositoryProcessor:
    """
    High-performance batch processor for enterprise-scale repository analysis.
    Optimized for processing 50-100 repositories with resource management.
    """
    
    def __init__(
        self,
        repository_processor: RepositoryProcessor,
        neo4j_client: Neo4jClient,
        chroma_client: ChromaDBClient,
        max_concurrent: int = 8,
        max_memory_mb: int = 4096,
        checkpoint_interval: int = 10
    ):
        self.repository_processor = repository_processor
        self.neo4j_client = neo4j_client
        self.chroma_client = chroma_client
        self.max_concurrent = max_concurrent
        self.max_memory_mb = max_memory_mb
        self.checkpoint_interval = checkpoint_interval
        
        # Performance monitoring
        self.start_memory = 0
        self.peak_memory = 0
        self.cpu_samples = []
        
        # Progress tracking
        self.progress_callback: Optional[Callable] = None
        self.checkpoint_dir = Path("data/batch_checkpoints")
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    async def process_repository_batch(
        self,
        repository_items: List[RepositoryBatchItem],
        batch_id: Optional[str] = None,
        resume_from_checkpoint: bool = False,
        progress_callback: Optional[Callable] = None
    ) -> BatchProcessingResult:
        """
        Process a batch of repositories with enterprise-grade features.
        
        Args:
            repository_items: List of repositories to process
            batch_id: Unique identifier for this batch
            resume_from_checkpoint: Whether to resume from previous checkpoint
            progress_callback: Optional callback for progress updates
            
        Returns:
            BatchProcessingResult with complete processing information
        """
        if not batch_id:
            batch_id = f"batch_{int(time.time())}"
        
        self.progress_callback = progress_callback
        start_time = datetime.now()
        
        logger.info(f"🚀 Starting batch processing: {batch_id}")
        logger.info(f"📊 Processing {len(repository_items)} repositories with {self.max_concurrent} concurrent workers")
        
        # Resume from checkpoint if requested
        if resume_from_checkpoint:
            repository_items = await self._load_checkpoint(batch_id, repository_items)
        
        # Initialize performance monitoring
        self.start_memory = psutil.Process().memory_info().rss / 1024 / 1024
        self.peak_memory = self.start_memory
        self.cpu_samples = []
        
        # Sort by priority (highest first)
        repository_items.sort(key=lambda x: x.priority, reverse=True)
        
        # Process repositories in batches to manage memory
        processed_items = []
        errors = []
        
        try:
            # Create semaphore for concurrent processing
            semaphore = asyncio.Semaphore(self.max_concurrent)
            
            # Process repositories
            tasks = []
            for item in repository_items:
                if item.status == ProcessingStatus.COMPLETED and resume_from_checkpoint:
                    processed_items.append(item)
                    continue
                    
                task = asyncio.create_task(
                    self._process_single_repository(item, semaphore)
                )
                tasks.append(task)
            
            # Execute all tasks with progress monitoring
            completed_tasks = 0
            for task in asyncio.as_completed(tasks):
                try:
                    item = await task
                    processed_items.append(item)
                    completed_tasks += 1
                    
                    # Progress callback
                    if self.progress_callback:
                        progress = completed_tasks / len(tasks) * 100
                        await self.progress_callback(progress, item)
                    
                    # Checkpoint periodically
                    if completed_tasks % self.checkpoint_interval == 0:
                        await self._save_checkpoint(batch_id, processed_items + 
                                                  [i for i in repository_items if i.status == ProcessingStatus.COMPLETED])
                    
                    # Memory management
                    await self._check_memory_usage()
                    
                except Exception as e:
                    error_msg = f"Task execution error: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
        except Exception as e:
            error_msg = f"Batch processing error: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
        
        end_time = datetime.now()
        
        # Calculate statistics
        stats = await self._calculate_batch_stats(processed_items, start_time, end_time)
        
        # Generate insights and recommendations
        performance_insights = await self._generate_performance_insights(processed_items, stats)
        recommendations = await self._generate_batch_recommendations(processed_items, stats)
        
        # Final checkpoint
        await self._save_checkpoint(batch_id, processed_items)
        
        result = BatchProcessingResult(
            batch_id=batch_id,
            start_time=start_time,
            end_time=end_time,
            repositories=processed_items,
            stats=stats,
            errors=errors,
            performance_insights=performance_insights,
            recommendations=recommendations
        )
        
        logger.info(f"✅ Batch processing completed: {batch_id}")
        logger.info(f"📊 Processed {stats.completed_repositories}/{stats.total_repositories} repositories")
        logger.info(f"⏱️ Total time: {stats.total_processing_time:.1f}s, Throughput: {stats.throughput_repos_per_hour:.1f} repos/hour")
        
        return result
    
    async def _process_single_repository(
        self, item: RepositoryBatchItem, semaphore: asyncio.Semaphore
    ) -> RepositoryBatchItem:
        """Process a single repository with error handling and retry logic."""
        async with semaphore:
            item.start_time = datetime.now()
            item.status = ProcessingStatus.IN_PROGRESS
            
            try:
                logger.info(f"🔄 Processing repository: {item.repo_name}")
                
                # Check if repository path exists
                if not Path(item.repo_path).exists():
                    raise FileNotFoundError(f"Repository path does not exist: {item.repo_path}")
                
                # Process repository with enhanced analysis
                result = await self.repository_processor.process_repository(
                    repository_name=item.repo_name,
                    repository_path=item.repo_path,
                    include_business_analysis=True,
                    store_embeddings=True
                )
                
                # Extract metrics from result
                item.components_found = result.components_processed
                item.business_rules_found = len(result.business_components.get('business_rules', []))
                item.relationships_created = result.relationships_created
                item.file_count = len(result.files_processed)
                
                # Store additional metadata
                item.metadata = {
                    'languages_detected': result.languages_processed,
                    'frameworks_detected': result.frameworks_detected,
                    'complexity_score': result.complexity_metrics.get('average_complexity', 0),
                    'processing_details': {
                        'chunks_created': result.chunks_processed,
                        'embeddings_stored': result.embeddings_stored,
                        'parsing_time': result.processing_time
                    }
                }
                
                item.status = ProcessingStatus.COMPLETED
                logger.info(f"✅ Completed repository: {item.repo_name} ({item.components_found} components)")
                
            except Exception as e:
                item.error_message = str(e)
                item.retry_count += 1
                
                # Retry logic for transient errors
                if item.retry_count < 3 and self._is_retryable_error(e):
                    logger.warning(f"⚠️ Retrying repository {item.repo_name} (attempt {item.retry_count + 1})")
                    await asyncio.sleep(2 ** item.retry_count)  # Exponential backoff
                    return await self._process_single_repository(item, semaphore)
                else:
                    item.status = ProcessingStatus.FAILED
                    logger.error(f"❌ Failed repository: {item.repo_name} - {str(e)}")
            
            finally:
                item.end_time = datetime.now()
                if item.start_time:
                    item.processing_time = (item.end_time - item.start_time).total_seconds()
        
        return item
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Determine if an error is retryable."""
        retryable_errors = [
            'connection',
            'timeout',
            'temporary',
            'unavailable',
            'rate limit'
        ]
        error_str = str(error).lower()
        return any(retryable in error_str for retryable in retryable_errors)
    
    async def _check_memory_usage(self):
        """Monitor memory usage and trigger garbage collection if needed."""
        current_memory = psutil.Process().memory_info().rss / 1024 / 1024
        self.peak_memory = max(self.peak_memory, current_memory)
        
        if current_memory > self.max_memory_mb:
            logger.warning(f"⚠️ Memory usage high: {current_memory:.1f}MB, triggering cleanup")
            import gc
            gc.collect()
            
            # Force garbage collection in ChromaDB if possible
            try:
                await self.chroma_client.clear_cache()
            except:
                pass
    
    async def _save_checkpoint(self, batch_id: str, items: List[RepositoryBatchItem]):
        """Save processing checkpoint for resumability."""
        checkpoint_file = self.checkpoint_dir / f"{batch_id}.json"
        
        checkpoint_data = {
            'batch_id': batch_id,
            'timestamp': datetime.now().isoformat(),
            'repositories': [
                {
                    'repo_name': item.repo_name,
                    'repo_path': item.repo_path,
                    'priority': item.priority,
                    'status': item.status.value,
                    'start_time': item.start_time.isoformat() if item.start_time else None,
                    'end_time': item.end_time.isoformat() if item.end_time else None,
                    'processing_time': item.processing_time,
                    'error_message': item.error_message,
                    'retry_count': item.retry_count,
                    'components_found': item.components_found,
                    'business_rules_found': item.business_rules_found,
                    'file_count': item.file_count,
                    'metadata': item.metadata
                }
                for item in items
            ]
        }
        
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f, indent=2)
        
        logger.debug(f"💾 Checkpoint saved: {checkpoint_file}")
    
    async def _load_checkpoint(
        self, batch_id: str, repository_items: List[RepositoryBatchItem]
    ) -> List[RepositoryBatchItem]:
        """Load processing checkpoint to resume batch."""
        checkpoint_file = self.checkpoint_dir / f"{batch_id}.json"
        
        if not checkpoint_file.exists():
            logger.info(f"No checkpoint found for batch: {batch_id}")
            return repository_items
        
        try:
            with open(checkpoint_file, 'r') as f:
                checkpoint_data = json.load(f)
            
            # Create mapping of existing items
            item_map = {item.repo_name: item for item in repository_items}
            
            # Update items with checkpoint data
            for repo_data in checkpoint_data['repositories']:
                repo_name = repo_data['repo_name']
                if repo_name in item_map:
                    item = item_map[repo_name]
                    item.status = ProcessingStatus(repo_data['status'])
                    item.start_time = datetime.fromisoformat(repo_data['start_time']) if repo_data['start_time'] else None
                    item.end_time = datetime.fromisoformat(repo_data['end_time']) if repo_data['end_time'] else None
                    item.processing_time = repo_data['processing_time']
                    item.error_message = repo_data['error_message']
                    item.retry_count = repo_data['retry_count']
                    item.components_found = repo_data['components_found']
                    item.business_rules_found = repo_data['business_rules_found']
                    item.file_count = repo_data['file_count']
                    item.metadata = repo_data['metadata']
            
            completed_count = sum(1 for item in repository_items if item.status == ProcessingStatus.COMPLETED)
            logger.info(f"📂 Loaded checkpoint: {completed_count} repositories already completed")
            
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
        
        return repository_items
    
    async def _calculate_batch_stats(
        self, items: List[RepositoryBatchItem], start_time: datetime, end_time: datetime
    ) -> BatchProcessingStats:
        """Calculate comprehensive batch processing statistics."""
        total_repos = len(items)
        completed_repos = sum(1 for item in items if item.status == ProcessingStatus.COMPLETED)
        failed_repos = sum(1 for item in items if item.status == ProcessingStatus.FAILED)
        skipped_repos = sum(1 for item in items if item.status == ProcessingStatus.SKIPPED)
        
        total_time = (end_time - start_time).total_seconds()
        
        # Calculate processing times for completed repositories
        processing_times = [item.processing_time for item in items 
                          if item.processing_time is not None]
        avg_processing_time = statistics.mean(processing_times) if processing_times else 0
        
        # Calculate component totals
        total_components = sum(item.components_found for item in items)
        total_business_rules = sum(item.business_rules_found for item in items)
        total_relationships = sum(item.relationships_created for item in items)
        
        # Calculate performance metrics
        throughput = (completed_repos / (total_time / 3600)) if total_time > 0 else 0
        error_rate = (failed_repos / total_repos * 100) if total_repos > 0 else 0
        
        # CPU usage average
        cpu_avg = statistics.mean(self.cpu_samples) if self.cpu_samples else 0
        
        return BatchProcessingStats(
            total_repositories=total_repos,
            completed_repositories=completed_repos,
            failed_repositories=failed_repos,
            skipped_repositories=skipped_repos,
            total_processing_time=total_time,
            average_processing_time=avg_processing_time,
            total_components=total_components,
            total_business_rules=total_business_rules,
            total_relationships=total_relationships,
            memory_peak_mb=self.peak_memory,
            cpu_usage_avg=cpu_avg,
            throughput_repos_per_hour=throughput,
            error_rate=error_rate
        )
    
    async def _generate_performance_insights(
        self, items: List[RepositoryBatchItem], stats: BatchProcessingStats
    ) -> List[str]:
        """Generate performance insights from batch processing."""
        insights = []
        
        # Throughput analysis
        if stats.throughput_repos_per_hour > 20:
            insights.append(f"🚀 Excellent throughput: {stats.throughput_repos_per_hour:.1f} repos/hour")
        elif stats.throughput_repos_per_hour > 10:
            insights.append(f"✅ Good throughput: {stats.throughput_repos_per_hour:.1f} repos/hour")
        else:
            insights.append(f"⚠️ Low throughput: {stats.throughput_repos_per_hour:.1f} repos/hour - consider optimization")
        
        # Error rate analysis
        if stats.error_rate < 5:
            insights.append(f"✅ Low error rate: {stats.error_rate:.1f}%")
        elif stats.error_rate < 15:
            insights.append(f"⚠️ Moderate error rate: {stats.error_rate:.1f}% - review failed repositories")
        else:
            insights.append(f"🚨 High error rate: {stats.error_rate:.1f}% - investigate common failure patterns")
        
        # Memory usage analysis
        if stats.memory_peak_mb > self.max_memory_mb * 0.9:
            insights.append(f"⚠️ High memory usage: {stats.memory_peak_mb:.1f}MB peak - consider reducing batch size")
        else:
            insights.append(f"✅ Efficient memory usage: {stats.memory_peak_mb:.1f}MB peak")
        
        # Processing time distribution
        processing_times = [item.processing_time for item in items if item.processing_time]
        if processing_times:
            time_std = statistics.stdev(processing_times)
            if time_std > stats.average_processing_time * 0.5:
                insights.append(f"📊 High processing time variance - some repositories significantly more complex")
        
        return insights
    
    async def _generate_batch_recommendations(
        self, items: List[RepositoryBatchItem], stats: BatchProcessingStats
    ) -> List[str]:
        """Generate recommendations for future batch processing."""
        recommendations = []
        
        # Performance recommendations
        if stats.throughput_repos_per_hour < 10:
            recommendations.append("Consider increasing concurrent processing limit or optimizing parsing algorithms")
        
        if stats.error_rate > 10:
            recommendations.append("Implement more robust error handling and pre-validation of repository paths")
        
        # Resource recommendations
        if stats.memory_peak_mb > self.max_memory_mb * 0.8:
            recommendations.append("Increase memory limit or process repositories in smaller batches")
        
        # Repository-specific recommendations
        large_repos = [item for item in items if item.file_count > 1000]
        if large_repos:
            recommendations.append(f"Consider pre-filtering or splitting {len(large_repos)} large repositories for better performance")
        
        failed_repos = [item for item in items if item.status == ProcessingStatus.FAILED]
        if failed_repos:
            common_errors = {}
            for item in failed_repos:
                if item.error_message:
                    error_type = item.error_message.split(':')[0]
                    common_errors[error_type] = common_errors.get(error_type, 0) + 1
            
            if common_errors:
                most_common = max(common_errors.items(), key=lambda x: x[1])
                recommendations.append(f"Address common error pattern: {most_common[0]} ({most_common[1]} occurrences)")
        
        return recommendations
    
    async def get_batch_status(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a running or completed batch."""
        checkpoint_file = self.checkpoint_dir / f"{batch_id}.json"
        
        if not checkpoint_file.exists():
            return None
        
        try:
            with open(checkpoint_file, 'r') as f:
                checkpoint_data = json.load(f)
                
            # Calculate current status
            repositories = checkpoint_data['repositories']
            total = len(repositories)
            completed = sum(1 for r in repositories if r['status'] == 'completed')
            failed = sum(1 for r in repositories if r['status'] == 'failed')
            in_progress = sum(1 for r in repositories if r['status'] == 'in_progress')
            
            return {
                'batch_id': batch_id,
                'last_update': checkpoint_data['timestamp'],
                'progress': {
                    'total': total,
                    'completed': completed,
                    'failed': failed,
                    'in_progress': in_progress,
                    'percentage': (completed / total * 100) if total > 0 else 0
                },
                'repositories': repositories
            }
            
        except Exception as e:
            logger.error(f"Failed to get batch status: {e}")
            return None


# Export main class
__all__ = ['BatchRepositoryProcessor', 'RepositoryBatchItem', 'ProcessingStatus', 'BatchProcessingResult']