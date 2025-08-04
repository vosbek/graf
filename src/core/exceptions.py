"""
Structured Exception System for GraphRAG
========================================

Comprehensive exception hierarchy with detailed error information,
recovery suggestions, and diagnostic data collection.

Features:
- Structured exception hierarchy
- Error categorization and severity levels
- Recovery suggestions and troubleshooting guidance
- Performance impact tracking
- Diagnostic data collection
- Error correlation and tracking

Author: Kiro AI Assistant
Version: 1.0.0
Last Updated: 2025-08-03
"""

import time
import traceback
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Union
import logging


class ErrorSeverity(str, Enum):
    """Error severity levels for categorization."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(str, Enum):
    """Error categories for classification."""
    CONFIGURATION = "configuration"
    NETWORK = "network"
    DATABASE = "database"
    PROCESSING = "processing"
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    RESOURCE = "resource"
    TIMEOUT = "timeout"
    DEPENDENCY = "dependency"
    SYSTEM = "system"


class RecoveryStrategy(str, Enum):
    """Recovery strategies for different error types."""
    RETRY = "retry"
    FALLBACK = "fallback"
    RESTART = "restart"
    MANUAL = "manual"
    IGNORE = "ignore"
    ESCALATE = "escalate"


@dataclass
class ErrorContext:
    """Context information for errors."""
    component: str
    operation: str
    start_time: float = field(default_factory=time.time)
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    repository_name: Optional[str] = None
    file_path: Optional[str] = None
    context_data: Dict[str, Any] = field(default_factory=dict)
    additional_data: Dict[str, Any] = field(default_factory=dict)
    
    def add_diagnostic_data(self, key: str, value: Any) -> None:
        """Add diagnostic data to the context."""
        self.context_data[key] = value
    
    def add_context_data(self, data: Dict[str, Any]) -> None:
        """Add multiple context data items."""
        self.context_data.update(data)
    
    def get_duration(self) -> float:
        """Get the duration since context creation."""
        return time.time() - self.start_time


@dataclass
class RecoveryAction:
    """Recovery action information."""
    strategy: RecoveryStrategy
    description: str
    automated: bool = False
    estimated_time: Optional[float] = None
    prerequisites: List[str] = field(default_factory=list)
    success_probability: float = 0.5


@dataclass
class DiagnosticInfo:
    """Diagnostic information for troubleshooting."""
    system_state: Dict[str, Any] = field(default_factory=dict)
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    resource_usage: Dict[str, Any] = field(default_factory=dict)
    related_errors: List[str] = field(default_factory=list)
    troubleshooting_steps: List[str] = field(default_factory=list)


class GraphRAGException(Exception):
    """
    Base exception class for GraphRAG system.
    
    Provides structured error information with diagnostic data,
    recovery suggestions, and performance impact tracking.
    """
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        context: Optional[ErrorContext] = None,
        cause: Optional[Exception] = None,
        recoverable: bool = True,
        recovery_actions: Optional[List[RecoveryAction]] = None,
        diagnostic_info: Optional[DiagnosticInfo] = None,
        component: Optional[str] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(message)
        
        # Core error information
        self.error_id = str(uuid.uuid4())
        self.message = message
        self.error_code = error_code or self._generate_error_code()
        self.severity = severity
        self.category = category
        self.timestamp = time.time()
        
        # Context and causation
        self.component = component or (context.component if context else "unknown")
        self.context = context or ErrorContext(component=self.component, operation="unknown")
        self.cause = cause
        self.original_error = original_error or cause
        self.recoverable = recoverable
        
        # Recovery and diagnostic information
        self.recovery_actions = recovery_actions or []
        self.diagnostic_info = diagnostic_info or DiagnosticInfo()
        
        # Performance tracking
        self.performance_impact = self._calculate_performance_impact()
        
        # Stack trace capture
        self.stack_trace = traceback.format_exc()
        
        # Log the error
        self._log_error()
    
    def _generate_error_code(self) -> str:
        """Generate a unique error code based on category and timestamp."""
        timestamp_suffix = str(int(self.timestamp))[-6:]
        return f"{self.category.upper()}_{timestamp_suffix}"
    
    def _calculate_performance_impact(self) -> float:
        """Calculate estimated performance impact (0.0 to 1.0)."""
        severity_impact = {
            ErrorSeverity.LOW: 0.1,
            ErrorSeverity.MEDIUM: 0.3,
            ErrorSeverity.HIGH: 0.7,
            ErrorSeverity.CRITICAL: 1.0
        }
        return severity_impact.get(self.severity, 0.5)
    
    def _log_error(self):
        """Log the error with structured information."""
        logger = logging.getLogger(f"graphrag.errors.{self.category}")
        
        log_data = {
            "error_id": self.error_id,
            "error_code": self.error_code,
            "severity": self.severity,
            "category": self.category,
            "component": self.context.component,
            "operation": self.context.operation,
            "recoverable": self.recoverable,
            "performance_impact": self.performance_impact,
            "recovery_actions_count": len(self.recovery_actions),
            "has_diagnostic_info": bool(self.diagnostic_info.system_state)
        }
        
        if self.context.repository_name:
            log_data["repository_name"] = self.context.repository_name
        if self.context.file_path:
            log_data["file_path"] = self.context.file_path
        
        logger.error(self.message, extra={"extra_fields": log_data})
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for serialization."""
        return {
            "error_id": self.error_id,
            "error_code": self.error_code,
            "message": self.message,
            "severity": self.severity,
            "category": self.category,
            "timestamp": self.timestamp,
            "recoverable": self.recoverable,
            "performance_impact": self.performance_impact,
            "context": {
                "component": self.context.component,
                "operation": self.context.operation,
                "repository_name": self.context.repository_name,
                "file_path": self.context.file_path,
                "additional_data": self.context.additional_data
            },
            "recovery_actions": [
                {
                    "strategy": action.strategy,
                    "description": action.description,
                    "automated": action.automated,
                    "estimated_time": action.estimated_time,
                    "success_probability": action.success_probability
                }
                for action in self.recovery_actions
            ],
            "diagnostic_info": {
                "system_state": self.diagnostic_info.system_state,
                "performance_metrics": self.diagnostic_info.performance_metrics,
                "troubleshooting_steps": self.diagnostic_info.troubleshooting_steps
            }
        }
    
    def add_recovery_action(self, action: RecoveryAction):
        """Add a recovery action to the exception."""
        self.recovery_actions.append(action)
    
    def add_diagnostic_data(self, key: str, value: Any):
        """Add diagnostic data to the exception."""
        self.diagnostic_info.system_state[key] = value
    
    def add_troubleshooting_step(self, step: str):
        """Add a troubleshooting step."""
        self.diagnostic_info.troubleshooting_steps.append(step)
    
    def add_context_data(self, data: Dict[str, Any]):
        """Add context data to the exception."""
        if hasattr(self.context, 'context_data'):
            self.context.context_data.update(data)
        else:
            self.context.additional_data.update(data)


class ConfigurationError(GraphRAGException):
    """Configuration-related errors."""
    
    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        kwargs.setdefault("category", ErrorCategory.CONFIGURATION)
        kwargs.setdefault("severity", ErrorSeverity.HIGH)
        
        # Add configuration-specific recovery actions
        recovery_actions = kwargs.get("recovery_actions", [])
        recovery_actions.extend([
            RecoveryAction(
                strategy=RecoveryStrategy.MANUAL,
                description="Check configuration file and environment variables",
                automated=False,
                success_probability=0.9
            ),
            RecoveryAction(
                strategy=RecoveryStrategy.RESTART,
                description="Restart service after configuration fix",
                automated=False,
                success_probability=0.8
            )
        ])
        kwargs["recovery_actions"] = recovery_actions
        
        # Add diagnostic information
        diagnostic_info = kwargs.get("diagnostic_info", DiagnosticInfo())
        if config_key:
            diagnostic_info.system_state["config_key"] = config_key
        diagnostic_info.troubleshooting_steps.extend([
            f"Verify {config_key} configuration" if config_key else "Check configuration files",
            "Validate environment variables",
            "Check file permissions",
            "Verify configuration syntax"
        ])
        kwargs["diagnostic_info"] = diagnostic_info
        
        super().__init__(message, **kwargs)


class DatabaseError(GraphRAGException):
    """Database-related errors."""
    
    def __init__(self, message: str, database_type: Optional[str] = None, **kwargs):
        kwargs.setdefault("category", ErrorCategory.DATABASE)
        kwargs.setdefault("severity", ErrorSeverity.HIGH)
        
        # Add database-specific recovery actions
        recovery_actions = kwargs.get("recovery_actions", [])
        recovery_actions.extend([
            RecoveryAction(
                strategy=RecoveryStrategy.RETRY,
                description="Retry database operation with exponential backoff",
                automated=True,
                estimated_time=5.0,
                success_probability=0.7
            ),
            RecoveryAction(
                strategy=RecoveryStrategy.RESTART,
                description="Restart database connection",
                automated=True,
                estimated_time=10.0,
                success_probability=0.8
            )
        ])
        kwargs["recovery_actions"] = recovery_actions
        
        # Add diagnostic information
        diagnostic_info = kwargs.get("diagnostic_info", DiagnosticInfo())
        if database_type:
            diagnostic_info.system_state["database_type"] = database_type
        diagnostic_info.troubleshooting_steps.extend([
            "Check database service status",
            "Verify connection parameters",
            "Check network connectivity",
            "Validate credentials",
            "Monitor database logs"
        ])
        kwargs["diagnostic_info"] = diagnostic_info
        
        super().__init__(message, **kwargs)


class ProcessingError(GraphRAGException):
    """Processing-related errors."""
    
    def __init__(self, message: str, processing_stage: Optional[str] = None, **kwargs):
        kwargs.setdefault("category", ErrorCategory.PROCESSING)
        kwargs.setdefault("severity", ErrorSeverity.MEDIUM)
        
        # Add processing-specific recovery actions
        recovery_actions = kwargs.get("recovery_actions", [])
        recovery_actions.extend([
            RecoveryAction(
                strategy=RecoveryStrategy.RETRY,
                description="Retry processing with different parameters",
                automated=True,
                estimated_time=30.0,
                success_probability=0.6
            ),
            RecoveryAction(
                strategy=RecoveryStrategy.FALLBACK,
                description="Use fallback processing method",
                automated=True,
                estimated_time=60.0,
                success_probability=0.8
            )
        ])
        kwargs["recovery_actions"] = recovery_actions
        
        # Add diagnostic information
        diagnostic_info = kwargs.get("diagnostic_info", DiagnosticInfo())
        if processing_stage:
            diagnostic_info.system_state["processing_stage"] = processing_stage
        diagnostic_info.troubleshooting_steps.extend([
            "Check input data validity",
            "Verify processing parameters",
            "Monitor system resources",
            "Check for data corruption",
            "Review processing logs"
        ])
        kwargs["diagnostic_info"] = diagnostic_info
        
        super().__init__(message, **kwargs)


class ValidationError(GraphRAGException):
    """Validation-related errors."""
    
    def __init__(self, message: str, validation_type: Optional[str] = None, **kwargs):
        kwargs.setdefault("category", ErrorCategory.VALIDATION)
        kwargs.setdefault("severity", ErrorSeverity.MEDIUM)
        kwargs.setdefault("recoverable", False)  # Validation errors usually require manual fix
        
        # Add validation-specific recovery actions
        recovery_actions = kwargs.get("recovery_actions", [])
        recovery_actions.extend([
            RecoveryAction(
                strategy=RecoveryStrategy.MANUAL,
                description="Fix validation issues manually",
                automated=False,
                success_probability=0.9
            )
        ])
        kwargs["recovery_actions"] = recovery_actions
        
        # Add diagnostic information
        diagnostic_info = kwargs.get("diagnostic_info", DiagnosticInfo())
        if validation_type:
            diagnostic_info.system_state["validation_type"] = validation_type
        diagnostic_info.troubleshooting_steps.extend([
            "Review validation rules",
            "Check input data format",
            "Verify data constraints",
            "Validate business rules"
        ])
        kwargs["diagnostic_info"] = diagnostic_info
        
        super().__init__(message, **kwargs)


class NetworkError(GraphRAGException):
    """Network-related errors."""
    
    def __init__(self, message: str, endpoint: Optional[str] = None, **kwargs):
        kwargs.setdefault("category", ErrorCategory.NETWORK)
        kwargs.setdefault("severity", ErrorSeverity.HIGH)
        
        # Add network-specific recovery actions
        recovery_actions = kwargs.get("recovery_actions", [])
        recovery_actions.extend([
            RecoveryAction(
                strategy=RecoveryStrategy.RETRY,
                description="Retry network operation with exponential backoff",
                automated=True,
                estimated_time=10.0,
                success_probability=0.7
            ),
            RecoveryAction(
                strategy=RecoveryStrategy.FALLBACK,
                description="Use alternative endpoint or method",
                automated=True,
                estimated_time=5.0,
                success_probability=0.5
            )
        ])
        kwargs["recovery_actions"] = recovery_actions
        
        # Add diagnostic information
        diagnostic_info = kwargs.get("diagnostic_info", DiagnosticInfo())
        if endpoint:
            diagnostic_info.system_state["endpoint"] = endpoint
        diagnostic_info.troubleshooting_steps.extend([
            "Check network connectivity",
            "Verify endpoint availability",
            "Check firewall settings",
            "Validate DNS resolution",
            "Monitor network latency"
        ])
        kwargs["diagnostic_info"] = diagnostic_info
        
        super().__init__(message, **kwargs)


class ResourceError(GraphRAGException):
    """Resource-related errors (memory, disk, CPU)."""
    
    def __init__(self, message: str, resource_type: Optional[str] = None, **kwargs):
        kwargs.setdefault("category", ErrorCategory.RESOURCE)
        kwargs.setdefault("severity", ErrorSeverity.HIGH)
        
        # Add resource-specific recovery actions
        recovery_actions = kwargs.get("recovery_actions", [])
        recovery_actions.extend([
            RecoveryAction(
                strategy=RecoveryStrategy.FALLBACK,
                description="Reduce resource usage and retry",
                automated=True,
                estimated_time=15.0,
                success_probability=0.6
            ),
            RecoveryAction(
                strategy=RecoveryStrategy.MANUAL,
                description="Free up system resources",
                automated=False,
                success_probability=0.8
            )
        ])
        kwargs["recovery_actions"] = recovery_actions
        
        # Add diagnostic information
        diagnostic_info = kwargs.get("diagnostic_info", DiagnosticInfo())
        if resource_type:
            diagnostic_info.system_state["resource_type"] = resource_type
        diagnostic_info.troubleshooting_steps.extend([
            "Check system resource usage",
            "Monitor memory consumption",
            "Check disk space availability",
            "Review CPU usage patterns",
            "Identify resource-intensive processes"
        ])
        kwargs["diagnostic_info"] = diagnostic_info
        
        super().__init__(message, **kwargs)


class TimeoutError(GraphRAGException):
    """Timeout-related errors."""
    
    def __init__(self, message: str, timeout_duration: Optional[float] = None, **kwargs):
        kwargs.setdefault("category", ErrorCategory.TIMEOUT)
        kwargs.setdefault("severity", ErrorSeverity.MEDIUM)
        
        # Add timeout-specific recovery actions
        recovery_actions = kwargs.get("recovery_actions", [])
        recovery_actions.extend([
            RecoveryAction(
                strategy=RecoveryStrategy.RETRY,
                description="Retry with increased timeout",
                automated=True,
                estimated_time=timeout_duration * 2 if timeout_duration else 60.0,
                success_probability=0.7
            ),
            RecoveryAction(
                strategy=RecoveryStrategy.FALLBACK,
                description="Use faster alternative method",
                automated=True,
                estimated_time=30.0,
                success_probability=0.5
            )
        ])
        kwargs["recovery_actions"] = recovery_actions
        
        # Add diagnostic information
        diagnostic_info = kwargs.get("diagnostic_info", DiagnosticInfo())
        if timeout_duration:
            diagnostic_info.system_state["timeout_duration"] = timeout_duration
        diagnostic_info.troubleshooting_steps.extend([
            "Check operation complexity",
            "Monitor system performance",
            "Verify network latency",
            "Review timeout configuration",
            "Optimize operation parameters"
        ])
        kwargs["diagnostic_info"] = diagnostic_info
        
        super().__init__(message, **kwargs)


# Exception factory functions for common scenarios
def create_database_connection_error(database_type: str, connection_string: str, cause: Exception) -> DatabaseError:
    """Create a standardized database connection error."""
    context = ErrorContext(
        component="database",
        operation="connect",
        additional_data={"connection_string": connection_string}
    )
    
    diagnostic_info = DiagnosticInfo()
    diagnostic_info.system_state.update({
        "database_type": database_type,
        "connection_string": connection_string,
        "cause_type": type(cause).__name__
    })
    
    return DatabaseError(
        message=f"Failed to connect to {database_type} database: {str(cause)}",
        database_type=database_type,
        context=context,
        cause=cause,
        diagnostic_info=diagnostic_info
    )


def create_processing_timeout_error(operation: str, timeout: float, context: ErrorContext) -> TimeoutError:
    """Create a standardized processing timeout error."""
    diagnostic_info = DiagnosticInfo()
    diagnostic_info.system_state.update({
        "operation": operation,
        "timeout_seconds": timeout
    })
    
    return TimeoutError(
        message=f"Operation '{operation}' timed out after {timeout} seconds",
        timeout_duration=timeout,
        context=context,
        diagnostic_info=diagnostic_info
    )


def create_validation_error(validation_type: str, details: str, context: ErrorContext) -> ValidationError:
    """Create a standardized validation error."""
    diagnostic_info = DiagnosticInfo()
    diagnostic_info.system_state.update({
        "validation_type": validation_type,
        "validation_details": details
    })
    
    return ValidationError(
        message=f"Validation failed for {validation_type}: {details}",
        validation_type=validation_type,
        context=context,
        diagnostic_info=diagnostic_info
    )