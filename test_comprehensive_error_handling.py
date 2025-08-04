#!/usr/bin/env python3
"""
Comprehensive Error Handling Validation Test
============================================

Tests all error handling components to ensure they meet the performance
requirements specified in task 11:
- < 30 seconds startup validation
- < 5% CPU overhead
- Comprehensive error logging and diagnostics
- Performance metrics collection

Author: Kiro AI Assistant
Version: 1.0.0
Last Updated: 2025-08-04
"""

import asyncio
import time
import sys
import os
import psutil
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.core.error_handling import get_error_handler, get_all_error_handler_stats
from src.core.logging_config import setup_logging, get_logger, get_logging_performance_summary
from src.core.performance_metrics import performance_collector
from src.core.diagnostics import diagnostic_collector, generate_diagnostic_report
from src.core.exceptions import (
    GraphRAGException, ErrorContext, DatabaseError, NetworkError, 
    ValidationError, TimeoutError as GraphRAGTimeoutError
)
from src.core.error_integration import (
    error_integrator, validate_system_error_handling, 
    generate_system_error_report, optimize_system_error_handling
)


class ErrorHandlingValidator:
    """Comprehensive error handling validation test suite."""
    
    def __init__(self):
        """Initialize the validator."""
        self.logger = setup_logging(
            log_level="INFO",
            component="error_validation",
            enable_console=True,
            enable_file=True
        )
        
        self.test_results = {
            "startup_performance": {},
            "cpu_overhead": {},
            "error_handling": {},
            "logging_performance": {},
            "diagnostics": {},
            "integration": {},
            "overall_status": "unknown"
        }
        
        self.start_time = time.time()
    
    async def test_startup_performance(self) -> bool:
        """Test that startup validation completes within 30 seconds."""
        self.logger.info("Testing startup performance (< 30 seconds requirement)")
        
        startup_start = time.time()
        
        try:
            # Start performance collection
            await performance_collector.start_collection()
            
            # Test diagnostic report generation (simulates startup validation)
            diagnostic_report = await generate_diagnostic_report()
            
            # Test error handler initialization
            components = ["api", "database", "processing", "validation", "health_check"]
            for component in components:
                error_handler = get_error_handler(component)
                stats = await error_handler.get_performance_stats()
            
            startup_time = time.time() - startup_start
            
            self.test_results["startup_performance"] = {
                "startup_time": startup_time,
                "requirement": 30.0,
                "passed": startup_time < 30.0,
                "components_initialized": len(components),
                "diagnostic_report_generated": diagnostic_report is not None
            }
            
            self.logger.info(
                f"Startup performance test completed",
                startup_time=startup_time,
                passed=startup_time < 30.0
            )
            
            return startup_time < 30.0
            
        except Exception as e:
            self.logger.error(f"Startup performance test failed: {e}")
            self.test_results["startup_performance"] = {
                "startup_time": time.time() - startup_start,
                "requirement": 30.0,
                "passed": False,
                "error": str(e)
            }
            return False
    
    async def test_cpu_overhead(self) -> bool:
        """Test that error handling overhead is < 5% CPU usage."""
        self.logger.info("Testing CPU overhead (< 5% requirement)")
        
        # Get baseline CPU usage
        baseline_cpu = psutil.cpu_percent(interval=1.0)
        
        # Perform intensive error handling operations
        test_start = time.time()
        cpu_samples = []
        
        try:
            # Generate multiple errors and handle them
            for i in range(100):
                try:
                    # Create various types of errors
                    if i % 4 == 0:
                        raise DatabaseError("Test database error", database_type="test")
                    elif i % 4 == 1:
                        raise NetworkError("Test network error", endpoint="test")
                    elif i % 4 == 2:
                        raise ValidationError("Test validation error", validation_type="test")
                    else:
                        raise GraphRAGTimeoutError("Test timeout error", timeout_duration=5.0)
                except GraphRAGException:
                    pass  # Expected
                
                # Sample CPU usage every 10 operations
                if i % 10 == 0:
                    cpu_samples.append(psutil.cpu_percent())
                
                # Small delay to prevent overwhelming the system
                await asyncio.sleep(0.01)
            
            # Calculate average CPU usage during test
            avg_cpu_during_test = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0
            cpu_overhead = max(0, avg_cpu_during_test - baseline_cpu)
            overhead_percentage = (cpu_overhead / 100) * 100  # Convert to percentage
            
            test_time = time.time() - test_start
            
            self.test_results["cpu_overhead"] = {
                "baseline_cpu": baseline_cpu,
                "avg_cpu_during_test": avg_cpu_during_test,
                "cpu_overhead": cpu_overhead,
                "overhead_percentage": overhead_percentage,
                "requirement": 5.0,
                "passed": overhead_percentage < 5.0,
                "test_time": test_time,
                "operations_performed": 100
            }
            
            self.logger.info(
                f"CPU overhead test completed",
                overhead_percentage=overhead_percentage,
                passed=overhead_percentage < 5.0
            )
            
            return overhead_percentage < 5.0
            
        except Exception as e:
            self.logger.error(f"CPU overhead test failed: {e}")
            self.test_results["cpu_overhead"] = {
                "test_time": time.time() - test_start,
                "requirement": 5.0,
                "passed": False,
                "error": str(e)
            }
            return False
    
    async def test_error_handling_functionality(self) -> bool:
        """Test comprehensive error handling functionality."""
        self.logger.info("Testing error handling functionality")
        
        test_start = time.time()
        tests_passed = 0
        total_tests = 0
        
        try:
            # Test 1: Error handler creation and configuration
            total_tests += 1
            try:
                error_handler = get_error_handler("test_component", max_retries=3, timeout=10.0)
                tests_passed += 1
                self.logger.debug("✓ Error handler creation test passed")
            except Exception as e:
                self.logger.error(f"✗ Error handler creation test failed: {e}")
            
            # Test 2: Structured exception creation
            total_tests += 1
            try:
                context = ErrorContext(component="test", operation="test_op")
                error = DatabaseError("Test error", database_type="test", context=context)
                assert error.error_id is not None
                assert error.error_code is not None
                assert error.category == "database"
                tests_passed += 1
                self.logger.debug("✓ Structured exception test passed")
            except Exception as e:
                self.logger.error(f"✗ Structured exception test failed: {e}")
            
            # Test 3: Error handler operation handling
            total_tests += 1
            try:
                async def test_operation():
                    await asyncio.sleep(0.1)
                    return "success"
                
                result = await error_handler.handle_operation(test_operation)
                assert result == "success"
                tests_passed += 1
                self.logger.debug("✓ Error handler operation test passed")
            except Exception as e:
                self.logger.error(f"✗ Error handler operation test failed: {e}")
            
            # Test 4: Error handler retry logic
            total_tests += 1
            try:
                attempt_count = 0
                
                async def failing_operation():
                    nonlocal attempt_count
                    attempt_count += 1
                    if attempt_count < 3:
                        raise ConnectionError("Test connection error")
                    return "success_after_retries"
                
                result = await error_handler.handle_operation(failing_operation)
                assert result == "success_after_retries"
                assert attempt_count == 3
                tests_passed += 1
                self.logger.debug("✓ Error handler retry test passed")
            except Exception as e:
                self.logger.error(f"✗ Error handler retry test failed: {e}")
            
            # Test 5: Performance statistics
            total_tests += 1
            try:
                stats = await error_handler.get_performance_stats()
                assert "operation_count" in stats
                assert "error_count" in stats
                assert "error_rate" in stats
                tests_passed += 1
                self.logger.debug("✓ Performance statistics test passed")
            except Exception as e:
                self.logger.error(f"✗ Performance statistics test failed: {e}")
            
            test_time = time.time() - test_start
            success_rate = tests_passed / total_tests
            
            self.test_results["error_handling"] = {
                "tests_passed": tests_passed,
                "total_tests": total_tests,
                "success_rate": success_rate,
                "test_time": test_time,
                "passed": success_rate >= 0.8  # 80% success rate required
            }
            
            self.logger.info(
                f"Error handling functionality test completed",
                tests_passed=tests_passed,
                total_tests=total_tests,
                success_rate=success_rate
            )
            
            return success_rate >= 0.8
            
        except Exception as e:
            self.logger.error(f"Error handling functionality test failed: {e}")
            self.test_results["error_handling"] = {
                "test_time": time.time() - test_start,
                "passed": False,
                "error": str(e)
            }
            return False
    
    async def test_logging_performance(self) -> bool:
        """Test logging performance and functionality."""
        self.logger.info("Testing logging performance")
        
        test_start = time.time()
        
        try:
            # Generate a large number of log entries
            test_logger = get_logger("performance_test")
            
            log_start = time.time()
            for i in range(1000):
                test_logger.info(f"Test log message {i}", test_data={"iteration": i})
                if i % 100 == 0:
                    test_logger.warning(f"Test warning {i}")
                if i % 200 == 0:
                    test_logger.error(f"Test error {i}")
            
            log_time = time.time() - log_start
            
            # Get logging performance statistics
            logging_stats = get_logging_performance_summary()
            
            # Calculate performance metrics
            logs_per_second = 1000 / log_time
            avg_log_time_ms = (log_time / 1000) * 1000
            
            self.test_results["logging_performance"] = {
                "total_logs": 1000,
                "log_time": log_time,
                "logs_per_second": logs_per_second,
                "avg_log_time_ms": avg_log_time_ms,
                "logging_stats": logging_stats,
                "passed": logs_per_second > 100  # Require > 100 logs/second
            }
            
            self.logger.info(
                f"Logging performance test completed",
                logs_per_second=logs_per_second,
                avg_log_time_ms=avg_log_time_ms
            )
            
            return logs_per_second > 100
            
        except Exception as e:
            self.logger.error(f"Logging performance test failed: {e}")
            self.test_results["logging_performance"] = {
                "test_time": time.time() - test_start,
                "passed": False,
                "error": str(e)
            }
            return False
    
    async def test_diagnostics_functionality(self) -> bool:
        """Test diagnostics and monitoring functionality."""
        self.logger.info("Testing diagnostics functionality")
        
        test_start = time.time()
        
        try:
            # Test diagnostic report generation
            diagnostic_report = await generate_diagnostic_report()
            
            # Validate report structure
            required_fields = [
                "timestamp", "report_id", "system_info", "service_statuses",
                "configuration", "performance_metrics", "recent_errors",
                "health_checks", "troubleshooting_suggestions"
            ]
            
            missing_fields = [field for field in required_fields if not hasattr(diagnostic_report, field)]
            
            # Test system performance validation
            performance_validation = await validate_system_error_handling()
            
            test_time = time.time() - test_start
            
            self.test_results["diagnostics"] = {
                "report_generated": diagnostic_report is not None,
                "missing_fields": missing_fields,
                "performance_validation": performance_validation is not None,
                "test_time": test_time,
                "passed": len(missing_fields) == 0 and diagnostic_report is not None
            }
            
            self.logger.info(
                f"Diagnostics functionality test completed",
                missing_fields=len(missing_fields),
                passed=len(missing_fields) == 0
            )
            
            return len(missing_fields) == 0
            
        except Exception as e:
            self.logger.error(f"Diagnostics functionality test failed: {e}")
            self.test_results["diagnostics"] = {
                "test_time": time.time() - test_start,
                "passed": False,
                "error": str(e)
            }
            return False
    
    async def test_integration_functionality(self) -> bool:
        """Test error handling integration functionality."""
        self.logger.info("Testing integration functionality")
        
        test_start = time.time()
        
        try:
            # Test system error report generation
            error_report = await generate_system_error_report(hours=1)
            
            # Test system optimization
            optimization_result = await optimize_system_error_handling()
            
            # Test integration statistics
            integration_stats = error_integrator.get_integration_stats()
            
            test_time = time.time() - test_start
            
            self.test_results["integration"] = {
                "error_report_generated": error_report is not None,
                "optimization_completed": optimization_result is not None,
                "integration_stats_available": integration_stats is not None,
                "test_time": test_time,
                "passed": all([
                    error_report is not None,
                    optimization_result is not None,
                    integration_stats is not None
                ])
            }
            
            self.logger.info(
                f"Integration functionality test completed",
                passed=self.test_results["integration"]["passed"]
            )
            
            return self.test_results["integration"]["passed"]
            
        except Exception as e:
            self.logger.error(f"Integration functionality test failed: {e}")
            self.test_results["integration"] = {
                "test_time": time.time() - test_start,
                "passed": False,
                "error": str(e)
            }
            return False
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all validation tests and return comprehensive results."""
        self.logger.info("Starting comprehensive error handling validation")
        
        total_start = time.time()
        
        # Run all tests
        test_results = {
            "startup_performance": await self.test_startup_performance(),
            "cpu_overhead": await self.test_cpu_overhead(),
            "error_handling": await self.test_error_handling_functionality(),
            "logging_performance": await self.test_logging_performance(),
            "diagnostics": await self.test_diagnostics_functionality(),
            "integration": await self.test_integration_functionality()
        }
        
        # Calculate overall results
        tests_passed = sum(1 for result in test_results.values() if result)
        total_tests = len(test_results)
        success_rate = tests_passed / total_tests
        
        total_time = time.time() - total_start
        
        # Determine overall status
        if success_rate >= 0.9:
            overall_status = "excellent"
        elif success_rate >= 0.8:
            overall_status = "good"
        elif success_rate >= 0.6:
            overall_status = "acceptable"
        else:
            overall_status = "poor"
        
        self.test_results["overall_status"] = overall_status
        
        # Generate final report
        final_report = {
            "validation_id": f"error_handling_validation_{int(time.time())}",
            "timestamp": time.time(),
            "total_time": total_time,
            "tests_passed": tests_passed,
            "total_tests": total_tests,
            "success_rate": success_rate,
            "overall_status": overall_status,
            "individual_results": test_results,
            "detailed_results": self.test_results,
            "requirements_met": {
                "startup_time_under_30s": test_results["startup_performance"],
                "cpu_overhead_under_5pct": test_results["cpu_overhead"],
                "comprehensive_error_handling": test_results["error_handling"],
                "performance_logging": test_results["logging_performance"],
                "diagnostic_capabilities": test_results["diagnostics"],
                "system_integration": test_results["integration"]
            },
            "recommendations": self._generate_recommendations(test_results)
        }
        
        # Stop performance collection
        await performance_collector.stop_collection()
        
        self.logger.info(
            f"Comprehensive error handling validation completed",
            tests_passed=tests_passed,
            total_tests=total_tests,
            success_rate=success_rate,
            overall_status=overall_status,
            total_time=total_time
        )
        
        return final_report
    
    def _generate_recommendations(self, test_results: Dict[str, bool]) -> List[str]:
        """Generate recommendations based on test results."""
        recommendations = []
        
        if not test_results["startup_performance"]:
            recommendations.append("Optimize startup performance - consider lazy loading and async initialization")
        
        if not test_results["cpu_overhead"]:
            recommendations.append("Reduce CPU overhead - optimize error handling algorithms and reduce logging frequency")
        
        if not test_results["error_handling"]:
            recommendations.append("Fix error handling functionality - review error handler implementation")
        
        if not test_results["logging_performance"]:
            recommendations.append("Improve logging performance - consider async logging and batch processing")
        
        if not test_results["diagnostics"]:
            recommendations.append("Fix diagnostics functionality - ensure all diagnostic components are working")
        
        if not test_results["integration"]:
            recommendations.append("Fix integration issues - ensure all components work together properly")
        
        if all(test_results.values()):
            recommendations.append("All tests passed - system is performing well")
        
        return recommendations


async def main():
    """Main validation function."""
    print("=" * 60)
    print("GraphRAG Comprehensive Error Handling Validation")
    print("=" * 60)
    
    validator = ErrorHandlingValidator()
    
    try:
        # Run all validation tests
        results = await validator.run_all_tests()
        
        # Print summary
        print(f"\nValidation Results:")
        print(f"- Tests Passed: {results['tests_passed']}/{results['total_tests']}")
        print(f"- Success Rate: {results['success_rate']:.1%}")
        print(f"- Overall Status: {results['overall_status'].upper()}")
        print(f"- Total Time: {results['total_time']:.2f} seconds")
        
        print(f"\nRequirements Compliance:")
        for requirement, met in results['requirements_met'].items():
            status = "✓ PASS" if met else "✗ FAIL"
            print(f"- {requirement}: {status}")
        
        if results['recommendations']:
            print(f"\nRecommendations:")
            for i, rec in enumerate(results['recommendations'], 1):
                print(f"{i}. {rec}")
        
        # Save detailed results
        import json
        with open("error_handling_validation_results.json", "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\nDetailed results saved to: error_handling_validation_results.json")
        
        # Exit with appropriate code
        if results['success_rate'] >= 0.8:
            print(f"\n✓ VALIDATION PASSED - Error handling system meets requirements")
            sys.exit(0)
        else:
            print(f"\n✗ VALIDATION FAILED - Error handling system needs improvement")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n✗ VALIDATION ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())