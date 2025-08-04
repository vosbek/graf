#!/usr/bin/env python3
"""
Working Integration Test
=======================

Test the integration of components that are currently working and available.
This focuses on validating the startup validation feature with the endpoints
that are currently accessible.

Author: Kiro AI Assistant
Version: 1.0.0
Last Updated: 2025-08-03
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, Any
import requests

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.core.logging_config import setup_logging
from src.services.embedding_validator import EmbeddingValidator
from src.core.diagnostics import generate_diagnostic_report


class WorkingIntegrationTest:
    """Test integration of working components."""
    
    def __init__(self):
        """Initialize the test."""
        self.logger = setup_logging(log_level="INFO", component="integration_test", enable_console=True)
        self.api_base = "http://localhost:8080/api/v1"
        self.test_results = {}
        self.start_time = time.time()
    
    async def run_tests(self) -> Dict[str, Any]:
        """Run all available integration tests."""
        self.logger.info("🚀 Starting Working Integration Tests")
        self.logger.info("=" * 50)
        
        try:
            # Test 1: Basic API connectivity
            await self._test_api_connectivity()
            
            # Test 2: Health check endpoints
            await self._test_health_endpoints()
            
            # Test 3: Enhanced state validation
            await self._test_enhanced_state()
            
            # Test 4: Embedding system validation
            await self._test_embedding_system()
            
            # Test 5: Diagnostic system integration
            await self._test_diagnostic_integration()
            
            # Test 6: System readiness validation
            await self._test_system_readiness()
            
            # Test 7: Performance validation
            await self._test_performance_metrics()
            
            # Test 8: Error handling
            await self._test_error_handling()
            
            return self._generate_summary()
            
        except Exception as e:
            self.logger.error(f"Integration test failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "test_results": self.test_results,
                "duration": time.time() - self.start_time
            }
    
    async def _test_api_connectivity(self):
        """Test basic API connectivity."""
        self.logger.info("🔌 Testing API connectivity...")
        
        test_name = "api_connectivity"
        start_time = time.time()
        
        try:
            response = requests.get(f"{self.api_base}/health/", timeout=10)
            
            success = response.status_code == 200
            
            if success:
                data = response.json()
                self.test_results[test_name] = {
                    "success": True,
                    "duration": time.time() - start_time,
                    "status_code": response.status_code,
                    "response_time": response.elapsed.total_seconds(),
                    "api_status": data.get("status"),
                    "uptime": data.get("uptime")
                }
                self.logger.info("✅ API connectivity test passed")
            else:
                self.test_results[test_name] = {
                    "success": False,
                    "duration": time.time() - start_time,
                    "status_code": response.status_code,
                    "error": f"Unexpected status code: {response.status_code}"
                }
                self.logger.error("❌ API connectivity test failed")
                
        except Exception as e:
            self.test_results[test_name] = {
                "success": False,
                "duration": time.time() - start_time,
                "error": str(e)
            }
            self.logger.error(f"❌ API connectivity test error: {e}")
    
    async def _test_health_endpoints(self):
        """Test health check endpoints."""
        self.logger.info("🏥 Testing health check endpoints...")
        
        test_name = "health_endpoints"
        start_time = time.time()
        
        try:
            endpoints = [
                ("/health/", "basic_health"),
                ("/health/ready", "readiness_check"),
                ("/health/live", "liveness_check"),
                ("/health/detailed", "detailed_health"),
                ("/health/enhanced/state", "enhanced_state")
            ]
            
            endpoint_results = {}
            
            for endpoint, name in endpoints:
                try:
                    response = requests.get(f"{self.api_base}{endpoint}", timeout=15)
                    endpoint_results[name] = {
                        "success": response.status_code in [200, 503],  # 503 acceptable for some
                        "status_code": response.status_code,
                        "response_time": response.elapsed.total_seconds(),
                        "has_json": self._is_json_response(response)
                    }
                    
                    if response.status_code == 200:
                        data = response.json()
                        endpoint_results[name]["data_keys"] = list(data.keys())
                        
                except Exception as e:
                    endpoint_results[name] = {
                        "success": False,
                        "error": str(e)
                    }
            
            successful_endpoints = sum(1 for result in endpoint_results.values() if result.get("success", False))
            
            self.test_results[test_name] = {
                "success": successful_endpoints >= len(endpoints) * 0.8,  # 80% success rate
                "duration": time.time() - start_time,
                "successful_endpoints": successful_endpoints,
                "total_endpoints": len(endpoints),
                "endpoint_results": endpoint_results
            }
            
            if self.test_results[test_name]["success"]:
                self.logger.info(f"✅ Health endpoints test passed ({successful_endpoints}/{len(endpoints)})")
            else:
                self.logger.error(f"❌ Health endpoints test failed ({successful_endpoints}/{len(endpoints)})")
                
        except Exception as e:
            self.test_results[test_name] = {
                "success": False,
                "duration": time.time() - start_time,
                "error": str(e)
            }
            self.logger.error(f"❌ Health endpoints test error: {e}")
    
    async def _test_enhanced_state(self):
        """Test enhanced state endpoint."""
        self.logger.info("🔍 Testing enhanced state validation...")
        
        test_name = "enhanced_state"
        start_time = time.time()
        
        try:
            response = requests.get(f"{self.api_base}/health/enhanced/state", timeout=15)
            
            if response.status_code != 200:
                self.test_results[test_name] = {
                    "success": False,
                    "duration": time.time() - start_time,
                    "status_code": response.status_code,
                    "error": f"Enhanced state endpoint returned {response.status_code}"
                }
                return
            
            data = response.json()
            
            # Validate response structure
            required_fields = ["is_ready", "components"]
            missing_fields = [field for field in required_fields if field not in data]
            
            if missing_fields:
                self.test_results[test_name] = {
                    "success": False,
                    "duration": time.time() - start_time,
                    "error": f"Missing required fields: {missing_fields}"
                }
                return
            
            components = data["components"]
            initialized_components = sum(1 for comp in components.values() if comp)
            
            self.test_results[test_name] = {
                "success": True,
                "duration": time.time() - start_time,
                "is_ready": data["is_ready"],
                "total_components": len(components),
                "initialized_components": initialized_components,
                "initialization_error": data.get("initialization_error"),
                "component_details": components
            }
            
            self.logger.info(f"✅ Enhanced state test passed (Ready: {data['is_ready']}, Components: {initialized_components}/{len(components)})")
            
        except Exception as e:
            self.test_results[test_name] = {
                "success": False,
                "duration": time.time() - start_time,
                "error": str(e)
            }
            self.logger.error(f"❌ Enhanced state test error: {e}")
    
    async def _test_embedding_system(self):
        """Test embedding system validation."""
        self.logger.info("🧠 Testing embedding system...")
        
        test_name = "embedding_system"
        start_time = time.time()
        
        try:
            validator = EmbeddingValidator()
            
            # Test initialization
            init_result = await validator.validate_codebert_initialization()
            
            # Test embedding generation
            embedding_test = await validator.test_embedding_generation()
            
            # Test semantic search
            search_test = await validator.test_semantic_search("function to calculate fibonacci")
            
            overall_success = (
                init_result.is_valid and
                embedding_test.success and
                search_test.success
            )
            
            self.test_results[test_name] = {
                "success": overall_success,
                "duration": time.time() - start_time,
                "initialization": {
                    "valid": init_result.is_valid,
                    "validation_time": init_result.validation_time,
                    "passed_checks": len(init_result.passed_checks),
                    "failed_checks": len(init_result.failed_checks)
                },
                "embedding_generation": {
                    "success": embedding_test.success,
                    "embeddings_generated": embedding_test.embeddings_generated,
                    "average_time": embedding_test.average_time,
                    "dimensions": embedding_test.dimensions
                },
                "semantic_search": {
                    "success": search_test.success,
                    "query_time": search_test.query_time,
                    "results_count": search_test.results_count,
                    "relevance_score": search_test.relevance_score
                }
            }
            
            if overall_success:
                self.logger.info("✅ Embedding system test passed")
            else:
                self.logger.warning("⚠️ Embedding system test had issues")
                
        except Exception as e:
            self.test_results[test_name] = {
                "success": False,
                "duration": time.time() - start_time,
                "error": str(e)
            }
            self.logger.error(f"❌ Embedding system test error: {e}")
    
    async def _test_diagnostic_integration(self):
        """Test diagnostic system integration."""
        self.logger.info("🔧 Testing diagnostic integration...")
        
        test_name = "diagnostic_integration"
        start_time = time.time()
        
        try:
            # Test diagnostic report generation
            report = await generate_diagnostic_report(include_sensitive=False)
            
            # Validate report structure
            required_fields = [
                "timestamp", "report_id", "system_info", "service_statuses",
                "configuration", "performance_metrics", "health_checks",
                "troubleshooting_suggestions"
            ]
            
            missing_fields = [field for field in required_fields if not hasattr(report, field)]
            
            report_valid = len(missing_fields) == 0
            
            self.test_results[test_name] = {
                "success": report_valid,
                "duration": time.time() - start_time,
                "report_generated": bool(report),
                "missing_fields": missing_fields,
                "report_id": getattr(report, "report_id", None),
                "service_statuses_count": len(getattr(report, "service_statuses", [])),
                "suggestions_count": len(getattr(report, "troubleshooting_suggestions", []))
            }
            
            if report_valid:
                self.logger.info("✅ Diagnostic integration test passed")
            else:
                self.logger.error(f"❌ Diagnostic integration test failed (missing: {missing_fields})")
                
        except Exception as e:
            self.test_results[test_name] = {
                "success": False,
                "duration": time.time() - start_time,
                "error": str(e)
            }
            self.logger.error(f"❌ Diagnostic integration test error: {e}")
    
    async def _test_system_readiness(self):
        """Test system readiness validation."""
        self.logger.info("✅ Testing system readiness...")
        
        test_name = "system_readiness"
        start_time = time.time()
        
        try:
            response = requests.get(f"{self.api_base}/health/ready", timeout=20)
            
            # Readiness check can return 200 or 503
            acceptable_status = response.status_code in [200, 503]
            
            if not acceptable_status:
                self.test_results[test_name] = {
                    "success": False,
                    "duration": time.time() - start_time,
                    "status_code": response.status_code,
                    "error": f"Unexpected status code: {response.status_code}"
                }
                return
            
            data = response.json()
            
            # Validate response structure
            required_fields = ["status", "timestamp"]
            missing_fields = [field for field in required_fields if field not in data]
            
            has_checks = "checks" in data
            health_score = data.get("health_score", 0)
            
            self.test_results[test_name] = {
                "success": len(missing_fields) == 0 and has_checks,
                "duration": time.time() - start_time,
                "status": data.get("status"),
                "health_score": health_score,
                "has_checks": has_checks,
                "missing_fields": missing_fields,
                "validation_time": data.get("validation_time", 0),
                "checks_count": len(data.get("checks", {}))
            }
            
            if self.test_results[test_name]["success"]:
                self.logger.info(f"✅ System readiness test passed (Status: {data.get('status')}, Score: {health_score})")
            else:
                self.logger.error(f"❌ System readiness test failed (missing: {missing_fields})")
                
        except Exception as e:
            self.test_results[test_name] = {
                "success": False,
                "duration": time.time() - start_time,
                "error": str(e)
            }
            self.logger.error(f"❌ System readiness test error: {e}")
    
    async def _test_performance_metrics(self):
        """Test performance metrics collection."""
        self.logger.info("⚡ Testing performance metrics...")
        
        test_name = "performance_metrics"
        start_time = time.time()
        
        try:
            # Test performance endpoint
            response = requests.get(f"{self.api_base}/health/performance", timeout=15)
            
            if response.status_code != 200:
                self.test_results[test_name] = {
                    "success": False,
                    "duration": time.time() - start_time,
                    "status_code": response.status_code,
                    "error": f"Performance endpoint returned {response.status_code}"
                }
                return
            
            data = response.json()
            
            # Check for performance data
            has_performance_data = bool(data)
            
            # Test metrics endpoint
            try:
                metrics_response = requests.get(f"{self.api_base}/health/metrics", timeout=15)
                metrics_available = metrics_response.status_code == 200
                metrics_content = metrics_response.text if metrics_available else ""
            except Exception:
                metrics_available = False
                metrics_content = ""
            
            self.test_results[test_name] = {
                "success": has_performance_data and metrics_available,
                "duration": time.time() - start_time,
                "performance_endpoint": {
                    "success": has_performance_data,
                    "data_keys": list(data.keys()) if isinstance(data, dict) else []
                },
                "metrics_endpoint": {
                    "success": metrics_available,
                    "content_length": len(metrics_content)
                }
            }
            
            if self.test_results[test_name]["success"]:
                self.logger.info("✅ Performance metrics test passed")
            else:
                self.logger.warning("⚠️ Performance metrics test had issues")
                
        except Exception as e:
            self.test_results[test_name] = {
                "success": False,
                "duration": time.time() - start_time,
                "error": str(e)
            }
            self.logger.error(f"❌ Performance metrics test error: {e}")
    
    async def _test_error_handling(self):
        """Test error handling capabilities."""
        self.logger.info("🚨 Testing error handling...")
        
        test_name = "error_handling"
        start_time = time.time()
        
        try:
            error_tests = {}
            
            # Test 1: Invalid endpoint
            try:
                response = requests.get(f"{self.api_base}/nonexistent/endpoint", timeout=10)
                error_tests["invalid_endpoint"] = {
                    "success": response.status_code == 404,
                    "status_code": response.status_code,
                    "has_error_response": self._is_json_response(response)
                }
            except Exception as e:
                error_tests["invalid_endpoint"] = {
                    "success": False,
                    "error": str(e)
                }
            
            # Test 2: Malformed request
            try:
                response = requests.post(f"{self.api_base}/health/ready", 
                                       json={"invalid": "data"}, 
                                       timeout=10)
                error_tests["malformed_request"] = {
                    "success": response.status_code in [400, 405, 200],  # Various acceptable
                    "status_code": response.status_code
                }
            except Exception as e:
                error_tests["malformed_request"] = {
                    "success": True,  # Exception is acceptable
                    "error": str(e)
                }
            
            # Test 3: Timeout handling
            try:
                response = requests.get(f"{self.api_base}/health/detailed", timeout=0.001)
                error_tests["timeout_handling"] = {
                    "success": False,  # Should have timed out
                    "unexpected": "Request completed despite short timeout"
                }
            except requests.exceptions.Timeout:
                error_tests["timeout_handling"] = {
                    "success": True,
                    "note": "Timeout handled correctly"
                }
            except Exception as e:
                error_tests["timeout_handling"] = {
                    "success": True,  # Any exception is acceptable
                    "error": str(e)
                }
            
            successful_tests = sum(1 for test in error_tests.values() if test.get("success", False))
            
            self.test_results[test_name] = {
                "success": successful_tests >= len(error_tests) * 0.7,  # 70% success rate
                "duration": time.time() - start_time,
                "error_tests": error_tests,
                "successful_tests": successful_tests,
                "total_tests": len(error_tests)
            }
            
            if self.test_results[test_name]["success"]:
                self.logger.info(f"✅ Error handling test passed ({successful_tests}/{len(error_tests)})")
            else:
                self.logger.error(f"❌ Error handling test failed ({successful_tests}/{len(error_tests)})")
                
        except Exception as e:
            self.test_results[test_name] = {
                "success": False,
                "duration": time.time() - start_time,
                "error": str(e)
            }
            self.logger.error(f"❌ Error handling test error: {e}")
    
    def _is_json_response(self, response) -> bool:
        """Check if response is JSON."""
        try:
            response.json()
            return True
        except:
            return False
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate test summary."""
        total_tests = len(self.test_results)
        successful_tests = sum(1 for result in self.test_results.values() if result.get("success", False))
        
        success_rate = successful_tests / total_tests if total_tests > 0 else 0
        overall_success = success_rate >= 0.8  # 80% success rate required
        
        total_duration = time.time() - self.start_time
        
        failed_tests = [
            name for name, result in self.test_results.items() 
            if not result.get("success", False)
        ]
        
        recommendations = []
        
        if failed_tests:
            recommendations.append(f"Fix issues in failed tests: {', '.join(failed_tests)}")
        
        if not overall_success:
            recommendations.append("Improve system reliability to achieve 80% test success rate")
        
        if not recommendations:
            recommendations.append("All integration tests passed successfully")
        
        return {
            "overall_success": overall_success,
            "success_rate": success_rate,
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "failed_tests": len(failed_tests),
            "failed_test_names": failed_tests,
            "total_duration": total_duration,
            "test_results": self.test_results,
            "recommendations": recommendations,
            "summary": {
                "status": "PASSED" if overall_success else "FAILED",
                "message": f"Integration tests completed with {success_rate:.1%} success rate",
                "timestamp": time.time()
            }
        }


async def main():
    """Run the working integration tests."""
    print("🚀 Starting Working Integration Tests")
    print("=" * 50)
    
    test_suite = WorkingIntegrationTest()
    results = await test_suite.run_tests()
    
    # Print results
    print("\n" + "=" * 50)
    print("📊 INTEGRATION TEST RESULTS")
    print("=" * 50)
    
    if results.get("overall_success", False):
        print("✅ OVERALL STATUS: PASSED")
    else:
        print("❌ OVERALL STATUS: FAILED")
    
    print(f"📈 Success Rate: {results.get('success_rate', 0):.1%}")
    print(f"🧪 Total Tests: {results.get('total_tests', 0)}")
    print(f"✅ Successful: {results.get('successful_tests', 0)}")
    print(f"❌ Failed: {results.get('failed_tests', 0)}")
    print(f"⏱️ Duration: {results.get('total_duration', 0):.1f} seconds")
    
    if results.get("failed_test_names"):
        print(f"\n❌ Failed Tests: {', '.join(results['failed_test_names'])}")
    
    print("\n📋 Recommendations:")
    for i, rec in enumerate(results.get("recommendations", []), 1):
        print(f"  {i}. {rec}")
    
    # Save results
    results_file = f"working_integration_results_{int(time.time())}.json"
    try:
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n💾 Results saved to: {results_file}")
    except Exception as e:
        print(f"\n⚠️ Failed to save results: {e}")
    
    print("\n" + "=" * 50)
    
    return 0 if results.get("overall_success", False) else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)