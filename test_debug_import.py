#!/usr/bin/env python3
"""Debug import test to find the issue."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    print("Testing step-by-step import...")
    
    # Test each import individually
    print("1. Testing basic imports...")
    import asyncio
    import functools
    import time
    import traceback
    from contextlib import asynccontextmanager, contextmanager
    from typing import Any, Callable, Dict, List, Optional, Type, Union, TypeVar
    import logging
    print("   ✓ Basic imports successful")
    
    print("2. Testing FastAPI import...")
    try:
        from fastapi import HTTPException
        print("   ✓ FastAPI import successful")
    except ImportError:
        print("   ! FastAPI not available, using fallback")
        class HTTPException(Exception):
            def __init__(self, status_code: int, detail: Any = None):
                self.status_code = status_code
                self.detail = detail
                super().__init__(detail)
    
    print("3. Testing exceptions import...")
    from core.exceptions import (
        GraphRAGException, ErrorContext, RecoveryAction, RecoveryStrategy,
        ErrorSeverity, ErrorCategory, DiagnosticInfo
    )
    print("   ✓ Exceptions import successful")
    
    print("4. Testing logging_config import...")
    from core.logging_config import get_logger, log_error_with_context, log_performance
    print("   ✓ Logging config import successful")
    
    print("5. Testing performance_metrics import...")
    from core.performance_metrics import performance_collector
    print("   ✓ Performance metrics import successful")
    
    print("6. Now testing the ErrorHandler class definition...")
    
    T = TypeVar('T')
    
    class ErrorHandler:
        """Test ErrorHandler class."""
        
        def __init__(self, 
                     component: str,
                     max_retries: int = 3,
                     retry_delay: float = 1.0,
                     exponential_backoff: bool = True,
                     timeout: Optional[float] = None):
            self.component = component
            self.max_retries = max_retries
            self.retry_delay = retry_delay
            self.exponential_backoff = exponential_backoff
            self.timeout = timeout
            
            # Performance tracking
            self.operation_count = 0
            self.total_operation_time = 0.0
            self.error_count = 0
            self.recovery_count = 0
            
            # Logger
            self.logger = get_logger(f"error_handler_{component}")
            
            # Thread safety
            self._lock = asyncio.Lock()
        
        async def get_performance_stats(self) -> Dict[str, Any]:
            """Get performance statistics."""
            async with self._lock:
                if self.operation_count == 0:
                    return {
                        "component": self.component,
                        "operation_count": 0,
                        "error_rate": 0.0,
                        "average_operation_time": 0.0,
                        "recovery_rate": 0.0
                    }
                
                return {
                    "component": self.component,
                    "operation_count": self.operation_count,
                    "error_count": self.error_count,
                    "recovery_count": self.recovery_count,
                    "error_rate": self.error_count / self.operation_count,
                    "average_operation_time": self.total_operation_time / self.operation_count,
                    "recovery_rate": self.recovery_count / max(self.error_count, 1),
                    "total_operation_time": self.total_operation_time
                }
    
    print("   ✓ ErrorHandler class defined successfully")
    
    print("7. Testing global registry...")
    _error_handlers: Dict[str, ErrorHandler] = {}
    
    def get_error_handler(component: str, **kwargs) -> ErrorHandler:
        """Get or create an error handler for a component."""
        if component not in _error_handlers:
            _error_handlers[component] = ErrorHandler(component, **kwargs)
        return _error_handlers[component]
    
    print("   ✓ Global registry and function defined successfully")
    
    print("8. Testing function call...")
    handler = get_error_handler("test")
    print(f"   ✓ Error handler created: {handler}")
    
    print("All tests passed! The issue is likely in the original file.")
    
except Exception as e:
    print(f"Error during debug test: {e}")
    import traceback
    traceback.print_exc()