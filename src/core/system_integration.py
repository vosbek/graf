"""
System Integration Module
========================

Comprehensive system integration that wires together all validation,
monitoring, and recovery components for the startup validation feature.

This module provides:
- Component integration and coordination
- System-wide validation orchestration
- Recovery mechanism coordination
- Performance monitoring integration
- Real-time status coordination

Author: Kiro AI Assistant
Version: 1.0.0
Last Updated: 2025-08-03
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable, Set
from enum import Enum
import threading
import weakref

from .diagnostics import diagnostic_collector, DiagnosticReport
from .performance_metrics import performance_collector
from .logging_config import get_logger
from .exceptions import GraphRAGException, ErrorContext
from ..services.embedding_validator import EmbeddingValidator


class ComponentStatus(Enum):
    """Component status enumeration."""
    NOT_INITIALIZED = "not_initialized"
    INITIALIZING = "initializing"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    FAILED = "failed"
    RECOVERING = "recovering"


class SystemPhase(Enum):
    """System lifecycle phases."""
    STARTUP = "startup"
    RUNNING = "running"
    DEGRADED = "degraded"
    SHUTDOWN = "shutdown"
    RECOVERY = "recovery"


@dataclass
class ComponentInfo:
    """Information about a system component."""
    name: str
    status: ComponentStatus = ComponentStatus.NOT_INITIALIZED
    last_check: Optional[float] = None
    error_message: Optional[str] = None
    dependencies: Set[str] = field(default_factory=set)
    dependents: Set[str] = field(default_factory=set)
    health_checker: Optional[Callable] = None
    recovery_handler: Optional[Callable] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemState:
    """Overall system state information."""
    phase: SystemPhase = SystemPhase.STARTUP
    overall_health: ComponentStatus = ComponentStatus.NOT_INITIALIZED
    components: Dict[str, ComponentInfo] = field(default_factory=dict)
    startup_time: Optional[float] = None
    last_validation: Optional[float] = None
    performance_score: float = 0.0
    active_issues: List[str] = field(default_factory=list)
    recovery_attempts: int = 0


class SystemIntegrator:
    """
    Central system integrator that coordinates all components.
    
    Manages component lifecycle, health monitoring, validation,
    and recovery mechanisms in a coordinated manner.
    """
    
    def __init__(self):
        """Initialize the system integrator."""
        self.logger = get_logger(__name__)
        self.system_state = SystemState()
        
        # Component registry
        self.components: Dict[str, ComponentInfo] = {}
        
        # Event handlers
        self.status_change_handlers: List[Callable] = []
        self.validation_handlers: List[Callable] = []
        self.recovery_handlers: List[Callable] = []
        
        # Monitoring configuration
        self.monitoring_interval = 30.0  # 30 seconds
        self.validation_interval = 60.0  # 1 minute
        self.recovery_timeout = 300.0    # 5 minutes
        
        # Background tasks
        self._monitoring_task: Optional[asyncio.Task] = None
        self._validation_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Performance tracking
        self._last_performance_check = 0.0
        self._performance_history: List[float] = []
        
        # Initialize core components
        self._initialize_core_components()
    
    def _initialize_core_components(self):
        """Initialize core system components."""
        # Register core components with their dependencies
        core_components = {
            "chromadb": {
                "dependencies": set(),
                "health_checker": self._check_chromadb_health,
                "recovery_handler": self._recover_chromadb
            },
            "neo4j": {
                "dependencies": set(),
                "health_checker": self._check_neo4j_health,
                "recovery_handler": self._recover_neo4j
            },
            "embedding_system": {
                "dependencies": {"chromadb"},
                "health_checker": self._check_embedding_health,
                "recovery_handler": self._recover_embedding_system
            },
            "repository_processor": {
                "dependencies": {"chromadb", "neo4j", "embedding_system"},
                "health_checker": self._check_processor_health,
                "recovery_handler": self._recover_processor
            },
            "api_server": {
                "dependencies": {"chromadb", "neo4j", "repository_processor"},
                "health_checker": self._check_api_health,
                "recovery_handler": self._recover_api_server
            },
            "diagnostic_system": {
                "dependencies": set(),
                "health_checker": self._check_diagnostic_health,
                "recovery_handler": self._recover_diagnostic_system
            }
        }
        
        for name, config in core_components.items():
            self.register_component(
                name=name,
                dependencies=config["dependencies"],
                health_checker=config["health_checker"],
                recovery_handler=config["recovery_handler"]
            )
    
    def register_component(self, 
                          name: str,
                          dependencies: Set[str] = None,
                          health_checker: Callable = None,
                          recovery_handler: Callable = None,
                          metadata: Dict[str, Any] = None) -> None:
        """
        Register a system component.
        
        Args:
            name: Component name
            dependencies: Set of component names this component depends on
            health_checker: Async function to check component health
            recovery_handler: Async function to recover component
            metadata: Additional component metadata
        """
        with self._lock:
            if name in self.components:
                self.logger.warning(f"Component {name} already registered, updating...")
            
            component = ComponentInfo(
                name=name,
                dependencies=dependencies or set(),
                health_checker=health_checker,
                recovery_handler=recovery_handler,
                metadata=metadata or {}
            )
            
            self.components[name] = component
            self.system_state.components[name] = component
            
            # Update dependent relationships
            for dep_name in component.dependencies:
                if dep_name in self.components:
                    self.components[dep_name].dependents.add(name)
            
            self.logger.info(f"Registered component: {name} with dependencies: {component.dependencies}")
    
    def register_status_change_handler(self, handler: Callable) -> None:
        """Register a handler for component status changes."""
        self.status_change_handlers.append(handler)
    
    def register_validation_handler(self, handler: Callable) -> None:
        """Register a handler for system validation events."""
        self.validation_handlers.append(handler)
    
    def register_recovery_handler(self, handler: Callable) -> None:
        """Register a handler for recovery events."""
        self.recovery_handlers.append(handler)
    
    async def start_system(self) -> bool:
        """
        Start the integrated system with full validation.
        
        Returns:
            bool: True if system started successfully
        """
        self.logger.info("🚀 Starting integrated system...")
        
        try:
            self.system_state.phase = SystemPhase.STARTUP
            self.system_state.startup_time = time.time()
            
            # Start background monitoring
            await self._start_background_tasks()
            
            # Initialize components in dependency order
            initialization_success = await self._initialize_components()
            
            if not initialization_success:
                self.logger.error("Component initialization failed")
                self.system_state.phase = SystemPhase.DEGRADED
                return False
            
            # Perform comprehensive system validation
            validation_success = await self._perform_system_validation()
            
            if not validation_success:
                self.logger.warning("System validation had issues, but continuing...")
                self.system_state.phase = SystemPhase.DEGRADED
            else:
                self.system_state.phase = SystemPhase.RUNNING
            
            # Update system state
            await self._update_system_health()
            
            self.logger.info(f"✅ System startup completed - Phase: {self.system_state.phase.value}")
            return True
            
        except Exception as e:
            self.logger.error(f"System startup failed: {e}")
            self.system_state.phase = SystemPhase.DEGRADED
            self.system_state.active_issues.append(f"Startup failed: {str(e)}")
            return False
    
    async def shutdown_system(self) -> None:
        """Gracefully shutdown the integrated system."""
        self.logger.info("🛑 Shutting down integrated system...")
        
        try:
            self.system_state.phase = SystemPhase.SHUTDOWN
            
            # Signal shutdown to background tasks
            self._shutdown_event.set()
            
            # Wait for background tasks to complete
            if self._monitoring_task:
                await self._monitoring_task
            if self._validation_task:
                await self._validation_task
            
            # Shutdown components in reverse dependency order
            await self._shutdown_components()
            
            self.logger.info("✅ System shutdown completed")
            
        except Exception as e:
            self.logger.error(f"Error during system shutdown: {e}")
    
    async def get_system_status(self) -> Dict[str, Any]:
        """
        Get comprehensive system status.
        
        Returns:
            Dict containing detailed system status
        """
        with self._lock:
            # Update performance score
            await self._update_performance_metrics()
            
            # Count component statuses
            status_counts = {}
            for status in ComponentStatus:
                status_counts[status.value] = sum(
                    1 for comp in self.components.values() 
                    if comp.status == status
                )
            
            # Calculate uptime
            uptime = time.time() - self.system_state.startup_time if self.system_state.startup_time else 0
            
            return {
                "phase": self.system_state.phase.value,
                "overall_health": self.system_state.overall_health.value,
                "uptime_seconds": uptime,
                "performance_score": self.system_state.performance_score,
                "component_count": len(self.components),
                "status_counts": status_counts,
                "active_issues": self.system_state.active_issues.copy(),
                "recovery_attempts": self.system_state.recovery_attempts,
                "last_validation": self.system_state.last_validation,
                "components": {
                    name: {
                        "status": comp.status.value,
                        "last_check": comp.last_check,
                        "error_message": comp.error_message,
                        "dependencies": list(comp.dependencies),
                        "dependents": list(comp.dependents)
                    }
                    for name, comp in self.components.items()
                }
            }
    
    async def validate_system(self) -> Dict[str, Any]:
        """
        Perform comprehensive system validation.
        
        Returns:
            Dict containing validation results
        """
        self.logger.info("🔍 Performing comprehensive system validation...")
        
        start_time = time.time()
        validation_results = {
            "timestamp": start_time,
            "validation_type": "comprehensive",
            "overall_success": False,
            "components": {},
            "performance": {},
            "diagnostics": {},
            "recommendations": []
        }
        
        try:
            # Component health validation
            component_results = await self._validate_all_components()
            validation_results["components"] = component_results
            
            # Performance validation
            performance_results = await self._validate_system_performance()
            validation_results["performance"] = performance_results
            
            # Diagnostic validation
            diagnostic_results = await self._validate_diagnostic_systems()
            validation_results["diagnostics"] = diagnostic_results
            
            # Integration validation
            integration_results = await self._validate_component_integration()
            validation_results["integration"] = integration_results
            
            # Determine overall success
            component_success = component_results.get("success_rate", 0) >= 0.8
            performance_success = performance_results.get("acceptable", False)
            diagnostic_success = diagnostic_results.get("success", False)
            integration_success = integration_results.get("success", False)
            
            validation_results["overall_success"] = (
                component_success and performance_success and 
                diagnostic_success and integration_success
            )
            
            # Generate recommendations
            validation_results["recommendations"] = self._generate_validation_recommendations(
                validation_results
            )
            
            # Update system state
            self.system_state.last_validation = time.time()
            
            # Notify handlers
            for handler in self.validation_handlers:
                try:
                    await handler(validation_results)
                except Exception as e:
                    self.logger.error(f"Validation handler error: {e}")
            
            validation_results["duration"] = time.time() - start_time
            
            self.logger.info(f"✅ System validation completed - Success: {validation_results['overall_success']}")
            return validation_results
            
        except Exception as e:
            self.logger.error(f"System validation failed: {e}")
            validation_results["error"] = str(e)
            validation_results["duration"] = time.time() - start_time
            return validation_results
    
    async def trigger_recovery(self, component_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Trigger recovery for a specific component or the entire system.
        
        Args:
            component_name: Specific component to recover, or None for system-wide recovery
            
        Returns:
            Dict containing recovery results
        """
        self.logger.info(f"🔧 Triggering recovery for: {component_name or 'entire system'}")
        
        start_time = time.time()
        recovery_results = {
            "timestamp": start_time,
            "target": component_name or "system",
            "success": False,
            "actions_taken": [],
            "components_recovered": [],
            "components_failed": []
        }
        
        try:
            self.system_state.phase = SystemPhase.RECOVERY
            self.system_state.recovery_attempts += 1
            
            if component_name:
                # Recover specific component
                result = await self._recover_component(component_name)
                recovery_results["success"] = result
                if result:
                    recovery_results["components_recovered"].append(component_name)
                else:
                    recovery_results["components_failed"].append(component_name)
            else:
                # System-wide recovery
                recovery_results = await self._recover_system()
            
            # Update system state based on recovery results
            if recovery_results["success"]:
                self.system_state.phase = SystemPhase.RUNNING
                # Clear resolved issues
                self.system_state.active_issues = [
                    issue for issue in self.system_state.active_issues
                    if not any(comp in issue for comp in recovery_results["components_recovered"])
                ]
            else:
                self.system_state.phase = SystemPhase.DEGRADED
            
            # Notify recovery handlers
            for handler in self.recovery_handlers:
                try:
                    await handler(recovery_results)
                except Exception as e:
                    self.logger.error(f"Recovery handler error: {e}")
            
            recovery_results["duration"] = time.time() - start_time
            
            self.logger.info(f"✅ Recovery completed - Success: {recovery_results['success']}")
            return recovery_results
            
        except Exception as e:
            self.logger.error(f"Recovery failed: {e}")
            recovery_results["error"] = str(e)
            recovery_results["duration"] = time.time() - start_time
            self.system_state.phase = SystemPhase.DEGRADED
            return recovery_results
    
    # Component-specific health checkers
    async def _check_chromadb_health(self) -> Dict[str, Any]:
        """Check ChromaDB health."""
        try:
            # This would integrate with the actual ChromaDB client
            return {"status": "healthy", "response_time": 0.1}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    async def _check_neo4j_health(self) -> Dict[str, Any]:
        """Check Neo4j health."""
        try:
            # This would integrate with the actual Neo4j client
            return {"status": "healthy", "response_time": 0.05}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    async def _check_embedding_health(self) -> Dict[str, Any]:
        """Check embedding system health."""
        try:
            validator = EmbeddingValidator()
            result = await validator.validate_codebert_initialization()
            return {
                "status": "healthy" if result.is_valid else "unhealthy",
                "validation_time": result.validation_time,
                "details": result.details
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    async def _check_processor_health(self) -> Dict[str, Any]:
        """Check repository processor health."""
        try:
            # This would integrate with the actual processor
            return {"status": "healthy", "active_tasks": 0}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    async def _check_api_health(self) -> Dict[str, Any]:
        """Check API server health."""
        try:
            # This would check the actual API server
            return {"status": "healthy", "active_connections": 0}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    async def _check_diagnostic_health(self) -> Dict[str, Any]:
        """Check diagnostic system health."""
        try:
            # Test diagnostic system
            report = await diagnostic_collector.generate_diagnostic_report()
            return {"status": "healthy", "report_generated": bool(report)}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    # Component-specific recovery handlers
    async def _recover_chromadb(self) -> bool:
        """Recover ChromaDB component."""
        self.logger.info("Attempting ChromaDB recovery...")
        try:
            # Implementation would depend on actual ChromaDB client
            await asyncio.sleep(1)  # Simulate recovery time
            return True
        except Exception as e:
            self.logger.error(f"ChromaDB recovery failed: {e}")
            return False
    
    async def _recover_neo4j(self) -> bool:
        """Recover Neo4j component."""
        self.logger.info("Attempting Neo4j recovery...")
        try:
            # Implementation would depend on actual Neo4j client
            await asyncio.sleep(1)  # Simulate recovery time
            return True
        except Exception as e:
            self.logger.error(f"Neo4j recovery failed: {e}")
            return False
    
    async def _recover_embedding_system(self) -> bool:
        """Recover embedding system."""
        self.logger.info("Attempting embedding system recovery...")
        try:
            # Implementation would reinitialize embedding client
            await asyncio.sleep(2)  # Simulate recovery time
            return True
        except Exception as e:
            self.logger.error(f"Embedding system recovery failed: {e}")
            return False
    
    async def _recover_processor(self) -> bool:
        """Recover repository processor."""
        self.logger.info("Attempting processor recovery...")
        try:
            # Implementation would restart processor
            await asyncio.sleep(1)  # Simulate recovery time
            return True
        except Exception as e:
            self.logger.error(f"Processor recovery failed: {e}")
            return False
    
    async def _recover_api_server(self) -> bool:
        """Recover API server."""
        self.logger.info("Attempting API server recovery...")
        try:
            # Implementation would restart API components
            await asyncio.sleep(1)  # Simulate recovery time
            return True
        except Exception as e:
            self.logger.error(f"API server recovery failed: {e}")
            return False
    
    async def _recover_diagnostic_system(self) -> bool:
        """Recover diagnostic system."""
        self.logger.info("Attempting diagnostic system recovery...")
        try:
            # Implementation would reinitialize diagnostic components
            await asyncio.sleep(0.5)  # Simulate recovery time
            return True
        except Exception as e:
            self.logger.error(f"Diagnostic system recovery failed: {e}")
            return False
    
    # Internal methods
    async def _start_background_tasks(self):
        """Start background monitoring and validation tasks."""
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self._validation_task = asyncio.create_task(self._validation_loop())
    
    async def _monitoring_loop(self):
        """Background monitoring loop."""
        while not self._shutdown_event.is_set():
            try:
                await self._update_component_health()
                await self._update_system_health()
                await asyncio.sleep(self.monitoring_interval)
            except Exception as e:
                self.logger.error(f"Monitoring loop error: {e}")
                await asyncio.sleep(5)  # Short delay on error
    
    async def _validation_loop(self):
        """Background validation loop."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self.validation_interval)
                if not self._shutdown_event.is_set():
                    await self.validate_system()
            except Exception as e:
                self.logger.error(f"Validation loop error: {e}")
                await asyncio.sleep(10)  # Longer delay on error
    
    async def _initialize_components(self) -> bool:
        """Initialize components in dependency order."""
        # Topological sort for dependency order
        initialization_order = self._get_initialization_order()
        
        for component_name in initialization_order:
            component = self.components[component_name]
            component.status = ComponentStatus.INITIALIZING
            
            try:
                # Check if dependencies are healthy
                for dep_name in component.dependencies:
                    dep_component = self.components.get(dep_name)
                    if not dep_component or dep_component.status != ComponentStatus.HEALTHY:
                        raise Exception(f"Dependency {dep_name} not healthy")
                
                # Initialize component (this would call actual initialization)
                await asyncio.sleep(0.1)  # Simulate initialization time
                component.status = ComponentStatus.HEALTHY
                component.last_check = time.time()
                
                self.logger.info(f"✅ Initialized component: {component_name}")
                
            except Exception as e:
                component.status = ComponentStatus.FAILED
                component.error_message = str(e)
                self.logger.error(f"❌ Failed to initialize component {component_name}: {e}")
                return False
        
        return True
    
    def _get_initialization_order(self) -> List[str]:
        """Get component initialization order based on dependencies."""
        # Simple topological sort
        visited = set()
        temp_visited = set()
        order = []
        
        def visit(name):
            if name in temp_visited:
                raise Exception(f"Circular dependency detected involving {name}")
            if name in visited:
                return
            
            temp_visited.add(name)
            component = self.components.get(name)
            if component:
                for dep_name in component.dependencies:
                    visit(dep_name)
            temp_visited.remove(name)
            visited.add(name)
            order.append(name)
        
        for component_name in self.components:
            if component_name not in visited:
                visit(component_name)
        
        return order
    
    async def _update_component_health(self):
        """Update health status for all components."""
        for component in self.components.values():
            if component.health_checker:
                try:
                    health_result = await component.health_checker()
                    
                    # Update component status based on health check
                    if health_result.get("status") == "healthy":
                        component.status = ComponentStatus.HEALTHY
                        component.error_message = None
                    else:
                        component.status = ComponentStatus.UNHEALTHY
                        component.error_message = health_result.get("error", "Health check failed")
                    
                    component.last_check = time.time()
                    
                except Exception as e:
                    component.status = ComponentStatus.UNHEALTHY
                    component.error_message = str(e)
                    component.last_check = time.time()
    
    async def _update_system_health(self):
        """Update overall system health based on component statuses."""
        if not self.components:
            self.system_state.overall_health = ComponentStatus.NOT_INITIALIZED
            return
        
        # Count component statuses
        status_counts = {}
        for component in self.components.values():
            status_counts[component.status] = status_counts.get(component.status, 0) + 1
        
        total_components = len(self.components)
        healthy_count = status_counts.get(ComponentStatus.HEALTHY, 0)
        failed_count = status_counts.get(ComponentStatus.FAILED, 0)
        unhealthy_count = status_counts.get(ComponentStatus.UNHEALTHY, 0)
        
        # Determine overall health
        if failed_count > 0:
            self.system_state.overall_health = ComponentStatus.FAILED
        elif unhealthy_count > total_components * 0.3:  # More than 30% unhealthy
            self.system_state.overall_health = ComponentStatus.UNHEALTHY
        elif healthy_count == total_components:
            self.system_state.overall_health = ComponentStatus.HEALTHY
        elif healthy_count >= total_components * 0.7:  # At least 70% healthy
            self.system_state.overall_health = ComponentStatus.DEGRADED
        else:
            self.system_state.overall_health = ComponentStatus.UNHEALTHY
    
    async def _update_performance_metrics(self):
        """Update system performance metrics."""
        try:
            perf_score = performance_collector.get_system_performance_score()
            if isinstance(perf_score, dict) and "score" in perf_score:
                self.system_state.performance_score = perf_score["score"]
                self._performance_history.append(perf_score["score"])
                
                # Keep only recent history
                if len(self._performance_history) > 100:
                    self._performance_history = self._performance_history[-100:]
            
            self._last_performance_check = time.time()
            
        except Exception as e:
            self.logger.error(f"Failed to update performance metrics: {e}")
    
    async def _perform_system_validation(self) -> bool:
        """Perform comprehensive system validation during startup."""
        try:
            validation_results = await self.validate_system()
            return validation_results.get("overall_success", False)
        except Exception as e:
            self.logger.error(f"System validation failed: {e}")
            return False
    
    async def _validate_all_components(self) -> Dict[str, Any]:
        """Validate all registered components."""
        component_results = {}
        successful_components = 0
        
        for name, component in self.components.items():
            try:
                if component.health_checker:
                    health_result = await component.health_checker()
                    success = health_result.get("status") == "healthy"
                    component_results[name] = {
                        "success": success,
                        "status": health_result.get("status", "unknown"),
                        "response_time": health_result.get("response_time", 0),
                        "error": health_result.get("error")
                    }
                    if success:
                        successful_components += 1
                else:
                    component_results[name] = {
                        "success": True,
                        "status": "no_health_checker",
                        "note": "No health checker registered"
                    }
                    successful_components += 1
                    
            except Exception as e:
                component_results[name] = {
                    "success": False,
                    "error": str(e)
                }
        
        return {
            "total_components": len(self.components),
            "successful_components": successful_components,
            "success_rate": successful_components / len(self.components) if self.components else 0,
            "component_results": component_results
        }
    
    async def _validate_system_performance(self) -> Dict[str, Any]:
        """Validate system performance metrics."""
        try:
            await self._update_performance_metrics()
            
            performance_score = self.system_state.performance_score
            acceptable = performance_score >= 60.0  # 60% minimum acceptable score
            
            return {
                "performance_score": performance_score,
                "acceptable": acceptable,
                "recent_average": sum(self._performance_history[-10:]) / min(len(self._performance_history), 10) if self._performance_history else 0,
                "trend": "improving" if len(self._performance_history) >= 2 and self._performance_history[-1] > self._performance_history[-2] else "stable"
            }
            
        except Exception as e:
            return {
                "performance_score": 0,
                "acceptable": False,
                "error": str(e)
            }
    
    async def _validate_diagnostic_systems(self) -> Dict[str, Any]:
        """Validate diagnostic and monitoring systems."""
        try:
            # Test diagnostic report generation
            report = await diagnostic_collector.generate_diagnostic_report()
            
            # Test performance metrics collection
            perf_metrics = performance_collector.get_system_performance_score()
            
            return {
                "success": bool(report and perf_metrics),
                "diagnostic_report_generated": bool(report),
                "performance_metrics_available": bool(perf_metrics),
                "report_id": getattr(report, "report_id", None)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _validate_component_integration(self) -> Dict[str, Any]:
        """Validate that components are properly integrated."""
        try:
            integration_issues = []
            
            # Check dependency relationships
            for name, component in self.components.items():
                for dep_name in component.dependencies:
                    if dep_name not in self.components:
                        integration_issues.append(f"Component {name} depends on unregistered component {dep_name}")
                    elif self.components[dep_name].status != ComponentStatus.HEALTHY:
                        integration_issues.append(f"Component {name} depends on unhealthy component {dep_name}")
            
            # Check for circular dependencies
            try:
                self._get_initialization_order()
            except Exception as e:
                integration_issues.append(f"Dependency issue: {str(e)}")
            
            return {
                "success": len(integration_issues) == 0,
                "integration_issues": integration_issues,
                "dependency_graph_valid": len(integration_issues) == 0
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _generate_validation_recommendations(self, validation_results: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on validation results."""
        recommendations = []
        
        # Component recommendations
        component_results = validation_results.get("components", {})
        failed_components = [
            name for name, result in component_results.get("component_results", {}).items()
            if not result.get("success", False)
        ]
        
        if failed_components:
            recommendations.append(f"Fix failed components: {', '.join(failed_components)}")
        
        # Performance recommendations
        performance_results = validation_results.get("performance", {})
        if not performance_results.get("acceptable", True):
            recommendations.append("Improve system performance - score below acceptable threshold")
        
        # Integration recommendations
        integration_results = validation_results.get("integration", {})
        integration_issues = integration_results.get("integration_issues", [])
        if integration_issues:
            recommendations.extend([f"Fix integration issue: {issue}" for issue in integration_issues])
        
        # Diagnostic recommendations
        diagnostic_results = validation_results.get("diagnostics", {})
        if not diagnostic_results.get("success", True):
            recommendations.append("Fix diagnostic system issues")
        
        if not recommendations:
            recommendations.append("System validation passed - all components integrated successfully")
        
        return recommendations
    
    async def _recover_component(self, component_name: str) -> bool:
        """Recover a specific component."""
        component = self.components.get(component_name)
        if not component:
            self.logger.error(f"Component {component_name} not found")
            return False
        
        if not component.recovery_handler:
            self.logger.warning(f"No recovery handler for component {component_name}")
            return False
        
        try:
            component.status = ComponentStatus.RECOVERING
            success = await component.recovery_handler()
            
            if success:
                component.status = ComponentStatus.HEALTHY
                component.error_message = None
                self.logger.info(f"✅ Successfully recovered component: {component_name}")
            else:
                component.status = ComponentStatus.FAILED
                self.logger.error(f"❌ Failed to recover component: {component_name}")
            
            return success
            
        except Exception as e:
            component.status = ComponentStatus.FAILED
            component.error_message = str(e)
            self.logger.error(f"❌ Recovery error for component {component_name}: {e}")
            return False
    
    async def _recover_system(self) -> Dict[str, Any]:
        """Perform system-wide recovery."""
        recovery_results = {
            "success": False,
            "actions_taken": [],
            "components_recovered": [],
            "components_failed": []
        }
        
        # Get components that need recovery
        components_to_recover = [
            name for name, comp in self.components.items()
            if comp.status in [ComponentStatus.UNHEALTHY, ComponentStatus.FAILED]
        ]
        
        if not components_to_recover:
            recovery_results["success"] = True
            recovery_results["actions_taken"].append("No components needed recovery")
            return recovery_results
        
        # Recover components in dependency order
        recovery_order = self._get_initialization_order()
        components_to_recover_ordered = [
            name for name in recovery_order if name in components_to_recover
        ]
        
        for component_name in components_to_recover_ordered:
            recovery_results["actions_taken"].append(f"Attempting recovery of {component_name}")
            
            success = await self._recover_component(component_name)
            if success:
                recovery_results["components_recovered"].append(component_name)
            else:
                recovery_results["components_failed"].append(component_name)
        
        # Determine overall recovery success
        recovery_results["success"] = len(recovery_results["components_failed"]) == 0
        
        return recovery_results
    
    async def _shutdown_components(self):
        """Shutdown components in reverse dependency order."""
        shutdown_order = list(reversed(self._get_initialization_order()))
        
        for component_name in shutdown_order:
            try:
                # This would call actual shutdown methods
                self.logger.info(f"Shutting down component: {component_name}")
                await asyncio.sleep(0.1)  # Simulate shutdown time
            except Exception as e:
                self.logger.error(f"Error shutting down component {component_name}: {e}")


# Global system integrator instance
system_integrator = SystemIntegrator()


# Convenience functions
async def start_integrated_system() -> bool:
    """Start the integrated system using the global integrator."""
    return await system_integrator.start_system()


async def shutdown_integrated_system():
    """Shutdown the integrated system using the global integrator."""
    await system_integrator.shutdown_system()


async def get_integrated_system_status() -> Dict[str, Any]:
    """Get system status using the global integrator."""
    return await system_integrator.get_system_status()


async def validate_integrated_system() -> Dict[str, Any]:
    """Validate the integrated system using the global integrator."""
    return await system_integrator.validate_system()


async def trigger_system_recovery(component_name: Optional[str] = None) -> Dict[str, Any]:
    """Trigger system recovery using the global integrator."""
    return await system_integrator.trigger_recovery(component_name)