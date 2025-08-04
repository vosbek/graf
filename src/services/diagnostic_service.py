"""
Diagnostic and troubleshooting service for system health monitoring.
"""

import asyncio
import json
import os
import platform
import psutil
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum

import logging
logger = logging.getLogger(__name__)


class DiagnosticLevel(Enum):
    """Diagnostic severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ComponentType(Enum):
    """System component types."""
    DATABASE = "database"
    SERVICE = "service"
    NETWORK = "network"
    FILESYSTEM = "filesystem"
    CONFIGURATION = "configuration"
    PERFORMANCE = "performance"


@dataclass
class DiagnosticIssue:
    """Represents a diagnostic issue."""
    id: str
    component: str
    component_type: ComponentType
    level: DiagnosticLevel
    title: str
    description: str
    detected_at: datetime
    remediation_steps: List[str]
    auto_fixable: bool = False
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['component_type'] = self.component_type.value
        data['level'] = self.level.value
        data['detected_at'] = self.detected_at.isoformat()
        return data


@dataclass
class SystemDiagnostics:
    """Complete system diagnostic report."""
    timestamp: datetime
    overall_health: str
    health_score: float
    issues: List[DiagnosticIssue]
    system_info: Dict[str, Any]
    component_status: Dict[str, Dict[str, Any]]
    performance_metrics: Dict[str, Any]
    recommendations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'overall_health': self.overall_health,
            'health_score': self.health_score,
            'issues': [issue.to_dict() for issue in self.issues],
            'system_info': self.system_info,
            'component_status': self.component_status,
            'performance_metrics': self.performance_metrics,
            'recommendations': self.recommendations
        }


class DiagnosticService:
    """Service for system diagnostics and troubleshooting."""

    def __init__(self):
        self.known_issues = {}
        self.remediation_database = self._build_remediation_database()
        self.performance_history = []
        self.max_history_size = 100

    def _build_remediation_database(self) -> Dict[str, Dict[str, Any]]:
        """Build database of known issues and their remediation steps."""
        return {
            "chromadb_connection_failed": {
                "title": "ChromaDB Connection Failed",
                "description": "Unable to connect to ChromaDB vector database",
                "remediation_steps": [
                    "Check if ChromaDB service is running",
                    "Verify CHROMADB_HOST and CHROMADB_PORT environment variables",
                    "Test network connectivity to ChromaDB host",
                    "Check ChromaDB service logs for errors",
                    "Restart ChromaDB service if necessary"
                ],
                "auto_fixable": False,
                "component_type": ComponentType.DATABASE
            },
            "neo4j_connection_failed": {
                "title": "Neo4j Connection Failed",
                "description": "Unable to connect to Neo4j graph database",
                "remediation_steps": [
                    "Check if Neo4j service is running",
                    "Verify NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD environment variables",
                    "Test Neo4j authentication credentials",
                    "Check Neo4j service status and logs",
                    "Verify Neo4j bolt port (7687) is accessible"
                ],
                "auto_fixable": False,
                "component_type": ComponentType.DATABASE
            },
            "embedding_model_failed": {
                "title": "CodeBERT Embedding Model Failed",
                "description": "CodeBERT embedding model failed to load or initialize",
                "remediation_steps": [
                    "Check if PyTorch is properly installed",
                    "Verify transformers library version compatibility",
                    "Check available system memory (model requires ~1GB)",
                    "Verify internet connectivity for model download",
                    "Clear model cache and retry: rm -rf ~/.cache/huggingface/transformers/"
                ],
                "auto_fixable": False,
                "component_type": ComponentType.SERVICE
            },
            "high_memory_usage": {
                "title": "High Memory Usage",
                "description": "System memory usage is above recommended threshold",
                "remediation_steps": [
                    "Identify memory-intensive processes",
                    "Restart services to free memory leaks",
                    "Consider increasing system memory",
                    "Optimize database connection pools",
                    "Clear application caches"
                ],
                "auto_fixable": False,
                "component_type": ComponentType.PERFORMANCE
            },
            "high_cpu_usage": {
                "title": "High CPU Usage",
                "description": "System CPU usage is above recommended threshold",
                "remediation_steps": [
                    "Identify CPU-intensive processes",
                    "Check for runaway background tasks",
                    "Optimize database queries",
                    "Consider scaling resources",
                    "Review indexing operations"
                ],
                "auto_fixable": False,
                "component_type": ComponentType.PERFORMANCE
            },
            "disk_space_low": {
                "title": "Low Disk Space",
                "description": "Available disk space is below recommended threshold",
                "remediation_steps": [
                    "Clean up temporary files and logs",
                    "Remove old repository clones",
                    "Clear database transaction logs",
                    "Archive old data",
                    "Increase disk space"
                ],
                "auto_fixable": True,
                "component_type": ComponentType.FILESYSTEM
            },
            "configuration_missing": {
                "title": "Missing Configuration",
                "description": "Required configuration variables are missing",
                "remediation_steps": [
                    "Check .env file exists and is readable",
                    "Verify all required environment variables are set",
                    "Copy .env.example to .env if needed",
                    "Restart application after configuration changes"
                ],
                "auto_fixable": False,
                "component_type": ComponentType.CONFIGURATION
            }
        }

    async def run_comprehensive_diagnostics(self, 
                                          chroma_client=None, 
                                          neo4j_client=None, 
                                          processor=None,
                                          embedding_client=None) -> SystemDiagnostics:
        """Run comprehensive system diagnostics."""
        start_time = time.time()
        issues = []
        component_status = {}
        
        # System information
        system_info = await self._collect_system_info()
        
        # Performance metrics
        performance_metrics = await self._collect_performance_metrics()
        
        # Database diagnostics
        if chroma_client:
            chroma_issues, chroma_status = await self._diagnose_chromadb(chroma_client)
            issues.extend(chroma_issues)
            component_status['chromadb'] = chroma_status
        
        if neo4j_client:
            neo4j_issues, neo4j_status = await self._diagnose_neo4j(neo4j_client)
            issues.extend(neo4j_issues)
            component_status['neo4j'] = neo4j_status
        
        # Service diagnostics
        if processor:
            processor_issues, processor_status = await self._diagnose_processor(processor)
            issues.extend(processor_issues)
            component_status['processor'] = processor_status
        
        if embedding_client:
            embedding_issues, embedding_status = await self._diagnose_embedding_system(embedding_client)
            issues.extend(embedding_issues)
            component_status['embedding_system'] = embedding_status
        
        # System resource diagnostics
        resource_issues = await self._diagnose_system_resources()
        issues.extend(resource_issues)
        
        # Configuration diagnostics
        config_issues = await self._diagnose_configuration()
        issues.extend(config_issues)
        
        # Calculate health score
        health_score = self._calculate_health_score(issues, performance_metrics)
        overall_health = self._determine_overall_health(health_score, issues)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(issues, performance_metrics)
        
        # Store performance history
        self.performance_history.append({
            'timestamp': datetime.now(),
            'health_score': health_score,
            'issue_count': len(issues),
            'critical_issues': len([i for i in issues if i.level == DiagnosticLevel.CRITICAL])
        })
        
        # Limit history size
        if len(self.performance_history) > self.max_history_size:
            self.performance_history = self.performance_history[-self.max_history_size:]
        
        diagnostics_time = time.time() - start_time
        performance_metrics['diagnostics_time'] = diagnostics_time
        
        return SystemDiagnostics(
            timestamp=datetime.now(),
            overall_health=overall_health,
            health_score=health_score,
            issues=issues,
            system_info=system_info,
            component_status=component_status,
            performance_metrics=performance_metrics,
            recommendations=recommendations
        )

    async def _collect_system_info(self) -> Dict[str, Any]:
        """Collect system information."""
        try:
            return {
                'platform': platform.platform(),
                'python_version': platform.python_version(),
                'cpu_count': psutil.cpu_count(),
                'memory_total': psutil.virtual_memory().total,
                'disk_total': psutil.disk_usage('/').total,
                'boot_time': datetime.fromtimestamp(psutil.boot_time()).isoformat(),
                'hostname': platform.node(),
                'architecture': platform.architecture()[0]
            }
        except Exception as e:
            logger.error(f"Failed to collect system info: {e}")
            return {'error': str(e)}

    async def _collect_performance_metrics(self) -> Dict[str, Any]:
        """Collect current performance metrics."""
        try:
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': memory.percent,
                'memory_available': memory.available,
                'disk_percent': (disk.used / disk.total) * 100,
                'disk_free': disk.free,
                'load_average': os.getloadavg() if hasattr(os, 'getloadavg') else None,
                'process_count': len(psutil.pids()),
                'network_connections': len(psutil.net_connections())
            }
        except Exception as e:
            logger.error(f"Failed to collect performance metrics: {e}")
            return {'error': str(e)}

    async def _diagnose_chromadb(self, chroma_client) -> tuple[List[DiagnosticIssue], Dict[str, Any]]:
        """Diagnose ChromaDB health."""
        issues = []
        status = {'component': 'chromadb', 'healthy': True}
        
        try:
            # Test connection
            health_check = await chroma_client.health_check()
            status['health_check'] = health_check
            
            if health_check.get('status') != 'healthy':
                issues.append(self._create_issue(
                    'chromadb_unhealthy',
                    'chromadb',
                    ComponentType.DATABASE,
                    DiagnosticLevel.ERROR,
                    'ChromaDB Unhealthy',
                    f"ChromaDB health check failed: {health_check.get('error', 'Unknown error')}",
                    self.remediation_database.get('chromadb_connection_failed', {}).get('remediation_steps', [])
                ))
                status['healthy'] = False
            
            # Test basic operations
            try:
                stats = await chroma_client.get_statistics()
                status['statistics'] = stats
                
                # Check for performance issues
                if stats.get('performance_metrics', {}).get('average_query_time', 0) > 2.0:
                    issues.append(self._create_issue(
                        'chromadb_slow_queries',
                        'chromadb',
                        ComponentType.PERFORMANCE,
                        DiagnosticLevel.WARNING,
                        'ChromaDB Slow Queries',
                        'ChromaDB queries are taking longer than expected',
                        [
                            'Check ChromaDB resource usage',
                            'Optimize query patterns',
                            'Consider increasing ChromaDB memory',
                            'Review index configuration'
                        ]
                    ))
                
            except Exception as e:
                issues.append(self._create_issue(
                    'chromadb_stats_failed',
                    'chromadb',
                    ComponentType.DATABASE,
                    DiagnosticLevel.WARNING,
                    'ChromaDB Statistics Failed',
                    f'Failed to retrieve ChromaDB statistics: {str(e)}',
                    ['Check ChromaDB service logs', 'Verify ChromaDB API accessibility']
                ))
                
        except Exception as e:
            issues.append(self._create_issue(
                'chromadb_connection_failed',
                'chromadb',
                ComponentType.DATABASE,
                DiagnosticLevel.CRITICAL,
                'ChromaDB Connection Failed',
                f'Failed to connect to ChromaDB: {str(e)}',
                self.remediation_database.get('chromadb_connection_failed', {}).get('remediation_steps', [])
            ))
            status['healthy'] = False
            status['error'] = str(e)
        
        return issues, status

    async def _diagnose_neo4j(self, neo4j_client) -> tuple[List[DiagnosticIssue], Dict[str, Any]]:
        """Diagnose Neo4j health."""
        issues = []
        status = {'component': 'neo4j', 'healthy': True}
        
        try:
            # Test connection
            health_check = await neo4j_client.health_check()
            status['health_check'] = health_check
            
            if health_check.get('status') != 'healthy':
                issues.append(self._create_issue(
                    'neo4j_unhealthy',
                    'neo4j',
                    ComponentType.DATABASE,
                    DiagnosticLevel.ERROR,
                    'Neo4j Unhealthy',
                    f"Neo4j health check failed: {health_check.get('error', 'Unknown error')}",
                    self.remediation_database.get('neo4j_connection_failed', {}).get('remediation_steps', [])
                ))
                status['healthy'] = False
            
            # Test basic operations
            try:
                stats = await neo4j_client.get_statistics()
                status['statistics'] = stats
                
                # Check for performance issues
                if stats.get('performance_metrics', {}).get('average_query_time', 0) > 1.0:
                    issues.append(self._create_issue(
                        'neo4j_slow_queries',
                        'neo4j',
                        ComponentType.PERFORMANCE,
                        DiagnosticLevel.WARNING,
                        'Neo4j Slow Queries',
                        'Neo4j queries are taking longer than expected',
                        [
                            'Check Neo4j resource usage',
                            'Review query performance',
                            'Consider adding indexes',
                            'Optimize Cypher queries'
                        ]
                    ))
                
            except Exception as e:
                issues.append(self._create_issue(
                    'neo4j_stats_failed',
                    'neo4j',
                    ComponentType.DATABASE,
                    DiagnosticLevel.WARNING,
                    'Neo4j Statistics Failed',
                    f'Failed to retrieve Neo4j statistics: {str(e)}',
                    ['Check Neo4j service logs', 'Verify Neo4j connectivity']
                ))
                
        except Exception as e:
            issues.append(self._create_issue(
                'neo4j_connection_failed',
                'neo4j',
                ComponentType.DATABASE,
                DiagnosticLevel.CRITICAL,
                'Neo4j Connection Failed',
                f'Failed to connect to Neo4j: {str(e)}',
                self.remediation_database.get('neo4j_connection_failed', {}).get('remediation_steps', [])
            ))
            status['healthy'] = False
            status['error'] = str(e)
        
        return issues, status

    async def _diagnose_processor(self, processor) -> tuple[List[DiagnosticIssue], Dict[str, Any]]:
        """Diagnose repository processor health."""
        issues = []
        status = {'component': 'processor', 'healthy': True}
        
        try:
            # Test processor health
            health_check = await processor.health_check()
            status['health_check'] = health_check
            
            if health_check.get('status') != 'healthy':
                issues.append(self._create_issue(
                    'processor_unhealthy',
                    'processor',
                    ComponentType.SERVICE,
                    DiagnosticLevel.ERROR,
                    'Repository Processor Unhealthy',
                    f"Processor health check failed: {health_check.get('error', 'Unknown error')}",
                    [
                        'Check processor dependencies',
                        'Verify database connections',
                        'Review processor configuration',
                        'Check system resources'
                    ]
                ))
                status['healthy'] = False
            
            # Check processing statistics
            try:
                stats = await processor.get_processing_statistics()
                status['statistics'] = stats
                
                # Check success rate
                success_rate = stats.get('success_rate', 1.0)
                if success_rate < 0.8:
                    issues.append(self._create_issue(
                        'processor_low_success_rate',
                        'processor',
                        ComponentType.SERVICE,
                        DiagnosticLevel.WARNING,
                        'Low Processing Success Rate',
                        f'Repository processing success rate is {success_rate:.1%}',
                        [
                            'Review failed repository logs',
                            'Check repository accessibility',
                            'Verify parsing configurations',
                            'Monitor system resources during processing'
                        ]
                    ))
                
            except Exception as e:
                issues.append(self._create_issue(
                    'processor_stats_failed',
                    'processor',
                    ComponentType.SERVICE,
                    DiagnosticLevel.WARNING,
                    'Processor Statistics Failed',
                    f'Failed to retrieve processor statistics: {str(e)}',
                    ['Check processor service logs']
                ))
                
        except Exception as e:
            issues.append(self._create_issue(
                'processor_failed',
                'processor',
                ComponentType.SERVICE,
                DiagnosticLevel.CRITICAL,
                'Repository Processor Failed',
                f'Failed to check processor: {str(e)}',
                [
                    'Restart repository processor service',
                    'Check processor dependencies',
                    'Verify configuration'
                ]
            ))
            status['healthy'] = False
            status['error'] = str(e)
        
        return issues, status

    async def _diagnose_embedding_system(self, embedding_client) -> tuple[List[DiagnosticIssue], Dict[str, Any]]:
        """Diagnose CodeBERT embedding system health."""
        issues = []
        status = {'component': 'embedding_system', 'healthy': True}
        
        try:
            # Test embedding system health
            health_check = await embedding_client.health_check()
            status['health_check'] = health_check
            
            if health_check.get('status') != 'healthy':
                issues.append(self._create_issue(
                    'embedding_system_unhealthy',
                    'embedding_system',
                    ComponentType.SERVICE,
                    DiagnosticLevel.ERROR,
                    'CodeBERT Embedding System Unhealthy',
                    f"Embedding system health check failed: {health_check.get('error', 'Unknown error')}",
                    self.remediation_database.get('embedding_model_failed', {}).get('remediation_steps', [])
                ))
                status['healthy'] = False
            
            # Test embedding generation
            try:
                test_code = "def hello_world(): return 'Hello, World!'"
                embedding_result = await embedding_client.generate_embedding(test_code)
                
                if not embedding_result or len(embedding_result) == 0:
                    issues.append(self._create_issue(
                        'embedding_generation_failed',
                        'embedding_system',
                        ComponentType.SERVICE,
                        DiagnosticLevel.ERROR,
                        'Embedding Generation Failed',
                        'Failed to generate embeddings for test code',
                        self.remediation_database.get('embedding_model_failed', {}).get('remediation_steps', [])
                    ))
                    status['healthy'] = False
                else:
                    status['test_embedding_size'] = len(embedding_result)
                
            except Exception as e:
                issues.append(self._create_issue(
                    'embedding_test_failed',
                    'embedding_system',
                    ComponentType.SERVICE,
                    DiagnosticLevel.WARNING,
                    'Embedding Test Failed',
                    f'Failed to test embedding generation: {str(e)}',
                    self.remediation_database.get('embedding_model_failed', {}).get('remediation_steps', [])
                ))
                
        except Exception as e:
            issues.append(self._create_issue(
                'embedding_system_failed',
                'embedding_system',
                ComponentType.SERVICE,
                DiagnosticLevel.CRITICAL,
                'CodeBERT Embedding System Failed',
                f'Failed to check embedding system: {str(e)}',
                self.remediation_database.get('embedding_model_failed', {}).get('remediation_steps', [])
            ))
            status['healthy'] = False
            status['error'] = str(e)
        
        return issues, status

    async def _diagnose_system_resources(self) -> List[DiagnosticIssue]:
        """Diagnose system resource usage."""
        issues = []
        
        try:
            # Memory usage
            memory = psutil.virtual_memory()
            if memory.percent > 85:
                level = DiagnosticLevel.CRITICAL if memory.percent > 95 else DiagnosticLevel.WARNING
                issues.append(self._create_issue(
                    'high_memory_usage',
                    'system',
                    ComponentType.PERFORMANCE,
                    level,
                    'High Memory Usage',
                    f'Memory usage is {memory.percent:.1f}%',
                    self.remediation_database.get('high_memory_usage', {}).get('remediation_steps', [])
                ))
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > 80:
                level = DiagnosticLevel.CRITICAL if cpu_percent > 95 else DiagnosticLevel.WARNING
                issues.append(self._create_issue(
                    'high_cpu_usage',
                    'system',
                    ComponentType.PERFORMANCE,
                    level,
                    'High CPU Usage',
                    f'CPU usage is {cpu_percent:.1f}%',
                    self.remediation_database.get('high_cpu_usage', {}).get('remediation_steps', [])
                ))
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            if disk_percent > 85:
                level = DiagnosticLevel.CRITICAL if disk_percent > 95 else DiagnosticLevel.WARNING
                issues.append(self._create_issue(
                    'disk_space_low',
                    'system',
                    ComponentType.FILESYSTEM,
                    level,
                    'Low Disk Space',
                    f'Disk usage is {disk_percent:.1f}%',
                    self.remediation_database.get('disk_space_low', {}).get('remediation_steps', [])
                ))
            
        except Exception as e:
            logger.error(f"Failed to diagnose system resources: {e}")
            issues.append(self._create_issue(
                'resource_check_failed',
                'system',
                ComponentType.PERFORMANCE,
                DiagnosticLevel.WARNING,
                'Resource Check Failed',
                f'Failed to check system resources: {str(e)}',
                ['Check system monitoring tools', 'Verify psutil installation']
            ))
        
        return issues

    async def _diagnose_configuration(self) -> List[DiagnosticIssue]:
        """Diagnose configuration issues."""
        issues = []
        
        # Check required environment variables
        required_vars = [
            'NEO4J_URI', 'NEO4J_USER', 'NEO4J_PASSWORD',
            'CHROMADB_HOST', 'CHROMADB_PORT'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            issues.append(self._create_issue(
                'configuration_missing',
                'configuration',
                ComponentType.CONFIGURATION,
                DiagnosticLevel.ERROR,
                'Missing Configuration Variables',
                f'Missing required environment variables: {", ".join(missing_vars)}',
                self.remediation_database.get('configuration_missing', {}).get('remediation_steps', [])
            ))
        
        # Check .env file
        if not os.path.exists('.env'):
            issues.append(self._create_issue(
                'env_file_missing',
                'configuration',
                ComponentType.CONFIGURATION,
                DiagnosticLevel.WARNING,
                'Environment File Missing',
                '.env file not found',
                [
                    'Copy .env.example to .env',
                    'Configure required environment variables',
                    'Restart application after configuration'
                ]
            ))
        
        return issues

    def _create_issue(self, issue_id: str, component: str, component_type: ComponentType,
                     level: DiagnosticLevel, title: str, description: str,
                     remediation_steps: List[str]) -> DiagnosticIssue:
        """Create a diagnostic issue."""
        return DiagnosticIssue(
            id=issue_id,
            component=component,
            component_type=component_type,
            level=level,
            title=title,
            description=description,
            detected_at=datetime.now(),
            remediation_steps=remediation_steps,
            auto_fixable=self.remediation_database.get(issue_id, {}).get('auto_fixable', False)
        )

    def _calculate_health_score(self, issues: List[DiagnosticIssue], 
                               performance_metrics: Dict[str, Any]) -> float:
        """Calculate overall system health score (0-100)."""
        base_score = 100.0
        
        # Deduct points for issues
        for issue in issues:
            if issue.level == DiagnosticLevel.CRITICAL:
                base_score -= 25
            elif issue.level == DiagnosticLevel.ERROR:
                base_score -= 15
            elif issue.level == DiagnosticLevel.WARNING:
                base_score -= 5
            # INFO issues don't affect score
        
        # Deduct points for poor performance
        cpu_percent = performance_metrics.get('cpu_percent', 0)
        if cpu_percent > 80:
            base_score -= (cpu_percent - 80) * 0.5
        
        memory_percent = performance_metrics.get('memory_percent', 0)
        if memory_percent > 80:
            base_score -= (memory_percent - 80) * 0.5
        
        disk_percent = performance_metrics.get('disk_percent', 0)
        if disk_percent > 80:
            base_score -= (disk_percent - 80) * 0.3
        
        return max(base_score, 0.0)

    def _determine_overall_health(self, health_score: float, issues: List[DiagnosticIssue]) -> str:
        """Determine overall system health status."""
        critical_issues = [i for i in issues if i.level == DiagnosticLevel.CRITICAL]
        error_issues = [i for i in issues if i.level == DiagnosticLevel.ERROR]
        
        if critical_issues:
            return "critical"
        elif error_issues or health_score < 50:
            return "unhealthy"
        elif health_score < 75:
            return "degraded"
        else:
            return "healthy"

    def _generate_recommendations(self, issues: List[DiagnosticIssue], 
                                 performance_metrics: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []
        
        # Issue-based recommendations
        critical_issues = [i for i in issues if i.level == DiagnosticLevel.CRITICAL]
        if critical_issues:
            recommendations.append(f"Address {len(critical_issues)} critical issues immediately")
        
        error_issues = [i for i in issues if i.level == DiagnosticLevel.ERROR]
        if error_issues:
            recommendations.append(f"Resolve {len(error_issues)} error-level issues")
        
        # Performance-based recommendations
        cpu_percent = performance_metrics.get('cpu_percent', 0)
        if cpu_percent > 80:
            recommendations.append("High CPU usage detected - consider scaling resources")
        
        memory_percent = performance_metrics.get('memory_percent', 0)
        if memory_percent > 80:
            recommendations.append("High memory usage detected - review memory leaks")
        
        disk_percent = performance_metrics.get('disk_percent', 0)
        if disk_percent > 80:
            recommendations.append("Low disk space - clean up unnecessary files")
        
        # General recommendations
        if not recommendations:
            recommendations.append("System is operating normally")
        
        recommendations.append("Run diagnostics regularly to maintain system health")
        
        return recommendations

    async def export_diagnostic_data(self, diagnostics: SystemDiagnostics, 
                                   format: str = 'json') -> str:
        """Export diagnostic data for support and debugging."""
        if format.lower() == 'json':
            return json.dumps(diagnostics.to_dict(), indent=2)
        elif format.lower() == 'text':
            return self._format_diagnostics_as_text(diagnostics)
        else:
            raise ValueError(f"Unsupported export format: {format}")

    def _format_diagnostics_as_text(self, diagnostics: SystemDiagnostics) -> str:
        """Format diagnostics as human-readable text."""
        lines = []
        lines.append("=== SYSTEM DIAGNOSTIC REPORT ===")
        lines.append(f"Generated: {diagnostics.timestamp}")
        lines.append(f"Overall Health: {diagnostics.overall_health.upper()}")
        lines.append(f"Health Score: {diagnostics.health_score:.1f}/100")
        lines.append("")
        
        if diagnostics.issues:
            lines.append("=== ISSUES DETECTED ===")
            for issue in diagnostics.issues:
                lines.append(f"[{issue.level.value.upper()}] {issue.title}")
                lines.append(f"  Component: {issue.component}")
                lines.append(f"  Description: {issue.description}")
                lines.append(f"  Remediation Steps:")
                for step in issue.remediation_steps:
                    lines.append(f"    - {step}")
                lines.append("")
        
        lines.append("=== SYSTEM INFORMATION ===")
        for key, value in diagnostics.system_info.items():
            lines.append(f"{key}: {value}")
        lines.append("")
        
        lines.append("=== PERFORMANCE METRICS ===")
        for key, value in diagnostics.performance_metrics.items():
            lines.append(f"{key}: {value}")
        lines.append("")
        
        if diagnostics.recommendations:
            lines.append("=== RECOMMENDATIONS ===")
            for i, rec in enumerate(diagnostics.recommendations, 1):
                lines.append(f"{i}. {rec}")
        
        return "\n".join(lines)

    async def get_performance_history(self) -> List[Dict[str, Any]]:
        """Get performance history for trending analysis."""
        return [
            {
                'timestamp': entry['timestamp'].isoformat(),
                'health_score': entry['health_score'],
                'issue_count': entry['issue_count'],
                'critical_issues': entry['critical_issues']
            }
            for entry in self.performance_history
        ]

    async def suggest_auto_fixes(self, diagnostics: SystemDiagnostics) -> List[Dict[str, Any]]:
        """Suggest automatic fixes for detected issues."""
        auto_fixes = []
        
        for issue in diagnostics.issues:
            if issue.auto_fixable:
                if issue.id == 'disk_space_low':
                    auto_fixes.append({
                        'issue_id': issue.id,
                        'title': 'Clean up temporary files',
                        'description': 'Remove temporary files and logs to free disk space',
                        'command': 'find /tmp -type f -atime +7 -delete',
                        'risk_level': 'low'
                    })
        
        return auto_fixes