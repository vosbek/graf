"""
Indexing API routes for repository processing and management.
Enhanced with comprehensive error handling, performance tracking, and validation.
"""

import asyncio
import time
from pathlib import Path
from typing import List, Optional, Dict, Any, AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query as QueryParam, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime
from enum import Enum
import json

from ...services.repository_processor_v2 import (
    EnhancedRepositoryProcessor, RepositoryConfig, RepositoryFilter, 
    RepositoryPriority, ProcessingStatus, LocalRepositoryConfig
)
from ...dependencies import get_repository_processor
from ...core.neo4j_client import GraphQuery
from ...core.error_handling import handle_api_errors, error_handling_context, get_error_handler
from ...core.logging_config import log_performance, log_validation_result, get_logger
from ...core.performance_metrics import performance_collector
from ...core.exceptions import (
    GraphRAGException, ErrorContext, ProcessingError, ValidationError, 
    TimeoutError as GraphRAGTimeoutError, ResourceError
)
from ...core.diagnostics import diagnostic_collector


router = APIRouter()


# Request/Response models
class RepositoryIndexRequest(BaseModel):
    """Request model for repository indexing."""
    name: str = Field(..., description="Repository name")
    url: HttpUrl = Field(..., description="Repository URL")
    branch: str = Field(default="main", description="Branch to index")
    priority: RepositoryPriority = Field(default=RepositoryPriority.MEDIUM, description="Processing priority")
    business_domain: Optional[str] = Field(None, description="Business domain")
    team_owner: Optional[str] = Field(None, description="Team owner")
    maven_enabled: bool = Field(default=True, description="Enable Maven processing")
    is_golden_repo: bool = Field(default=False, description="Mark as golden repository")
    
    class Config:
        schema_extra = {
            "example": {
                "name": "user-service",
                "url": "https://github.com/company/user-service",
                "branch": "main",
                "priority": "high",
                "business_domain": "authentication",
                "team_owner": "platform-team",
                "maven_enabled": True,
                "is_golden_repo": False
            }
        }


class LocalRepositoryIndexRequest(BaseModel):
    """Request model for local repository indexing."""
    name: str = Field(..., description="Repository name")
    local_path: str = Field(..., description="Local filesystem path to repository")
    priority: RepositoryPriority = Field(default=RepositoryPriority.MEDIUM, description="Processing priority")
    business_domain: Optional[str] = Field(None, description="Business domain")
    team_owner: Optional[str] = Field(None, description="Team owner")
    is_golden_repo: bool = Field(default=False, description="Mark as golden repository")
    
    class Config:
        schema_extra = {
            "example": {
                "name": "local-project",
                "local_path": "C:/devl/projects/my-app",
                "priority": "high",
                "business_domain": "core",
                "team_owner": "dev-team",
                "is_golden_repo": False
            }
        }


class BulkIndexRequest(BaseModel):
    """Request model for bulk repository indexing."""
    repositories: List[RepositoryIndexRequest] = Field(..., description="List of repositories to index")
    max_concurrent: int = Field(default=5, ge=1, le=20, description="Maximum concurrent processing")
    
    class Config:
        schema_extra = {
            "example": {
                "repositories": [
                    {
                        "name": "user-service",
                        "url": "https://github.com/company/user-service",
                        "branch": "main",
                        "priority": "high",
                        "business_domain": "authentication"
                    }
                ],
                "max_concurrent": 5
            }
        }


class RepositoryFilterRequest(BaseModel):
    """Request model for repository filtering."""
    name_patterns: List[str] = Field(default_factory=list, description="Name patterns to match")
    domains: List[str] = Field(default_factory=list, description="Business domains to include")
    teams: List[str] = Field(default_factory=list, description="Teams to include")
    priorities: List[RepositoryPriority] = Field(default_factory=list, description="Priorities to include")
    languages: List[str] = Field(default_factory=list, description="Programming languages to include")
    is_golden_repo: Optional[bool] = Field(None, description="Filter by golden repository status")
    exclude_names: List[str] = Field(default_factory=list, description="Repository names to exclude")
    
    class Config:
        schema_extra = {
            "example": {
                "domains": ["authentication", "user_management"],
                "priorities": ["high", "critical"],
                "is_golden_repo": True,
                "exclude_names": ["archived-service"]
            }
        }


class ProcessingStage(str, Enum):
    """Enhanced processing stages for detailed tracking."""
    QUEUED = "queued"
    CLONING = "cloning"
    ANALYZING = "analyzing"
    PARSING = "parsing"
    EMBEDDING = "embedding"
    STORING = "storing"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"


class StageProgress(BaseModel):
    """Progress information for a specific processing stage."""
    stage: ProcessingStage
    started_at: datetime
    completed_at: Optional[datetime] = None
    progress_percentage: float = Field(ge=0.0, le=100.0, default=0.0)
    current_operation: Optional[str] = None
    processed_items: int = 0
    total_items: Optional[int] = None
    error_message: Optional[str] = None


class EmbeddingProgress(BaseModel):
    """Detailed embedding generation progress."""
    total_chunks: int = 0
    embedded_chunks: int = 0
    embedding_rate: float = 0.0  # chunks per second
    estimated_completion: Optional[datetime] = None
    current_file: Optional[str] = None
    embedding_errors: List[str] = Field(default_factory=list)


class IndexingError(BaseModel):
    """Detailed error information for indexing operations."""
    error_type: str
    error_message: str
    file_path: Optional[str] = None
    stage: ProcessingStage
    timestamp: datetime
    recoverable: bool = True
    stack_trace: Optional[str] = None


class EnhancedIndexingStatus(BaseModel):
    """Enhanced indexing status with detailed progress tracking."""
    repository_name: str
    task_id: str
    run_id: str
    status: ProcessingStatus
    current_stage: ProcessingStage
    overall_progress: float = Field(ge=0.0, le=100.0, default=0.0)
    
    # Stage tracking
    stage_history: List[StageProgress] = Field(default_factory=list)
    current_stage_progress: Optional[StageProgress] = None
    
    # File processing
    processed_files: int = 0
    total_files: Optional[int] = None
    current_file: Optional[str] = None
    files_by_language: Dict[str, int] = Field(default_factory=dict)
    
    # Embedding tracking
    embedding_progress: EmbeddingProgress = Field(default_factory=EmbeddingProgress)
    
    # Chunk generation
    generated_chunks: int = 0
    stored_chunks: int = 0
    
    # Timing
    started_at: datetime
    estimated_completion: Optional[datetime] = None
    processing_time: float = 0.0
    
    # Error tracking
    errors: List[IndexingError] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    
    # Performance metrics
    throughput_files_per_second: float = 0.0
    throughput_chunks_per_second: float = 0.0
    
    class Config:
        schema_extra = {
            "example": {
                "repository_name": "user-service",
                "task_id": "user-service_1691234567",
                "run_id": "abc123def456",
                "status": "in_progress",
                "current_stage": "embedding",
                "overall_progress": 65.5,
                "processed_files": 82,
                "total_files": 125,
                "current_file": "src/main/java/UserService.java",
                "generated_chunks": 347,
                "stored_chunks": 320,
                "embedding_progress": {
                    "total_chunks": 347,
                    "embedded_chunks": 320,
                    "embedding_rate": 12.5,
                    "current_file": "src/main/java/UserService.java"
                },
                "processing_time": 45.6,
                "errors": [],
                "warnings": ["Large file skipped: config/large-data.json"]
            }
        }


class IndexingStatusResponse(BaseModel):
    """Response model for indexing status."""
    task_id: str = Field(..., description="Unique ID for the indexing task")
    repository_name: str
    status: ProcessingStatus
    progress: float = Field(ge=0.0, le=1.0, description="Progress percentage")
    processed_files: int
    generated_chunks: int
    processing_time: float
    error_message: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "repository_name": "user-service",
                "status": "completed",
                "progress": 1.0,
                "processed_files": 125,
                "generated_chunks": 847,
                "processing_time": 45.6,
                "error_message": None
            }
        }


from ...core.redis_client import RedisClient, get_redis_client
from typing import Optional


# WebSocket connection management
active_websockets: Dict[str, List[WebSocket]] = {}

class StatusUpdateManager:
    """Manages real-time status updates and WebSocket connections using Redis."""
    
    def __init__(self, redis_client: RedisClient):
        self.redis = redis_client

    async def update_task_status(self, task_id: str, updates: Dict[str, Any]) -> None:
        """Update task status in Redis and notify WebSocket clients."""
        current_status = await self.redis.get_task_status(task_id)
        if current_status:
            # Update the status object
            current_status.update(updates)
            await self.redis.set_task_status(task_id, current_status)
            
            # Notify WebSocket clients
            await self.broadcast_status_update(task_id, current_status)
    
    async def add_stage_progress(self, task_id: str, stage: ProcessingStage, **kwargs) -> None:
        """Add a new stage to the progress history."""
        current_status = await self.redis.get_task_status(task_id)
        if current_status:
            stage_progress = StageProgress(
                stage=stage,
                started_at=datetime.now(),
                **kwargs
            ).dict()
            current_status['stage_history'].append(stage_progress)
            current_status['current_stage'] = stage
            current_status['current_stage_progress'] = stage_progress
            
            await self.redis.set_task_status(task_id, current_status)
            await self.broadcast_status_update(task_id, current_status)
    
    async def complete_stage(self, task_id: str, **kwargs) -> None:
        """Mark the current stage as completed."""
        current_status = await self.redis.get_task_status(task_id)
        if current_status and current_status.get('current_stage_progress'):
            current_status['current_stage_progress']['completed_at'] = datetime.now().isoformat()
            current_status['current_stage_progress']['progress_percentage'] = 100.0
            current_status['current_stage_progress'].update(kwargs)
            
            await self.redis.set_task_status(task_id, current_status)
            await self.broadcast_status_update(task_id, current_status)
    
    async def add_error(self, task_id: str, error_type: str, error_message: str, 
                       file_path: Optional[str] = None, recoverable: bool = True) -> None:
        """Add an error to the task status."""
        current_status = await self.redis.get_task_status(task_id)
        if current_status:
            error = IndexingError(
                error_type=error_type,
                error_message=error_message,
                file_path=file_path,
                stage=current_status['current_stage'],
                timestamp=datetime.now(),
                recoverable=recoverable
            ).dict()
            current_status['errors'].append(error)
            
            await self.redis.set_task_status(task_id, current_status)
            await self.broadcast_status_update(task_id, current_status)
    
    async def broadcast_status_update(self, task_id: str, status: Dict[str, Any]) -> None:
        """Broadcast status update to all connected WebSocket clients."""
        if task_id in active_websockets:
            message = {
                "type": "status_update",
                "task_id": task_id,
                "data": status
            }
            
            # Remove disconnected clients
            connected_clients = []
            for websocket in active_websockets[task_id]:
                try:
                    await websocket.send_text(json.dumps(message, default=str))
                    connected_clients.append(websocket)
                except:
                    # Client disconnected, skip
                    pass
            
            active_websockets[task_id] = connected_clients
            if not connected_clients:
                del active_websockets[task_id]


@router.post("/repository", response_model=IndexingStatusResponse)
@handle_api_errors
async def index_repository(
    request: RepositoryIndexRequest,
    background_tasks: BackgroundTasks,
    processor: EnhancedRepositoryProcessor = Depends(get_repository_processor),
    redis_client: RedisClient = Depends(get_redis_client),
    dry_run: bool = QueryParam(default=False, description="Analyze and estimate without writing to Neo4j/Chroma")
):
    """
    Index a single repository.
    
    This endpoint starts the indexing process for a repository and returns
    immediately with a task ID for status tracking.
    """
    async with error_handling_context(
        "indexing",
        "index_repository",
        repository_name=request.name,
        repository_url=str(request.url),
        dry_run=dry_run
    ) as ctx:
        try:
            # Create repository config
            repo_config = RepositoryConfig(
                name=request.name,
                url=str(request.url),
                branch=request.branch,
                priority=request.priority,
                business_domain=request.business_domain,
                team_owner=request.team_owner,
                maven_enabled=request.maven_enabled,
                is_golden_repo=request.is_golden_repo
            )
            
            # Start background processing
            task_id = f"{request.name}_{int(time.time())}"
            run_id = __import__("uuid").uuid4().hex

            status_manager = StatusUpdateManager(redis_client)

            async def process_repository():
                try:
                    # Initialize enhanced status tracking in Redis
                    initial_status = EnhancedIndexingStatus(
                        repository_name=request.name,
                        task_id=task_id,
                        run_id=run_id,
                        status=ProcessingStatus.IN_PROGRESS,
                        current_stage=ProcessingStage.QUEUED,
                        started_at=datetime.now()
                    ).dict()
                    await redis_client.set_task_status(task_id, initial_status)

                    # Stage 1: Cloning/Preparation
                    await status_manager.add_stage_progress(
                        task_id, ProcessingStage.CLONING,
                        current_operation="Preparing repository for processing"
                    )
                    
                    start_time = time.time()
                    
                    if dry_run:
                        result = await processor.process_repository_dry_run(repo_config, run_id=run_id)
                    else:
                        # Enhanced processing with progress callbacks
                        result = await processor.process_repository(
                            repo_config,
                            run_id=run_id,
                            progress_callback=lambda stage, progress, details=None:
                                asyncio.create_task(status_manager.update_task_status(task_id, {
                                    'current_stage': stage,
                                    'overall_progress': progress,
                                    **(details or {})
                                }))
                        )

                    await status_manager.complete_stage(task_id)
                    
                    # Update final status
                    await status_manager.update_task_status(task_id, {
                        "status": result.status.value,
                        "current_stage": (ProcessingStage.COMPLETED if result.status == ProcessingStatus.COMPLETED else ProcessingStatus.FAILED).value,
                        "overall_progress": 100.0,
                        "processed_files": result.processed_files,
                        "generated_chunks": result.generated_chunks,
                        "stored_chunks": result.generated_chunks,
                        "processing_time": time.time() - start_time,
                        "throughput_files_per_second": result.processed_files / max(time.time() - start_time, 1),
                        "throughput_chunks_per_second": result.generated_chunks / max(time.time() - start_time, 1)
                    })

                    if result.error_message:
                        await status_manager.add_error(
                            task_id, "processing_error", result.error_message, recoverable=False
                        )

                except Exception as e:
                    await status_manager.update_task_status(task_id, {
                        "status": ProcessingStatus.FAILED.value,
                        "current_stage": ProcessingStage.FAILED.value,
                        "processing_time": time.time() - start_time if 'start_time' in locals() else 0
                    })
                    await status_manager.add_error(
                        task_id, "unexpected_error", str(e), recoverable=False
                    )
                finally:
                    # Ensure stage is marked complete in case of early failure
                    try:
                        await status_manager.complete_stage(task_id)
                    except Exception:
                        pass

            # Start the background task
            background_tasks.add_task(process_repository)
            
            # Return initial status
            return IndexingStatusResponse(
                task_id=task_id,
                repository_name=request.name,
                status=ProcessingStatus.IN_PROGRESS,
                progress=0.0,
                processed_files=0,
                generated_chunks=0,
                processing_time=0.0
            )
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to start indexing: {str(e)}")


@router.post("/repository/local", response_model=IndexingStatusResponse)
async def index_repository_local(
    request: LocalRepositoryIndexRequest,
    background_tasks: BackgroundTasks,
    processor: EnhancedRepositoryProcessor = Depends(get_repository_processor),
    redis_client: RedisClient = Depends(get_redis_client),
    dry_run: bool = QueryParam(default=False, description="Analyze and estimate without writing to Neo4j/Chroma")
):
    """
    Index a local repository from filesystem path.
    
    This endpoint indexes a repository from a local filesystem path without
    requiring git clone. Returns immediately with a task ID for status tracking.
    """
    try:
        # Validate local path exists and is directory
        local_path = Path(request.local_path)
        if not local_path.exists():
            raise HTTPException(status_code=400, detail=f"Local path does not exist: {request.local_path}")
        if not local_path.is_dir():
            raise HTTPException(status_code=400, detail=f"Local path is not a directory: {request.local_path}")
        
        # Create local repository config
        local_config = LocalRepositoryConfig(
            name=request.name,
            path=str(local_path.absolute()),
            priority=request.priority,
            business_domain=request.business_domain,
            team_owner=request.team_owner,
            is_golden_repo=request.is_golden_repo
        )
        
        # Start background processing
        task_id = f"{request.name}_{int(time.time())}"
        run_id = __import__("uuid").uuid4().hex

        status_manager = StatusUpdateManager(redis_client)

        async def process_local_repository():
            try:
                # Initialize enhanced status tracking in Redis
                initial_status = EnhancedIndexingStatus(
                    repository_name=request.name,
                    task_id=task_id,
                    run_id=run_id,
                    status=ProcessingStatus.IN_PROGRESS,
                    current_stage=ProcessingStage.ANALYZING,
                    started_at=datetime.now()
                ).dict()
                await redis_client.set_task_status(task_id, initial_status)

                # Stage 1: Analysis (no cloning needed for local repos)
                await status_manager.add_stage_progress(
                    task_id, ProcessingStage.ANALYZING,
                    current_operation="Analyzing local repository structure"
                )
                
                start_time = time.time()

                if dry_run:
                    result = await processor.process_local_repository_dry_run(local_config, run_id=run_id)
                else:
                    # Enhanced processing with progress callbacks
                    result = await processor.process_local_repository(
                        local_config, 
                        run_id=run_id,
                        progress_callback=lambda stage, progress, details=None: 
                            asyncio.create_task(status_manager.update_task_status(task_id, {
                                'current_stage': stage,
                                'overall_progress': progress,
                                **(details or {})
                            }))
                    )

                await status_manager.complete_stage(task_id)
                
                # Update final status
                await status_manager.update_task_status(task_id, {
                    "status": result.status.value,
                    "current_stage": (ProcessingStage.COMPLETED if result.status == ProcessingStatus.COMPLETED else ProcessingStatus.FAILED).value,
                    "overall_progress": 100.0,
                    "processed_files": result.processed_files,
                    "generated_chunks": result.generated_chunks,
                    "stored_chunks": result.generated_chunks,
                    "processing_time": time.time() - start_time,
                    "throughput_files_per_second": result.processed_files / max(time.time() - start_time, 1),
                    "throughput_chunks_per_second": result.generated_chunks / max(time.time() - start_time, 1)
                })

                if result.error_message:
                    await status_manager.add_error(
                        task_id, "processing_error", result.error_message, recoverable=False
                    )

            except Exception as e:
                await status_manager.update_task_status(task_id, {
                    "status": ProcessingStatus.FAILED.value,
                    "current_stage": ProcessingStage.FAILED.value,
                    "processing_time": time.time() - start_time if 'start_time' in locals() else 0
                })
                await status_manager.add_error(
                    task_id, "unexpected_error", str(e), recoverable=False
                )

        # Start the background task
        background_tasks.add_task(process_local_repository)
        
        # Return initial status
        return IndexingStatusResponse(
            task_id=task_id,
            repository_name=request.name,
            status=ProcessingStatus.IN_PROGRESS,
            progress=0.0,
            processed_files=0,
            generated_chunks=0,
            processing_time=0.0
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start local indexing: {str(e)}")


@router.post("/bulk")
async def bulk_index_repositories(
    request: BulkIndexRequest,
    background_tasks: BackgroundTasks,
    processor: EnhancedRepositoryProcessor = Depends(get_repository_processor),
    redis_client: RedisClient = Depends(get_redis_client)
):
    """
    Index multiple repositories in bulk.
    
    This endpoint processes multiple repositories concurrently with
    configurable concurrency limits.
    """
    try:
        # Create repository configs
        repo_configs = []
        for repo_request in request.repositories:
            repo_config = RepositoryConfig(
                name=repo_request.name,
                url=str(repo_request.url),
                branch=repo_request.branch,
                priority=repo_request.priority,
                business_domain=repo_request.business_domain,
                team_owner=repo_request.team_owner,
                maven_enabled=repo_request.maven_enabled,
                is_golden_repo=repo_request.is_golden_repo
            )
            repo_configs.append(repo_config)
        
        # Start bulk processing
        task_id = f"bulk_{int(time.time())}"
        run_id = __import__("uuid").uuid4().hex

        status_manager = StatusUpdateManager(redis_client)
        
        async def process_bulk():
            try:
                # Initialize bulk processing status
                initial_status = EnhancedIndexingStatus(
                    repository_name=f"bulk_processing_{len(repo_configs)}_repos",
                    task_id=task_id,
                    run_id=run_id,
                    status=ProcessingStatus.IN_PROGRESS,
                    current_stage=ProcessingStage.QUEUED,
                    started_at=datetime.now(),
                    total_files=len(repo_configs)  # Using total_files to track repositories
                ).dict()
                await redis_client.set_task_status(task_id, initial_status)
                
                await status_manager.add_stage_progress(
                    task_id, ProcessingStage.ANALYZING,
                    current_operation=f"Processing {len(repo_configs)} repositories in bulk"
                )
                
                start_time = time.time()
                
                # Process repositories with progress tracking
                results = []
                for i, repo_config in enumerate(repo_configs):
                    try:
                        await status_manager.update_task_status(task_id, {
                            "current_file": f"Repository: {repo_config.name}",
                            "processed_files": i,
                            "overall_progress": (i / len(repo_configs)) * 100
                        })
                        
                        result = await processor.process_repository(repo_config)
                        results.append(result)
                        
                        if result.status == ProcessingStatus.FAILED:
                            await status_manager.add_error(
                                task_id, "repository_failed", 
                                f"Failed to process {repo_config.name}: {result.error_message}",
                                recoverable=True
                            )
                        
                    except Exception as e:
                        await status_manager.add_error(
                            task_id, "repository_error",
                            f"Error processing {repo_config.name}: {str(e)}",
                            recoverable=True
                        )
                
                # Calculate final statistics
                completed = sum(1 for r in results if r.status == ProcessingStatus.COMPLETED)
                failed = sum(1 for r in results if r.status == ProcessingStatus.FAILED)
                total_chunks = sum(r.generated_chunks for r in results)
                
                await status_manager.update_task_status(task_id, {
                    "status": ProcessingStatus.COMPLETED.value,
                    "current_stage": ProcessingStage.COMPLETED.value,
                    "overall_progress": 100.0,
                    "processed_files": len(repo_configs),
                    "generated_chunks": total_chunks,
                    "stored_chunks": total_chunks,
                    "processing_time": time.time() - start_time
                })
                
                # Store bulk results in a custom field (extend model if needed)
                current_status = await redis_client.get_task_status(task_id)
                if current_status:
                    current_status['warnings'].append(f"Bulk processing completed: {completed} successful, {failed} failed")
                    await redis_client.set_task_status(task_id, current_status)
                
            except Exception as e:
                await status_manager.update_task_status(task_id, {
                    "status": ProcessingStatus.FAILED.value,
                    "current_stage": ProcessingStage.FAILED.value,
                    "processing_time": time.time() - start_time if 'start_time' in locals() else 0
                })
                await status_manager.add_error(
                    task_id, "bulk_processing_error", str(e), recoverable=False
                )
        
        # Start the background task
        background_tasks.add_task(process_bulk)
        
        return {
            "task_id": task_id,
            "total_repositories": len(repo_configs),
            "status": "started",
            "message": f"Started bulk processing of {len(repo_configs)} repositories"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start bulk indexing: {str(e)}")


# Safe wrapper: return None instead of raising when Redis client is not initialized
async def try_get_redis_client() -> Optional[RedisClient]:
    try:
        return await get_redis_client()
    except Exception:
        return None


@router.get("/status")
async def get_all_indexing_statuses(redis_client: Optional[RedisClient] = Depends(try_get_redis_client)):
    """
    Return a summary of all active and recently tracked indexing tasks.

    This endpoint is used by the frontend ActiveIndexingTasks panel to poll for
    all current tasks without needing a specific task_id. It aggregates the
    Redis-backed task_status:* keys and returns a compact list.

    If Redis is not initialized (e.g., startup dependencies failed), return an empty list
    with a warning so the frontend UI remains stable instead of 500.
    """
    if not redis_client:
        return {
            "tasks": [],
            "total": 0,
            "warning": "redis_unavailable: client_not_initialized",
            "timestamp": datetime.now().isoformat()
        }

    try:
        all_statuses: Dict[str, Dict[str, Any]] = await redis_client.get_all_task_statuses()
    except Exception as e:
        # Resilient fallback when redis_client is unreachable
        return {
            "tasks": [],
            "total": 0,
            "warning": f"redis_unavailable: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

    summaries = []
    for task_id, status in all_statuses.items():
        try:
            summaries.append({
                "task_id": task_id,
                "repository_name": status.get("repository_name"),
                "status": status.get("status"),
                "current_stage": status.get("current_stage"),
                "overall_progress": status.get("overall_progress"),
                "processed_files": status.get("processed_files"),
                "generated_chunks": status.get("generated_chunks"),
                "started_at": status.get("started_at"),
                "estimated_completion": status.get("estimated_completion"),
                "errors_count": len(status.get("errors", [])),
                "warnings_count": len(status.get("warnings", [])),
            })
        except Exception:
            continue

    return {
        "tasks": summaries,
        "total": len(summaries),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/status/{task_id}", response_model=EnhancedIndexingStatus)
async def get_indexing_status(task_id: str, redis_client: RedisClient = Depends(get_redis_client)):
    """
    Get the enhanced status of an indexing task.
    
    This endpoint returns comprehensive status and progress information
    including stage tracking, embedding progress, and error details.
    """
    status_data = await redis_client.get_task_status(task_id)
    if not status_data:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return EnhancedIndexingStatus(**status_data)


@router.websocket("/status/{task_id}/stream")
async def stream_indexing_status(websocket: WebSocket, task_id: str, redis_client: RedisClient = Depends(get_redis_client)):
    """
    WebSocket endpoint for real-time indexing status updates.
    
    This endpoint provides live streaming of indexing progress including
    stage transitions, embedding generation progress, and error notifications.
    """
    await websocket.accept()
    
    # Add client to active connections
    if task_id not in active_websockets:
        active_websockets[task_id] = []
    active_websockets[task_id].append(websocket)
    
    try:
        # Send initial status if task exists
        initial_status_data = await redis_client.get_task_status(task_id)
        if initial_status_data:
            initial_message = {
                "type": "initial_status",
                "task_id": task_id,
                "data": initial_status_data
            }
            await websocket.send_text(json.dumps(initial_message, default=str))
        else:
            error_message = {
                "type": "error",
                "message": f"Task {task_id} not found"
            }
            await websocket.send_text(json.dumps(error_message))
            return
        
        # Keep connection alive and handle client messages
        while True:
            try:
                # Wait for client messages (ping/pong, etc.) with a longer timeout
                message = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                
                # Handle client messages
                try:
                    client_data = json.loads(message)
                    if client_data.get("type") == "ping":
                        pong_message = {"type": "pong", "timestamp": datetime.now().isoformat()}
                        await websocket.send_text(json.dumps(pong_message))
                except json.JSONDecodeError:
                    # Ignore invalid JSON
                    pass
                    
            except asyncio.TimeoutError:
                # Send periodic heartbeat to keep connection alive
                heartbeat = {
                    "type": "heartbeat",
                    "timestamp": datetime.now().isoformat(),
                    "task_id": task_id
                }
                try:
                    await websocket.send_text(json.dumps(heartbeat))
                except WebSocketDisconnect:
                    # Client disconnected, break the loop
                    break
                except Exception:
                    # Other send error, break the loop
                    break
                
    except WebSocketDisconnect:
        # Client disconnected
        pass
    except Exception as e:
        # Handle other errors
        try:
            error_message = {
                "type": "error",
                "message": f"WebSocket error: {str(e)}"
            }
            await websocket.send_text(json.dumps(error_message))
        except:
            pass
    finally:
        # Clean up connection
        if task_id in active_websockets:
            try:
                active_websockets[task_id].remove(websocket)
                if not active_websockets[task_id]:
                    del active_websockets[task_id]
            except ValueError:
                pass


@router.get("/status/{task_id}/logs")
async def get_indexing_logs(task_id: str, level: str = QueryParam(default="INFO"), redis_client: RedisClient = Depends(get_redis_client)):
    """
    Get detailed logs for an indexing task.
    
    This endpoint returns structured logs with filtering capabilities
    for debugging and monitoring indexing operations.
    """
    status = await redis_client.get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Compile logs from various sources
    logs = []
    
    # Stage history logs
    for stage_progress_data in status['stage_history']:
        stage_progress = StageProgress(**stage_progress_data)
        logs.append({
            "timestamp": stage_progress.started_at,
            "level": "INFO",
            "stage": stage_progress.stage,
            "message": f"Stage {stage_progress.stage} started",
            "details": {
                "progress": stage_progress.progress_percentage,
                "operation": stage_progress.current_operation
            }
        })
        
        if stage_progress.completed_at:
            logs.append({
                "timestamp": stage_progress.completed_at,
                "level": "INFO",
                "stage": stage_progress.stage,
                "message": f"Stage {stage_progress.stage} completed",
                "details": {
                    "duration": (datetime.fromisoformat(stage_progress.completed_at) - stage_progress.started_at).total_seconds()
                }
            })
    
    # Error logs
    for error_data in status['errors']:
        error = IndexingError(**error_data)
        logs.append({
            "timestamp": error.timestamp,
            "level": "ERROR",
            "stage": error.stage,
            "message": error.error_message,
            "details": {
                "error_type": error.error_type,
                "file_path": error.file_path,
                "recoverable": error.recoverable
            }
        })
    
    # Warning logs
    for warning in status['warnings']:
        logs.append({
            "timestamp": datetime.now(),  # Warnings don't have timestamps in current model
            "level": "WARNING",
            "stage": status['current_stage'],
            "message": warning,
            "details": {}
        })
    
    # Sort by timestamp
    logs.sort(key=lambda x: x["timestamp"])
    
    # Filter by level if specified
    level_priority = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}
    min_level = level_priority.get(level.upper(), 1)
    filtered_logs = [log for log in logs if level_priority.get(log["level"], 1) >= min_level]
    
    return {
        "task_id": task_id,
        "repository_name": status['repository_name'],
        "log_level": level,
        "total_logs": len(filtered_logs),
        "logs": filtered_logs
    }


@router.get("/metrics/stages")
async def get_stage_metrics(redis_client: RedisClient = Depends(get_redis_client)):
    """
    Get detailed metrics about processing stages across all tasks.
    
    This endpoint provides insights into stage performance, bottlenecks,
    and processing patterns for monitoring and optimization.
    """
    all_statuses = await redis_client.get_all_task_statuses()
    stage_metrics = {}
    
    for status_data in all_statuses.values():
        status = EnhancedIndexingStatus(**status_data)
        for stage_progress in status.stage_history:
            stage = stage_progress.stage
            
            if stage not in stage_metrics:
                stage_metrics[stage] = {
                    "total_executions": 0,
                    "total_duration": 0.0,
                    "average_duration": 0.0,
                    "min_duration": float('inf'),
                    "max_duration": 0.0,
                    "success_count": 0,
                    "error_count": 0,
                    "current_active": 0
                }
            
            metrics = stage_metrics[stage]
            metrics["total_executions"] += 1
            
            if stage_progress.completed_at:
                duration = (datetime.fromisoformat(stage_progress.completed_at) - stage_progress.started_at).total_seconds()
                metrics["total_duration"] += duration
                metrics["min_duration"] = min(metrics["min_duration"], duration)
                metrics["max_duration"] = max(metrics["max_duration"], duration)
                metrics["success_count"] += 1
            else:
                # Stage is still active
                metrics["current_active"] += 1
                
                # Check if stage has errors
                if stage_progress.error_message:
                    metrics["error_count"] += 1
    
    # Calculate averages
    for metrics in stage_metrics.values():
        if metrics["success_count"] > 0:
            metrics["average_duration"] = metrics["total_duration"] / metrics["success_count"]
        if metrics["min_duration"] == float('inf'):
            metrics["min_duration"] = 0.0
    
    return {
        "stage_metrics": stage_metrics,
        "total_stages_tracked": len(stage_metrics),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/metrics/embedding")
async def get_embedding_metrics(redis_client: RedisClient = Depends(get_redis_client)):
    """
    Get detailed metrics about embedding generation across all tasks.
    
    This endpoint provides insights into embedding performance, throughput,
    and quality metrics for CodeBERT processing optimization.
    """
    all_statuses = await redis_client.get_all_task_statuses()
    embedding_metrics = {
        "total_chunks_embedded": 0,
        "total_embedding_time": 0.0,
        "average_embedding_rate": 0.0,
        "active_embedding_tasks": 0,
        "embedding_errors": 0,
        "repositories_with_embeddings": 0,
        "embedding_quality_metrics": {
            "dimension_consistency": True,
            "average_embedding_size": 0,
            "null_embeddings": 0
        }
    }
    
    repositories_with_embeddings = set()
    total_embedding_rates = []
    
    for status_data in all_statuses.values():
        status = EnhancedIndexingStatus(**status_data)
        if status.embedding_progress.total_chunks > 0:
            repositories_with_embeddings.add(status.repository_name)
            embedding_metrics["total_chunks_embedded"] += status.embedding_progress.embedded_chunks
            
            if status.embedding_progress.embedding_rate > 0:
                total_embedding_rates.append(status.embedding_progress.embedding_rate)
            
            embedding_metrics["embedding_errors"] += len(status.embedding_progress.embedding_errors)
            
            # Check if currently embedding
            if status.current_stage == ProcessingStage.EMBEDDING:
                embedding_metrics["active_embedding_tasks"] += 1
    
    embedding_metrics["repositories_with_embeddings"] = len(repositories_with_embeddings)
    
    if total_embedding_rates:
        embedding_metrics["average_embedding_rate"] = sum(total_embedding_rates) / len(total_embedding_rates)
    
    return {
        "embedding_metrics": embedding_metrics,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/update/{repository_name}")
async def update_repository(
    repository_name: str,
    background_tasks: BackgroundTasks,
    processor: EnhancedRepositoryProcessor = Depends(get_repository_processor),
    redis_client: RedisClient = Depends(get_redis_client)
):
    """
    Perform incremental update for a repository.
    
    This endpoint performs an incremental update for a repository,
    processing only changed files since the last update.
    """
    try:
        # Start incremental update
        task_id = f"{repository_name}_update_{int(time.time())}"
        run_id = __import__("uuid").uuid4().hex

        status_manager = StatusUpdateManager(redis_client)
        
        async def perform_update():
            try:
                initial_status = EnhancedIndexingStatus(
                    repository_name=repository_name,
                    task_id=task_id,
                    run_id=run_id,
                    status=ProcessingStatus.IN_PROGRESS,
                    current_stage=ProcessingStage.QUEUED,
                    started_at=datetime.now()
                ).dict()
                await redis_client.set_task_status(task_id, initial_status)
                
                result = await processor.incremental_update(repository_name)
                
                await status_manager.update_task_status(task_id, {
                    "status": result.status.value,
                    "processing_time": result.processing_time,
                    "processed_files": result.processed_files,
                    "generated_chunks": result.generated_chunks,
                    "error_message": result.error_message
                })
                
            except Exception as e:
                await status_manager.update_task_status(task_id, {
                    "status": ProcessingStatus.FAILED.value,
                    "error_message": str(e)
                })
        
        # Start the background task
        background_tasks.add_task(perform_update)
        
        return {
            "task_id": task_id,
            "repository_name": repository_name,
            "update_type": "incremental",
            "status": "started"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start incremental update: {str(e)}")


@router.delete("/repository/{repository_name}")
async def delete_repository_index(
    repository_name: str,
    processor: EnhancedRepositoryProcessor = Depends(get_repository_processor)
):
    """
    Delete a repository from the index.
    
    This endpoint removes all indexed data for a repository from both
    ChromaDB and Neo4j databases.
    """
    try:
        # Delete from ChromaDB
        chroma_success = await processor.chroma_client.delete_repository(repository_name)
        
        # Delete from Neo4j
        neo4j_query = GraphQuery(
            cypher="""
            MATCH (r:Repository {name: $repository_name})
            DETACH DELETE r
            """,
            parameters={"repository_name": repository_name},
            read_only=False
        )
        
        await processor.neo4j_client.execute_query(neo4j_query)
        
        return {
            "repository_name": repository_name,
            "status": "deleted",
            "chromadb_success": chroma_success,
            "neo4j_success": True
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete repository: {str(e)}")


@router.post("/filter")
async def filter_repositories(
    filter_request: RepositoryFilterRequest,
    processor: EnhancedRepositoryProcessor = Depends(get_repository_processor)
):
    """
    Filter repositories based on criteria.
    
    This endpoint returns a list of repositories that match the specified
    filtering criteria.
    """
    try:
        # Create filter object
        repo_filter = RepositoryFilter(
            name_patterns=filter_request.name_patterns,
            domains=filter_request.domains,
            teams=filter_request.teams,
            priorities=filter_request.priorities,
            is_golden_repo=filter_request.is_golden_repo,
            exclude_names=filter_request.exclude_names
        )
        
        # Get all repositories from Neo4j
        query = GraphQuery(
            cypher="""
            MATCH (r:Repository)
            RETURN r.name as name, r.url as url, r.branch as branch,
                   r.priority as priority, r.business_domain as business_domain,
                   r.team_owner as team_owner, r.is_golden_repo as is_golden_repo,
                   r.languages as languages, r.file_count as file_count,
                   r.lines_of_code as lines_of_code, r.chunks_count as chunks_count
            ORDER BY r.name
            """,
            read_only=True
        )
        
        result = await processor.neo4j_client.execute_query(query)
        
        # Apply filtering
        filtered_repos = []
        for record in result.records:
            # Check name patterns
            if filter_request.name_patterns:
                if not any(pattern in record['name'] for pattern in filter_request.name_patterns):
                    continue
            
            # Check domains
            if filter_request.domains:
                if record['business_domain'] not in filter_request.domains:
                    continue
            
            # Check teams
            if filter_request.teams:
                if record['team_owner'] not in filter_request.teams:
                    continue
            
            # Check priorities
            if filter_request.priorities:
                if record['priority'] not in [p.value for p in filter_request.priorities]:
                    continue
            
            # Check golden repo flag
            if filter_request.is_golden_repo is not None:
                if record['is_golden_repo'] != filter_request.is_golden_repo:
                    continue
            
            # Check exclusions
            if record['name'] in filter_request.exclude_names:
                continue
            
            filtered_repos.append(record)
        
        return {
            "filtered_repositories": filtered_repos,
            "total_repositories": len(filtered_repos),
            "filter_criteria": filter_request.dict()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to filter repositories: {str(e)}")


@router.get("/repositories")
async def list_repositories(
    limit: int = QueryParam(default=50, ge=1, le=200),
    offset: int = QueryParam(default=0, ge=0),
    processor: EnhancedRepositoryProcessor = Depends(get_repository_processor)
):
    """
    List all indexed repositories.
    
    This endpoint returns a paginated list of all repositories in the system.
    """
    try:
        query = GraphQuery(
            cypher="""
            MATCH (r:Repository)
            RETURN r.name as name, r.url as url, r.branch as branch,
                   r.priority as priority, r.business_domain as business_domain,
                   r.team_owner as team_owner, r.is_golden_repo as is_golden_repo,
                   r.languages as languages, r.file_count as file_count,
                   r.lines_of_code as lines_of_code, r.chunks_count as chunks_count,
                   r.updated_at as updated_at
            ORDER BY r.name
            SKIP $offset
            LIMIT $limit
            """,
            parameters={"offset": offset, "limit": limit},
            read_only=True
        )
        
        result = await processor.neo4j_client.execute_query(query)
        
        # Get total count
        count_query = GraphQuery(
            cypher="MATCH (r:Repository) RETURN count(r) as total",
            read_only=True
        )
        
        count_result = await processor.neo4j_client.execute_query(count_query)
        total_count = count_result.records[0]['total'] if count_result.records else 0
        
        return {
            "repositories": result.records,
            "total_repositories": total_count,
            "page_info": {
                "offset": offset,
                "limit": limit,
                "has_next": offset + limit < total_count
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list repositories: {str(e)}")


@router.get("/repositories/{repository_name}")
async def get_repository_details(
    repository_name: str,
    processor: EnhancedRepositoryProcessor = Depends(get_repository_processor)
):
    """
    Get detailed information about a specific repository.
    
    This endpoint returns comprehensive information about a repository,
    including statistics and health metrics.
    """
    try:
        # Get repository info
        query = GraphQuery(
            cypher="""
            MATCH (r:Repository {name: $repository_name})
            RETURN r.name as name, r.url as url, r.branch as branch,
                   r.priority as priority, r.business_domain as business_domain,
                   r.team_owner as team_owner, r.is_golden_repo as is_golden_repo,
                   r.languages as languages, r.file_count as file_count,
                   r.lines_of_code as lines_of_code, r.chunks_count as chunks_count,
                   r.updated_at as updated_at
            """,
            parameters={"repository_name": repository_name},
            read_only=True
        )
        
        result = await processor.neo4j_client.execute_query(query)
        
        if not result.records:
            raise HTTPException(status_code=404, detail="Repository not found")
        
        repo_info = result.records[0]
        
        # Get health metrics
        health_metrics = await processor.neo4j_client.analyze_repository_health(repository_name)
        
        return {
            "repository_info": repo_info,
            "health_metrics": health_metrics,
            "last_updated": repo_info.get('updated_at')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get repository details: {str(e)}")


@router.get("/statistics")
async def get_indexing_statistics(
    processor: EnhancedRepositoryProcessor = Depends(get_repository_processor),
    redis_client: RedisClient = Depends(get_redis_client)
):
    """
    Get indexing pipeline statistics.
    
    This endpoint returns comprehensive statistics about the indexing pipeline
    and database contents.
    """
    try:
        stats = await processor.get_processing_statistics()
        all_statuses = await redis_client.get_all_task_statuses()
        
        active_tasks = sum(1 for status in all_statuses.values() if status['status'] == ProcessingStatus.IN_PROGRESS.value)
        total_tracked_tasks = len(all_statuses)

        return {
            "processing_statistics": stats,
            "active_tasks": active_tasks,
            "tracked_tasks": total_tracked_tasks,
            "timestamp": time.time()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")


@router.post("/optimize")
async def optimize_indices(
    processor: EnhancedRepositoryProcessor = Depends(get_repository_processor)
):
    """
    Optimize database indices for better performance.
    
    This endpoint triggers optimization routines for both ChromaDB and Neo4j
    to improve query performance.
    """
    try:
        # Optimize ChromaDB
        await processor.chroma_client.optimize_collection()
        
        # Optimize Neo4j (example optimization queries)
        optimization_queries = [
            "CALL db.index.fulltext.drop('code_search')",
            "CALL db.index.fulltext.createNodeIndex('code_search', ['CodeChunk'], ['name', 'content'])",
            "CALL gds.graph.drop('dependency_graph', false)",
            "CALL gds.graph.create.cypher('dependency_graph', 'MATCH (n:MavenArtifact) RETURN id(n) AS id', 'MATCH (a:MavenArtifact)-[:DEPENDS_ON]->(b:MavenArtifact) RETURN id(a) AS source, id(b) AS target')"
        ]
        
        for query in optimization_queries:
            try:
                await processor.neo4j_client.execute_query(GraphQuery(
                    cypher=query,
                    read_only=False
                ))
            except Exception as e:
                # Some optimization queries might fail if objects don't exist
                continue
        
        return {
            "status": "optimization_completed",
            "message": "Database optimization completed successfully",
            "timestamp": time.time()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to optimize indices: {str(e)}")


@router.post("/cleanup")
async def cleanup_old_tasks(redis_client: RedisClient = Depends(get_redis_client)):
    """
    Clean up old completed tasks.
    
    This endpoint removes old task statuses to free up memory.
    """
    try:
        current_time = time.time()
        cleanup_threshold = 24 * 60 * 60  # 24 hours
        
        # Remove old task statuses from Redis
        all_task_ids = await redis_client.client.keys("task_status:*")
        cleaned_count = 0
        for key in all_task_ids:
            status_data = await redis_client.client.get(key)
            if status_data:
                status = json.loads(status_data)
                started_at_timestamp = datetime.fromisoformat(status['started_at']).timestamp()
                if current_time - started_at_timestamp > cleanup_threshold and status['status'] != ProcessingStatus.IN_PROGRESS.value:
                    await redis_client.client.delete(key)
                    cleaned_count += 1
        
        return {
            "status": "cleanup_completed",
            "cleaned_task_statuses": cleaned_count,
            "remaining_task_statuses": len(await redis_client.client.keys("task_status:*"))
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cleanup tasks: {str(e)}")