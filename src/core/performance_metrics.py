"""
Performance Metrics Collection System
====================================

Comprehensive performance monitoring and metrics collection for GraphRAG system.
Tracks operation timing, resource usage, and system performance with minimal overhead.

Features:
- Operation timing and profiling
- Resource usage monitoring
- Performance threshold monitoring
- Metrics aggregation and reporting
- Low-overhead collection (< 5% CPU)
- Real-time performance alerts

Author: Kiro AI Assistant
Version: 1.0.0
Last Updated: 2025-08-03
"""

import asyncio
import psutil
import time
import threading
from collections import defaultdict, deque
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Callable, Union
import logging
import weakref


class MetricType(str, Enum):
    """Types of metrics collected."""
    TIMING = "timing"
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    RESOURCE = "resource"


class PerformanceLevel(str, Enum):
    """Performance levels for threshold monitoring."""
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"
    CRITICAL = "critical"


@dataclass
class MetricValue:
    """Individual metric value with metadata."""
    value: Union[float, int]
    timestamp: float
    labels: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceThreshold:
    """Performance threshold configuration."""
    metric_name: str
    warning_threshold: float
    critical_threshold: float
    comparison: str = "greater_than"  # greater_than, less_than, equals
    window_size: int = 10  # Number of samples to consider
    alert_callback: Optional[Callable] = None


@dataclass
class OperationMetrics:
    """Metrics for a specific operation."""
    operation_name: str
    total_calls: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    error_count: int = 0
    success_count: int = 0
    last_execution: Optional[float] = None
    recent_times: deque = field(default_factory=lambda: deque(maxlen=100))
    
    @property
    def average_time(self) -> float:
        """Calculate average execution time."""
        return self.total_time / max(self.total_calls, 1)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        total = self.success_count + self.error_count
        return self.success_count / max(total, 1)
    
    @property
    def recent_average(self) -> float:
        """Calculate recent average from last N executions."""
        if not self.recent_times:
            return 0.0
        return sum(self.recent_times) / len(self.recent_times)


class PerformanceCollector:
    """
    High-performance metrics collector with minimal overhead.
    
    Designed to meet the < 5% CPU overhead requirement while providing
    comprehensive performance monitoring.
    """
    
    def __init__(self, collection_interval: float = 1.0, max_metrics_history: int = 1000):
        """
        Initialize performance collector.
        
        Args:
            collection_interval: Interval between system metrics collection (seconds)
            max_metrics_history: Maximum number of metric values to retain
        """
        self.collection_interval = collection_interval
        self.max_metrics_history = max_metrics_history
        
        # Metrics storage
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_metrics_history))
        self.operation_metrics: Dict[str, OperationMetrics] = {}
        self.thresholds: Dict[str, PerformanceThreshold] = {}
        
        # System monitoring
        self.system_metrics_enabled = True
        self.system_metrics_task: Optional[asyncio.Task] = None
        
        # Performance tracking
        self.collection_overhead = deque(maxlen=100)
        self.active_timers: Dict[str, float] = {}
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Logger
        self.logger = logging.getLogger(__name__)
        
        # Weak references to avoid memory leaks
        self._cleanup_refs: List[weakref.ref] = []
    
    async def start_collection(self):
        """Start background metrics collection."""
        if self.system_metrics_task is None:
            self.system_metrics_task = asyncio.create_task(self._collect_system_metrics())
            self.logger.info("Performance metrics collection started")
    
    async def stop_collection(self):
        """Stop background metrics collection."""
        if self.system_metrics_task:
            self.system_metrics_task.cancel()
            try:
                await self.system_metrics_task
            except asyncio.CancelledError:
                pass
            self.system_metrics_task = None
            self.logger.info("Performance metrics collection stopped")
    
    def record_metric(self, name: str, value: Union[float, int], 
                     metric_type: MetricType = MetricType.GAUGE,
                     labels: Optional[Dict[str, str]] = None,
                     metadata: Optional[Dict[str, Any]] = None):
        """
        Record a metric value.
        
        Args:
            name: Metric name
            value: Metric value
            metric_type: Type of metric
            labels: Optional labels for the metric
            metadata: Optional metadata
        """
        start_time = time.perf_counter()
        
        try:
            with self._lock:
                metric_value = MetricValue(
                    value=value,
                    timestamp=time.time(),
                    labels=labels or {},
                    metadata=metadata or {}
                )
                
                self.metrics[name].append(metric_value)
                
                # Check thresholds
                if name in self.thresholds:
                    self._check_threshold(name, value)
        
        finally:
            # Track collection overhead
            overhead = time.perf_counter() - start_time
            self.collection_overhead.append(overhead)
    
    def record_timing(self, operation: str, duration: float, success: bool = True,
                     labels: Optional[Dict[str, str]] = None):
        """
        Record timing information for an operation.
        
        Args:
            operation: Operation name
            duration: Duration in seconds
            success: Whether the operation was successful
            labels: Optional labels
        """
        with self._lock:
            if operation not in self.operation_metrics:
                self.operation_metrics[operation] = OperationMetrics(operation_name=operation)
            
            metrics = self.operation_metrics[operation]
            metrics.total_calls += 1
            metrics.total_time += duration
            metrics.min_time = min(metrics.min_time, duration)
            metrics.max_time = max(metrics.max_time, duration)
            metrics.last_execution = time.time()
            metrics.recent_times.append(duration)
            
            if success:
                metrics.success_count += 1
            else:
                metrics.error_count += 1
        
        # Record as a metric as well
        self.record_metric(
            f"operation_duration_{operation}",
            duration,
            MetricType.TIMING,
            labels=labels
        )
    
    @contextmanager
    def time_operation(self, operation: str, labels: Optional[Dict[str, str]] = None):
        """
        Context manager for timing operations.
        
        Args:
            operation: Operation name
            labels: Optional labels
        """
        start_time = time.perf_counter()
        success = True
        
        try:
            yield
        except Exception:
            success = False
            raise
        finally:
            duration = time.perf_counter() - start_time
            self.record_timing(operation, duration, success, labels)
    
    @asynccontextmanager
    async def async_time_operation(self, operation: str, labels: Optional[Dict[str, str]] = None):
        """
        Async context manager for timing operations.
        
        Args:
            operation: Operation name
            labels: Optional labels
        """
        start_time = time.perf_counter()
        success = True
        
        try:
            yield
        except Exception:
            success = False
            raise
        finally:
            duration = time.perf_counter() - start_time
            self.record_timing(operation, duration, success, labels)
    
    def increment_counter(self, name: str, value: int = 1, 
                         labels: Optional[Dict[str, str]] = None):
        """
        Increment a counter metric.
        
        Args:
            name: Counter name
            value: Increment value
            labels: Optional labels
        """
        self.record_metric(name, value, MetricType.COUNTER, labels)
    
    def set_gauge(self, name: str, value: Union[float, int],
                 labels: Optional[Dict[str, str]] = None):
        """
        Set a gauge metric value.
        
        Args:
            name: Gauge name
            value: Gauge value
            labels: Optional labels
        """
        self.record_metric(name, value, MetricType.GAUGE, labels)
    
    def add_threshold(self, threshold: PerformanceThreshold):
        """
        Add a performance threshold for monitoring.
        
        Args:
            threshold: Threshold configuration
        """
        with self._lock:
            self.thresholds[threshold.metric_name] = threshold
            self.logger.info(f"Added performance threshold for {threshold.metric_name}")
    
    def _check_threshold(self, metric_name: str, value: float):
        """Check if a metric value exceeds thresholds."""
        threshold = self.thresholds[metric_name]
        
        # Get recent values for window-based checking
        recent_values = list(self.metrics[metric_name])[-threshold.window_size:]
        if len(recent_values) < threshold.window_size:
            return
        
        # Calculate average of recent values
        avg_value = sum(mv.value for mv in recent_values) / len(recent_values)
        
        # Check threshold
        exceeded = False
        level = PerformanceLevel.EXCELLENT
        
        if threshold.comparison == "greater_than":
            if avg_value > threshold.critical_threshold:
                exceeded = True
                level = PerformanceLevel.CRITICAL
            elif avg_value > threshold.warning_threshold:
                exceeded = True
                level = PerformanceLevel.POOR
        elif threshold.comparison == "less_than":
            if avg_value < threshold.critical_threshold:
                exceeded = True
                level = PerformanceLevel.CRITICAL
            elif avg_value < threshold.warning_threshold:
                exceeded = True
                level = PerformanceLevel.POOR
        
        if exceeded and threshold.alert_callback:
            try:
                threshold.alert_callback(metric_name, avg_value, level)
            except Exception as e:
                self.logger.error(f"Error in threshold alert callback: {e}")
    
    async def _collect_system_metrics(self):
        """Background task to collect system metrics."""
        while True:
            try:
                start_time = time.perf_counter()
                
                # CPU metrics
                cpu_percent = psutil.cpu_percent(interval=None)
                self.record_metric("system_cpu_percent", cpu_percent, MetricType.GAUGE)
                
                # Memory metrics
                memory = psutil.virtual_memory()
                self.record_metric("system_memory_percent", memory.percent, MetricType.GAUGE)
                self.record_metric("system_memory_available_mb", memory.available / 1024 / 1024, MetricType.GAUGE)
                
                # Disk metrics
                disk = psutil.disk_usage('/')
                self.record_metric("system_disk_percent", disk.percent, MetricType.GAUGE)
                self.record_metric("system_disk_free_gb", disk.free / 1024 / 1024 / 1024, MetricType.GAUGE)
                
                # Process metrics
                process = psutil.Process()
                process_memory = process.memory_info()
                self.record_metric("process_memory_rss_mb", process_memory.rss / 1024 / 1024, MetricType.GAUGE)
                self.record_metric("process_memory_vms_mb", process_memory.vms / 1024 / 1024, MetricType.GAUGE)
                self.record_metric("process_cpu_percent", process.cpu_percent(), MetricType.GAUGE)
                
                # Collection overhead tracking
                collection_time = time.perf_counter() - start_time
                self.record_metric("metrics_collection_time_ms", collection_time * 1000, MetricType.TIMING)
                
                await asyncio.sleep(self.collection_interval)
                
            except Exception as e:
                self.logger.error(f"Error collecting system metrics: {e}")
                await asyncio.sleep(self.collection_interval)
    
    def get_metric_summary(self, name: str, window_seconds: Optional[float] = None) -> Dict[str, Any]:
        """
        Get summary statistics for a metric.
        
        Args:
            name: Metric name
            window_seconds: Time window for analysis (None for all data)
            
        Returns:
            Dictionary with summary statistics
        """
        with self._lock:
            if name not in self.metrics:
                return {"error": f"Metric {name} not found"}
            
            values = list(self.metrics[name])
            
            # Filter by time window if specified
            if window_seconds:
                cutoff_time = time.time() - window_seconds
                values = [v for v in values if v.timestamp >= cutoff_time]
            
            if not values:
                return {"error": "No data points in specified window"}
            
            numeric_values = [v.value for v in values]
            
            return {
                "count": len(numeric_values),
                "min": min(numeric_values),
                "max": max(numeric_values),
                "mean": sum(numeric_values) / len(numeric_values),
                "latest": numeric_values[-1],
                "first_timestamp": values[0].timestamp,
                "last_timestamp": values[-1].timestamp
            }
    
    def get_operation_summary(self, operation: str) -> Dict[str, Any]:
        """
        Get summary for an operation.
        
        Args:
            operation: Operation name
            
        Returns:
            Dictionary with operation statistics
        """
        with self._lock:
            if operation not in self.operation_metrics:
                return {"error": f"Operation {operation} not found"}
            
            metrics = self.operation_metrics[operation]
            
            return {
                "operation_name": metrics.operation_name,
                "total_calls": metrics.total_calls,
                "success_count": metrics.success_count,
                "error_count": metrics.error_count,
                "success_rate": metrics.success_rate,
                "average_time": metrics.average_time,
                "recent_average": metrics.recent_average,
                "min_time": metrics.min_time if metrics.min_time != float('inf') else 0,
                "max_time": metrics.max_time,
                "last_execution": metrics.last_execution
            }
    
    def get_system_performance_score(self) -> Dict[str, Any]:
        """
        Calculate overall system performance score.
        
        Returns:
            Dictionary with performance score and details
        """
        score = 100.0
        details = {}
        
        # CPU performance (weight: 30%)
        cpu_summary = self.get_metric_summary("system_cpu_percent", window_seconds=60)
        if "mean" in cpu_summary:
            cpu_usage = cpu_summary["mean"]
            details["cpu_usage"] = cpu_usage
            if cpu_usage > 80:
                score -= 30
            elif cpu_usage > 60:
                score -= 15
            elif cpu_usage > 40:
                score -= 5
        
        # Memory performance (weight: 25%)
        memory_summary = self.get_metric_summary("system_memory_percent", window_seconds=60)
        if "mean" in memory_summary:
            memory_usage = memory_summary["mean"]
            details["memory_usage"] = memory_usage
            if memory_usage > 90:
                score -= 25
            elif memory_usage > 75:
                score -= 15
            elif memory_usage > 60:
                score -= 8
        
        # Collection overhead (weight: 20%)
        if self.collection_overhead:
            avg_overhead = sum(self.collection_overhead) / len(self.collection_overhead)
            overhead_percent = (avg_overhead / self.collection_interval) * 100
            details["collection_overhead_percent"] = overhead_percent
            if overhead_percent > 5:  # Requirement: < 5% overhead
                score -= 20
            elif overhead_percent > 3:
                score -= 10
            elif overhead_percent > 1:
                score -= 5
        
        # Operation performance (weight: 25%)
        operation_scores = []
        for op_name, op_metrics in self.operation_metrics.items():
            if op_metrics.total_calls > 0:
                op_score = 100.0
                
                # Success rate impact
                if op_metrics.success_rate < 0.95:
                    op_score -= (0.95 - op_metrics.success_rate) * 100
                
                # Performance impact (if recent average is significantly higher than overall average)
                if op_metrics.recent_average > op_metrics.average_time * 1.5:
                    op_score -= 20
                
                operation_scores.append(op_score)
        
        if operation_scores:
            avg_operation_score = sum(operation_scores) / len(operation_scores)
            score = score * 0.75 + avg_operation_score * 0.25
        
        # Determine performance level
        if score >= 90:
            level = PerformanceLevel.EXCELLENT
        elif score >= 75:
            level = PerformanceLevel.GOOD
        elif score >= 60:
            level = PerformanceLevel.ACCEPTABLE
        elif score >= 40:
            level = PerformanceLevel.POOR
        else:
            level = PerformanceLevel.CRITICAL
        
        return {
            "score": max(0, min(100, score)),
            "level": level,
            "details": details,
            "timestamp": time.time()
        }
    
    def export_metrics(self, format: str = "dict") -> Union[Dict[str, Any], str]:
        """
        Export all metrics in specified format.
        
        Args:
            format: Export format ("dict", "json", "prometheus")
            
        Returns:
            Metrics in specified format
        """
        with self._lock:
            if format == "dict":
                return {
                    "metrics": {name: [mv.__dict__ for mv in values] 
                              for name, values in self.metrics.items()},
                    "operations": {name: op.__dict__ for name, op in self.operation_metrics.items()},
                    "thresholds": {name: th.__dict__ for name, th in self.thresholds.items()},
                    "export_timestamp": time.time()
                }
            elif format == "json":
                import json
                return json.dumps(self.export_metrics("dict"), default=str, indent=2)
            elif format == "prometheus":
                return self._export_prometheus_format()
            else:
                raise ValueError(f"Unsupported export format: {format}")
    
    def _export_prometheus_format(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        
        # Export gauge metrics
        for name, values in self.metrics.items():
            if values:
                latest = values[-1]
                lines.append(f"# HELP {name} {name} metric")
                lines.append(f"# TYPE {name} gauge")
                
                labels_str = ""
                if latest.labels:
                    label_pairs = [f'{k}="{v}"' for k, v in latest.labels.items()]
                    labels_str = "{" + ",".join(label_pairs) + "}"
                
                lines.append(f"{name}{labels_str} {latest.value}")
        
        # Export operation metrics
        for op_name, op_metrics in self.operation_metrics.items():
            safe_name = op_name.replace("-", "_").replace(".", "_")
            
            lines.append(f"# HELP operation_calls_total_{safe_name} Total calls for {op_name}")
            lines.append(f"# TYPE operation_calls_total_{safe_name} counter")
            lines.append(f"operation_calls_total_{safe_name} {op_metrics.total_calls}")
            
            lines.append(f"# HELP operation_duration_avg_{safe_name} Average duration for {op_name}")
            lines.append(f"# TYPE operation_duration_avg_{safe_name} gauge")
            lines.append(f"operation_duration_avg_{safe_name} {op_metrics.average_time}")
            
            lines.append(f"# HELP operation_success_rate_{safe_name} Success rate for {op_name}")
            lines.append(f"# TYPE operation_success_rate_{safe_name} gauge")
            lines.append(f"operation_success_rate_{safe_name} {op_metrics.success_rate}")
        
        return "\n".join(lines)
    
    def reset_metrics(self, metric_names: Optional[List[str]] = None):
        """
        Reset metrics data.
        
        Args:
            metric_names: Specific metrics to reset (None for all)
        """
        with self._lock:
            if metric_names is None:
                self.metrics.clear()
                self.operation_metrics.clear()
                self.collection_overhead.clear()
                self.logger.info("All metrics reset")
            else:
                for name in metric_names:
                    if name in self.metrics:
                        del self.metrics[name]
                    if name in self.operation_metrics:
                        del self.operation_metrics[name]
                self.logger.info(f"Reset metrics: {metric_names}")


# Global performance collector instance
performance_collector = PerformanceCollector()


# Convenience functions
def record_metric(name: str, value: Union[float, int], **kwargs):
    """Record a metric using the global collector."""
    performance_collector.record_metric(name, value, **kwargs)


def time_operation(operation: str, **kwargs):
    """Time an operation using the global collector."""
    return performance_collector.time_operation(operation, **kwargs)


def async_time_operation(operation: str, **kwargs):
    """Async time an operation using the global collector."""
    return performance_collector.async_time_operation(operation, **kwargs)


def increment_counter(name: str, value: int = 1, **kwargs):
    """Increment a counter using the global collector."""
    performance_collector.increment_counter(name, value, **kwargs)


def set_gauge(name: str, value: Union[float, int], **kwargs):
    """Set a gauge using the global collector."""
    performance_collector.set_gauge(name, value, **kwargs)