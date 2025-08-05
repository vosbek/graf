"""
Shared Dependency Analysis for Cross-Repository Analysis
=======================================================

Analyzes shared libraries, Maven dependencies, and common frameworks
across multiple repositories to identify consolidation opportunities
and migration coordination requirements.

Perfect for legacy migration analysis to identify:
- Common Struts/CORBA/JSP versions across repositories
- Shared utility libraries that need coordinated updates
- Version conflicts that need resolution
- Consolidation opportunities for shared components
"""

import asyncio
import logging
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any, Tuple
import json
import statistics

from ..core.neo4j_client import Neo4jClient, GraphQuery


logger = logging.getLogger(__name__)


@dataclass
class SharedDependency:
    """Represents a dependency shared across multiple repositories."""
    artifact_id: str
    group_id: str
    versions: List[str]
    repositories: List[str]
    usage_count: int
    version_conflicts: bool
    latest_version: str
    migration_priority: str  # HIGH, MEDIUM, LOW
    framework_type: str  # struts, corba, jsp, utility, etc.


@dataclass
class VersionConflict:
    """Represents a version conflict for a shared dependency."""
    artifact_id: str
    group_id: str
    conflicting_versions: List[str]
    affected_repositories: List[str]
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    resolution_strategy: str


@dataclass
class SharedDependencyAnalysisResult:
    """Complete shared dependency analysis results."""
    total_repositories: int
    total_dependencies: int
    shared_dependencies: List[SharedDependency]
    version_conflicts: List[VersionConflict]
    framework_distribution: Dict[str, int]
    consolidation_opportunities: List[Dict[str, Any]]
    migration_recommendations: List[str]
    analysis_time: float


class SharedDependencyAnalyzer:
    """
    Analyzes shared dependencies and libraries across repositories
    for migration planning and consolidation opportunities.
    """
    
    def __init__(self, neo4j_client: Neo4jClient):
        self.neo4j_client = neo4j_client
        
        # Framework patterns for classification
        self.framework_patterns = {
            'struts': ['struts', 'org.apache.struts'],
            'corba': ['corba', 'omg.org', 'jacorb', 'org.omg'],
            'jsp': ['jsp', 'jstl', 'servlet', 'javax.servlet'],
            'spring': ['springframework', 'spring-'],
            'hibernate': ['hibernate', 'org.hibernate'],
            'apache': ['apache', 'org.apache'],
            'logging': ['log4j', 'slf4j', 'logback', 'commons-logging'],
            'testing': ['junit', 'testng', 'mockito', 'easymock'],
            'utility': ['commons-', 'guava', 'jackson']
        }
    
    async def analyze_shared_dependencies(
        self, repository_names: List[str]
    ) -> SharedDependencyAnalysisResult:
        """
        Analyze shared dependencies across multiple repositories.
        
        Args:
            repository_names: List of repository names to analyze
            
        Returns:
            SharedDependencyAnalysisResult with comprehensive analysis
        """
        start_time = asyncio.get_event_loop().time()
        logger.info(f"🔍 Starting shared dependency analysis for {len(repository_names)} repositories")
        
        # Phase 1: Gather all Maven artifacts from repositories
        logger.info("📦 Phase 1: Gathering Maven dependencies...")
        repository_dependencies = await self._gather_repository_dependencies(repository_names)
        
        # Phase 2: Identify shared dependencies
        logger.info("🔗 Phase 2: Identifying shared dependencies...")
        shared_dependencies = await self._identify_shared_dependencies(repository_dependencies)
        
        # Phase 3: Detect version conflicts
        logger.info("⚠️ Phase 3: Detecting version conflicts...")
        version_conflicts = await self._detect_version_conflicts(shared_dependencies)
        
        # Phase 4: Classify frameworks and analyze distribution
        logger.info("🏗️ Phase 4: Analyzing framework distribution...")
        framework_distribution = await self._analyze_framework_distribution(shared_dependencies)
        
        # Phase 5: Identify consolidation opportunities
        logger.info("💡 Phase 5: Identifying consolidation opportunities...")
        consolidation_opportunities = await self._identify_consolidation_opportunities(
            shared_dependencies, repository_dependencies
        )
        
        # Phase 6: Generate migration recommendations
        logger.info("📋 Phase 6: Generating migration recommendations...")
        migration_recommendations = await self._generate_migration_recommendations(
            shared_dependencies, version_conflicts, consolidation_opportunities
        )
        
        analysis_time = asyncio.get_event_loop().time() - start_time
        
        result = SharedDependencyAnalysisResult(
            total_repositories=len(repository_names),
            total_dependencies=len(shared_dependencies),
            shared_dependencies=shared_dependencies,
            version_conflicts=version_conflicts,
            framework_distribution=framework_distribution,
            consolidation_opportunities=consolidation_opportunities,
            migration_recommendations=migration_recommendations,
            analysis_time=analysis_time
        )
        
        logger.info(f"✅ Shared dependency analysis completed in {analysis_time:.2f}s")
        logger.info(f"📊 Found {len(shared_dependencies)} shared dependencies with {len(version_conflicts)} conflicts")
        
        return result
    
    async def _gather_repository_dependencies(
        self, repository_names: List[str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Gather all Maven dependencies from specified repositories."""
        repository_dependencies = {}
        
        for repo_name in repository_names:
            logger.debug(f"Gathering dependencies from {repo_name}")
            
            # Query Maven artifacts for this repository
            query = GraphQuery(
                cypher="""
                MATCH (repo:Repository {name: $repo_name})-[:CONTAINS]->(artifact:MavenArtifact)
                RETURN artifact.groupId as groupId,
                       artifact.artifactId as artifactId,
                       artifact.version as version,
                       artifact.scope as scope,
                       artifact.type as type
                ORDER BY artifact.groupId, artifact.artifactId
                """,
                parameters={"repo_name": repo_name},
                read_only=True
            )
            
            result = await self.neo4j_client.execute_query(query)
            
            dependencies = []
            for record in result.records:
                dependencies.append({
                    'groupId': record['groupId'],
                    'artifactId': record['artifactId'],
                    'version': record['version'],
                    'scope': record['scope'] or 'compile',
                    'type': record['type'] or 'jar'
                })
            
            repository_dependencies[repo_name] = dependencies
            logger.debug(f"Found {len(dependencies)} dependencies in {repo_name}")
        
        return repository_dependencies
    
    async def _identify_shared_dependencies(
        self, repository_dependencies: Dict[str, List[Dict[str, Any]]]
    ) -> List[SharedDependency]:
        """Identify dependencies that are shared across multiple repositories."""
        # Build dependency index: (groupId, artifactId) -> repos and versions
        dependency_index = defaultdict(lambda: {'repos': set(), 'versions': set()})
        
        for repo_name, dependencies in repository_dependencies.items():
            for dep in dependencies:
                key = (dep['groupId'], dep['artifactId'])
                dependency_index[key]['repos'].add(repo_name)
                dependency_index[key]['versions'].add(dep['version'])
        
        # Filter to only shared dependencies (used by 2+ repositories)
        shared_dependencies = []
        
        for (group_id, artifact_id), data in dependency_index.items():
            if len(data['repos']) >= 2:  # Shared by at least 2 repositories
                versions = sorted(list(data['versions']))
                repositories = sorted(list(data['repos']))
                
                # Determine if there are version conflicts
                version_conflicts = len(versions) > 1
                
                # Classify framework type
                framework_type = self._classify_framework_type(group_id, artifact_id)
                
                # Determine migration priority
                migration_priority = self._determine_migration_priority(
                    framework_type, version_conflicts, len(repositories)
                )
                
                # Try to determine latest version (simple alphabetical for now)
                latest_version = max(versions) if versions else "unknown"
                
                shared_dep = SharedDependency(
                    artifact_id=artifact_id,
                    group_id=group_id,
                    versions=versions,
                    repositories=repositories,
                    usage_count=len(repositories),
                    version_conflicts=version_conflicts,
                    latest_version=latest_version,
                    migration_priority=migration_priority,
                    framework_type=framework_type
                )
                
                shared_dependencies.append(shared_dep)
        
        # Sort by usage count (most widely used first)
        shared_dependencies.sort(key=lambda x: x.usage_count, reverse=True)
        
        return shared_dependencies
    
    def _classify_framework_type(self, group_id: str, artifact_id: str) -> str:
        """Classify the framework type of a dependency."""
        full_name = f"{group_id}:{artifact_id}".lower()
        
        for framework, patterns in self.framework_patterns.items():
            if any(pattern in full_name for pattern in patterns):
                return framework
        
        return 'other'
    
    def _determine_migration_priority(
        self, framework_type: str, has_conflicts: bool, usage_count: int
    ) -> str:
        """Determine migration priority for a shared dependency."""
        # High priority for legacy frameworks with conflicts
        if framework_type in ['struts', 'corba', 'jsp'] and has_conflicts:
            return 'HIGH'
        
        # High priority for widely used dependencies with conflicts
        if has_conflicts and usage_count >= 5:
            return 'HIGH'
        
        # Medium priority for legacy frameworks or widely used
        if framework_type in ['struts', 'corba', 'jsp'] or usage_count >= 3:
            return 'MEDIUM'
        
        return 'LOW'
    
    async def _detect_version_conflicts(
        self, shared_dependencies: List[SharedDependency]
    ) -> List[VersionConflict]:
        """Detect and analyze version conflicts in shared dependencies."""
        version_conflicts = []
        
        for dep in shared_dependencies:
            if dep.version_conflicts:
                # Determine conflict severity
                severity = self._assess_conflict_severity(dep)
                
                # Suggest resolution strategy
                resolution_strategy = self._suggest_resolution_strategy(dep)
                
                conflict = VersionConflict(
                    artifact_id=dep.artifact_id,
                    group_id=dep.group_id,
                    conflicting_versions=dep.versions,
                    affected_repositories=dep.repositories,
                    severity=severity,
                    resolution_strategy=resolution_strategy
                )
                
                version_conflicts.append(conflict)
        
        # Sort by severity (critical first)
        severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        version_conflicts.sort(key=lambda x: severity_order.get(x.severity, 4))
        
        return version_conflicts
    
    def _assess_conflict_severity(self, dep: SharedDependency) -> str:
        """Assess the severity of a version conflict."""
        # Critical for legacy frameworks with many versions
        if dep.framework_type in ['struts', 'corba'] and len(dep.versions) > 2:
            return 'CRITICAL'
        
        # High for widely used dependencies with major version differences
        if dep.usage_count >= 5 and self._has_major_version_differences(dep.versions):
            return 'HIGH'
        
        # High for security-sensitive components
        if dep.framework_type in ['logging', 'apache'] and len(dep.versions) > 1:
            return 'HIGH'
        
        # Medium for moderate conflicts
        if len(dep.versions) > 2 or dep.usage_count >= 3:
            return 'MEDIUM'
        
        return 'LOW'
    
    def _has_major_version_differences(self, versions: List[str]) -> bool:
        """Check if versions have major version differences."""
        try:
            major_versions = set()
            for version in versions:
                # Extract major version (first number)
                major = version.split('.')[0]
                if major.isdigit():
                    major_versions.add(int(major))
            
            return len(major_versions) > 1
        except:
            return True  # Assume conflict if can't parse
    
    def _suggest_resolution_strategy(self, dep: SharedDependency) -> str:
        """Suggest a resolution strategy for version conflicts."""
        if dep.framework_type in ['struts', 'corba', 'jsp']:
            return f"Coordinate {dep.framework_type.upper()} migration across all repositories to unified version"
        
        if len(dep.versions) == 2:
            return f"Upgrade all repositories to latest version ({dep.latest_version})"
        
        if dep.usage_count >= 5:
            return "Create shared library service or parent POM with unified version"
        
        return "Standardize on single version across affected repositories"
    
    async def _analyze_framework_distribution(
        self, shared_dependencies: List[SharedDependency]
    ) -> Dict[str, int]:
        """Analyze the distribution of frameworks across dependencies."""
        framework_counts = Counter()
        
        for dep in shared_dependencies:
            framework_counts[dep.framework_type] += dep.usage_count
        
        return dict(framework_counts)
    
    async def _identify_consolidation_opportunities(
        self,
        shared_dependencies: List[SharedDependency],
        repository_dependencies: Dict[str, List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """Identify opportunities for dependency consolidation."""
        opportunities = []
        
        # Group by framework type for consolidation analysis
        framework_groups = defaultdict(list)
        for dep in shared_dependencies:
            framework_groups[dep.framework_type].append(dep)
        
        for framework_type, deps in framework_groups.items():
            if len(deps) >= 3:  # Multiple dependencies of same framework
                total_usage = sum(dep.usage_count for dep in deps)
                conflicted_deps = [dep for dep in deps if dep.version_conflicts]
                
                opportunity = {
                    'type': 'framework_consolidation',
                    'framework': framework_type,
                    'dependencies_count': len(deps),
                    'total_usage': total_usage,
                    'conflicts_count': len(conflicted_deps),
                    'recommendation': f"Consider consolidating {len(deps)} {framework_type} dependencies",
                    'impact': 'HIGH' if len(conflicted_deps) > 1 else 'MEDIUM',
                    'dependencies': [f"{dep.group_id}:{dep.artifact_id}" for dep in deps]
                }
                opportunities.append(opportunity)
        
        # Look for duplicate functionality
        utility_deps = [dep for dep in shared_dependencies if dep.framework_type == 'utility']
        if len(utility_deps) >= 5:
            opportunities.append({
                'type': 'utility_consolidation',
                'framework': 'utility',
                'dependencies_count': len(utility_deps),
                'total_usage': sum(dep.usage_count for dep in utility_deps),
                'recommendation': "Review utility libraries for duplicate functionality",
                'impact': 'MEDIUM',
                'dependencies': [f"{dep.group_id}:{dep.artifact_id}" for dep in utility_deps[:10]]
            })
        
        return opportunities
    
    async def _generate_migration_recommendations(
        self,
        shared_dependencies: List[SharedDependency],
        version_conflicts: List[VersionConflict],
        consolidation_opportunities: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate migration recommendations based on analysis."""
        recommendations = []
        
        # High-level statistics
        total_shared = len(shared_dependencies)
        total_conflicts = len(version_conflicts)
        critical_conflicts = len([c for c in version_conflicts if c.severity == 'CRITICAL'])
        
        recommendations.append(f"📊 Portfolio Overview: {total_shared} shared dependencies with {total_conflicts} version conflicts")
        
        # Critical conflict recommendations
        if critical_conflicts > 0:
            critical_frameworks = set()
            for conflict in version_conflicts:
                if conflict.severity == 'CRITICAL':
                    # Find framework type
                    for dep in shared_dependencies:
                        if dep.group_id == conflict.group_id and dep.artifact_id == conflict.artifact_id:
                            critical_frameworks.add(dep.framework_type)
                            break
            
            recommendations.append(f"🚨 Critical Priority: {critical_conflicts} critical conflicts in {', '.join(critical_frameworks)} frameworks")
        
        # Framework-specific recommendations
        legacy_deps = [dep for dep in shared_dependencies if dep.framework_type in ['struts', 'corba', 'jsp']]
        if legacy_deps:
            legacy_conflicts = sum(1 for dep in legacy_deps if dep.version_conflicts)
            recommendations.append(f"🏗️ Legacy Framework Alert: {len(legacy_deps)} legacy dependencies, {legacy_conflicts} with version conflicts")
        
        # Consolidation recommendations
        high_impact_opportunities = [opp for opp in consolidation_opportunities if opp.get('impact') == 'HIGH']
        if high_impact_opportunities:
            recommendations.append(f"💡 Consolidation Opportunities: {len(high_impact_opportunities)} high-impact consolidation opportunities identified")
        
        # Widely used dependencies
        widely_used = [dep for dep in shared_dependencies if dep.usage_count >= 5]
        if widely_used:
            conflicted_widely_used = [dep for dep in widely_used if dep.version_conflicts]
            recommendations.append(f"📈 Widely Used Dependencies: {len(widely_used)} dependencies used by 5+ repositories, {len(conflicted_widely_used)} have conflicts")
        
        # Migration strategy recommendation
        if critical_conflicts > 0:
            recommendations.append("🎯 Recommended Strategy: Address critical conflicts first, then consolidate by framework type")
        elif total_conflicts > 0:
            recommendations.append("🎯 Recommended Strategy: Standardize versions by framework, focusing on legacy components")
        else:
            recommendations.append("✅ Recommended Strategy: Dependencies are well-aligned, focus on modernization planning")
        
        return recommendations


# Export main class
__all__ = ['SharedDependencyAnalyzer', 'SharedDependency', 'VersionConflict', 'SharedDependencyAnalysisResult']