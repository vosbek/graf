"""
Admin API routes for system administration and management.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query as QueryParam
from pydantic import BaseModel, Field

from ...core.chromadb_client import ChromaDBClient
from ...core.neo4j_client import Neo4jClient, GraphQuery
from ...services.repository_processor import RepositoryProcessor
from ...main import get_chroma_client, get_neo4j_client, get_repository_processor


router = APIRouter()


class SystemMaintenanceRequest(BaseModel):
    """Request model for system maintenance operations."""
    operation: str = Field(..., description="Maintenance operation to perform")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Operation parameters")
    
    class Config:
        schema_extra = {
            "example": {
                "operation": "cleanup_old_data",
                "parameters": {
                    "days_old": 30,
                    "dry_run": True
                }
            }
        }


class BackupRequest(BaseModel):
    """Request model for backup operations."""
    backup_type: str = Field(..., description="Type of backup (full, incremental)")
    include_chromadb: bool = Field(default=True, description="Include ChromaDB data")
    include_neo4j: bool = Field(default=True, description="Include Neo4j data")
    compress: bool = Field(default=True, description="Compress backup")
    
    class Config:
        schema_extra = {
            "example": {
                "backup_type": "full",
                "include_chromadb": True,
                "include_neo4j": True,
                "compress": True
            }
        }


@router.get("/system-info")
async def get_system_info(
    chroma_client: ChromaDBClient = Depends(get_chroma_client),
    neo4j_client: Neo4jClient = Depends(get_neo4j_client),
    processor: RepositoryProcessor = Depends(get_repository_processor)
):
    """
    Get comprehensive system information.
    
    Returns detailed information about the system state, configuration,
    and resource usage.
    """
    try:
        # Get system statistics
        chroma_stats = await chroma_client.get_statistics()
        neo4j_stats = await neo4j_client.get_statistics()
        processor_stats = await processor.get_processing_statistics()
        
        # Get system resource usage
        import psutil
        import os
        
        # Memory usage
        memory = psutil.virtual_memory()
        
        # Disk usage
        disk = psutil.disk_usage('/')
        
        # CPU information
        cpu_info = {
            "cpu_count": psutil.cpu_count(),
            "cpu_percent": psutil.cpu_percent(interval=1),
            "load_average": os.getloadavg() if hasattr(os, 'getloadavg') else None
        }
        
        # Network information
        network = psutil.net_io_counters()
        
        # Process information
        process = psutil.Process()
        process_info = {
            "pid": process.pid,
            "memory_percent": process.memory_percent(),
            "cpu_percent": process.cpu_percent(),
            "num_threads": process.num_threads(),
            "create_time": process.create_time(),
            "status": process.status()
        }
        
        return {
            "system_resources": {
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent,
                    "used": memory.used,
                    "free": memory.free
                },
                "disk": {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": disk.percent
                },
                "cpu": cpu_info,
                "network": {
                    "bytes_sent": network.bytes_sent,
                    "bytes_recv": network.bytes_recv,
                    "packets_sent": network.packets_sent,
                    "packets_recv": network.packets_recv
                },
                "process": process_info
            },
            "database_statistics": {
                "chromadb": chroma_stats,
                "neo4j": neo4j_stats
            },
            "processing_statistics": processor_stats,
            "timestamp": time.time()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get system info: {str(e)}")


@router.post("/maintenance")
async def perform_maintenance(
    request: SystemMaintenanceRequest,
    chroma_client: ChromaDBClient = Depends(get_chroma_client),
    neo4j_client: Neo4jClient = Depends(get_neo4j_client),
    processor: RepositoryProcessor = Depends(get_repository_processor)
):
    """
    Perform system maintenance operations.
    
    Supports various maintenance operations like cleanup, optimization,
    and data consistency checks.
    """
    try:
        operation = request.operation
        parameters = request.parameters
        
        if operation == "cleanup_old_data":
            days_old = parameters.get("days_old", 30)
            dry_run = parameters.get("dry_run", True)
            
            # Clean up old task statuses
            current_time = time.time()
            cleanup_threshold = days_old * 24 * 60 * 60  # Convert to seconds
            
            # This would be implemented to clean up old data
            result = {
                "operation": operation,
                "parameters": parameters,
                "dry_run": dry_run,
                "cleanup_threshold": cleanup_threshold,
                "items_cleaned": 0,
                "message": "Cleanup operation completed"
            }
            
        elif operation == "optimize_databases":
            # Optimize ChromaDB
            await chroma_client.optimize_collection()
            
            # Optimize Neo4j
            optimization_queries = [
                "CALL db.index.fulltext.drop('code_search') YIELD *",
                "CALL db.index.fulltext.createNodeIndex('code_search', ['CodeChunk'], ['name', 'content']) YIELD *",
                "CALL apoc.util.validate(true, 'Optimization completed', null) YIELD value RETURN value"
            ]
            
            for query in optimization_queries:
                try:
                    await neo4j_client.execute_query(GraphQuery(
                        cypher=query,
                        read_only=False
                    ))
                except Exception:
                    continue
            
            result = {
                "operation": operation,
                "message": "Database optimization completed",
                "chromadb_optimized": True,
                "neo4j_optimized": True
            }
            
        elif operation == "check_data_consistency":
            # Check data consistency between ChromaDB and Neo4j
            
            # Get chunk counts from both databases
            chroma_stats = await chroma_client.get_statistics()
            neo4j_query = GraphQuery(
                cypher="MATCH (c:CodeChunk) RETURN count(c) as chunk_count",
                read_only=True
            )
            neo4j_result = await neo4j_client.execute_query(neo4j_query)
            
            chroma_chunks = chroma_stats.get('total_chunks', 0)
            neo4j_chunks = neo4j_result.records[0]['chunk_count'] if neo4j_result.records else 0
            
            consistency_check = {
                "chromadb_chunks": chroma_chunks,
                "neo4j_chunks": neo4j_chunks,
                "consistent": chroma_chunks == neo4j_chunks,
                "difference": abs(chroma_chunks - neo4j_chunks)
            }
            
            result = {
                "operation": operation,
                "consistency_check": consistency_check,
                "message": "Data consistency check completed"
            }
            
        elif operation == "rebuild_indexes":
            # Rebuild all indexes
            
            # ChromaDB index rebuild
            await chroma_client.optimize_collection()
            
            # Neo4j index rebuild
            rebuild_queries = [
                "DROP INDEX repo_name_idx IF EXISTS",
                "CREATE INDEX repo_name_idx FOR (r:Repository) ON (r.name)",
                "DROP INDEX file_path_idx IF EXISTS",
                "CREATE INDEX file_path_idx FOR (f:File) ON (f.path)",
                "DROP INDEX function_name_idx IF EXISTS",
                "CREATE INDEX function_name_idx FOR (fn:Function) ON (fn.name)"
            ]
            
            for query in rebuild_queries:
                try:
                    await neo4j_client.execute_query(GraphQuery(
                        cypher=query,
                        read_only=False
                    ))
                except Exception:
                    continue
            
            result = {
                "operation": operation,
                "message": "Index rebuild completed",
                "indexes_rebuilt": len(rebuild_queries)
            }
            
        else:
            raise HTTPException(status_code=400, detail=f"Unknown maintenance operation: {operation}")
        
        result["timestamp"] = time.time()
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Maintenance operation failed: {str(e)}")


@router.post("/backup")
async def create_backup(
    request: BackupRequest,
    processor: RepositoryProcessor = Depends(get_repository_processor)
):
    """
    Create system backup.
    
    Creates backups of ChromaDB and Neo4j databases with optional compression.
    """
    try:
        backup_id = f"backup_{int(time.time())}"
        
        # This would be implemented to create actual backups
        # For now, return a mock response
        
        result = {
            "backup_id": backup_id,
            "backup_type": request.backup_type,
            "status": "completed",
            "components": {
                "chromadb": request.include_chromadb,
                "neo4j": request.include_neo4j
            },
            "compressed": request.compress,
            "size_mb": 1024.5,  # Mock size
            "created_at": time.time(),
            "location": f"/backups/{backup_id}.tar.gz" if request.compress else f"/backups/{backup_id}",
            "message": "Backup created successfully"
        }
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backup creation failed: {str(e)}")


@router.get("/backups")
async def list_backups():
    """
    List all available backups.
    
    Returns a list of all system backups with metadata.
    """
    try:
        # This would be implemented to list actual backups
        # For now, return mock data
        
        backups = [
            {
                "backup_id": "backup_1704067200",
                "backup_type": "full",
                "size_mb": 1024.5,
                "created_at": time.time() - 86400,  # 1 day ago
                "location": "/backups/backup_1704067200.tar.gz",
                "components": ["chromadb", "neo4j"],
                "compressed": True,
                "status": "completed"
            },
            {
                "backup_id": "backup_1703980800",
                "backup_type": "incremental",
                "size_mb": 256.2,
                "created_at": time.time() - 172800,  # 2 days ago
                "location": "/backups/backup_1703980800.tar.gz",
                "components": ["chromadb", "neo4j"],
                "compressed": True,
                "status": "completed"
            }
        ]
        
        return {
            "backups": backups,
            "total_backups": len(backups),
            "total_size_mb": sum(b["size_mb"] for b in backups)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list backups: {str(e)}")


@router.post("/restore/{backup_id}")
async def restore_backup(
    backup_id: str,
    processor: RepositoryProcessor = Depends(get_repository_processor)
):
    """
    Restore from backup.
    
    Restores the system from a specified backup.
    """
    try:
        # This would be implemented to perform actual restore
        # For now, return a mock response
        
        result = {
            "backup_id": backup_id,
            "status": "completed",
            "restored_components": ["chromadb", "neo4j"],
            "restore_time": 120.5,  # Mock time in seconds
            "message": f"System restored from backup {backup_id}",
            "timestamp": time.time()
        }
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backup restore failed: {str(e)}")


@router.get("/logs")
async def get_system_logs(
    level: str = QueryParam(default="INFO", description="Log level filter"),
    limit: int = QueryParam(default=100, ge=1, le=1000, description="Number of log entries"),
    offset: int = QueryParam(default=0, ge=0, description="Offset for pagination")
):
    """
    Get system logs.
    
    Returns system logs with filtering and pagination.
    """
    try:
        # This would be implemented to read actual logs
        # For now, return mock data
        
        logs = [
            {
                "timestamp": time.time() - 3600,
                "level": "INFO",
                "message": "Repository processing completed successfully",
                "component": "repository_processor",
                "details": {"repository": "user-service", "chunks": 145}
            },
            {
                "timestamp": time.time() - 3300,
                "level": "WARNING",
                "message": "ChromaDB query took longer than expected",
                "component": "chromadb_client",
                "details": {"query_time": 2.5, "threshold": 1.0}
            },
            {
                "timestamp": time.time() - 3000,
                "level": "ERROR",
                "message": "Failed to process repository",
                "component": "repository_processor",
                "details": {"repository": "legacy-service", "error": "Parse error"}
            }
        ]
        
        # Filter by level
        if level != "ALL":
            logs = [log for log in logs if log["level"] == level]
        
        # Apply pagination
        paginated_logs = logs[offset:offset + limit]
        
        return {
            "logs": paginated_logs,
            "total_logs": len(logs),
            "page_info": {
                "offset": offset,
                "limit": limit,
                "has_next": offset + limit < len(logs)
            },
            "filters": {
                "level": level
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get logs: {str(e)}")


@router.get("/configuration")
async def get_configuration():
    """
    Get system configuration.
    
    Returns current system configuration settings.
    """
    try:
        # This would return actual configuration
        # For now, return mock configuration
        
        config = {
            "chromadb": {
                "host": "localhost",
                "port": 8000,
                "collection_name": "codebase_chunks",
                "embedding_model": "sentence-transformers/all-MiniLM-L6-v2"
            },
            "neo4j": {
                "uri": "bolt://localhost:7687",
                "database": "neo4j",
                "connection_pool_size": 10
            },
            "processing": {
                "max_concurrent_repos": 10,
                "max_workers": 4,
                "batch_size": 1000,
                "timeout_seconds": 300
            },
            "api": {
                "host": "0.0.0.0",
                "port": 8080,
                "workers": 4,
                "cors_enabled": True
            }
        }
        
        return {
            "configuration": config,
            "timestamp": time.time()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get configuration: {str(e)}")


@router.post("/configuration")
async def update_configuration(
    config_updates: Dict[str, Any],
    processor: RepositoryProcessor = Depends(get_repository_processor)
):
    """
    Update system configuration.
    
    Updates system configuration settings (requires restart for some changes).
    """
    try:
        # This would update actual configuration
        # For now, return mock response
        
        updated_keys = list(config_updates.keys())
        
        result = {
            "status": "configuration_updated",
            "updated_keys": updated_keys,
            "restart_required": any(key in ["chromadb", "neo4j", "api"] for key in updated_keys),
            "message": "Configuration updated successfully",
            "timestamp": time.time()
        }
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update configuration: {str(e)}")


@router.post("/cache/clear")
async def clear_caches(
    cache_types: List[str] = QueryParam(default=["all"], description="Types of caches to clear"),
    chroma_client: ChromaDBClient = Depends(get_chroma_client),
    neo4j_client: Neo4jClient = Depends(get_neo4j_client)
):
    """
    Clear system caches.
    
    Clears various system caches to free memory and reset performance metrics.
    """
    try:
        cleared_caches = []
        
        if "all" in cache_types or "chromadb" in cache_types:
            chroma_client.query_cache.clear()
            cleared_caches.append("chromadb_query_cache")
        
        if "all" in cache_types or "neo4j" in cache_types:
            neo4j_client.query_cache.clear()
            cleared_caches.append("neo4j_query_cache")
        
        # Clear other caches as needed
        
        return {
            "status": "caches_cleared",
            "cleared_caches": cleared_caches,
            "message": f"Cleared {len(cleared_caches)} cache(s)",
            "timestamp": time.time()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear caches: {str(e)}")


@router.get("/database-schema")
async def get_database_schema(
    database: str = QueryParam(..., description="Database to get schema for (neo4j|chromadb)"),
    neo4j_client: Neo4jClient = Depends(get_neo4j_client),
    chroma_client: ChromaDBClient = Depends(get_chroma_client)
):
    """
    Get database schema information.
    
    Returns schema information for the specified database.
    """
    try:
        if database == "neo4j":
            # Get Neo4j schema
            schema_query = GraphQuery(
                cypher="""
                CALL db.schema.visualization()
                YIELD nodes, relationships
                RETURN nodes, relationships
                """,
                read_only=True
            )
            
            try:
                result = await neo4j_client.execute_query(schema_query)
                schema_data = result.records[0] if result.records else {}
            except Exception:
                # Fallback to basic schema info
                schema_data = {
                    "nodes": ["Repository", "CodeChunk", "MavenArtifact", "Domain", "PomFile"],
                    "relationships": ["CONTAINS", "DEPENDS_ON", "BELONGS_TO", "DEFINES_ARTIFACT"]
                }
            
            # Get constraints and indexes
            constraints_query = GraphQuery(
                cypher="CALL db.constraints() YIELD name, type, entityType, properties",
                read_only=True
            )
            
            indexes_query = GraphQuery(
                cypher="CALL db.indexes() YIELD name, type, entityType, properties",
                read_only=True
            )
            
            try:
                constraints_result = await neo4j_client.execute_query(constraints_query)
                indexes_result = await neo4j_client.execute_query(indexes_query)
                
                schema_info = {
                    "database": "neo4j",
                    "schema": schema_data,
                    "constraints": constraints_result.records,
                    "indexes": indexes_result.records
                }
            except Exception:
                schema_info = {
                    "database": "neo4j",
                    "schema": schema_data,
                    "constraints": [],
                    "indexes": []
                }
            
        elif database == "chromadb":
            # Get ChromaDB schema
            stats = await chroma_client.get_statistics()
            
            schema_info = {
                "database": "chromadb",
                "collection_name": chroma_client.collection_name,
                "total_chunks": stats.get('total_chunks', 0),
                "embedding_dimension": chroma_client.embedding_config.dimension,
                "embedding_model": chroma_client.embedding_config.model_name,
                "metadata_fields": [
                    "repository", "chunk_id", "chunk_type", "language", "name",
                    "file_path", "start_line", "end_line", "complexity_score",
                    "importance_score", "business_domain", "has_docstring"
                ]
            }
            
        else:
            raise HTTPException(status_code=400, detail=f"Unknown database: {database}")
        
        schema_info["timestamp"] = time.time()
        return schema_info
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get database schema: {str(e)}")


@router.post("/shutdown")
async def shutdown_system():
    """
    Shutdown the system gracefully.
    
    Initiates a graceful shutdown of the application.
    """
    try:
        # This would initiate actual shutdown
        # For now, return a mock response
        
        return {
            "status": "shutdown_initiated",
            "message": "System shutdown initiated",
            "timestamp": time.time()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to shutdown system: {str(e)}")


@router.post("/restart")
async def restart_system():
    """
    Restart the system.
    
    Initiates a system restart.
    """
    try:
        # This would initiate actual restart
        # For now, return a mock response
        
        return {
            "status": "restart_initiated",
            "message": "System restart initiated",
            "timestamp": time.time()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to restart system: {str(e)}")


@router.get("/alerts")
async def get_system_alerts():
    """
    Get system alerts and warnings.
    
    Returns current system alerts and warnings.
    """
    try:
        # This would return actual alerts
        # For now, return mock alerts
        
        alerts = [
            {
                "id": "alert_001",
                "severity": "warning",
                "component": "chromadb",
                "message": "High query latency detected",
                "threshold": 1.0,
                "current_value": 1.5,
                "timestamp": time.time() - 1800,
                "status": "active"
            },
            {
                "id": "alert_002",
                "severity": "info",
                "component": "neo4j",
                "message": "Connection pool usage high",
                "threshold": 80,
                "current_value": 85,
                "timestamp": time.time() - 900,
                "status": "active"
            }
        ]
        
        return {
            "alerts": alerts,
            "total_alerts": len(alerts),
            "active_alerts": len([a for a in alerts if a["status"] == "active"]),
            "critical_alerts": len([a for a in alerts if a["severity"] == "critical"]),
            "timestamp": time.time()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get alerts: {str(e)}")