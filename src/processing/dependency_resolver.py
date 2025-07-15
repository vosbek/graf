"""
Advanced dependency conflict detection and resolution system.
Implements sophisticated algorithms for Maven dependency resolution including
transitive dependency analysis, version conflict detection, and resolution strategies.
"""

import asyncio
import hashlib
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Union

from packaging import version
from packaging.version import InvalidVersion

from .maven_parser import MavenCoordinates, MavenDependency, DependencyScope, PomFile


class ConflictResolutionStrategy(Enum):
    """Strategies for resolving dependency conflicts."""
    NEAREST_WINS = "nearest"
    NEWEST_WINS = "newest"
    OLDEST_WINS = "oldest"
    FAIL_FAST = "fail"
    MANAGED_DEPENDENCIES = "managed"


class ConflictSeverity(Enum):
    """Severity levels for dependency conflicts."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DependencyConflict:
    """Represents a dependency version conflict."""
    artifact_ga: str  # group:artifact coordinates
    conflicting_versions: List[str]
    dependencies: List[MavenDependency]
    resolution_strategy: ConflictResolutionStrategy
    resolved_version: Optional[str] = None
    severity: ConflictSeverity = ConflictSeverity.MEDIUM
    impact_analysis: Dict[str, any] = field(default_factory=dict)
    resolution_rationale: str = ""
    
    @property
    def conflict_id(self) -> str:
        """Generate unique conflict ID."""
        content = f"{self.artifact_ga}:{sorted(self.conflicting_versions)}"
        return hashlib.md5(content.encode()).hexdigest()[:8]


@dataclass
class DependencyPath:
    """Represents a path to a dependency in the resolution tree."""
    coordinates: List[str]
    depth: int
    scope_chain: List[DependencyScope]
    is_optional_chain: bool = False
    
    def __str__(self) -> str:
        return " -> ".join(self.coordinates)


@dataclass
class ResolvedDependency:
    """A dependency that has been resolved with conflict resolution applied."""
    dependency: MavenDependency
    selected_version: str
    conflict_resolution: Optional[ConflictResolutionStrategy] = None
    excluded_versions: List[str] = field(default_factory=list)
    dependency_paths: List[DependencyPath] = field(default_factory=list)
    vulnerability_info: Optional[Dict[str, any]] = None
    license_info: Optional[Dict[str, any]] = None
    
    @property
    def coordinates(self) -> str:
        """Get resolved coordinates."""
        return f"{self.dependency.coordinates.group_id}:{self.dependency.coordinates.artifact_id}:{self.selected_version}"


@dataclass
class CircularDependency:
    """Represents a circular dependency in the resolution graph."""
    cycle_path: List[str]
    depth: int
    severity: ConflictSeverity
    
    @property
    def cycle_id(self) -> str:
        """Generate unique cycle ID."""
        normalized_cycle = sorted(self.cycle_path)
        content = "->".join(normalized_cycle)
        return hashlib.md5(content.encode()).hexdigest()[:8]


@dataclass
class ResolutionResult:
    """Result of dependency resolution process."""
    resolved_dependencies: List[ResolvedDependency]
    conflicts: List[DependencyConflict]
    circular_dependencies: List[CircularDependency]
    excluded_dependencies: List[MavenDependency]
    vulnerability_count: int = 0
    license_conflicts: List[Dict[str, any]] = field(default_factory=list)
    resolution_time_ms: float = 0.0
    
    @property
    def total_dependencies(self) -> int:
        """Get total number of resolved dependencies."""
        return len(self.resolved_dependencies)
    
    @property
    def conflict_count(self) -> int:
        """Get number of conflicts detected."""
        return len(self.conflicts)
    
    @property
    def has_critical_issues(self) -> bool:
        """Check if there are any critical issues."""
        return any(conflict.severity == ConflictSeverity.CRITICAL for conflict in self.conflicts)


class DependencyResolver:
    """Advanced dependency resolver with conflict detection and resolution."""
    
    def __init__(self, 
                 resolution_strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.NEAREST_WINS,
                 include_test_dependencies: bool = False,
                 max_depth: int = 50):
        self.resolution_strategy = resolution_strategy
        self.include_test_dependencies = include_test_dependencies
        self.max_depth = max_depth
        self.logger = logging.getLogger(__name__)
        
        # Resolution caches
        self.resolution_cache: Dict[str, ResolutionResult] = {}
        self.pom_cache: Dict[str, PomFile] = {}
        self.version_cache: Dict[str, List[str]] = {}
        
        # Conflict detection patterns
        self.breaking_change_patterns = [
            r'^\d+\.0\.0$',  # Major version changes
            r'.*-SNAPSHOT$',  # Snapshot versions
            r'.*-beta.*$',    # Beta versions
            r'.*-alpha.*$',   # Alpha versions
            r'.*-rc.*$',      # Release candidates
        ]
    
    async def resolve_dependencies(self, 
                                 pom: PomFile,
                                 managed_dependencies: Dict[str, MavenDependency] = None) -> ResolutionResult:
        """
        Resolve all dependencies for a POM file with conflict detection.
        
        Args:
            pom: POM file to resolve dependencies for
            managed_dependencies: Dependency management from parent POMs
            
        Returns:
            ResolutionResult with resolved dependencies and conflicts
        """
        start_time = asyncio.get_event_loop().time()
        
        # Check cache
        cache_key = self._generate_cache_key(pom, managed_dependencies)
        if cache_key in self.resolution_cache:
            return self.resolution_cache[cache_key]
        
        # Initialize resolution context
        context = ResolutionContext(
            root_pom=pom,
            managed_dependencies=managed_dependencies or {},
            visited_artifacts=set(),
            resolution_path=[],
            depth=0
        )
        
        # Phase 1: Collect all dependencies
        all_dependencies = await self._collect_dependencies(context)
        
        # Phase 2: Detect conflicts
        conflicts = await self._detect_conflicts(all_dependencies)
        
        # Phase 3: Detect circular dependencies
        circular_deps = await self._detect_circular_dependencies(all_dependencies)
        
        # Phase 4: Apply resolution strategy
        resolved_deps = await self._apply_resolution_strategy(all_dependencies, conflicts)
        
        # Phase 5: Post-processing
        excluded_deps = await self._find_excluded_dependencies(all_dependencies, resolved_deps)
        vulnerability_count = await self._count_vulnerabilities(resolved_deps)
        license_conflicts = await self._detect_license_conflicts(resolved_deps)
        
        # Create result
        end_time = asyncio.get_event_loop().time()
        resolution_time = (end_time - start_time) * 1000  # Convert to milliseconds
        
        result = ResolutionResult(
            resolved_dependencies=resolved_deps,
            conflicts=conflicts,
            circular_dependencies=circular_deps,
            excluded_dependencies=excluded_deps,
            vulnerability_count=vulnerability_count,
            license_conflicts=license_conflicts,
            resolution_time_ms=resolution_time
        )
        
        # Cache result
        self.resolution_cache[cache_key] = result
        
        return result
    
    async def _collect_dependencies(self, context: 'ResolutionContext') -> List[MavenDependency]:
        """Collect all dependencies including transitive ones."""
        collected = []
        
        # Process direct dependencies
        for dependency in context.root_pom.dependencies:
            if await self._should_include_dependency(dependency, context):
                # Apply dependency management
                managed_dep = self._apply_dependency_management(dependency, context)
                managed_dep.depth_level = context.depth
                managed_dep.dependency_path = context.resolution_path.copy()
                
                collected.append(managed_dep)
                
                # Collect transitive dependencies
                if context.depth < self.max_depth:
                    transitive_deps = await self._collect_transitive_dependencies(managed_dep, context)
                    collected.extend(transitive_deps)
        
        return collected
    
    async def _should_include_dependency(self, dependency: MavenDependency, context: 'ResolutionContext') -> bool:
        """Determine if a dependency should be included in resolution."""
        # Skip test dependencies if not requested
        if not self.include_test_dependencies and dependency.coordinates.scope == DependencyScope.TEST:
            return False
        
        # Skip optional dependencies
        if dependency.is_optional:
            return False
        
        # Check exclusions
        if await self._is_excluded(dependency, context):
            return False
        
        # Check circular dependencies
        if dependency.coordinates.coordinates in context.visited_artifacts:
            return False
        
        return True
    
    async def _is_excluded(self, dependency: MavenDependency, context: 'ResolutionContext') -> bool:
        """Check if dependency is excluded."""
        ga_coords = dependency.ga_coordinates
        
        # Check exclusions from parent dependencies
        for parent_dep in context.resolution_path:
            parent_dependency = context.dependency_map.get(parent_dep)
            if parent_dependency and ga_coords in parent_dependency.exclusions:
                return True
        
        return False
    
    def _apply_dependency_management(self, 
                                   dependency: MavenDependency, 
                                   context: 'ResolutionContext') -> MavenDependency:
        """Apply dependency management to override versions."""
        ga_coords = dependency.ga_coordinates
        managed = context.managed_dependencies.get(ga_coords)
        
        if managed:
            # Create new dependency with managed version
            new_coords = MavenCoordinates(
                group_id=dependency.coordinates.group_id,
                artifact_id=dependency.coordinates.artifact_id,
                version=managed.coordinates.version,
                type=dependency.coordinates.type,
                classifier=dependency.coordinates.classifier,
                scope=dependency.coordinates.scope
            )
            
            return MavenDependency(
                coordinates=new_coords,
                version_range=managed.version_range,
                is_optional=dependency.is_optional,
                exclusions=dependency.exclusions,
                system_path=dependency.system_path,
                is_inherited=dependency.is_inherited,
                depth_level=dependency.depth_level,
                dependency_path=dependency.dependency_path,
                resolved_version=managed.coordinates.version,
                conflict_resolution="managed"
            )
        
        return dependency
    
    async def _collect_transitive_dependencies(self, 
                                             dependency: MavenDependency, 
                                             context: 'ResolutionContext') -> List[MavenDependency]:
        """Collect transitive dependencies for a given dependency."""
        # This would fetch the POM for the dependency and resolve its dependencies
        # For now, return empty list as this requires repository access
        # TODO: Implement actual transitive dependency resolution
        return []
    
    async def _detect_conflicts(self, dependencies: List[MavenDependency]) -> List[DependencyConflict]:
        """Detect version conflicts in dependencies."""
        conflicts = []
        
        # Group dependencies by GA coordinates
        dep_groups = defaultdict(list)
        for dep in dependencies:
            dep_groups[dep.ga_coordinates].append(dep)
        
        # Find conflicts
        for ga_coords, deps in dep_groups.items():
            if len(deps) > 1:
                versions = [dep.coordinates.version for dep in deps]
                unique_versions = list(set(versions))
                
                if len(unique_versions) > 1:
                    severity = await self._assess_conflict_severity(unique_versions)
                    
                    conflict = DependencyConflict(
                        artifact_ga=ga_coords,
                        conflicting_versions=unique_versions,
                        dependencies=deps,
                        resolution_strategy=self.resolution_strategy,
                        severity=severity
                    )
                    
                    # Analyze impact
                    conflict.impact_analysis = await self._analyze_conflict_impact(conflict)
                    
                    conflicts.append(conflict)
        
        return conflicts
    
    async def _assess_conflict_severity(self, versions: List[str]) -> ConflictSeverity:
        """Assess the severity of a version conflict."""
        try:
            parsed_versions = [version.parse(v) for v in versions if v and v != "*"]
            
            if not parsed_versions:
                return ConflictSeverity.LOW
            
            # Check for major version differences
            major_versions = set(v.major for v in parsed_versions)
            if len(major_versions) > 1:
                return ConflictSeverity.CRITICAL
            
            # Check for minor version differences
            minor_versions = set(v.minor for v in parsed_versions)
            if len(minor_versions) > 2:
                return ConflictSeverity.HIGH
            
            # Check for pre-release versions
            has_prerelease = any(v.is_prerelease for v in parsed_versions)
            if has_prerelease:
                return ConflictSeverity.HIGH
            
            return ConflictSeverity.MEDIUM
            
        except InvalidVersion:
            return ConflictSeverity.MEDIUM
    
    async def _analyze_conflict_impact(self, conflict: DependencyConflict) -> Dict[str, any]:
        """Analyze the impact of a dependency conflict."""
        impact = {
            'affected_dependencies': len(conflict.dependencies),
            'depth_levels': [dep.depth_level for dep in conflict.dependencies],
            'scopes': [dep.coordinates.scope.value for dep in conflict.dependencies],
            'breaking_changes_risk': False,
            'api_compatibility_risk': False
        }
        
        # Check for breaking changes
        try:
            versions = [version.parse(v) for v in conflict.conflicting_versions if v and v != "*"]
            if versions:
                min_version = min(versions)
                max_version = max(versions)
                
                # Major version change indicates breaking changes
                if min_version.major != max_version.major:
                    impact['breaking_changes_risk'] = True
                
                # Minor version changes in 0.x.x versions can be breaking
                if min_version.major == 0 and min_version.minor != max_version.minor:
                    impact['api_compatibility_risk'] = True
        except InvalidVersion:
            pass
        
        return impact
    
    async def _detect_circular_dependencies(self, dependencies: List[MavenDependency]) -> List[CircularDependency]:
        """Detect circular dependencies in the dependency graph."""
        circular_deps = []
        
        # Build dependency graph
        graph = defaultdict(set)
        for dep in dependencies:
            if dep.dependency_path:
                parent = dep.dependency_path[-1]
                graph[parent].add(dep.coordinates.coordinates)
        
        # Find cycles using DFS
        visited = set()
        rec_stack = set()
        
        def dfs(node: str, path: List[str]) -> None:
            if node in rec_stack:
                # Found a cycle
                cycle_start = path.index(node)
                cycle_path = path[cycle_start:] + [node]
                
                circular_dep = CircularDependency(
                    cycle_path=cycle_path,
                    depth=len(cycle_path),
                    severity=ConflictSeverity.HIGH if len(cycle_path) > 5 else ConflictSeverity.MEDIUM
                )
                circular_deps.append(circular_dep)
                return
            
            if node in visited:
                return
            
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph[node]:
                dfs(neighbor, path + [neighbor])
            
            rec_stack.remove(node)
        
        # Check all nodes for cycles
        for node in graph:
            if node not in visited:
                dfs(node, [node])
        
        return circular_deps
    
    async def _apply_resolution_strategy(self, 
                                       dependencies: List[MavenDependency], 
                                       conflicts: List[DependencyConflict]) -> List[ResolvedDependency]:
        """Apply the configured resolution strategy to resolve conflicts."""
        resolved = []
        
        # Create conflict map for quick lookup
        conflict_map = {conflict.artifact_ga: conflict for conflict in conflicts}
        
        # Group dependencies by GA coordinates
        dep_groups = defaultdict(list)
        for dep in dependencies:
            dep_groups[dep.ga_coordinates].append(dep)
        
        # Resolve each group
        for ga_coords, deps in dep_groups.items():
            conflict = conflict_map.get(ga_coords)
            
            if conflict:
                # Apply conflict resolution
                resolved_dep = await self._resolve_conflict(conflict, deps)
                resolved.append(resolved_dep)
            else:
                # No conflict, use the single dependency
                resolved_dep = ResolvedDependency(
                    dependency=deps[0],
                    selected_version=deps[0].coordinates.version,
                    dependency_paths=self._create_dependency_paths(deps[0])
                )
                resolved.append(resolved_dep)
        
        return resolved
    
    async def _resolve_conflict(self, 
                              conflict: DependencyConflict, 
                              dependencies: List[MavenDependency]) -> ResolvedDependency:
        """Resolve a specific conflict using the configured strategy."""
        if self.resolution_strategy == ConflictResolutionStrategy.NEAREST_WINS:
            winner = min(dependencies, key=lambda d: d.depth_level)
        
        elif self.resolution_strategy == ConflictResolutionStrategy.NEWEST_WINS:
            winner = await self._select_newest_version(dependencies)
        
        elif self.resolution_strategy == ConflictResolutionStrategy.OLDEST_WINS:
            winner = await self._select_oldest_version(dependencies)
        
        elif self.resolution_strategy == ConflictResolutionStrategy.MANAGED_DEPENDENCIES:
            winner = await self._select_managed_version(dependencies)
        
        else:  # FAIL_FAST
            raise ValueError(f"Unresolved dependency conflict: {conflict.artifact_ga}")
        
        # Update conflict with resolution
        conflict.resolved_version = winner.coordinates.version
        conflict.resolution_rationale = f"Selected using {self.resolution_strategy.value} strategy"
        
        # Create resolved dependency
        excluded_versions = [dep.coordinates.version for dep in dependencies if dep != winner]
        
        return ResolvedDependency(
            dependency=winner,
            selected_version=winner.coordinates.version,
            conflict_resolution=self.resolution_strategy,
            excluded_versions=excluded_versions,
            dependency_paths=self._create_dependency_paths_for_all(dependencies)
        )
    
    async def _select_newest_version(self, dependencies: List[MavenDependency]) -> MavenDependency:
        """Select dependency with newest version."""
        try:
            return max(dependencies, key=lambda d: version.parse(d.coordinates.version))
        except InvalidVersion:
            # Fall back to string comparison
            return max(dependencies, key=lambda d: d.coordinates.version)
    
    async def _select_oldest_version(self, dependencies: List[MavenDependency]) -> MavenDependency:
        """Select dependency with oldest version."""
        try:
            return min(dependencies, key=lambda d: version.parse(d.coordinates.version))
        except InvalidVersion:
            # Fall back to string comparison
            return min(dependencies, key=lambda d: d.coordinates.version)
    
    async def _select_managed_version(self, dependencies: List[MavenDependency]) -> MavenDependency:
        """Select dependency with managed version."""
        managed_deps = [dep for dep in dependencies if dep.conflict_resolution == "managed"]
        if managed_deps:
            return managed_deps[0]
        
        # Fall back to nearest wins
        return min(dependencies, key=lambda d: d.depth_level)
    
    def _create_dependency_paths(self, dependency: MavenDependency) -> List[DependencyPath]:
        """Create dependency paths for a single dependency."""
        return [DependencyPath(
            coordinates=dependency.dependency_path + [dependency.coordinates.coordinates],
            depth=dependency.depth_level,
            scope_chain=[dependency.coordinates.scope],
            is_optional_chain=dependency.is_optional
        )]
    
    def _create_dependency_paths_for_all(self, dependencies: List[MavenDependency]) -> List[DependencyPath]:
        """Create dependency paths for all dependencies."""
        paths = []
        for dep in dependencies:
            paths.extend(self._create_dependency_paths(dep))
        return paths
    
    async def _find_excluded_dependencies(self, 
                                        all_dependencies: List[MavenDependency], 
                                        resolved_dependencies: List[ResolvedDependency]) -> List[MavenDependency]:
        """Find dependencies that were excluded during resolution."""
        resolved_coords = set(dep.coordinates for dep in resolved_dependencies)
        excluded = []
        
        for dep in all_dependencies:
            if dep.coordinates.coordinates not in resolved_coords:
                excluded.append(dep)
        
        return excluded
    
    async def _count_vulnerabilities(self, resolved_dependencies: List[ResolvedDependency]) -> int:
        """Count vulnerabilities in resolved dependencies."""
        # This would integrate with vulnerability databases
        # For now, return 0
        return 0
    
    async def _detect_license_conflicts(self, resolved_dependencies: List[ResolvedDependency]) -> List[Dict[str, any]]:
        """Detect license conflicts in resolved dependencies."""
        # This would check for incompatible licenses
        # For now, return empty list
        return []
    
    def _generate_cache_key(self, pom: PomFile, managed_dependencies: Dict[str, MavenDependency]) -> str:
        """Generate cache key for resolution results."""
        content = f"{pom.coordinates.coordinates}:{self.resolution_strategy.value}:{self.include_test_dependencies}"
        if managed_dependencies:
            managed_coords = sorted(managed_dependencies.keys())
            content += f":{':'.join(managed_coords)}"
        
        return hashlib.md5(content.encode()).hexdigest()
    
    def analyze_dependency_health(self, result: ResolutionResult) -> Dict[str, any]:
        """Analyze overall dependency health."""
        total_deps = result.total_dependencies
        conflict_count = result.conflict_count
        
        # Calculate health score
        health_score = 100.0
        
        # Deduct points for conflicts
        if conflict_count > 0:
            conflict_penalty = min(conflict_count * 5, 50)  # Max 50 points for conflicts
            health_score -= conflict_penalty
        
        # Deduct points for circular dependencies
        if result.circular_dependencies:
            circular_penalty = min(len(result.circular_dependencies) * 10, 30)  # Max 30 points
            health_score -= circular_penalty
        
        # Deduct points for vulnerabilities
        if result.vulnerability_count > 0:
            vuln_penalty = min(result.vulnerability_count * 3, 20)  # Max 20 points
            health_score -= vuln_penalty
        
        health_score = max(health_score, 0)
        
        # Determine grade
        if health_score >= 90:
            grade = "A"
        elif health_score >= 80:
            grade = "B"
        elif health_score >= 70:
            grade = "C"
        elif health_score >= 60:
            grade = "D"
        else:
            grade = "F"
        
        return {
            'health_score': health_score,
            'grade': grade,
            'total_dependencies': total_deps,
            'conflicts': conflict_count,
            'circular_dependencies': len(result.circular_dependencies),
            'vulnerabilities': result.vulnerability_count,
            'resolution_time_ms': result.resolution_time_ms,
            'recommendations': self._generate_recommendations(result)
        }
    
    def _generate_recommendations(self, result: ResolutionResult) -> List[str]:
        """Generate recommendations for improving dependency health."""
        recommendations = []
        
        if result.conflict_count > 5:
            recommendations.append("Consider consolidating dependencies to reduce version conflicts")
        
        if result.circular_dependencies:
            recommendations.append("Refactor code to eliminate circular dependencies")
        
        if result.vulnerability_count > 0:
            recommendations.append("Update vulnerable dependencies to secure versions")
        
        if result.resolution_time_ms > 5000:
            recommendations.append("Consider caching dependency resolution results")
        
        critical_conflicts = [c for c in result.conflicts if c.severity == ConflictSeverity.CRITICAL]
        if critical_conflicts:
            recommendations.append("Address critical version conflicts immediately")
        
        return recommendations


@dataclass
class ResolutionContext:
    """Context for dependency resolution."""
    root_pom: PomFile
    managed_dependencies: Dict[str, MavenDependency]
    visited_artifacts: Set[str]
    resolution_path: List[str]
    depth: int
    dependency_map: Dict[str, MavenDependency] = field(default_factory=dict)
    
    def enter_dependency(self, dependency: MavenDependency):
        """Enter a dependency in the resolution context."""
        self.visited_artifacts.add(dependency.coordinates.coordinates)
        self.resolution_path.append(dependency.coordinates.coordinates)
        self.dependency_map[dependency.coordinates.coordinates] = dependency
        self.depth += 1
    
    def exit_dependency(self, dependency: MavenDependency):
        """Exit a dependency from the resolution context."""
        if dependency.coordinates.coordinates in self.visited_artifacts:
            self.visited_artifacts.remove(dependency.coordinates.coordinates)
        if self.resolution_path and self.resolution_path[-1] == dependency.coordinates.coordinates:
            self.resolution_path.pop()
        self.depth -= 1


class DependencyGraphAnalyzer:
    """Analyzer for dependency graph structure and patterns."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def analyze_graph_structure(self, result: ResolutionResult) -> Dict[str, any]:
        """Analyze the structure of the dependency graph."""
        dependencies = result.resolved_dependencies
        
        # Calculate graph metrics
        total_nodes = len(dependencies)
        max_depth = max(path.depth for dep in dependencies for path in dep.dependency_paths) if dependencies else 0
        
        # Analyze scope distribution
        scope_distribution = defaultdict(int)
        for dep in dependencies:
            scope_distribution[dep.dependency.coordinates.scope.value] += 1
        
        # Find hub dependencies (most connected)
        connection_counts = defaultdict(int)
        for dep in dependencies:
            for path in dep.dependency_paths:
                for coord in path.coordinates:
                    connection_counts[coord] += 1
        
        top_hubs = sorted(connection_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Calculate complexity metrics
        average_depth = sum(path.depth for dep in dependencies for path in dep.dependency_paths) / max(1, sum(len(dep.dependency_paths) for dep in dependencies))
        
        return {
            'total_nodes': total_nodes,
            'max_depth': max_depth,
            'average_depth': average_depth,
            'scope_distribution': dict(scope_distribution),
            'top_hubs': top_hubs,
            'complexity_score': self._calculate_complexity_score(dependencies)
        }
    
    def _calculate_complexity_score(self, dependencies: List[ResolvedDependency]) -> float:
        """Calculate complexity score for the dependency graph."""
        if not dependencies:
            return 0.0
        
        # Factors that contribute to complexity
        total_deps = len(dependencies)
        max_depth = max(path.depth for dep in dependencies for path in dep.dependency_paths) if dependencies else 0
        total_paths = sum(len(dep.dependency_paths) for dep in dependencies)
        
        # Normalize and combine factors
        depth_factor = min(max_depth / 10.0, 1.0)  # Normalize to 0-1
        path_factor = min(total_paths / (total_deps * 3), 1.0)  # Normalize to 0-1
        size_factor = min(total_deps / 100.0, 1.0)  # Normalize to 0-1
        
        complexity_score = (depth_factor + path_factor + size_factor) / 3.0 * 100
        
        return complexity_score
    
    def find_optimization_opportunities(self, result: ResolutionResult) -> List[Dict[str, any]]:
        """Find opportunities to optimize the dependency graph."""
        opportunities = []
        
        # Find dependencies with many conflicts
        frequent_conflicts = defaultdict(int)
        for conflict in result.conflicts:
            frequent_conflicts[conflict.artifact_ga] += 1
        
        for ga_coords, count in frequent_conflicts.items():
            if count > 2:
                opportunities.append({
                    'type': 'frequent_conflict',
                    'artifact': ga_coords,
                    'conflict_count': count,
                    'recommendation': 'Consider using dependency management to control version'
                })
        
        # Find deep dependency chains
        for dep in result.resolved_dependencies:
            for path in dep.dependency_paths:
                if path.depth > 8:
                    opportunities.append({
                        'type': 'deep_chain',
                        'artifact': dep.coordinates,
                        'depth': path.depth,
                        'recommendation': 'Consider flattening dependency hierarchy'
                    })
        
        # Find potential duplicate functionality
        group_artifacts = defaultdict(list)
        for dep in result.resolved_dependencies:
            group_id = dep.dependency.coordinates.group_id
            group_artifacts[group_id].append(dep)
        
        for group_id, deps in group_artifacts.items():
            if len(deps) > 5:
                opportunities.append({
                    'type': 'group_proliferation',
                    'group_id': group_id,
                    'artifact_count': len(deps),
                    'recommendation': 'Review if all artifacts from this group are necessary'
                })
        
        return opportunities