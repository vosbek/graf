"""
Health check API routes for system monitoring.
"""

import time
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...core.chromadb_client import ChromaDBClient
from ...core.neo4j_client import Neo4jClient
from ...services.repository_processor import RepositoryProcessor
from ...main import get_chroma_client, get_neo4j_client, get_repository_processor


router = APIRouter()


class HealthStatus(BaseModel):
    """Health status response model."""
    status: str
    timestamp: float
    uptime: float
    version: str = "1.0.0"


class DetailedHealthStatus(BaseModel):
    """Detailed health status response model."""
    status: str
    timestamp: float
    uptime: float
    version: str = "1.0.0"
    components: Dict[str, Any]
    system_info: Dict[str, Any]


# Track application start time
app_start_time = time.time()


@router.get("/", response_model=HealthStatus)
async def basic_health_check():
    """
    Basic health check endpoint.
    
    Returns basic application health status.
    """
    return HealthStatus(
        status="healthy",
        timestamp=time.time(),
        uptime=time.time() - app_start_time
    )


@router.get("/ready")
async def readiness_check(
    chroma_client: ChromaDBClient = Depends(get_chroma_client),
    neo4j_client: Neo4jClient = Depends(get_neo4j_client),
    processor: RepositoryProcessor = Depends(get_repository_processor)
):
    """
    Readiness check endpoint.
    
    Returns whether the application is ready to serve requests.
    This includes checking all critical dependencies.
    """
    try:
        # Check ChromaDB
        chroma_health = await chroma_client.health_check()
        
        # Check Neo4j
        neo4j_health = await neo4j_client.health_check()
        
        # Check processor
        processor_health = await processor.health_check()
        
        # Determine overall readiness
        is_ready = (
            chroma_health["status"] == "healthy" and
            neo4j_health["status"] == "healthy" and
            processor_health["status"] == "healthy"
        )
        
        status_code = 200 if is_ready else 503
        
        return {
            "status": "ready" if is_ready else "not_ready",
            "timestamp": time.time(),
            "checks": {
                "chromadb": chroma_health,
                "neo4j": neo4j_health,
                "processor": processor_health
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "error": str(e),
                "timestamp": time.time()
            }
        )


@router.get("/live")
async def liveness_check():
    """
    Liveness check endpoint.
    
    Returns whether the application is alive and running.
    This is a lightweight check for container orchestration.
    """
    return {
        "status": "alive",
        "timestamp": time.time(),
        "uptime": time.time() - app_start_time
    }


@router.get("/detailed", response_model=DetailedHealthStatus)
async def detailed_health_check(
    chroma_client: ChromaDBClient = Depends(get_chroma_client),
    neo4j_client: Neo4jClient = Depends(get_neo4j_client),
    processor: RepositoryProcessor = Depends(get_repository_processor)
):
    """
    Detailed health check endpoint.
    
    Returns comprehensive health information including component status,
    performance metrics, and system information.
    """
    try:
        # Get component health
        chroma_health = await chroma_client.health_check()
        neo4j_health = await neo4j_client.health_check()
        processor_health = await processor.health_check()
        
        # Get statistics
        chroma_stats = await chroma_client.get_statistics()
        neo4j_stats = await neo4j_client.get_statistics()
        processor_stats = await processor.get_processing_statistics()
        
        # Determine overall health
        component_statuses = [
            chroma_health["status"],
            neo4j_health["status"],
            processor_health["status"]
        ]
        
        overall_status = "healthy" if all(s == "healthy" for s in component_statuses) else "unhealthy"
        
        # System information
        import psutil
        import os
        
        system_info = {
            "cpu_usage": psutil.cpu_percent(interval=1),
            "memory_usage": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent,
            "process_count": len(psutil.pids()),
            "python_version": f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
            "platform": os.sys.platform
        }
        
        return DetailedHealthStatus(
            status=overall_status,
            timestamp=time.time(),
            uptime=time.time() - app_start_time,
            components={
                "chromadb": {
                    "health": chroma_health,
                    "statistics": chroma_stats
                },
                "neo4j": {
                    "health": neo4j_health,
                    "statistics": neo4j_stats
                },
                "repository_processor": {
                    "health": processor_health,
                    "statistics": processor_stats
                }
            },
            system_info=system_info
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "error": str(e),
                "timestamp": time.time()
            }
        )


@router.get("/metrics")
async def get_metrics(
    chroma_client: ChromaDBClient = Depends(get_chroma_client),
    neo4j_client: Neo4jClient = Depends(get_neo4j_client),
    processor: RepositoryProcessor = Depends(get_repository_processor)
):
    """
    Get application metrics in Prometheus format.
    
    Returns metrics that can be scraped by Prometheus for monitoring.
    """
    try:
        # Get statistics from all components
        chroma_stats = await chroma_client.get_statistics()
        neo4j_stats = await neo4j_client.get_statistics()
        processor_stats = await processor.get_processing_statistics()
        
        # Build Prometheus metrics
        metrics = []
        
        # Application metrics
        metrics.append(f"# HELP codebase_rag_uptime_seconds Application uptime in seconds")
        metrics.append(f"# TYPE codebase_rag_uptime_seconds counter")
        metrics.append(f"codebase_rag_uptime_seconds {time.time() - app_start_time}")
        
        # ChromaDB metrics
        if chroma_stats.get('total_chunks'):
            metrics.append(f"# HELP codebase_rag_chromadb_chunks_total Total number of chunks in ChromaDB")
            metrics.append(f"# TYPE codebase_rag_chromadb_chunks_total gauge")
            metrics.append(f"codebase_rag_chromadb_chunks_total {chroma_stats['total_chunks']}")
        
        if chroma_stats.get('performance_metrics', {}).get('total_queries'):
            metrics.append(f"# HELP codebase_rag_chromadb_queries_total Total number of queries to ChromaDB")
            metrics.append(f"# TYPE codebase_rag_chromadb_queries_total counter")
            metrics.append(f"codebase_rag_chromadb_queries_total {chroma_stats['performance_metrics']['total_queries']}")
        
        # Neo4j metrics
        if neo4j_stats.get('total_nodes'):
            metrics.append(f"# HELP codebase_rag_neo4j_nodes_total Total number of nodes in Neo4j")
            metrics.append(f"# TYPE codebase_rag_neo4j_nodes_total gauge")
            metrics.append(f"codebase_rag_neo4j_nodes_total {neo4j_stats['total_nodes']}")
        
        if neo4j_stats.get('total_relationships'):
            metrics.append(f"# HELP codebase_rag_neo4j_relationships_total Total number of relationships in Neo4j")
            metrics.append(f"# TYPE codebase_rag_neo4j_relationships_total gauge")
            metrics.append(f"codebase_rag_neo4j_relationships_total {neo4j_stats['total_relationships']}")
        
        # Processing metrics
        if processor_stats.get('total_repositories'):
            metrics.append(f"# HELP codebase_rag_repositories_total Total number of processed repositories")
            metrics.append(f"# TYPE codebase_rag_repositories_total gauge")
            metrics.append(f"codebase_rag_repositories_total {processor_stats['total_repositories']}")
        
        if processor_stats.get('completed_repositories'):
            metrics.append(f"# HELP codebase_rag_repositories_completed_total Total number of successfully processed repositories")
            metrics.append(f"# TYPE codebase_rag_repositories_completed_total counter")
            metrics.append(f"codebase_rag_repositories_completed_total {processor_stats['completed_repositories']}")
        
        if processor_stats.get('failed_repositories'):
            metrics.append(f"# HELP codebase_rag_repositories_failed_total Total number of failed repository processing")
            metrics.append(f"# TYPE codebase_rag_repositories_failed_total counter")
            metrics.append(f"codebase_rag_repositories_failed_total {processor_stats['failed_repositories']}")
        
        # System metrics
        import psutil
        
        metrics.append(f"# HELP codebase_rag_cpu_usage_percent CPU usage percentage")
        metrics.append(f"# TYPE codebase_rag_cpu_usage_percent gauge")
        metrics.append(f"codebase_rag_cpu_usage_percent {psutil.cpu_percent(interval=1)}")
        
        metrics.append(f"# HELP codebase_rag_memory_usage_percent Memory usage percentage")
        metrics.append(f"# TYPE codebase_rag_memory_usage_percent gauge")
        metrics.append(f"codebase_rag_memory_usage_percent {psutil.virtual_memory().percent}")
        
        # Return metrics in Prometheus format
        return "\n".join(metrics)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")


@router.get("/database-status")
async def get_database_status(
    chroma_client: ChromaDBClient = Depends(get_chroma_client),
    neo4j_client: Neo4jClient = Depends(get_neo4j_client)
):
    """
    Get detailed database status and statistics.
    
    Returns comprehensive information about database health and performance.
    """
    try:
        # Get database statistics
        chroma_stats = await chroma_client.get_statistics()
        neo4j_stats = await neo4j_client.get_statistics()
        
        # Get health checks
        chroma_health = await chroma_client.health_check()
        neo4j_health = await neo4j_client.health_check()
        
        return {
            "chromadb": {
                "status": chroma_health["status"],
                "statistics": chroma_stats,
                "health_checks": chroma_health.get("checks", {})
            },
            "neo4j": {
                "status": neo4j_health["status"],
                "statistics": neo4j_stats,
                "health_checks": neo4j_health.get("checks", {})
            },
            "timestamp": time.time()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get database status: {str(e)}")


@router.get("/performance")
async def get_performance_metrics(
    chroma_client: ChromaDBClient = Depends(get_chroma_client),
    neo4j_client: Neo4jClient = Depends(get_neo4j_client),
    processor: RepositoryProcessor = Depends(get_repository_processor)
):
    """
    Get performance metrics for all components.
    
    Returns detailed performance metrics for monitoring and optimization.
    """
    try:
        # Get performance data from all components
        chroma_stats = await chroma_client.get_statistics()
        neo4j_stats = await neo4j_client.get_statistics()
        processor_stats = await processor.get_processing_statistics()
        
        # Extract performance metrics
        performance_metrics = {
            "chromadb": {
                "total_queries": chroma_stats.get('performance_metrics', {}).get('total_queries', 0),
                "average_query_time": chroma_stats.get('performance_metrics', {}).get('average_query_time', 0),
                "cache_hit_rate": chroma_stats.get('performance_metrics', {}).get('cache_hit_rate', 0),
                "cache_size": chroma_stats.get('performance_metrics', {}).get('cache_size', 0)
            },
            "neo4j": {
                "total_queries": neo4j_stats.get('performance_metrics', {}).get('total_queries', 0),
                "average_query_time": neo4j_stats.get('performance_metrics', {}).get('average_query_time', 0),
                "cache_size": neo4j_stats.get('performance_metrics', {}).get('cache_size', 0)
            },
            "processor": {
                "total_repositories": processor_stats.get('total_repositories', 0),
                "completed_repositories": processor_stats.get('completed_repositories', 0),
                "failed_repositories": processor_stats.get('failed_repositories', 0),
                "success_rate": processor_stats.get('success_rate', 0),
                "average_processing_time": processor_stats.get('average_processing_time', 0),
                "total_processing_time": processor_stats.get('total_processing_time', 0)
            }
        }
        
        # Calculate overall performance score
        overall_score = 100.0
        
        # Deduct points for high average query times
        chroma_avg_time = performance_metrics['chromadb']['average_query_time']
        if chroma_avg_time > 1.0:
            overall_score -= min((chroma_avg_time - 1.0) * 10, 20)
        
        neo4j_avg_time = performance_metrics['neo4j']['average_query_time']
        if neo4j_avg_time > 0.5:
            overall_score -= min((neo4j_avg_time - 0.5) * 20, 20)
        
        # Deduct points for low success rate
        success_rate = performance_metrics['processor']['success_rate']
        if success_rate < 0.9:
            overall_score -= (0.9 - success_rate) * 100
        
        # Deduct points for low cache hit rate
        cache_hit_rate = performance_metrics['chromadb']['cache_hit_rate']
        if cache_hit_rate < 0.3:
            overall_score -= (0.3 - cache_hit_rate) * 50
        
        performance_metrics['overall_score'] = max(overall_score, 0)
        performance_metrics['timestamp'] = time.time()
        
        return performance_metrics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get performance metrics: {str(e)}")


@router.post("/reset-metrics")
async def reset_metrics(
    chroma_client: ChromaDBClient = Depends(get_chroma_client),
    neo4j_client: Neo4jClient = Depends(get_neo4j_client),
    processor: RepositoryProcessor = Depends(get_repository_processor)
):
    """
    Reset performance metrics.
    
    Resets all performance counters and metrics to zero.
    """
    try:
        # Reset ChromaDB metrics
        chroma_client.query_count = 0
        chroma_client.total_query_time = 0.0
        chroma_client.cache_hits = 0
        chroma_client.query_cache.clear()
        
        # Reset Neo4j metrics
        neo4j_client.query_count = 0
        neo4j_client.total_query_time = 0.0
        neo4j_client.query_cache.clear()
        
        # Reset processor metrics
        processor.processing_stats = type(processor.processing_stats)()
        
        return {
            "status": "metrics_reset",
            "message": "All performance metrics have been reset",
            "timestamp": time.time()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset metrics: {str(e)}")


@router.get("/version")
async def get_version():
    """
    Get application version information.
    
    Returns version information and build details.
    """
    return {
        "version": "1.0.0",
        "build_date": "2024-01-01",
        "git_commit": "unknown",
        "python_version": f"{__import__('sys').version_info.major}.{__import__('sys').version_info.minor}.{__import__('sys').version_info.micro}",
        "dependencies": {
            "fastapi": "0.104.1",
            "chromadb": "0.4.18",
            "neo4j": "5.15.0",
            "sentence-transformers": "2.2.2"
        }
    }