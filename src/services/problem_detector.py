"""
Automated problem detection and resolution suggestions.
"""

import asyncio
import logging
import os
import psutil
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from .diagnostic_service import DiagnosticService, DiagnosticIssue, DiagnosticLevel, ComponentType

logger = logging.getLogger(__name__)


class ProblemSeverity(Enum):
    """Problem severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AutoFixSuggestion:
    """Represents an automatic fix suggestion."""
    problem_id: str
    title: str
    description: str
    fix_command: str
    risk_level: str
    estimated_time: str
    prerequisites: List[str]
    success_criteria: List[str]
    rollback_command: Optional[str] = None


@dataclass
class DetectedProblem:
    """Represents a detected system problem."""
    id: str
    title: str
    description: str
    severity: ProblemSeverity
    component: str
    detected_at: datetime
    symptoms: List[str]
    root_causes: List[str]
    impact: str
    auto_fix_available: bool
    manual_steps: List[str]
    monitoring_metrics: Dict[str, Any]


class ProblemDetector:
    """Service for automated problem detection and resolution suggestions."""

    def __init__(self, diagnostic_service: DiagnosticService):
        self.diagnostic_service = diagnostic_service
        self.detection_rules = self._build_detection_rules()
        self.auto_fix_catalog = self._build_auto_fix_catalog()
        self.problem_history = []
        self.monitoring_thresholds = self._build_monitoring_thresholds()

    def _build_detection_rules(self) -> Dict[str, Dict[str, Any]]:
        """Build problem detection rules."""
        return {
            "memory_leak_detected": {
                "title": "Memory Leak Detected",
                "description": "System memory usage is consistently increasing over time",
                "severity": ProblemSeverity.HIGH,
                "component": "system",
                "detection_logic": self._detect_memory_leak,
                "symptoms": [
                    "Memory usage increasing over time",
                    "System becoming slower",
                    "Out of memory errors"
                ],
                "root_causes": [
                    "Application memory leaks",
                    "Unclosed database connections",
                    "Large object retention",
                    "Memory-intensive operations"
                ],
                "impact": "System performance degradation and potential crashes"
            },
            "database_connection_pool_exhausted": {
                "title": "Database Connection Pool Exhausted",
                "description": "Database connection pool is running out of available connections",
                "severity": ProblemSeverity.CRITICAL,
                "component": "database",
                "detection_logic": self._detect_connection_pool_exhaustion,
                "symptoms": [
                    "Database connection timeouts",
                    "Slow database queries",
                    "Connection refused errors"
                ],
                "root_causes": [
                    "Too many concurrent requests",
                    "Long-running transactions",
                    "Connection leaks",
                    "Insufficient pool size"
                ],
                "impact": "Application unable to access database, service disruption"
            },
            "disk_io_bottleneck": {
                "title": "Disk I/O Bottleneck",
                "description": "High disk I/O wait times affecting system performance",
                "severity": ProblemSeverity.MEDIUM,
                "component": "system",
                "detection_logic": self._detect_disk_io_bottleneck,
                "symptoms": [
                    "High disk I/O wait times",
                    "Slow file operations",
                    "System responsiveness issues"
                ],
                "root_causes": [
                    "Insufficient disk performance",
                    "Heavy concurrent I/O operations",
                    "Fragmented disk",
                    "Large file operations"
                ],
                "impact": "Reduced system performance and user experience"
            },
            "embedding_model_performance_degraded": {
                "title": "Embedding Model Performance Degraded",
                "description": "CodeBERT embedding generation is taking longer than expected",
                "severity": ProblemSeverity.MEDIUM,
                "component": "embedding_system",
                "detection_logic": self._detect_embedding_performance_issues,
                "symptoms": [
                    "Slow embedding generation",
                    "Indexing operations timing out",
                    "High CPU usage during embedding"
                ],
                "root_causes": [
                    "Insufficient GPU/CPU resources",
                    "Model not optimized",
                    "Large batch sizes",
                    "Memory constraints"
                ],
                "impact": "Slower repository indexing and search functionality"
            },
            "chromadb_index_corruption": {
                "title": "ChromaDB Index Corruption",
                "description": "ChromaDB vector index appears to be corrupted or inconsistent",
                "severity": ProblemSeverity.HIGH,
                "component": "chromadb",
                "detection_logic": self._detect_chromadb_corruption,
                "symptoms": [
                    "Inconsistent search results",
                    "ChromaDB errors",
                    "Missing or corrupted vectors"
                ],
                "root_causes": [
                    "Unexpected shutdown during write operations",
                    "Disk corruption",
                    "Version compatibility issues",
                    "Concurrent write conflicts"
                ],
                "impact": "Inaccurate search results and potential data loss"
            },
            "neo4j_query_performance_degraded": {
                "title": "Neo4j Query Performance Degraded",
                "description": "Neo4j queries are taking significantly longer than baseline",
                "severity": ProblemSeverity.MEDIUM,
                "component": "neo4j",
                "detection_logic": self._detect_neo4j_performance_issues,
                "symptoms": [
                    "Slow graph queries",
                    "High Neo4j CPU usage",
                    "Query timeouts"
                ],
                "root_causes": [
                    "Missing or outdated indexes",
                    "Inefficient query patterns",
                    "Large dataset growth",
                    "Memory constraints"
                ],
                "impact": "Slower dependency analysis and graph operations"
            }
        }

    def _build_auto_fix_catalog(self) -> Dict[str, AutoFixSuggestion]:
        """Build catalog of automatic fixes."""
        return {
            "restart_chromadb_service": AutoFixSuggestion(
                problem_id="chromadb_connection_failed",
                title="Restart ChromaDB Service",
                description="Restart the ChromaDB service to resolve connection issues",
                fix_command="docker restart chromadb || systemctl restart chromadb",
                risk_level="low",
                estimated_time="30 seconds",
                prerequisites=["Docker or systemd access"],
                success_criteria=["ChromaDB health check passes", "Connection established"],
                rollback_command="docker stop chromadb && docker start chromadb"
            ),
            "clear_chromadb_cache": AutoFixSuggestion(
                problem_id="chromadb_index_corruption",
                title="Clear ChromaDB Cache",
                description="Clear ChromaDB cache and rebuild indexes",
                fix_command="rm -rf /tmp/chromadb_cache && docker exec chromadb chroma reset",
                risk_level="medium",
                estimated_time="5 minutes",
                prerequisites=["ChromaDB admin access", "Backup available"],
                success_criteria=["Cache cleared", "Indexes rebuilt", "Search results consistent"],
                rollback_command="Restore from backup if available"
            ),
            "optimize_neo4j_indexes": AutoFixSuggestion(
                problem_id="neo4j_query_performance_degraded",
                title="Optimize Neo4j Indexes",
                description="Create missing indexes and update statistics",
                fix_command="cypher-shell -u neo4j -p password < optimize_indexes.cypher",
                risk_level="low",
                estimated_time="2 minutes",
                prerequisites=["Neo4j admin access"],
                success_criteria=["Indexes created", "Query performance improved"],
                rollback_command="DROP INDEX IF EXISTS index_name"
            ),
            "cleanup_temp_files": AutoFixSuggestion(
                problem_id="disk_space_low",
                title="Clean Up Temporary Files",
                description="Remove temporary files and logs to free disk space",
                fix_command="find /tmp -type f -atime +7 -delete && find ./logs -name '*.log' -mtime +30 -delete",
                risk_level="low",
                estimated_time="1 minute",
                prerequisites=["File system access"],
                success_criteria=["Disk space freed", "Temporary files removed"],
                rollback_command="None (files are temporary)"
            ),
            "restart_application": AutoFixSuggestion(
                problem_id="memory_leak_detected",
                title="Restart Application",
                description="Restart the application to clear memory leaks",
                fix_command="systemctl restart codebase-rag || docker-compose restart",
                risk_level="medium",
                estimated_time="2 minutes",
                prerequisites=["Service restart permissions"],
                success_criteria=["Application restarted", "Memory usage normalized"],
                rollback_command="Check logs and restart if needed"
            )
        }

    def _build_monitoring_thresholds(self) -> Dict[str, Dict[str, Any]]:
        """Build monitoring thresholds for problem detection."""
        return {
            "memory_usage": {
                "warning": 80.0,
                "critical": 90.0,
                "trend_window": 300,  # 5 minutes
                "trend_threshold": 5.0  # 5% increase
            },
            "cpu_usage": {
                "warning": 80.0,
                "critical": 95.0,
                "sustained_duration": 300  # 5 minutes
            },
            "disk_usage": {
                "warning": 85.0,
                "critical": 95.0
            },
            "query_response_time": {
                "chromadb_warning": 2.0,  # seconds
                "chromadb_critical": 5.0,
                "neo4j_warning": 1.0,
                "neo4j_critical": 3.0
            },
            "connection_pool": {
                "warning_ratio": 0.8,  # 80% of pool used
                "critical_ratio": 0.95  # 95% of pool used
            }
        }

    async def detect_problems(self, 
                            chroma_client=None, 
                            neo4j_client=None, 
                            processor=None,
                            embedding_client=None) -> List[DetectedProblem]:
        """Run automated problem detection."""
        detected_problems = []
        
        try:
            # Run all detection rules
            for rule_id, rule in self.detection_rules.items():
                try:
                    detection_result = await rule["detection_logic"](
                        chroma_client, neo4j_client, processor, embedding_client
                    )
                    
                    if detection_result["detected"]:
                        problem = DetectedProblem(
                            id=rule_id,
                            title=rule["title"],
                            description=rule["description"],
                            severity=rule["severity"],
                            component=rule["component"],
                            detected_at=datetime.now(),
                            symptoms=rule["symptoms"],
                            root_causes=rule["root_causes"],
                            impact=rule["impact"],
                            auto_fix_available=rule_id in self.auto_fix_catalog,
                            manual_steps=detection_result.get("manual_steps", []),
                            monitoring_metrics=detection_result.get("metrics", {})
                        )
                        detected_problems.append(problem)
                        
                except Exception as e:
                    logger.error(f"Error in detection rule {rule_id}: {e}")
                    continue
            
            # Store in history
            self.problem_history.extend(detected_problems)
            
            # Limit history size
            if len(self.problem_history) > 1000:
                self.problem_history = self.problem_history[-1000:]
            
            return detected_problems
            
        except Exception as e:
            logger.error(f"Problem detection failed: {e}")
            return []

    async def _detect_memory_leak(self, chroma_client, neo4j_client, processor, embedding_client) -> Dict[str, Any]:
        """Detect memory leak patterns."""
        try:
            memory = psutil.virtual_memory()
            current_usage = memory.percent
            
            # Simple heuristic: if memory usage is very high, flag as potential leak
            if current_usage > self.monitoring_thresholds["memory_usage"]["critical"]:
                return {
                    "detected": True,
                    "metrics": {
                        "current_memory_usage": current_usage,
                        "available_memory": memory.available,
                        "threshold": self.monitoring_thresholds["memory_usage"]["critical"]
                    },
                    "manual_steps": [
                        "Monitor memory usage over time",
                        "Identify memory-intensive processes",
                        "Check for memory leaks in application code",
                        "Consider restarting services"
                    ]
                }
            
            return {"detected": False}
            
        except Exception as e:
            logger.error(f"Memory leak detection failed: {e}")
            return {"detected": False}

    async def _detect_connection_pool_exhaustion(self, chroma_client, neo4j_client, processor, embedding_client) -> Dict[str, Any]:
        """Detect database connection pool exhaustion."""
        try:
            # This is a simplified check - in practice, you'd query actual connection pool metrics
            connection_count = len(psutil.net_connections())
            
            # Heuristic: if there are too many connections, flag as potential exhaustion
            if connection_count > 1000:  # Arbitrary threshold
                return {
                    "detected": True,
                    "metrics": {
                        "active_connections": connection_count,
                        "threshold": 1000
                    },
                    "manual_steps": [
                        "Check database connection pool configuration",
                        "Monitor active connections",
                        "Look for connection leaks",
                        "Consider increasing pool size"
                    ]
                }
            
            return {"detected": False}
            
        except Exception as e:
            logger.error(f"Connection pool detection failed: {e}")
            return {"detected": False}

    async def _detect_disk_io_bottleneck(self, chroma_client, neo4j_client, processor, embedding_client) -> Dict[str, Any]:
        """Detect disk I/O bottlenecks."""
        try:
            # Get disk I/O statistics
            disk_io = psutil.disk_io_counters()
            
            if disk_io:
                # Simple heuristic based on I/O wait time
                # In practice, you'd need more sophisticated monitoring
                return {"detected": False}  # Placeholder
            
            return {"detected": False}
            
        except Exception as e:
            logger.error(f"Disk I/O detection failed: {e}")
            return {"detected": False}

    async def _detect_embedding_performance_issues(self, chroma_client, neo4j_client, processor, embedding_client) -> Dict[str, Any]:
        """Detect embedding model performance issues."""
        try:
            if not embedding_client:
                return {"detected": False}
            
            # Test embedding generation time
            start_time = time.time()
            test_code = "def test_function(): return 'test'"
            
            try:
                await embedding_client.generate_embedding(test_code)
                generation_time = time.time() - start_time
                
                # If embedding takes too long, flag as performance issue
                if generation_time > 5.0:  # 5 seconds threshold
                    return {
                        "detected": True,
                        "metrics": {
                            "embedding_generation_time": generation_time,
                            "threshold": 5.0
                        },
                        "manual_steps": [
                            "Check system resources (CPU/GPU)",
                            "Monitor embedding model performance",
                            "Consider model optimization",
                            "Review batch sizes"
                        ]
                    }
                
            except Exception as e:
                return {
                    "detected": True,
                    "metrics": {"error": str(e)},
                    "manual_steps": [
                        "Check embedding model availability",
                        "Verify model dependencies",
                        "Review embedding client configuration"
                    ]
                }
            
            return {"detected": False}
            
        except Exception as e:
            logger.error(f"Embedding performance detection failed: {e}")
            return {"detected": False}

    async def _detect_chromadb_corruption(self, chroma_client, neo4j_client, processor, embedding_client) -> Dict[str, Any]:
        """Detect ChromaDB index corruption."""
        try:
            if not chroma_client:
                return {"detected": False}
            
            # Test basic ChromaDB operations
            try:
                health_check = await chroma_client.health_check()
                
                if health_check.get("status") != "healthy":
                    return {
                        "detected": True,
                        "metrics": {"health_status": health_check.get("status")},
                        "manual_steps": [
                            "Check ChromaDB logs for errors",
                            "Verify ChromaDB data integrity",
                            "Consider rebuilding indexes",
                            "Restore from backup if necessary"
                        ]
                    }
                
            except Exception as e:
                return {
                    "detected": True,
                    "metrics": {"error": str(e)},
                    "manual_steps": [
                        "Check ChromaDB service status",
                        "Review ChromaDB configuration",
                        "Verify data directory permissions"
                    ]
                }
            
            return {"detected": False}
            
        except Exception as e:
            logger.error(f"ChromaDB corruption detection failed: {e}")
            return {"detected": False}

    async def _detect_neo4j_performance_issues(self, chroma_client, neo4j_client, processor, embedding_client) -> Dict[str, Any]:
        """Detect Neo4j performance issues."""
        try:
            if not neo4j_client:
                return {"detected": False}
            
            # Test basic Neo4j query performance
            start_time = time.time()
            
            try:
                # Simple test query
                from ..core.neo4j_client import GraphQuery
                test_query = GraphQuery(cypher="RETURN 1 as test", read_only=True)
                await neo4j_client.execute_query(test_query)
                
                query_time = time.time() - start_time
                
                # If query takes too long, flag as performance issue
                if query_time > self.monitoring_thresholds["query_response_time"]["neo4j_critical"]:
                    return {
                        "detected": True,
                        "metrics": {
                            "query_time": query_time,
                            "threshold": self.monitoring_thresholds["query_response_time"]["neo4j_critical"]
                        },
                        "manual_steps": [
                            "Check Neo4j indexes",
                            "Review query performance",
                            "Monitor Neo4j resources",
                            "Consider query optimization"
                        ]
                    }
                
            except Exception as e:
                return {
                    "detected": True,
                    "metrics": {"error": str(e)},
                    "manual_steps": [
                        "Check Neo4j service status",
                        "Verify Neo4j connectivity",
                        "Review Neo4j logs"
                    ]
                }
            
            return {"detected": False}
            
        except Exception as e:
            logger.error(f"Neo4j performance detection failed: {e}")
            return {"detected": False}

    async def get_auto_fix_suggestions(self, problems: List[DetectedProblem]) -> List[AutoFixSuggestion]:
        """Get automatic fix suggestions for detected problems."""
        suggestions = []
        
        for problem in problems:
            if problem.auto_fix_available and problem.id in self.auto_fix_catalog:
                suggestion = self.auto_fix_catalog[problem.id]
                suggestions.append(suggestion)
        
        return suggestions

    async def generate_problem_report(self, problems: List[DetectedProblem]) -> Dict[str, Any]:
        """Generate comprehensive problem report."""
        if not problems:
            return {
                "status": "healthy",
                "message": "No problems detected",
                "timestamp": datetime.now().isoformat(),
                "problems": [],
                "auto_fixes": [],
                "recommendations": ["System is operating normally"]
            }
        
        # Categorize problems by severity
        critical_problems = [p for p in problems if p.severity == ProblemSeverity.CRITICAL]
        high_problems = [p for p in problems if p.severity == ProblemSeverity.HIGH]
        medium_problems = [p for p in problems if p.severity == ProblemSeverity.MEDIUM]
        low_problems = [p for p in problems if p.severity == ProblemSeverity.LOW]
        
        # Get auto-fix suggestions
        auto_fixes = await self.get_auto_fix_suggestions(problems)
        
        # Generate recommendations
        recommendations = []
        if critical_problems:
            recommendations.append(f"Address {len(critical_problems)} critical problems immediately")
        if high_problems:
            recommendations.append(f"Resolve {len(high_problems)} high-priority problems")
        if auto_fixes:
            recommendations.append(f"Consider applying {len(auto_fixes)} available automatic fixes")
        
        return {
            "status": "problems_detected",
            "message": f"{len(problems)} problems detected",
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_problems": len(problems),
                "critical": len(critical_problems),
                "high": len(high_problems),
                "medium": len(medium_problems),
                "low": len(low_problems),
                "auto_fixable": len(auto_fixes)
            },
            "problems": [
                {
                    "id": p.id,
                    "title": p.title,
                    "description": p.description,
                    "severity": p.severity.value,
                    "component": p.component,
                    "detected_at": p.detected_at.isoformat(),
                    "symptoms": p.symptoms,
                    "root_causes": p.root_causes,
                    "impact": p.impact,
                    "auto_fix_available": p.auto_fix_available,
                    "manual_steps": p.manual_steps,
                    "monitoring_metrics": p.monitoring_metrics
                }
                for p in problems
            ],
            "auto_fixes": [
                {
                    "problem_id": fix.problem_id,
                    "title": fix.title,
                    "description": fix.description,
                    "fix_command": fix.fix_command,
                    "risk_level": fix.risk_level,
                    "estimated_time": fix.estimated_time,
                    "prerequisites": fix.prerequisites,
                    "success_criteria": fix.success_criteria,
                    "rollback_command": fix.rollback_command
                }
                for fix in auto_fixes
            ],
            "recommendations": recommendations
        }