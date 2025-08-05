"""
Centralized Redis client for reliable task management, caching, and real-time messaging.

This module provides a robust, async-first Redis client that includes:
- Connection pooling and graceful connection handling.
- Structured logging for all Redis operations.
- Clear, high-level methods for application-specific use cases (e.g., task status).
- Built-in JSON serialization with sensible defaults.
- Health check for integration with system diagnostics.
"""

import asyncio
import json
from typing import Optional, Any, Dict, List

import redis.asyncio as redis
# Compatibility shim: RedisError import location differs between redis 4.x and 5.x
try:
    # redis 5.x style (exceptions exposed under redis.asyncio)
    from redis.asyncio import RedisError  # type: ignore
except Exception:
    # redis 4.x style
    from redis.exceptions import RedisError  # type: ignore

from .logging_config import get_logger
from .exceptions import DatabaseError, ErrorContext

# Initialize logger for this module
logger = get_logger("redis_client")

class RedisClient:
    """A robust, async-first Redis client with connection pooling and structured logging."""

    def __init__(self, redis_url: str):
        """Initializes the RedisClient.

        Args:
            redis_url: The connection URL for the Redis server.
        """
        self.redis_url = redis_url
        self.pool = redis.ConnectionPool.from_url(self.redis_url, decode_responses=True)
        self.client = redis.Redis(connection_pool=self.pool)
        logger.info("RedisClient initialized", redis_url=self.redis_url)

    async def close(self):
        """Gracefully closes the Redis connection pool."""
        logger.info("Closing Redis connection pool")
        await self.pool.disconnect()

    async def health_check(self) -> Dict[str, Any]:
        """Performs a health check on the Redis connection.

        Returns:
            A dictionary containing the health status, never raises.
        """
        try:
            ping_response = await self.client.ping()
            if ping_response:
                logger.debug("Redis health check successful")
                return {"status": "healthy", "message": "Redis connection is active."}
            else:
                logger.warning("Redis ping returned False")
                return {"status": "error", "message": "Ping returned False"}
        except RedisError as e:
            logger.error("Redis health check failed", error=str(e))
            # Return structured error rather than raising to keep callers resilient
            return {"status": "error", "message": f"Redis error: {str(e)}"}

    async def set_task_status(self, task_id: str, status: Dict[str, Any], ttl: int = 3600):
        """Sets the status of an indexing task in Redis with a TTL.

        Args:
            task_id: The unique identifier for the task.
            status: A dictionary representing the task's status.
            ttl: Time-to-live for the key in seconds (default: 1 hour).
        """
        key = f"task_status:{task_id}"
        try:
            # Use default=str for objects that are not directly serializable (like datetime)
            await self.client.set(key, json.dumps(status, default=str), ex=ttl)
            logger.debug("Task status set successfully", task_id=task_id)
        except RedisError as e:
            logger.error("Failed to set task status in Redis", task_id=task_id, error=str(e))
            # Degrade gracefully: do not raise here to avoid bubbling failures to API routes
            return

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves the status of an indexing task from Redis.

        Args:
            task_id: The unique identifier for the task.

        Returns:
            A dictionary representing the task's status, or None if not found.
        """
        key = f"task_status:{task_id}"
        try:
            status_json = await self.client.get(key)
            if status_json:
                logger.debug("Task status retrieved successfully", task_id=task_id)
                return json.loads(status_json)
            logger.warning("Task status not found in Redis", task_id=task_id)
            return None
        except RedisError as e:
            logger.error("Failed to get task status from Redis", task_id=task_id, error=str(e))
            # Graceful degradation for polling endpoints
            return None

    async def get_all_task_statuses(self) -> Dict[str, Dict[str, Any]]:
        """Retrieves all task statuses from Redis.

        Returns:
            A dictionary mapping task IDs to their status.
        """
        statuses = {}
        try:
            async for key in self.client.scan_iter("task_status:*"):
                task_id = key.split(":", 1)[1]
                status = await self.get_task_status(task_id)
                if status:
                    statuses[task_id] = status
            logger.info(f"Retrieved {len(statuses)} task statuses from Redis")
            return statuses
        except RedisError as e:
            logger.error("Failed to scan for task statuses in Redis", error=str(e))
            # Return empty set on error to keep /status responsive
            return {}

# --- Dependency Injection --- #

# This global instance will be managed by the application's lifespan events.
redis_client: Optional[RedisClient] = None

def get_redis_url_from_env():
    """Retrieves Redis URL from environment variables (a placeholder for real config management)."""
    import os
    return os.getenv("REDIS_URL", "redis://localhost:6379")

async def get_redis_client() -> RedisClient:
    """FastAPI dependency injector for the Redis client.

    Raises:
        Exception: If the Redis client has not been initialized.

    Returns:
        The global RedisClient instance.
    """
    if redis_client is None:
        # This should not happen in a running application with proper lifespan management
        logger.critical("Redis client not initialized. Ensure it is created in the application lifespan.")
        raise Exception("Redis client has not been initialized.")
    return redis_client

async def create_redis_client() -> RedisClient:
    """Factory function to create and connect a Redis client instance.

    Startup policy:
      - Attempt to connect and ping Redis
      - If ping fails, keep the client instance for later retries and log a warning (non-fatal)
    """
    global redis_client
    redis_url = get_redis_url_from_env()
    redis_client = RedisClient(redis_url)
    try:
        await redis_client.health_check()
        logger.info("Redis client created and connection verified.")
    except DatabaseError as e:
        # Do NOT raise on startup; allow app to run with degraded Redis
        # Avoid accessing attributes that may not exist on the exception
        logger.warning("Redis client initialization degraded; ping failed", error=str(e))
        # Keep redis_client set so dependencies can attempt later operations
    return redis_client

async def close_redis_client():
    """Function to be called during application shutdown."""
    if redis_client:
        await redis_client.close()