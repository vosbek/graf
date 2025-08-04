"""
Enhanced Centralized Logging Configuration for GraphRAG System
=============================================================

Provides unified logging across all components with structured output,
performance tracking, error correlation, and comprehensive diagnostics.

Features:
- Structured JSON logging with metadata
- Performance metrics integration
- Error correlation and tracking
- Automatic log rotation and cleanup
- Real-time log aggregation
- Diagnostic information collection

Author: Kiro AI Assistant (Enhanced)
Version: 2.0.0
Last Updated: 2025-08-03
"""
import logging
import logging.handlers
import os
import sys
import json
import time
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
import uuid


class EnhancedGraphRAGFormatter(logging.Formatter):
    """Enhanced formatter for GraphRAG logs with structured output and performance tracking."""
    
    def __init__(self):
        super().__init__()
        self.hostname = os.environ.get('HOSTNAME', 'localhost')
        self.session_id = str(uuid.uuid4())[:8]
        self.format_start_time = time.time()
        
        # Performance tracking
        self.format_count = 0
        self.total_format_time = 0.0
        self._lock = threading.RLock()
    
    def format(self, record):
        format_start = time.perf_counter()
        
        try:
            with self._lock:
                self.format_count += 1
                
                # Create enhanced structured log entry
                log_entry = {
                    'timestamp': datetime.fromtimestamp(record.created).isoformat(),
                    'level': record.levelname,
                    'logger': record.name,
                    'message': record.getMessage(),
                    'module': record.module,
                    'function': record.funcName,
                    'line': record.lineno,
                    'hostname': self.hostname,
                    'process_id': os.getpid(),
                    'thread_id': record.thread,
                    'session_id': self.session_id,
                    'log_id': str(uuid.uuid4())[:8]
                }
                
                # Add performance context
                log_entry['performance'] = {
                    'log_sequence': self.format_count,
                    'uptime_seconds': time.time() - self.format_start_time
                }
                
                # Add exception info if present
                if record.exc_info:
                    log_entry['exception'] = {
                        'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                        'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                        'traceback': self.formatException(record.exc_info)
                    }
                
                # Add extra fields with validation
                if hasattr(record, 'extra_fields') and isinstance(record.extra_fields, dict):
                    # Sanitize extra fields to prevent JSON serialization issues
                    sanitized_extra = {}
                    for key, value in record.extra_fields.items():
                        try:
                            # Test JSON serialization
                            json.dumps(value)
                            sanitized_extra[key] = value
                        except (TypeError, ValueError):
                            # Convert non-serializable values to strings
                            sanitized_extra[key] = str(value)
                    
                    log_entry.update(sanitized_extra)
                
                # Add correlation ID if available in thread local storage
                try:
                    import threading
                    local_data = getattr(threading.current_thread(), 'log_context', {})
                    if 'correlation_id' in local_data:
                        log_entry['correlation_id'] = local_data['correlation_id']
                    if 'request_id' in local_data:
                        log_entry['request_id'] = local_data['request_id']
                except Exception:
                    pass
                
                # Track formatting performance
                format_time = time.perf_counter() - format_start
                self.total_format_time += format_time
                log_entry['performance']['format_time_ms'] = format_time * 1000
                
                return json.dumps(log_entry, ensure_ascii=False, default=str)
                
        except Exception as e:
            # Fallback to simple format if structured logging fails
            fallback_entry = {
                'timestamp': datetime.fromtimestamp(record.created).isoformat(),
                'level': record.levelname,
                'logger': record.name,
                'message': record.getMessage(),
                'format_error': str(e)
            }
            return json.dumps(fallback_entry, ensure_ascii=False)
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get formatter performance statistics."""
        with self._lock:
            if self.format_count == 0:
                return {'format_count': 0, 'average_time_ms': 0.0}
            
            return {
                'format_count': self.format_count,
                'total_time_ms': self.total_format_time * 1000,
                'average_time_ms': (self.total_format_time / self.format_count) * 1000,
                'uptime_seconds': time.time() - self.format_start_time
            }


class EnhancedComponentLogger:
    """Enhanced logger wrapper for specific components with performance tracking."""
    
    def __init__(self, component_name: str):
        self.component_name = component_name
        self.logger = logging.getLogger(f"graphrag.{component_name}")
        
        # Performance tracking
        self.log_counts = defaultdict(int)
        self.error_counts = defaultdict(int)
        self.last_error_time = None
        self.start_time = time.time()
        
        # Rate limiting for error spam prevention
        self.error_rate_limit = 10  # Max errors per minute
        self.error_timestamps = deque(maxlen=self.error_rate_limit)
        
        # Thread safety
        self._lock = threading.RLock()
    
    def with_context(self, **context) -> 'EnhancedContextLogger':
        """Create a context logger with additional fields."""
        return EnhancedContextLogger(self.logger, self.component_name, context)
    
    def _should_log_error(self) -> bool:
        """Check if error should be logged based on rate limiting."""
        current_time = time.time()
        
        with self._lock:
            # Remove old timestamps (older than 1 minute)
            while self.error_timestamps and current_time - self.error_timestamps[0] > 60:
                self.error_timestamps.popleft()
            
            # Check if we're under the rate limit
            if len(self.error_timestamps) < self.error_rate_limit:
                self.error_timestamps.append(current_time)
                return True
            
            return False
    
    def _log_with_performance(self, level: str, message: str, **extra):
        """Log with performance tracking."""
        start_time = time.perf_counter()
        
        with self._lock:
            self.log_counts[level] += 1
            
            # Add performance and component context
            enhanced_extra = {
                'component': self.component_name,
                'log_level': level,
                'component_uptime': time.time() - self.start_time,
                'component_log_count': sum(self.log_counts.values()),
                **extra
            }
            
            # Add error tracking for error logs
            if level == 'error':
                self.error_counts[message[:50]] += 1  # Track by message prefix
                self.last_error_time = time.time()
                enhanced_extra.update({
                    'error_count_for_message': self.error_counts[message[:50]],
                    'total_error_count': sum(self.error_counts.values()),
                    'time_since_last_error': 0.0
                })
            
            # Log the message
            log_method = getattr(self.logger, level)
            log_method(message, extra={'extra_fields': enhanced_extra})
            
            # Track logging performance
            log_time = time.perf_counter() - start_time
            if log_time > 0.001:  # Log slow logging operations (>1ms)
                self.logger.debug(
                    f"Slow logging operation detected",
                    extra={'extra_fields': {
                        'component': self.component_name,
                        'slow_log_time_ms': log_time * 1000,
                        'original_message': message[:100]
                    }}
                )
    
    def info(self, message: str, **extra):
        """Log info message with performance tracking."""
        self._log_with_performance('info', message, **extra)
    
    def warning(self, message: str, **extra):
        """Log warning message with performance tracking."""
        self._log_with_performance('warning', message, **extra)
    
    def error(self, message: str, **extra):
        """Log error message with rate limiting and performance tracking."""
        if self._should_log_error():
            self._log_with_performance('error', message, **extra)
        else:
            # Log rate limit exceeded message (but only once per minute)
            current_time = time.time()
            if not hasattr(self, '_last_rate_limit_log') or current_time - self._last_rate_limit_log > 60:
                self._last_rate_limit_log = current_time
                self._log_with_performance('warning', 
                    f"Error rate limit exceeded for component {self.component_name}. "
                    f"Suppressing similar errors for 1 minute.",
                    suppressed_error_message=message[:100]
                )
    
    def debug(self, message: str, **extra):
        """Log debug message with performance tracking."""
        self._log_with_performance('debug', message, **extra)
    
    def critical(self, message: str, **extra):
        """Log critical message (always logged, bypasses rate limiting)."""
        self._log_with_performance('critical', message, **extra)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get logging statistics for this component."""
        with self._lock:
            return {
                'component': self.component_name,
                'uptime_seconds': time.time() - self.start_time,
                'log_counts': dict(self.log_counts),
                'total_logs': sum(self.log_counts.values()),
                'error_counts': dict(self.error_counts),
                'total_errors': sum(self.error_counts.values()),
                'last_error_time': self.last_error_time,
                'current_error_rate': len(self.error_timestamps)
            }


class EnhancedContextLogger:
    """Enhanced logger with persistent context and correlation tracking."""
    
    def __init__(self, logger: logging.Logger, component_name: str, context: Dict[str, Any]):
        self.logger = logger
        self.component_name = component_name
        self.context = context
        self.context_id = str(uuid.uuid4())[:8]
        self.created_at = time.time()
        
        # Set correlation ID in thread local storage
        try:
            import threading
            thread = threading.current_thread()
            if not hasattr(thread, 'log_context'):
                thread.log_context = {}
            thread.log_context['correlation_id'] = self.context_id
        except Exception:
            pass
    
    def _log_with_context(self, level: str, message: str, **extra):
        """Log with enhanced context information."""
        enhanced_context = {
            **self.context,
            'component': self.component_name,
            'context_id': self.context_id,
            'context_age_seconds': time.time() - self.created_at,
            **extra
        }
        
        log_method = getattr(self.logger, level)
        log_method(message, extra={'extra_fields': enhanced_context})
    
    def info(self, message: str, **extra):
        """Log info message with context."""
        self._log_with_context('info', message, **extra)
    
    def warning(self, message: str, **extra):
        """Log warning message with context."""
        self._log_with_context('warning', message, **extra)
    
    def error(self, message: str, **extra):
        """Log error message with context."""
        self._log_with_context('error', message, **extra)
    
    def debug(self, message: str, **extra):
        """Log debug message with context."""
        self._log_with_context('debug', message, **extra)
    
    def critical(self, message: str, **extra):
        """Log critical message with context."""
        self._log_with_context('critical', message, **extra)


def setup_logging(
    log_level: str = "INFO",
    log_dir: str = "logs",
    component: str = "main",
    enable_console: bool = True,
    enable_file: bool = True,
    max_file_size: int = 50 * 1024 * 1024,  # 50MB
    backup_count: int = 5,
    enable_performance_tracking: bool = True
) -> EnhancedComponentLogger:
    """
    Setup enhanced centralized logging for GraphRAG components.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_dir: Directory for log files
        component: Component name for log identification
        enable_console: Enable console output
        enable_file: Enable file output
        max_file_size: Maximum file size before rotation
        backup_count: Number of backup files to keep
        enable_performance_tracking: Enable performance metrics collection
    
    Returns:
        EnhancedComponentLogger instance
    """
    
    # Create logs directory
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger("graphrag")
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Create enhanced formatter
    formatter = EnhancedGraphRAGFormatter()
    
    # Console handler
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper()))
        
        # Use simple format for console
        console_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)8s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    
    # File handlers
    if enable_file:
        # Main log file (rotating)
        main_log_file = log_path / f"{component}-main.log"
        main_handler = logging.handlers.RotatingFileHandler(
            main_log_file,
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        main_handler.setLevel(getattr(logging, log_level.upper()))
        main_handler.setFormatter(formatter)
        root_logger.addHandler(main_handler)
        
        # Error log file (errors only)
        error_log_file = log_path / f"{component}-errors.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=max_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        root_logger.addHandler(error_handler)
        
        # Debug log file (all levels, larger files)
        if log_level.upper() == "DEBUG":
            debug_log_file = log_path / f"{component}-debug.log"
            debug_handler = logging.handlers.RotatingFileHandler(
                debug_log_file,
                maxBytes=max_file_size * 2,  # Larger debug files
                backupCount=backup_count,
                encoding='utf-8'
            )
            debug_handler.setLevel(logging.DEBUG)
            debug_handler.setFormatter(formatter)
            root_logger.addHandler(debug_handler)
    
    # Suppress some noisy loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    # Create enhanced component logger
    component_logger = EnhancedComponentLogger(component)
    
    # Register with global registry for monitoring
    if enable_performance_tracking:
        _register_component_logger(component, component_logger)
    
    return component_logger


def get_logger(component: str) -> EnhancedComponentLogger:
    """Get an enhanced logger for a specific component."""
    return EnhancedComponentLogger(component)


class EnhancedLogAggregator:
    """Enhanced log aggregator with performance monitoring and error correlation."""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        
        # Performance tracking
        self.aggregation_stats = {
            'total_logs_processed': 0,
            'total_errors_found': 0,
            'last_aggregation_time': 0,
            'aggregation_duration_ms': 0
        }
        
        # Error correlation
        self.error_patterns = defaultdict(int)
        self.error_correlations = defaultdict(list)
        
        # Thread safety
        self._lock = threading.RLock()
    
    def get_recent_logs(self, component: Optional[str] = None, limit: int = 100) -> list:
        """Get recent log entries, optionally filtered by component."""
        logs = []
        
        # Find log files
        pattern = f"{component}-main.log" if component else "*-main.log"
        log_files = list(self.log_dir.glob(pattern))
        
        for log_file in log_files:
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    for line in reversed(lines[-limit:]):
                        try:
                            log_entry = json.loads(line.strip())
                            logs.append(log_entry)
                        except json.JSONDecodeError:
                            # Skip non-JSON lines
                            continue
            except Exception as e:
                print(f"Error reading log file {log_file}: {e}")
        
        # Sort by timestamp
        logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return logs[:limit]
    
    def get_error_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get summary of errors in the last N hours."""
        from datetime import datetime, timedelta
        
        cutoff = datetime.now() - timedelta(hours=hours)
        error_files = list(self.log_dir.glob("*-errors.log"))
        
        errors = []
        error_counts = {}
        
        for error_file in error_files:
            component = error_file.stem.replace('-errors', '')
            try:
                with open(error_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            log_entry = json.loads(line.strip())
                            entry_time = datetime.fromisoformat(log_entry['timestamp'])
                            
                            if entry_time > cutoff:
                                errors.append(log_entry)
                                error_type = log_entry.get('message', 'Unknown Error')
                                error_counts[error_type] = error_counts.get(error_type, 0) + 1
                        except (json.JSONDecodeError, ValueError):
                            continue
            except Exception as e:
                print(f"Error reading error log {error_file}: {e}")
        
        return {
            'total_errors': len(errors),
            'error_counts': error_counts,
            'recent_errors': errors[-10:],  # Last 10 errors
            'time_period_hours': hours
        }
    
    def cleanup_old_logs(self, days: int = 7):
        """Clean up log files older than specified days."""
        from datetime import datetime, timedelta
        
        cutoff = datetime.now() - timedelta(days=days)
        
        for log_file in self.log_dir.glob("*.log*"):
            try:
                file_time = datetime.fromtimestamp(log_file.stat().st_mtime)
                if file_time < cutoff:
                    log_file.unlink()
                    print(f"Cleaned up old log file: {log_file}")
            except Exception as e:
                print(f"Error cleaning up {log_file}: {e}")


# Global component logger registry for monitoring
_component_loggers: Dict[str, EnhancedComponentLogger] = {}
_registry_lock = threading.RLock()

def _register_component_logger(component: str, logger: EnhancedComponentLogger):
    """Register a component logger for monitoring."""
    with _registry_lock:
        _component_loggers[component] = logger

def get_all_component_stats() -> Dict[str, Any]:
    """Get statistics for all registered component loggers."""
    with _registry_lock:
        return {
            component: logger.get_stats() 
            for component, logger in _component_loggers.items()
        }

def get_logging_performance_summary() -> Dict[str, Any]:
    """Get overall logging performance summary."""
    with _registry_lock:
        total_logs = 0
        total_errors = 0
        components_count = len(_component_loggers)
        
        for logger in _component_loggers.values():
            stats = logger.get_stats()
            total_logs += stats['total_logs']
            total_errors += stats['total_errors']
        
        return {
            'total_components': components_count,
            'total_logs': total_logs,
            'total_errors': total_errors,
            'error_rate': total_errors / max(total_logs, 1),
            'components': list(_component_loggers.keys())
        }

# Global enhanced log aggregator instance
log_aggregator = EnhancedLogAggregator()


def log_performance(component: str, operation: str, duration: float, **metadata):
    """Log performance metrics with enhanced tracking."""
    logger = get_logger(component)
    
    # Determine performance level
    performance_level = "excellent"
    if duration > 10.0:
        performance_level = "critical"
    elif duration > 5.0:
        performance_level = "poor"
    elif duration > 1.0:
        performance_level = "acceptable"
    elif duration > 0.1:
        performance_level = "good"
    
    logger.info(
        f"Performance: {operation} completed in {duration:.3f}s",
        operation=operation,
        duration_ms=duration * 1000,
        performance_level=performance_level,
        performance_category="timing",
        **metadata
    )
    
    # Record in performance collector if available
    try:
        from .performance_metrics import performance_collector
        performance_collector.record_timing(f"{component}_{operation}", duration, True)
    except ImportError:
        pass


def log_api_request(method: str, path: str, status_code: int, duration: float, **metadata):
    """Log API request metrics with enhanced tracking."""
    logger = get_logger("api")
    
    # Determine request status
    request_status = "success" if 200 <= status_code < 400 else "error"
    performance_level = "excellent"
    
    if duration > 30.0:
        performance_level = "critical"
    elif duration > 10.0:
        performance_level = "poor"
    elif duration > 5.0:
        performance_level = "acceptable"
    elif duration > 1.0:
        performance_level = "good"
    
    log_method = logger.info if request_status == "success" else logger.warning
    log_method(
        f"API Request: {method} {path} -> {status_code} ({duration:.3f}s)",
        method=method,
        path=path,
        status_code=status_code,
        duration_ms=duration * 1000,
        request_status=request_status,
        performance_level=performance_level,
        performance_category="api_request",
        **metadata
    )
    
    # Record in performance collector if available
    try:
        from .performance_metrics import performance_collector
        performance_collector.record_timing(
            f"api_request_{method.lower()}",
            duration,
            request_status == "success",
            {"path": path, "status_code": str(status_code)}
        )
    except ImportError:
        pass


def log_database_operation(database: str, operation: str, duration: float, **metadata):
    """Log database operation metrics with enhanced tracking."""
    logger = get_logger("database")
    
    # Determine performance level for database operations
    performance_level = "excellent"
    if duration > 5.0:
        performance_level = "critical"
    elif duration > 2.0:
        performance_level = "poor"
    elif duration > 1.0:
        performance_level = "acceptable"
    elif duration > 0.5:
        performance_level = "good"
    
    logger.info(
        f"Database: {database} {operation} completed in {duration:.3f}s",
        database=database,
        operation=operation,
        duration_ms=duration * 1000,
        performance_level=performance_level,
        performance_category="database",
        **metadata
    )
    
    # Record in performance collector if available
    try:
        from .performance_metrics import performance_collector
        performance_collector.record_timing(
            f"db_{database}_{operation}",
            duration,
            True,
            {"database": database, "operation": operation}
        )
    except ImportError:
        pass


def log_error_with_context(component: str, error: Exception, context: Optional[Dict[str, Any]] = None):
    """Log error with enhanced context and correlation."""
    logger = get_logger(component)
    
    error_context = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        'component': component,
        **(context or {})
    }
    
    # Check if this is a GraphRAG structured exception
    if hasattr(error, 'error_id'):
        error_context.update({
            'error_id': error.error_id,
            'error_code': error.error_code,
            'severity': error.severity,
            'category': error.category,
            'recoverable': error.recoverable
        })
    
    logger.error(
        f"Error in {component}: {str(error)}",
        **error_context
    )


def log_validation_result(component: str, validation_name: str, is_valid: bool, 
                         duration: float, details: Optional[Dict[str, Any]] = None):
    """Log validation results with performance tracking."""
    logger = get_logger(component)
    
    status = "passed" if is_valid else "failed"
    log_method = logger.info if is_valid else logger.warning
    
    log_method(
        f"Validation: {validation_name} {status} in {duration:.3f}s",
        validation_name=validation_name,
        validation_status=status,
        duration_ms=duration * 1000,
        performance_category="validation",
        **(details or {})
    )
    
    # Record in performance collector if available
    try:
        from .performance_metrics import performance_collector
        performance_collector.record_timing(
            f"validation_{validation_name}",
            duration,
            is_valid,
            {"validation_name": validation_name}
        )
    except ImportError:
        pass