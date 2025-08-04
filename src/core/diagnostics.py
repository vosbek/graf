"""
Diagnostic Information Collection System
=======================================

Comprehensive diagnostic data collection for troubleshooting and system analysis.
Collects system state, configuration, performance data, and error context.

Features:
- System state collection
- Configuration validation
- Error context gathering
- Performance diagnostics
- Health check integration
- Automated troubleshooting suggestions

Author: Kiro AI Assistant
Version: 1.0.0
Last Updated: 2025-08-03
"""

import asyncio
import json
import os
import platform
import psutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Callable
import logging
import subprocess
import socket
import threading

from .exceptions import GraphRAGException, ErrorContext
from .performance_metrics import performance_collector


@dataclass
class SystemInfo:
    """System information collection."""
    platform: str
    python_version: str
    cpu_count: int
    memory_total_gb: float
    disk_total_gb: float
    disk_free_gb: float
    hostname: str
    ip_address: str
    process_id: int
    uptime_seconds: float
    load_average: Optional[List[float]] = None


@dataclass
class ServiceStatus:
    """Status of a system service."""
    name: str
    status: str  # healthy, unhealthy, unknown, disabled
    response_time: Optional[float] = None
    error_message: Optional[str] = None
    last_check: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConfigurationItem:
    """Configuration item with validation."""
    key: str
    value: Any
    source: str  # environment, file, default
    is_valid: bool = True
    validation_message: Optional[str] = None
    is_sensitive: bool = False


@dataclass
class DiagnosticReport:
    """Comprehensive diagnostic report."""
    timestamp: float
    report_id: str
    system_info: SystemInfo
    service_statuses: List[ServiceStatus]
    configuration: List[ConfigurationItem]
    performance_metrics: Dict[str, Any]
    recent_errors: List[Dict[str, Any]]
    health_checks: Dict[str, Any]
    troubleshooting_suggestions: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


class DiagnosticCollector:
    """
    Comprehensive diagnostic information collector.
    
    Collects system state, configuration, performance data,
    and provides troubleshooting suggestions.
    """
    
    def __init__(self):
        """Initialize diagnostic collector."""
        self.logger = logging.getLogger(__name__)
        self.service_checkers: Dict[str, Callable] = {}
        self.config_validators: Dict[str, Callable] = {}
        self.troubleshooting_rules: List[Callable] = []
        
        # Cache for expensive operations
        self._system_info_cache: Optional[SystemInfo] = None
        self._cache_timestamp: float = 0
        self._cache_ttl: float = 60.0  # 1 minute cache
        
        # Thread safety
        self._lock = threading.RLock()
    
    def register_service_checker(self, service_name: str, checker_func: Callable):
        """
        Register a service health checker.
        
        Args:
            service_name: Name of the service
            checker_func: Async function that returns ServiceStatus
        """
        self.service_checkers[service_name] = checker_func
        self.logger.debug(f"Registered service checker for {service_name}")
    
    def register_config_validator(self, config_key: str, validator_func: Callable):
        """
        Register a configuration validator.
        
        Args:
            config_key: Configuration key to validate
            validator_func: Function that validates the configuration
        """
        self.config_validators[config_key] = validator_func
        self.logger.debug(f"Registered config validator for {config_key}")
    
    def register_troubleshooting_rule(self, rule_func: Callable):
        """
        Register a troubleshooting rule.
        
        Args:
            rule_func: Function that analyzes diagnostic data and returns suggestions
        """
        self.troubleshooting_rules.append(rule_func)
        self.logger.debug("Registered troubleshooting rule")
    
    async def collect_system_info(self, force_refresh: bool = False) -> SystemInfo:
        """
        Collect system information with caching.
        
        Args:
            force_refresh: Force refresh of cached data
            
        Returns:
            SystemInfo object
        """
        current_time = time.time()
        
        with self._lock:
            if (not force_refresh and 
                self._system_info_cache and 
                current_time - self._cache_timestamp < self._cache_ttl):
                return self._system_info_cache
        
        try:
            # Get system information
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Get IP address
            try:
                # Connect to a remote address to get local IP
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.connect(("8.8.8.8", 80))
                    ip_address = s.getsockname()[0]
            except Exception:
                ip_address = "unknown"
            
            # Get load average (Unix-like systems only)
            load_average = None
            try:
                if hasattr(os, 'getloadavg'):
                    load_average = list(os.getloadavg())
            except Exception:
                pass
            
            # Get process uptime
            process = psutil.Process()
            uptime_seconds = time.time() - process.create_time()
            
            system_info = SystemInfo(
                platform=platform.platform(),
                python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                cpu_count=psutil.cpu_count(),
                memory_total_gb=memory.total / (1024**3),
                disk_total_gb=disk.total / (1024**3),
                disk_free_gb=disk.free / (1024**3),
                hostname=socket.gethostname(),
                ip_address=ip_address,
                process_id=os.getpid(),
                uptime_seconds=uptime_seconds,
                load_average=load_average
            )
            
            with self._lock:
                self._system_info_cache = system_info
                self._cache_timestamp = current_time
            
            return system_info
            
        except Exception as e:
            self.logger.error(f"Failed to collect system info: {e}")
            # Return minimal system info
            return SystemInfo(
                platform="unknown",
                python_version="unknown",
                cpu_count=0,
                memory_total_gb=0.0,
                disk_total_gb=0.0,
                disk_free_gb=0.0,
                hostname="unknown",
                ip_address="unknown",
                process_id=os.getpid(),
                uptime_seconds=0.0
            )
    
    async def check_services(self) -> List[ServiceStatus]:
        """
        Check status of all registered services.
        
        Returns:
            List of ServiceStatus objects
        """
        service_statuses = []
        
        # Run all service checks concurrently
        tasks = []
        for service_name, checker_func in self.service_checkers.items():
            task = asyncio.create_task(self._safe_service_check(service_name, checker_func))
            tasks.append(task)
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, ServiceStatus):
                    service_statuses.append(result)
                elif isinstance(result, Exception):
                    self.logger.error(f"Service check failed: {result}")
        
        return service_statuses
    
    async def _safe_service_check(self, service_name: str, checker_func: Callable) -> ServiceStatus:
        """
        Safely execute a service check with timeout and error handling.
        
        Args:
            service_name: Name of the service
            checker_func: Service checker function
            
        Returns:
            ServiceStatus object
        """
        start_time = time.time()
        
        try:
            # Execute with timeout
            status = await asyncio.wait_for(checker_func(), timeout=10.0)
            
            if isinstance(status, ServiceStatus):
                status.last_check = time.time()
                status.response_time = time.time() - start_time
                return status
            else:
                # Convert to ServiceStatus if needed
                return ServiceStatus(
                    name=service_name,
                    status="unknown",
                    response_time=time.time() - start_time,
                    last_check=time.time(),
                    error_message="Invalid status format returned"
                )
                
        except asyncio.TimeoutError:
            return ServiceStatus(
                name=service_name,
                status="unhealthy",
                response_time=time.time() - start_time,
                last_check=time.time(),
                error_message="Service check timed out"
            )
        except Exception as e:
            return ServiceStatus(
                name=service_name,
                status="unhealthy",
                response_time=time.time() - start_time,
                last_check=time.time(),
                error_message=str(e)
            )
    
    def validate_configuration(self) -> List[ConfigurationItem]:
        """
        Validate system configuration.
        
        Returns:
            List of ConfigurationItem objects
        """
        config_items = []
        
        # Standard environment variables
        standard_configs = {
            "NEO4J_URI": {"sensitive": False, "required": True},
            "NEO4J_USERNAME": {"sensitive": False, "required": True},
            "NEO4J_PASSWORD": {"sensitive": True, "required": True},
            "CHROMADB_HOST": {"sensitive": False, "required": True},
            "CHROMADB_PORT": {"sensitive": False, "required": True},
            "API_HOST": {"sensitive": False, "required": False},
            "API_PORT": {"sensitive": False, "required": False},
            "LOG_LEVEL": {"sensitive": False, "required": False},
            "AWS_REGION": {"sensitive": False, "required": False},
            "BEDROCK_MODEL_ID": {"sensitive": False, "required": False}
        }
        
        for key, config in standard_configs.items():
            value = os.environ.get(key)
            source = "environment" if value else "default"
            
            # Validate configuration
            is_valid = True
            validation_message = None
            
            if config["required"] and not value:
                is_valid = False
                validation_message = f"Required configuration {key} is missing"
            
            # Run custom validator if registered
            if key in self.config_validators and value:
                try:
                    validator_result = self.config_validators[key](value)
                    if isinstance(validator_result, tuple):
                        is_valid, validation_message = validator_result
                    else:
                        is_valid = bool(validator_result)
                except Exception as e:
                    is_valid = False
                    validation_message = f"Validation error: {str(e)}"
            
            # Mask sensitive values
            display_value = value
            if config["sensitive"] and value:
                display_value = "*" * min(len(value), 8)
            
            config_items.append(ConfigurationItem(
                key=key,
                value=display_value,
                source=source,
                is_valid=is_valid,
                validation_message=validation_message,
                is_sensitive=config["sensitive"]
            ))
        
        return config_items
    
    def collect_recent_errors(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Collect recent errors from logs.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            List of error dictionaries
        """
        try:
            from .logging_config import log_aggregator
            return log_aggregator.get_error_summary(hours).get("recent_errors", [])
        except Exception as e:
            self.logger.error(f"Failed to collect recent errors: {e}")
            return []
    
    def collect_performance_metrics(self) -> Dict[str, Any]:
        """
        Collect current performance metrics.
        
        Returns:
            Dictionary of performance metrics
        """
        try:
            return {
                "system_performance_score": performance_collector.get_system_performance_score(),
                "collection_overhead": {
                    "average_ms": sum(performance_collector.collection_overhead) / 
                                 max(len(performance_collector.collection_overhead), 1) * 1000
                    if performance_collector.collection_overhead else 0,
                    "samples": len(performance_collector.collection_overhead)
                },
                "active_operations": len(performance_collector.operation_metrics),
                "total_metrics": len(performance_collector.metrics)
            }
        except Exception as e:
            self.logger.error(f"Failed to collect performance metrics: {e}")
            return {"error": str(e)}
    
    def generate_troubleshooting_suggestions(self, 
                                           system_info: SystemInfo,
                                           service_statuses: List[ServiceStatus],
                                           config_items: List[ConfigurationItem],
                                           performance_metrics: Dict[str, Any],
                                           recent_errors: List[Dict[str, Any]]) -> List[str]:
        """
        Generate troubleshooting suggestions based on diagnostic data.
        
        Args:
            system_info: System information
            service_statuses: Service status list
            config_items: Configuration items
            performance_metrics: Performance metrics
            recent_errors: Recent errors
            
        Returns:
            List of troubleshooting suggestions
        """
        suggestions = []
        
        # System resource checks
        if system_info.memory_total_gb > 0:
            memory_usage_percent = (system_info.memory_total_gb - 
                                   psutil.virtual_memory().available / (1024**3)) / system_info.memory_total_gb * 100
            if memory_usage_percent > 90:
                suggestions.append("High memory usage detected (>90%). Consider freeing memory or increasing system RAM.")
            elif memory_usage_percent > 75:
                suggestions.append("Moderate memory usage detected (>75%). Monitor memory consumption.")
        
        if system_info.disk_free_gb < 1.0:
            suggestions.append("Low disk space detected (<1GB free). Free up disk space immediately.")
        elif system_info.disk_free_gb < 5.0:
            suggestions.append("Limited disk space detected (<5GB free). Consider cleaning up old files.")
        
        # Service status checks
        unhealthy_services = [s for s in service_statuses if s.status == "unhealthy"]
        if unhealthy_services:
            service_names = [s.name for s in unhealthy_services]
            suggestions.append(f"Unhealthy services detected: {', '.join(service_names)}. Check service logs and restart if necessary.")
        
        slow_services = [s for s in service_statuses if s.response_time and s.response_time > 5.0]
        if slow_services:
            service_names = [s.name for s in slow_services]
            suggestions.append(f"Slow service responses detected: {', '.join(service_names)}. Check network connectivity and service performance.")
        
        # Configuration checks
        invalid_configs = [c for c in config_items if not c.is_valid]
        if invalid_configs:
            config_keys = [c.key for c in invalid_configs]
            suggestions.append(f"Invalid configuration detected: {', '.join(config_keys)}. Review and fix configuration values.")
        
        # Performance checks
        perf_score = performance_metrics.get("system_performance_score", {})
        if isinstance(perf_score, dict):
            score = perf_score.get("score", 100)
            if score < 60:
                suggestions.append("Poor system performance detected. Check CPU, memory usage, and optimize operations.")
            elif score < 75:
                suggestions.append("Suboptimal system performance detected. Monitor resource usage and consider optimization.")
        
        # Error pattern analysis
        if recent_errors:
            error_count = len(recent_errors)
            if error_count > 50:
                suggestions.append(f"High error rate detected ({error_count} errors recently). Review error logs and fix underlying issues.")
            elif error_count > 20:
                suggestions.append(f"Moderate error rate detected ({error_count} errors recently). Monitor error patterns.")
            
            # Check for common error patterns
            error_messages = [e.get("message", "") for e in recent_errors]
            connection_errors = sum(1 for msg in error_messages if "connection" in msg.lower())
            if connection_errors > 5:
                suggestions.append("Multiple connection errors detected. Check network connectivity and service availability.")
            
            timeout_errors = sum(1 for msg in error_messages if "timeout" in msg.lower())
            if timeout_errors > 5:
                suggestions.append("Multiple timeout errors detected. Check system performance and increase timeout values if necessary.")
        
        # Run custom troubleshooting rules
        for rule_func in self.troubleshooting_rules:
            try:
                rule_suggestions = rule_func(system_info, service_statuses, config_items, performance_metrics, recent_errors)
                if isinstance(rule_suggestions, list):
                    suggestions.extend(rule_suggestions)
                elif isinstance(rule_suggestions, str):
                    suggestions.append(rule_suggestions)
            except Exception as e:
                self.logger.error(f"Error in troubleshooting rule: {e}")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_suggestions = []
        for suggestion in suggestions:
            if suggestion not in seen:
                seen.add(suggestion)
                unique_suggestions.append(suggestion)
        
        return unique_suggestions
    
    async def generate_diagnostic_report(self, include_sensitive: bool = False) -> DiagnosticReport:
        """
        Generate comprehensive diagnostic report.
        
        Args:
            include_sensitive: Whether to include sensitive configuration data
            
        Returns:
            DiagnosticReport object
        """
        report_id = f"diag_{int(time.time())}_{os.getpid()}"
        
        try:
            # Collect all diagnostic data concurrently where possible
            system_info_task = asyncio.create_task(self.collect_system_info())
            service_status_task = asyncio.create_task(self.check_services())
            
            # Wait for async tasks
            system_info = await system_info_task
            service_statuses = await service_status_task
            
            # Collect synchronous data
            config_items = self.validate_configuration()
            performance_metrics = self.collect_performance_metrics()
            recent_errors = self.collect_recent_errors()
            
            # Filter sensitive data if requested
            if not include_sensitive:
                config_items = [
                    item for item in config_items 
                    if not item.is_sensitive or item.value == "*" * min(len(str(item.value)), 8)
                ]
            
            # Generate troubleshooting suggestions
            suggestions = self.generate_troubleshooting_suggestions(
                system_info, service_statuses, config_items, performance_metrics, recent_errors
            )
            
            # Create health checks summary
            health_checks = {
                "total_services": len(service_statuses),
                "healthy_services": len([s for s in service_statuses if s.status == "healthy"]),
                "unhealthy_services": len([s for s in service_statuses if s.status == "unhealthy"]),
                "unknown_services": len([s for s in service_statuses if s.status == "unknown"]),
                "average_response_time": sum(s.response_time for s in service_statuses if s.response_time) / 
                                       max(len([s for s in service_statuses if s.response_time]), 1)
            }
            
            return DiagnosticReport(
                timestamp=time.time(),
                report_id=report_id,
                system_info=system_info,
                service_statuses=service_statuses,
                configuration=config_items,
                performance_metrics=performance_metrics,
                recent_errors=recent_errors,
                health_checks=health_checks,
                troubleshooting_suggestions=suggestions,
                metadata={
                    "collection_time": time.time(),
                    "python_version": sys.version,
                    "platform": platform.platform(),
                    "include_sensitive": include_sensitive
                }
            )
            
        except Exception as e:
            self.logger.error(f"Failed to generate diagnostic report: {e}")
            
            # Return minimal report on failure
            return DiagnosticReport(
                timestamp=time.time(),
                report_id=report_id,
                system_info=SystemInfo(
                    platform="unknown", python_version="unknown", cpu_count=0,
                    memory_total_gb=0.0, disk_total_gb=0.0, disk_free_gb=0.0,
                    hostname="unknown", ip_address="unknown", process_id=os.getpid(),
                    uptime_seconds=0.0
                ),
                service_statuses=[],
                configuration=[],
                performance_metrics={"error": str(e)},
                recent_errors=[],
                health_checks={},
                troubleshooting_suggestions=[f"Failed to generate diagnostic report: {str(e)}"],
                metadata={"error": str(e)}
            )
    
    def export_report(self, report: DiagnosticReport, format: str = "json") -> Union[str, Dict[str, Any]]:
        """
        Export diagnostic report in specified format.
        
        Args:
            report: DiagnosticReport to export
            format: Export format ("json", "dict", "text")
            
        Returns:
            Report in specified format
        """
        if format == "dict":
            return {
                "timestamp": report.timestamp,
                "report_id": report.report_id,
                "system_info": report.system_info.__dict__,
                "service_statuses": [s.__dict__ for s in report.service_statuses],
                "configuration": [c.__dict__ for c in report.configuration],
                "performance_metrics": report.performance_metrics,
                "recent_errors": report.recent_errors,
                "health_checks": report.health_checks,
                "troubleshooting_suggestions": report.troubleshooting_suggestions,
                "metadata": report.metadata
            }
        elif format == "json":
            return json.dumps(self.export_report(report, "dict"), indent=2, default=str)
        elif format == "text":
            return self._format_text_report(report)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def _format_text_report(self, report: DiagnosticReport) -> str:
        """Format diagnostic report as human-readable text."""
        lines = []
        lines.append(f"=== DIAGNOSTIC REPORT ===")
        lines.append(f"Report ID: {report.report_id}")
        lines.append(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(report.timestamp))}")
        lines.append("")
        
        # System Information
        lines.append("=== SYSTEM INFORMATION ===")
        lines.append(f"Platform: {report.system_info.platform}")
        lines.append(f"Python Version: {report.system_info.python_version}")
        lines.append(f"CPU Count: {report.system_info.cpu_count}")
        lines.append(f"Memory: {report.system_info.memory_total_gb:.1f} GB total")
        lines.append(f"Disk: {report.system_info.disk_free_gb:.1f} GB free of {report.system_info.disk_total_gb:.1f} GB")
        lines.append(f"Hostname: {report.system_info.hostname}")
        lines.append(f"Uptime: {report.system_info.uptime_seconds:.0f} seconds")
        lines.append("")
        
        # Service Status
        lines.append("=== SERVICE STATUS ===")
        for service in report.service_statuses:
            status_icon = "✓" if service.status == "healthy" else "✗" if service.status == "unhealthy" else "?"
            response_time = f" ({service.response_time:.2f}s)" if service.response_time else ""
            lines.append(f"{status_icon} {service.name}: {service.status}{response_time}")
            if service.error_message:
                lines.append(f"   Error: {service.error_message}")
        lines.append("")
        
        # Configuration
        lines.append("=== CONFIGURATION ===")
        for config in report.configuration:
            status_icon = "✓" if config.is_valid else "✗"
            lines.append(f"{status_icon} {config.key}: {config.value} ({config.source})")
            if config.validation_message:
                lines.append(f"   Issue: {config.validation_message}")
        lines.append("")
        
        # Performance
        lines.append("=== PERFORMANCE ===")
        perf_score = report.performance_metrics.get("system_performance_score", {})
        if isinstance(perf_score, dict):
            score = perf_score.get("score", 0)
            level = perf_score.get("level", "unknown")
            lines.append(f"Overall Score: {score:.1f}/100 ({level})")
        lines.append("")
        
        # Troubleshooting
        if report.troubleshooting_suggestions:
            lines.append("=== TROUBLESHOOTING SUGGESTIONS ===")
            for i, suggestion in enumerate(report.troubleshooting_suggestions, 1):
                lines.append(f"{i}. {suggestion}")
            lines.append("")
        
        return "\n".join(lines)


# Global diagnostic collector instance
diagnostic_collector = DiagnosticCollector()


# Convenience functions
async def generate_diagnostic_report(include_sensitive: bool = False) -> DiagnosticReport:
    """Generate a diagnostic report using the global collector."""
    return await diagnostic_collector.generate_diagnostic_report(include_sensitive)


def register_service_checker(service_name: str, checker_func: Callable):
    """Register a service checker using the global collector."""
    diagnostic_collector.register_service_checker(service_name, checker_func)


def register_config_validator(config_key: str, validator_func: Callable):
    """Register a config validator using the global collector."""
    diagnostic_collector.register_config_validator(config_key, validator_func)


def register_troubleshooting_rule(rule_func: Callable):
    """Register a troubleshooting rule using the global collector."""
    diagnostic_collector.register_troubleshooting_rule(rule_func)