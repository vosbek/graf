"""
Error Handling Integration Module
================================

Integrates all error handling components and ensures they work together
seamlessly across the GraphRAG system. Provides centralized configuration
and monitoring for error handling performance.

Features:
- Centralized error handler configuration
- Performance monitoring integration
- Diagnostic collector integration
- Error correlation and analysis
- System-wide error handling metrics

Author: Kiro AI Assistant
Version: 1.0.0
Last Updated: 2025-08-04
"""

import asyncio
import time
from typing import Dict, Any, List, Optional
import logging

from .error_handling import get_error_handler, get_all_error_handler_stats
from .logging_config import get_logger, get_all_component_stats, get_logging_performance_summary
from .performance_metrics import performance_collector
from .diagnostics import diagnostic_collector
from .exceptions import GraphRAGException, ErrorContext


class ErrorHandlingIntegrator:
    """
    Centralized error handling integration and monitoring.
    
    Coordinates all error handling components and provides
    system-wide error handling metrics and analysis.
    """
    
    def __init__(self):
        """Initialize the error handling integrator."""
        self.logger = get_logger("error_integration")
        self.start_time = time.time()
        
        # Error handling configuration
        self.component_configs = {
            "api": {"max_retries": 2, "timeout": 30.0},
            "database": {"max_retries": 3, "timeout": 10.0},
            "processing": {"max_retries": 3, "timeout": 1800.0},
            "validation": {"max_retries": 1, "timeout": 5.0},
            "health_check": {"max_retries": 1, "timeout": 5.0},
            "embedding": {"max_retries": 2, "timeout": 60.0}
        }
        
        # Performance thresholds
        self.performance_thresholds = {
            "error_rate": 0.05,  # 5% max error rate
            "avg_response_time": 5.0,  # 5 seconds max average response
            "collection_overhead": 0.05,  # 5% max overhead
            "memory_usage": 0.8,  # 80% max memory usage
            "cpu_usage": 0.8  # 80% max CPU usage
        }
        
        # Initialize component error handlers
        self._initialize_error_handlers()
        
        self.logger.info("Error handling integration initialized")
    
    def _initialize_error_handlers(self):
        """Initialize error handlers for all components."""
        for component, config in self.component_configs.items():
            try:
                error_handler = get_error_handler(component, **config)
                self.logger.debug(f"Initialized error handler for {component}")
            except Exception as e:
                self.logger.error(f"Failed to initialize error handler for {component}: {e}")
    
    async def validate_system_performance(self) -> Dict[str, Any]:
        """
        Validate system-wide error handling performance.
        
        Returns:
            Dict containing validation results and recommendations
        """
        validation_start = time.time()
        
        try:
            # Get error handler statistics
            error_stats = await get_all_error_handler_stats()
            
            # Get logging performance
            logging_stats = get_logging_performance_summary()
            
            # Get performance metrics
            performance_score = performance_collector.get_system_performance_score()
            
            # Validate performance against thresholds
            validation_results = {
                "overall_status": "healthy",
                "validation_time": 0.0,
                "component_results": {},
                "performance_score": performance_score,
                "recommendations": []
            }
            
            # Check error rates
            for component, stats in error_stats.get("error_handlers", {}).items():
                error_rate = stats.get("error_rate", 0.0)
                avg_time = stats.get("average_operation_time", 0.0)
                
                component_status = "healthy"
                component_issues = []
                
                if error_rate > self.performance_thresholds["error_rate"]:
                    component_status = "unhealthy"
                    component_issues.append(f"High error rate: {error_rate:.2%}")
                    validation_results["recommendations"].append(
                        f"Investigate high error rate in {component} component"
                    )
                
                if avg_time > self.performance_thresholds["avg_response_time"]:
                    component_status = "degraded" if component_status == "healthy" else component_status
                    component_issues.append(f"Slow response time: {avg_time:.2f}s")
                    validation_results["recommendations"].append(
                        f"Optimize performance in {component} component"
                    )
                
                validation_results["component_results"][component] = {
                    "status": component_status,
                    "error_rate": error_rate,
                    "average_time": avg_time,
                    "issues": component_issues
                }
                
                if component_status != "healthy":
                    validation_results["overall_status"] = "degraded"
            
            # Check logging performance
            total_errors = logging_stats.get("total_errors", 0)
            total_logs = logging_stats.get("total_logs", 1)
            logging_error_rate = total_errors / total_logs
            
            if logging_error_rate > self.performance_thresholds["error_rate"]:
                validation_results["overall_status"] = "degraded"
                validation_results["recommendations"].append(
                    "High logging error rate detected - investigate system issues"
                )
            
            # Check system performance score
            system_score = performance_score.get("score", 100)
            if system_score < 60:
                validation_results["overall_status"] = "unhealthy"
                validation_results["recommendations"].append(
                    "Poor system performance detected - check resources and optimize"
                )
            elif system_score < 75:
                validation_results["overall_status"] = "degraded"
                validation_results["recommendations"].append(
                    "Suboptimal system performance - consider optimization"
                )
            
            validation_results["validation_time"] = time.time() - validation_start
            
            # Log validation results
            self.logger.info(
                f"System performance validation completed",
                overall_status=validation_results["overall_status"],
                validation_time=validation_results["validation_time"],
                performance_score=system_score,
                recommendations_count=len(validation_results["recommendations"])
            )
            
            return validation_results
            
        except Exception as e:
            self.logger.error(f"System performance validation failed: {e}")
            return {
                "overall_status": "error",
                "validation_time": time.time() - validation_start,
                "error": str(e),
                "recommendations": ["Fix validation system and retry"]
            }
    
    async def generate_error_report(self, hours: int = 24) -> Dict[str, Any]:
        """
        Generate comprehensive error report for the specified time period.
        
        Args:
            hours: Number of hours to analyze
            
        Returns:
            Dict containing comprehensive error analysis
        """
        report_start = time.time()
        
        try:
            # Get error handler statistics
            error_stats = await get_all_error_handler_stats()
            
            # Get component logging statistics
            component_stats = get_all_component_stats()
            
            # Get recent errors from diagnostic collector
            diagnostic_report = await diagnostic_collector.generate_diagnostic_report()
            recent_errors = diagnostic_report.recent_errors
            
            # Analyze error patterns
            error_patterns = {}
            error_categories = {}
            
            for error in recent_errors:
                # Categorize by error type
                error_type = error.get("error_type", "unknown")
                error_categories[error_type] = error_categories.get(error_type, 0) + 1
                
                # Look for patterns in error messages
                message = error.get("message", "")
                for keyword in ["connection", "timeout", "memory", "validation", "database"]:
                    if keyword in message.lower():
                        error_patterns[keyword] = error_patterns.get(keyword, 0) + 1
            
            # Calculate error trends
            total_errors = sum(
                stats.get("total_errors", 0) 
                for stats in component_stats.values()
            )
            total_operations = sum(
                stats.get("total_logs", 0) 
                for stats in component_stats.values()
            )
            
            overall_error_rate = total_errors / max(total_operations, 1)
            
            # Generate recommendations
            recommendations = []
            
            if overall_error_rate > 0.1:  # 10% error rate
                recommendations.append("Critical: Very high error rate detected - immediate investigation required")
            elif overall_error_rate > 0.05:  # 5% error rate
                recommendations.append("High error rate detected - investigate and optimize error-prone components")
            
            # Pattern-based recommendations
            if error_patterns.get("connection", 0) > 5:
                recommendations.append("Multiple connection errors - check network and service availability")
            
            if error_patterns.get("timeout", 0) > 5:
                recommendations.append("Multiple timeout errors - consider increasing timeouts or optimizing performance")
            
            if error_patterns.get("memory", 0) > 3:
                recommendations.append("Memory-related errors detected - check system resources and optimize memory usage")
            
            # Component-specific recommendations
            for component, stats in component_stats.items():
                component_error_rate = stats.get("total_errors", 0) / max(stats.get("total_logs", 1), 1)
                if component_error_rate > 0.1:
                    recommendations.append(f"High error rate in {component} component - focus optimization efforts here")
            
            report = {
                "report_id": f"error_report_{int(time.time())}",
                "generated_at": time.time(),
                "analysis_period_hours": hours,
                "generation_time": time.time() - report_start,
                "summary": {
                    "total_errors": total_errors,
                    "total_operations": total_operations,
                    "overall_error_rate": overall_error_rate,
                    "unique_error_types": len(error_categories),
                    "error_patterns_found": len(error_patterns)
                },
                "error_categories": error_categories,
                "error_patterns": error_patterns,
                "component_analysis": component_stats,
                "error_handler_performance": error_stats,
                "recent_errors": recent_errors[-10:],  # Last 10 errors
                "recommendations": recommendations,
                "system_health": diagnostic_report.health_checks
            }
            
            self.logger.info(
                f"Error report generated",
                total_errors=total_errors,
                error_rate=overall_error_rate,
                recommendations_count=len(recommendations),
                generation_time=report["generation_time"]
            )
            
            return report
            
        except Exception as e:
            self.logger.error(f"Error report generation failed: {e}")
            return {
                "report_id": f"error_report_failed_{int(time.time())}",
                "generated_at": time.time(),
                "generation_time": time.time() - report_start,
                "error": str(e),
                "recommendations": ["Fix error reporting system and retry"]
            }
    
    async def optimize_error_handling(self) -> Dict[str, Any]:
        """
        Analyze system performance and optimize error handling configuration.
        
        Returns:
            Dict containing optimization results and applied changes
        """
        optimization_start = time.time()
        
        try:
            # Get current performance metrics
            validation_results = await self.validate_system_performance()
            
            optimizations_applied = []
            
            # Optimize based on component performance
            for component, results in validation_results.get("component_results", {}).items():
                if results["status"] != "healthy":
                    error_rate = results["error_rate"]
                    avg_time = results["average_time"]
                    
                    # Adjust retry configuration for high error rates
                    if error_rate > 0.1:  # 10% error rate
                        current_config = self.component_configs.get(component, {})
                        if current_config.get("max_retries", 3) < 5:
                            current_config["max_retries"] = min(current_config.get("max_retries", 3) + 1, 5)
                            optimizations_applied.append(
                                f"Increased max retries for {component} to {current_config['max_retries']}"
                            )
                    
                    # Adjust timeout for slow responses
                    if avg_time > 10.0:
                        current_config = self.component_configs.get(component, {})
                        new_timeout = min(current_config.get("timeout", 30.0) * 1.5, 300.0)  # Max 5 minutes
                        current_config["timeout"] = new_timeout
                        optimizations_applied.append(
                            f"Increased timeout for {component} to {new_timeout}s"
                        )
            
            # Apply optimizations by reinitializing error handlers
            if optimizations_applied:
                self._initialize_error_handlers()
            
            optimization_result = {
                "optimization_time": time.time() - optimization_start,
                "optimizations_applied": optimizations_applied,
                "performance_before": validation_results,
                "recommendations": [
                    "Monitor system performance after optimizations",
                    "Consider scaling resources if issues persist",
                    "Review error patterns for systematic issues"
                ]
            }
            
            self.logger.info(
                f"Error handling optimization completed",
                optimizations_count=len(optimizations_applied),
                optimization_time=optimization_result["optimization_time"]
            )
            
            return optimization_result
            
        except Exception as e:
            self.logger.error(f"Error handling optimization failed: {e}")
            return {
                "optimization_time": time.time() - optimization_start,
                "error": str(e),
                "optimizations_applied": [],
                "recommendations": ["Fix optimization system and retry"]
            }
    
    def get_integration_stats(self) -> Dict[str, Any]:
        """
        Get integration statistics and health metrics.
        
        Returns:
            Dict containing integration statistics
        """
        return {
            "integrator_uptime": time.time() - self.start_time,
            "component_configs": self.component_configs,
            "performance_thresholds": self.performance_thresholds,
            "initialized_components": len(self.component_configs),
            "status": "healthy"
        }


# Global error handling integrator instance
error_integrator = ErrorHandlingIntegrator()


# Convenience functions
async def validate_system_error_handling() -> Dict[str, Any]:
    """Validate system-wide error handling performance."""
    return await error_integrator.validate_system_performance()


async def generate_system_error_report(hours: int = 24) -> Dict[str, Any]:
    """Generate comprehensive system error report."""
    return await error_integrator.generate_error_report(hours)


async def optimize_system_error_handling() -> Dict[str, Any]:
    """Optimize system error handling configuration."""
    return await error_integrator.optimize_error_handling()


def get_error_integration_stats() -> Dict[str, Any]:
    """Get error handling integration statistics."""
    return error_integrator.get_integration_stats()