"""
Error Handling Module
====================

Provides comprehensive error handling functionality including context managers,
error handlers, and API error decorators for the GraphRAG system.

Features:
- Context managers for error handling
- Configurable error handlers with retry logic
- API error decorators
- Error statistics and monitoring

Author: GraphRAG System
Version: 1.0.0
"""

import asyncio
import functools
import logging
import time
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, Callable, List
from fastapi import HTTPException

from .exceptions import GraphRAGException, ErrorContext


class ErrorHandler:
    """
    Configurable error handler with retry logic and statistics.
    """
    
    def __init__(self, component: str, max_retries: int = 3, timeout: float = 30.0):
        """Initialize error handler."""
        self.component = component
        self.max_retries = max_retries
        self.timeout = timeout
        self.stats = {
            "total_errors": 0,
            "retry_attempts": 0,
            "successful_retries": 0,
            "failed_retries": 0,
            "timeouts": 0
        }
        self.logger = logging.getLogger(f"error_handler.{component}")
    
    async def handle_with_retry(self, operation: Callable, *args, **kwargs) -> Any:
        """Execute operation with retry logic."""
        for attempt in range(self.max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(operation):
                    return await asyncio.wait_for(operation(*args, **kwargs), timeout=self.timeout)
                else:
                    return operation(*args, **kwargs)
            except asyncio.TimeoutError:
                self.stats["timeouts"] += 1
                if attempt == self.max_retries:
                    self.stats["total_errors"] += 1
                    raise
                self.stats["retry_attempts"] += 1
                await asyncio.sleep(0.1 * (2 ** attempt))
            except Exception as e:
                self.stats["total_errors"] += 1
                if attempt == self.max_retries:
                    self.stats["failed_retries"] += 1
                    raise
                self.stats["retry_attempts"] += 1
                self.logger.warning(f"Attempt {attempt + 1} failed: {e}, retrying...")
                await asyncio.sleep(0.1 * (2 ** attempt))
        
        self.stats["successful_retries"] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get error handler statistics."""
        return {
            "component": self.component,
            "config": {
                "max_retries": self.max_retries,
                "timeout": self.timeout
            },
            "stats": self.stats.copy()
        }


# Global error handler registry
_error_handlers: Dict[str, ErrorHandler] = {}


def get_error_handler(component: str, max_retries: int = 3, timeout: float = 30.0, **kwargs) -> ErrorHandler:
    """Get or create error handler for component.
    
    Accept and ignore unknown kwargs (e.g., retry_delay) for forwards/backwards compatibility across modules.
    """
    # Explicitly ignore unsupported kwargs to prevent signature drift from breaking startup
    # Example: retry_delay from newer callers; we simply do not use it here.
    _ = kwargs  # no-op to silence linters
    
    if component not in _error_handlers:
        _error_handlers[component] = ErrorHandler(component, max_retries, timeout)
    else:
        # Update existing handler config if parameters differ
        handler = _error_handlers[component]
        handler.max_retries = max_retries
        handler.timeout = timeout
    return _error_handlers[component]


def get_all_error_handler_stats() -> List[Dict[str, Any]]:
    """Get statistics from all error handlers."""
    return [handler.get_stats() for handler in _error_handlers.values()]


@asynccontextmanager
async def error_handling_context(component: str, operation: str, **context_data):
    """
    Async context manager for comprehensive error handling.
    
    Args:
        component: Component name for logging
        operation: Operation name for logging
        **context_data: Additional context data
    
    Yields:
        ErrorContext: Context object for adding diagnostic data
    """
    start_time = time.time()
    logger = logging.getLogger(f"error_context.{component}")
    
    ctx = ErrorContext(
        component=component,
        operation=operation,
        start_time=start_time,
        context_data=context_data.copy()
    )
    
    try:
        logger.debug(f"Starting {operation} in {component}")
        yield ctx
        
        duration = time.time() - start_time
        logger.debug(f"Completed {operation} in {component} ({duration:.3f}s)")
        
    except GraphRAGException as e:
        duration = time.time() - start_time
        logger.error(f"GraphRAG error in {component}.{operation} after {duration:.3f}s: {e}")
        # Add context data to exception
        e.add_context_data(ctx.context_data)
        raise
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Unexpected error in {component}.{operation} after {duration:.3f}s: {e}")
        # Convert to GraphRAG exception with context
        graph_error = GraphRAGException(
            message=f"Error in {operation}",
            component=component,
            original_error=e
        )
        graph_error.add_context_data(ctx.context_data)
        raise graph_error


def handle_api_errors(func: Callable) -> Callable:
    """
    Decorator for handling API errors and converting them to proper HTTP responses.
    
    Args:
        func: The function to decorate
        
    Returns:
        Decorated function that handles errors
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
                
        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
            
        except GraphRAGException as e:
            # Convert GraphRAG exceptions to HTTP exceptions
            status_code = getattr(e, 'status_code', 500)
            detail = {
                "error": "GraphRAG Error",
                "message": str(e),
                "component": e.component,
                "timestamp": time.time()
            }
            
            if hasattr(e, 'context_data') and e.context_data:
                detail["context"] = e.context_data
                
            raise HTTPException(status_code=status_code, detail=detail)
            
        except Exception as e:
            # Convert other exceptions to 500 errors
            detail = {
                "error": "Internal Server Error",
                "message": str(e),
                "timestamp": time.time()
            }
            raise HTTPException(status_code=500, detail=detail)
    
    return wrapper


# Initialize default error handlers
get_error_handler("api", max_retries=2, timeout=30.0)
get_error_handler("database", max_retries=3, timeout=10.0)
get_error_handler("processing", max_retries=3, timeout=1800.0)
get_error_handler("health_check", max_retries=1, timeout=5.0)