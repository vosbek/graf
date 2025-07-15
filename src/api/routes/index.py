"""
Indexing API routes for repository processing and management.
"""

import asyncio
import time
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query as QueryParam
from pydantic import BaseModel, Field, HttpUrl

from ...services.repository_processor import (
    RepositoryProcessor, RepositoryConfig, RepositoryFilter, 
    RepositoryPriority, ProcessingStatus
)
from ...main import get_repository_processor


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


class IndexingStatusResponse(BaseModel):
    """Response model for indexing status."""
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


# Global task tracking
processing_tasks: Dict[str, asyncio.Task] = {}
task_status: Dict[str, Dict[str, Any]] = {}


@router.post("/repository", response_model=IndexingStatusResponse)
async def index_repository(
    request: RepositoryIndexRequest,
    background_tasks: BackgroundTasks,
    processor: RepositoryProcessor = Depends(get_repository_processor)
):
    """
    Index a single repository.
    
    This endpoint starts the indexing process for a repository and returns
    immediately with a task ID for status tracking.
    """
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
        
        async def process_repository():
            try:
                task_status[task_id] = {
                    "repository_name": request.name,
                    "status": ProcessingStatus.IN_PROGRESS,
                    "progress": 0.0,
                    "processed_files": 0,
                    "generated_chunks": 0,
                    "processing_time": 0.0,
                    "error_message": None,
                    "started_at": time.time()
                }
                
                result = await processor.process_repository(repo_config)
                
                task_status[task_id].update({
                    "status": result.status,
                    "progress": 1.0,
                    "processed_files": result.processed_files,
                    "generated_chunks": result.generated_chunks,
                    "processing_time": result.processing_time,
                    "error_message": result.error_message
                })
                
            except Exception as e:
                task_status[task_id].update({
                    "status": ProcessingStatus.FAILED,
                    "error_message": str(e)
                })
        
        # Start the task
        processing_tasks[task_id] = asyncio.create_task(process_repository())
        
        # Return initial status
        return IndexingStatusResponse(
            repository_name=request.name,
            status=ProcessingStatus.IN_PROGRESS,
            progress=0.0,
            processed_files=0,
            generated_chunks=0,
            processing_time=0.0
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start indexing: {str(e)}")


@router.post("/bulk")
async def bulk_index_repositories(
    request: BulkIndexRequest,
    background_tasks: BackgroundTasks,
    processor: RepositoryProcessor = Depends(get_repository_processor)
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
        
        async def process_bulk():
            try:
                task_status[task_id] = {
                    "task_type": "bulk_processing",
                    "status": ProcessingStatus.IN_PROGRESS,
                    "total_repositories": len(repo_configs),
                    "completed_repositories": 0,
                    "failed_repositories": 0,
                    "progress": 0.0,
                    "started_at": time.time(),
                    "repository_results": []
                }
                
                # Process repositories
                results = await processor.process_repositories(repo_configs)
                
                # Update status
                completed = sum(1 for r in results if r.status == ProcessingStatus.COMPLETED)
                failed = sum(1 for r in results if r.status == ProcessingStatus.FAILED)
                
                task_status[task_id].update({
                    "status": ProcessingStatus.COMPLETED,
                    "completed_repositories": completed,
                    "failed_repositories": failed,
                    "progress": 1.0,
                    "repository_results": [r.to_dict() for r in results]
                })
                
            except Exception as e:
                task_status[task_id].update({
                    "status": ProcessingStatus.FAILED,
                    "error_message": str(e)
                })
        
        # Start the task
        processing_tasks[task_id] = asyncio.create_task(process_bulk())
        
        return {
            "task_id": task_id,
            "total_repositories": len(repo_configs),
            "status": "started",
            "message": f"Started bulk processing of {len(repo_configs)} repositories"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start bulk indexing: {str(e)}")


@router.get("/status/{task_id}")
async def get_indexing_status(task_id: str):
    """
    Get the status of an indexing task.
    
    This endpoint returns the current status and progress of an indexing task.
    """
    if task_id not in task_status:
        raise HTTPException(status_code=404, detail="Task not found")
    
    status = task_status[task_id]
    
    # Check if task is complete
    if task_id in processing_tasks:
        task = processing_tasks[task_id]
        if task.done():
            # Task is finished, clean up
            del processing_tasks[task_id]
            
            # Update final status if needed
            if task.exception():
                status.update({
                    "status": ProcessingStatus.FAILED,
                    "error_message": str(task.exception())
                })
    
    return status


@router.get("/status")
async def get_all_indexing_status():
    """
    Get the status of all indexing tasks.
    
    This endpoint returns the status of all currently tracked indexing tasks.
    """
    # Clean up completed tasks
    completed_tasks = []
    for task_id, task in processing_tasks.items():
        if task.done():
            completed_tasks.append(task_id)
    
    for task_id in completed_tasks:
        del processing_tasks[task_id]
    
    return {
        "active_tasks": len(processing_tasks),
        "total_tracked_tasks": len(task_status),
        "task_statuses": task_status
    }


@router.post("/update/{repository_name}")
async def update_repository(
    repository_name: str,
    background_tasks: BackgroundTasks,
    processor: RepositoryProcessor = Depends(get_repository_processor)
):
    """
    Perform incremental update for a repository.
    
    This endpoint performs an incremental update for a repository,
    processing only changed files since the last update.
    """
    try:
        # Start incremental update
        task_id = f"{repository_name}_update_{int(time.time())}"
        
        async def perform_update():
            try:
                task_status[task_id] = {
                    "repository_name": repository_name,
                    "status": ProcessingStatus.IN_PROGRESS,
                    "update_type": "incremental",
                    "started_at": time.time()
                }
                
                result = await processor.incremental_update(repository_name)
                
                task_status[task_id].update({
                    "status": result.status,
                    "processing_time": result.processing_time,
                    "processed_files": result.processed_files,
                    "generated_chunks": result.generated_chunks,
                    "error_message": result.error_message
                })
                
            except Exception as e:
                task_status[task_id].update({
                    "status": ProcessingStatus.FAILED,
                    "error_message": str(e)
                })
        
        # Start the task
        processing_tasks[task_id] = asyncio.create_task(perform_update())
        
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
    processor: RepositoryProcessor = Depends(get_repository_processor)
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
        neo4j_query = {
            "cypher": """
            MATCH (r:Repository {name: $repository_name})
            DETACH DELETE r
            """,
            "parameters": {"repository_name": repository_name},
            "read_only": False
        }
        
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
    processor: RepositoryProcessor = Depends(get_repository_processor)
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
        query = {
            "cypher": """
            MATCH (r:Repository)
            RETURN r.name as name, r.url as url, r.branch as branch,
                   r.priority as priority, r.business_domain as business_domain,
                   r.team_owner as team_owner, r.is_golden_repo as is_golden_repo,
                   r.languages as languages, r.file_count as file_count,
                   r.lines_of_code as lines_of_code, r.chunks_count as chunks_count
            ORDER BY r.name
            """,
            "read_only": True
        }
        
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
    processor: RepositoryProcessor = Depends(get_repository_processor)
):
    """
    List all indexed repositories.
    
    This endpoint returns a paginated list of all repositories in the system.
    """
    try:
        query = {
            "cypher": """
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
            "parameters": {"offset": offset, "limit": limit},
            "read_only": True
        }
        
        result = await processor.neo4j_client.execute_query(query)
        
        # Get total count
        count_query = {
            "cypher": "MATCH (r:Repository) RETURN count(r) as total",
            "read_only": True
        }
        
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
    processor: RepositoryProcessor = Depends(get_repository_processor)
):
    """
    Get detailed information about a specific repository.
    
    This endpoint returns comprehensive information about a repository,
    including statistics and health metrics.
    """
    try:
        # Get repository info
        query = {
            "cypher": """
            MATCH (r:Repository {name: $repository_name})
            RETURN r.name as name, r.url as url, r.branch as branch,
                   r.priority as priority, r.business_domain as business_domain,
                   r.team_owner as team_owner, r.is_golden_repo as is_golden_repo,
                   r.languages as languages, r.file_count as file_count,
                   r.lines_of_code as lines_of_code, r.chunks_count as chunks_count,
                   r.updated_at as updated_at
            """,
            "parameters": {"repository_name": repository_name},
            "read_only": True
        }
        
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
    processor: RepositoryProcessor = Depends(get_repository_processor)
):
    """
    Get indexing pipeline statistics.
    
    This endpoint returns comprehensive statistics about the indexing pipeline
    and database contents.
    """
    try:
        stats = await processor.get_processing_statistics()
        
        return {
            "processing_statistics": stats,
            "active_tasks": len(processing_tasks),
            "tracked_tasks": len(task_status),
            "timestamp": time.time()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")


@router.post("/optimize")
async def optimize_indices(
    processor: RepositoryProcessor = Depends(get_repository_processor)
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
                await processor.neo4j_client.execute_query({
                    "cypher": query,
                    "read_only": False
                })
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
async def cleanup_old_tasks():
    """
    Clean up old completed tasks.
    
    This endpoint removes old task statuses to free up memory.
    """
    try:
        current_time = time.time()
        cleanup_threshold = 24 * 60 * 60  # 24 hours
        
        # Remove old task statuses
        old_tasks = []
        for task_id, status in task_status.items():
            started_at = status.get('started_at', current_time)
            if current_time - started_at > cleanup_threshold:
                old_tasks.append(task_id)
        
        for task_id in old_tasks:
            del task_status[task_id]
        
        # Clean up completed processing tasks
        completed_tasks = []
        for task_id, task in processing_tasks.items():
            if task.done():
                completed_tasks.append(task_id)
        
        for task_id in completed_tasks:
            del processing_tasks[task_id]
        
        return {
            "status": "cleanup_completed",
            "cleaned_task_statuses": len(old_tasks),
            "cleaned_processing_tasks": len(completed_tasks),
            "remaining_task_statuses": len(task_status),
            "remaining_processing_tasks": len(processing_tasks)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cleanup tasks: {str(e)}")