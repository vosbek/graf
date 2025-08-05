"""
Cross-Repository Analysis System for Legacy Migration
=====================================================

Analyzes dependencies, business relationships, and migration complexity
across 50-100 legacy repositories for enterprise migration planning.

Key Features:
- Cross-repository dependency mapping
- Business rule relationship analysis
- Migration complexity scoring
- Batch processing optimization
- Enterprise-scale performance
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any, Tuple
from pathlib import Path
import json
import statistics

from ..core.neo4j_client import Neo4jClient, GraphQuery
from ..core.chromadb_client import ChromaDBClient
from ..processing.dependency_resolver import DependencyResolver
from .repository_processor_v2 import RepositoryProcessor


logger = logging.getLogger(__name__)


@dataclass
class CrossRepoRelationship:
    """Represents a relationship between components across repositories."""
    source_repo: str
    source_component: str
    source_type: str  # StrutsAction, BusinessRule, CORBAInterface, etc.
    target_repo: str
    target_component: str
    target_type: str
    relationship_type: str  # CALLS_SERVICE, IMPLEMENTS_BUSINESS_RULE, etc.
    confidence_score: float
    migration_impact: str  # LOW, MEDIUM, HIGH, CRITICAL
    business_context: Optional[str] = None


@dataclass
class RepositoryMigrationProfile:
    """Migration complexity profile for a single repository."""
    repo_name: str
    total_components: int
    business_rules_count: int
    struts_actions_count: int
    corba_interfaces_count: int
    jsp_components_count: int
    external_dependencies: int
    internal_dependencies: int
    migration_complexity: float  # 0-100 scale
    migration_priority: str  # LOW, MEDIUM, HIGH, CRITICAL
    estimated_effort_days: int
    blockers: List[str] = field(default_factory=list)
    dependencies_on: List[str] = field(default_factory=list)  # Other repos
    dependents: List[str] = field(default_factory=list)  # Other repos depend on this


@dataclass
class CrossRepoAnalysisResult:
    """Complete cross-repository analysis results."""
    total_repositories: int
    total_relationships: int
    cross_repo_relationships: List[CrossRepoRelationship]
    repository_profiles: Dict[str, RepositoryMigrationProfile]
    migration_order: List[str]  # Recommended migration order
    critical_paths: List[List[str]]  # Critical dependency chains
    business_domains: Dict[str, List[str]]  # Domain -> repo mapping
    analysis_time: float
    recommendations: List[str]


class CrossRepositoryAnalyzer:
    """
    Analyzes business relationships and migration complexity across
    multiple repositories for enterprise legacy system migration.
    """
    
    def __init__(
        self,
        neo4j_client: Neo4jClient,
        chroma_client: ChromaDBClient,
        repository_processor: RepositoryProcessor
    ):
        self.neo4j_client = neo4j_client
        self.chroma_client = chroma_client
        self.repository_processor = repository_processor
        self.dependency_resolver = DependencyResolver()
        
    async def analyze_cross_repository_relationships(
        self,
        repository_names: List[str],
        include_business_context: bool = True,
        max_depth: int = 3
    ) -> CrossRepoAnalysisResult:
        """
        Perform comprehensive cross-repository analysis.
        
        Args:
            repository_names: List of repository names to analyze
            include_business_context: Whether to include business rule analysis
            max_depth: Maximum dependency traversal depth
            
        Returns:
            CrossRepoAnalysisResult with complete analysis
        """
        start_time = time.time()
        logger.info(f"🔍 Starting cross-repository analysis for {len(repository_names)} repositories")
        
        # Phase 1: Gather repository data
        logger.info("📊 Phase 1: Gathering repository component data...")
        repo_components = await self._gather_repository_components(repository_names)
        
        # Phase 2: Analyze cross-repository relationships
        logger.info("🔗 Phase 2: Analyzing cross-repository relationships...")
        cross_repo_relationships = await self._analyze_cross_repo_relationships(
            repo_components, max_depth
        )
        
        # Phase 3: Build repository migration profiles
        logger.info("📋 Phase 3: Building repository migration profiles...")
        repository_profiles = await self._build_migration_profiles(
            repo_components, cross_repo_relationships
        )
        
        # Phase 4: Determine migration order
        logger.info("🎯 Phase 4: Determining optimal migration order...")
        migration_order = await self._calculate_migration_order(
            repository_profiles, cross_repo_relationships
        )
        
        # Phase 5: Identify critical paths
        logger.info("⚠️ Phase 5: Identifying critical dependency paths...")
        critical_paths = await self._identify_critical_paths(
            repository_profiles, cross_repo_relationships
        )
        
        # Phase 6: Business domain mapping
        logger.info("🏢 Phase 6: Mapping business domains...")
        business_domains = await self._map_business_domains(repo_components)
        
        # Phase 7: Generate recommendations
        logger.info("💡 Phase 7: Generating migration recommendations...")
        recommendations = await self._generate_recommendations(
            repository_profiles, cross_repo_relationships, critical_paths
        )
        
        analysis_time = time.time() - start_time
        
        result = CrossRepoAnalysisResult(
            total_repositories=len(repository_names),
            total_relationships=len(cross_repo_relationships),
            cross_repo_relationships=cross_repo_relationships,
            repository_profiles=repository_profiles,
            migration_order=migration_order,
            critical_paths=critical_paths,
            business_domains=business_domains,
            analysis_time=analysis_time,
            recommendations=recommendations
        )
        
        logger.info(f"✅ Cross-repository analysis completed in {analysis_time:.2f}s")
        logger.info(f"📊 Found {len(cross_repo_relationships)} cross-repository relationships")
        
        return result
    
    async def _gather_repository_components(
        self, repository_names: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Gather all components from specified repositories."""
        repo_components = {}
        
        for repo_name in repository_names:
            logger.debug(f"Gathering components from {repo_name}")
            
            # Query all components for this repository
            query = GraphQuery(
                cypher="""
                MATCH (repo:Repository {name: $repo_name})
                OPTIONAL MATCH (repo)-[:CONTAINS]->(br:BusinessRule)
                OPTIONAL MATCH (repo)-[:CONTAINS]->(sa:StrutsAction)
                OPTIONAL MATCH (repo)-[:CONTAINS]->(ci:CORBAInterface)
                OPTIONAL MATCH (repo)-[:CONTAINS]->(jsp:JSPComponent)
                OPTIONAL MATCH (repo)-[:CONTAINS]->(f:File)
                OPTIONAL MATCH (repo)-[:CONTAINS]->(chunk:CodeChunk)
                
                RETURN repo,
                       collect(DISTINCT br) as business_rules,
                       collect(DISTINCT sa) as struts_actions,
                       collect(DISTINCT ci) as corba_interfaces,
                       collect(DISTINCT jsp) as jsp_components,
                       collect(DISTINCT f) as files,
                       collect(DISTINCT chunk) as code_chunks
                """,
                parameters={"repo_name": repo_name},
                read_only=True
            )
            
            result = await self.neo4j_client.execute_query(query)
            
            if result.records:
                record = result.records[0]
                repo_components[repo_name] = {
                    'repository': record['repo'],
                    'business_rules': [dict(br) for br in record['business_rules'] if br],
                    'struts_actions': [dict(sa) for sa in record['struts_actions'] if sa],
                    'corba_interfaces': [dict(ci) for ci in record['corba_interfaces'] if ci],
                    'jsp_components': [dict(jsp) for jsp in record['jsp_components'] if jsp],
                    'files': [dict(f) for f in record['files'] if f],
                    'code_chunks': [dict(chunk) for chunk in record['code_chunks'] if chunk]
                }
            else:
                logger.warning(f"No components found for repository: {repo_name}")
                repo_components[repo_name] = {
                    'repository': None,
                    'business_rules': [],
                    'struts_actions': [],
                    'corba_interfaces': [],
                    'jsp_components': [],
                    'files': [],
                    'code_chunks': []
                }
        
        return repo_components
    
    async def _analyze_cross_repo_relationships(
        self, repo_components: Dict[str, Dict[str, Any]], max_depth: int
    ) -> List[CrossRepoRelationship]:
        """Analyze relationships between components across repositories."""
        cross_repo_relationships = []
        
        # Build component index for fast lookup
        component_index = defaultdict(list)
        for repo_name, components in repo_components.items():
            for component_type in ['business_rules', 'struts_actions', 'corba_interfaces', 'jsp_components']:
                for component in components[component_type]:
                    if component:
                        component_index[component.get('name', '')].append({
                            'repo': repo_name,
                            'component': component,
                            'type': component_type.rstrip('s').replace('_', '').title()
                        })
        
        # Analyze cross-repository references
        for source_repo, components in repo_components.items():
            await self._find_cross_repo_references(
                source_repo, components, component_index, cross_repo_relationships
            )
        
        # Analyze business rule dependencies across repos
        await self._analyze_business_rule_dependencies(
            repo_components, cross_repo_relationships
        )
        
        # Calculate confidence scores and migration impact
        for relationship in cross_repo_relationships:
            relationship.confidence_score = await self._calculate_confidence_score(relationship)
            relationship.migration_impact = await self._assess_migration_impact(relationship)
        
        return cross_repo_relationships
    
    async def _find_cross_repo_references(
        self,
        source_repo: str,
        components: Dict[str, Any],
        component_index: Dict[str, List[Dict]],
        cross_repo_relationships: List[CrossRepoRelationship]
    ):
        """Find references between components across repositories."""
        
        # Analyze Struts actions calling services in other repos
        for struts_action in components['struts_actions']:
            if not struts_action:
                continue
                
            # Look for service calls in action implementation
            business_purpose = struts_action.get('business_purpose', '')
            implementation = struts_action.get('implementation_details', '')
            
            # Simple pattern matching for cross-repo service calls
            # In real implementation, this would use AST analysis
            for pattern in ['ServiceLocator.', 'RemoteService.', '.lookup(', 'JNDI.']:
                if pattern in implementation or pattern in business_purpose:
                    # Find potential target services
                    for service_name, candidates in component_index.items():
                        if service_name and service_name in implementation:
                            for candidate in candidates:
                                if candidate['repo'] != source_repo:
                                    cross_repo_relationships.append(CrossRepoRelationship(
                                        source_repo=source_repo,
                                        source_component=struts_action.get('path', ''),
                                        source_type='StrutsAction',
                                        target_repo=candidate['repo'],
                                        target_component=service_name,
                                        target_type=candidate['type'],
                                        relationship_type='CALLS_SERVICE',
                                        confidence_score=0.0,  # Will be calculated later
                                        migration_impact='',  # Will be assessed later
                                        business_context=business_purpose
                                    ))
        
        # Analyze CORBA interface dependencies
        for corba_interface in components['corba_interfaces']:
            if not corba_interface:
                continue
                
            # Look for inheritance or composition with other CORBA interfaces
            operations = corba_interface.get('operations', [])
            for operation in operations:
                # Check if operation references types from other repositories
                for type_name, candidates in component_index.items():
                    if type_name and type_name in str(operation):
                        for candidate in candidates:
                            if candidate['repo'] != source_repo and candidate['type'] == 'CORBAInterface':
                                cross_repo_relationships.append(CrossRepoRelationship(
                                    source_repo=source_repo,
                                    source_component=corba_interface.get('interface_name', ''),
                                    source_type='CORBAInterface',
                                    target_repo=candidate['repo'],
                                    target_component=type_name,
                                    target_type='CORBAInterface',
                                    relationship_type='DEPENDS_ON_TYPE',
                                    confidence_score=0.0,
                                    migration_impact='',
                                    business_context=corba_interface.get('business_purpose', '')
                                ))
    
    async def _analyze_business_rule_dependencies(
        self,
        repo_components: Dict[str, Dict[str, Any]],
        cross_repo_relationships: List[CrossRepoRelationship]
    ):
        """Analyze business rule dependencies across repositories."""
        
        # Use Neo4j to find business rule relationships
        query = GraphQuery(
            cypher="""
            MATCH (br1:BusinessRule)-[r:IMPLEMENTS_BUSINESS_RULE|CALLS_SERVICE|DEPENDS_ON]->(br2:BusinessRule)
            MATCH (repo1:Repository)-[:CONTAINS]->(br1)
            MATCH (repo2:Repository)-[:CONTAINS]->(br2)
            WHERE repo1.name <> repo2.name
            RETURN repo1.name as source_repo,
                   br1.rule_id as source_rule,
                   repo2.name as target_repo,
                   br2.rule_id as target_rule,
                   type(r) as relationship_type,
                   br1.domain as source_domain,
                   br2.domain as target_domain
            """,
            read_only=True
        )
        
        result = await self.neo4j_client.execute_query(query)
        
        for record in result.records:
            cross_repo_relationships.append(CrossRepoRelationship(
                source_repo=record['source_repo'],
                source_component=record['source_rule'],
                source_type='BusinessRule',
                target_repo=record['target_repo'],
                target_component=record['target_rule'],
                target_type='BusinessRule',
                relationship_type=record['relationship_type'],
                confidence_score=0.8,  # High confidence from graph data
                migration_impact='HIGH',  # Business rules are critical
                business_context=f"Cross-domain: {record['source_domain']} -> {record['target_domain']}"
            ))
    
    async def _build_migration_profiles(
        self,
        repo_components: Dict[str, Dict[str, Any]],
        cross_repo_relationships: List[CrossRepoRelationship]
    ) -> Dict[str, RepositoryMigrationProfile]:
        """Build migration complexity profiles for each repository."""
        profiles = {}
        
        for repo_name, components in repo_components.items():
            # Count components
            business_rules_count = len(components['business_rules'])
            struts_actions_count = len(components['struts_actions'])
            corba_interfaces_count = len(components['corba_interfaces'])
            jsp_components_count = len(components['jsp_components'])
            total_components = business_rules_count + struts_actions_count + corba_interfaces_count + jsp_components_count
            
            # Count dependencies
            external_deps = len([r for r in cross_repo_relationships if r.source_repo == repo_name])
            internal_deps = len([r for r in cross_repo_relationships if r.target_repo == repo_name])
            
            # Calculate migration complexity (0-100 scale)
            complexity_factors = {
                'component_count': min(total_components / 100, 1.0) * 30,  # Max 30 points
                'corba_complexity': min(corba_interfaces_count / 20, 1.0) * 25,  # Max 25 points
                'struts_complexity': min(struts_actions_count / 50, 1.0) * 20,  # Max 20 points
                'external_deps': min(external_deps / 10, 1.0) * 15,  # Max 15 points
                'business_rules': min(business_rules_count / 30, 1.0) * 10  # Max 10 points
            }
            
            migration_complexity = sum(complexity_factors.values())
            
            # Determine priority
            if migration_complexity >= 80:
                priority = 'CRITICAL'
            elif migration_complexity >= 60:
                priority = 'HIGH'
            elif migration_complexity >= 30:
                priority = 'MEDIUM'
            else:
                priority = 'LOW'
            
            # Estimate effort (rough calculation)
            effort_days = int(
                total_components * 0.5 +  # Base effort per component
                corba_interfaces_count * 3 +  # CORBA is complex
                struts_actions_count * 1.5 +  # Struts refactoring
                external_deps * 2  # Cross-repo coordination
            )
            
            # Identify blockers
            blockers = []
            if corba_interfaces_count > 10:
                blockers.append(f"High CORBA complexity ({corba_interfaces_count} interfaces)")
            if external_deps > 5:
                blockers.append(f"Many external dependencies ({external_deps})")
            
            # Find dependencies
            dependencies_on = list(set([r.target_repo for r in cross_repo_relationships 
                                      if r.source_repo == repo_name]))
            dependents = list(set([r.source_repo for r in cross_repo_relationships 
                                 if r.target_repo == repo_name]))
            
            profiles[repo_name] = RepositoryMigrationProfile(
                repo_name=repo_name,
                total_components=total_components,
                business_rules_count=business_rules_count,
                struts_actions_count=struts_actions_count,
                corba_interfaces_count=corba_interfaces_count,
                jsp_components_count=jsp_components_count,
                external_dependencies=external_deps,
                internal_dependencies=internal_deps,
                migration_complexity=migration_complexity,
                migration_priority=priority,
                estimated_effort_days=effort_days,
                blockers=blockers,
                dependencies_on=dependencies_on,
                dependents=dependents
            )
        
        return profiles
    
    async def _calculate_migration_order(
        self,
        profiles: Dict[str, RepositoryMigrationProfile],
        relationships: List[CrossRepoRelationship]
    ) -> List[str]:
        """Calculate optimal migration order using topological sort with priority weighting."""
        
        # Build dependency graph
        graph = defaultdict(set)
        in_degree = defaultdict(int)
        
        # Initialize all repositories
        for repo_name in profiles.keys():
            in_degree[repo_name] = 0
        
        # Add dependency edges
        for relationship in relationships:
            if relationship.migration_impact in ['HIGH', 'CRITICAL']:
                # Target repo should be migrated before source repo
                if relationship.target_repo not in graph[relationship.source_repo]:
                    graph[relationship.source_repo].add(relationship.target_repo)
                    in_degree[relationship.target_repo] += 1
        
        # Modified topological sort with priority
        result = []
        queue = []
        
        # Start with repositories that have no dependencies
        for repo_name in profiles.keys():
            if in_degree[repo_name] == 0:
                queue.append((profiles[repo_name].migration_complexity, repo_name))
        
        queue.sort(reverse=True)  # Higher complexity first for independent repos
        
        while queue:
            _, current_repo = queue.pop(0)
            result.append(current_repo)
            
            # Remove this repo from graph and update in-degrees
            for dependent_repo in graph[current_repo]:
                in_degree[dependent_repo] -= 1
                if in_degree[dependent_repo] == 0:
                    queue.append((profiles[dependent_repo].migration_complexity, dependent_repo))
                    queue.sort(reverse=True)
        
        return result
    
    async def _identify_critical_paths(
        self,
        profiles: Dict[str, RepositoryMigrationProfile],
        relationships: List[CrossRepoRelationship]
    ) -> List[List[str]]:
        """Identify critical dependency paths that could block migration."""
        critical_paths = []
        
        # Build graph of critical relationships
        critical_graph = defaultdict(set)
        for rel in relationships:
            if rel.migration_impact in ['HIGH', 'CRITICAL']:
                critical_graph[rel.source_repo].add(rel.target_repo)
        
        # Find longest paths (potential bottlenecks)
        def find_longest_paths(start_repo, visited=None, path=None):
            if visited is None:
                visited = set()
            if path is None:
                path = []
            
            visited.add(start_repo)
            path.append(start_repo)
            
            paths = []
            has_unvisited_neighbors = False
            
            for neighbor in critical_graph[start_repo]:
                if neighbor not in visited:
                    has_unvisited_neighbors = True
                    neighbor_paths = find_longest_paths(neighbor, visited.copy(), path.copy())
                    paths.extend(neighbor_paths)
            
            if not has_unvisited_neighbors:
                paths.append(path.copy())
            
            return paths
        
        # Find critical paths from each repository
        all_paths = []
        for repo_name in profiles.keys():
            paths = find_longest_paths(repo_name)
            all_paths.extend(paths)
        
        # Filter to only include paths longer than 2 repositories
        critical_paths = [path for path in all_paths if len(path) > 2]
        
        # Sort by length (longer paths are more critical)
        critical_paths.sort(key=len, reverse=True)
        
        return critical_paths[:10]  # Return top 10 critical paths
    
    async def _map_business_domains(
        self, repo_components: Dict[str, Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """Map repositories to business domains based on business rules."""
        domain_mapping = defaultdict(list)
        
        for repo_name, components in repo_components.items():
            domains = set()
            
            # Extract domains from business rules
            for business_rule in components['business_rules']:
                if business_rule and 'domain' in business_rule:
                    domains.add(business_rule['domain'])
            
            # Extract domains from Struts actions
            for struts_action in components['struts_actions']:
                if struts_action and 'business_purpose' in struts_action:
                    purpose = struts_action['business_purpose'].lower()
                    # Simple domain detection based on keywords
                    if any(keyword in purpose for keyword in ['customer', 'user', 'account']):
                        domains.add('Customer Management')
                    elif any(keyword in purpose for keyword in ['order', 'purchase', 'billing']):
                        domains.add('Order Management')
                    elif any(keyword in purpose for keyword in ['inventory', 'product', 'catalog']):
                        domains.add('Inventory Management')
                    elif any(keyword in purpose for keyword in ['report', 'analytics', 'dashboard']):
                        domains.add('Reporting')
            
            # Assign to domains or create default
            if not domains:
                domains.add('General')
            
            for domain in domains:
                domain_mapping[domain].append(repo_name)
        
        return dict(domain_mapping)
    
    async def _generate_recommendations(
        self,
        profiles: Dict[str, RepositoryMigrationProfile],
        relationships: List[CrossRepoRelationship],
        critical_paths: List[List[str]]
    ) -> List[str]:
        """Generate migration recommendations based on analysis."""
        recommendations = []
        
        # High-level recommendations
        total_repos = len(profiles)
        avg_complexity = statistics.mean([p.migration_complexity for p in profiles.values()])
        
        recommendations.append(f"📊 Portfolio Overview: {total_repos} repositories with average complexity {avg_complexity:.1f}/100")
        
        # Priority recommendations
        critical_repos = [name for name, profile in profiles.items() 
                         if profile.migration_priority == 'CRITICAL']
        if critical_repos:
            recommendations.append(f"🚨 Critical Priority: {len(critical_repos)} repositories require immediate attention: {', '.join(critical_repos[:3])}")
        
        # Dependency recommendations
        high_dependency_repos = [name for name, profile in profiles.items() 
                               if profile.external_dependencies > 5]
        if high_dependency_repos:
            recommendations.append(f"🔗 High Dependencies: Consider migrating dependencies first for: {', '.join(high_dependency_repos[:3])}")
        
        # Critical path recommendations
        if critical_paths:
            longest_path = critical_paths[0]
            recommendations.append(f"⚠️ Critical Path Alert: Longest dependency chain has {len(longest_path)} repositories, starting with {longest_path[0]}")
        
        # CORBA-specific recommendations
        corba_heavy_repos = [name for name, profile in profiles.items() 
                           if profile.corba_interfaces_count > 10]
        if corba_heavy_repos:
            recommendations.append(f"🔧 CORBA Complexity: {len(corba_heavy_repos)} repositories have heavy CORBA usage, plan extra time for modernization")
        
        # Effort estimation
        total_effort = sum(profile.estimated_effort_days for profile in profiles.values())
        recommendations.append(f"⏱️ Estimated Total Effort: {total_effort} person-days ({total_effort/22:.1f} person-months)")
        
        return recommendations
    
    async def _calculate_confidence_score(self, relationship: CrossRepoRelationship) -> float:
        """Calculate confidence score for a cross-repository relationship."""
        base_score = 0.5
        
        # Boost confidence based on relationship type
        if relationship.relationship_type == 'IMPLEMENTS_BUSINESS_RULE':
            base_score += 0.3
        elif relationship.relationship_type == 'CALLS_SERVICE':
            base_score += 0.2
        elif relationship.relationship_type == 'DEPENDS_ON_TYPE':
            base_score += 0.1
        
        # Boost confidence if business context is available
        if relationship.business_context:
            base_score += 0.1
        
        return min(base_score, 1.0)
    
    async def _assess_migration_impact(self, relationship: CrossRepoRelationship) -> str:
        """Assess migration impact level for a relationship."""
        if relationship.source_type == 'BusinessRule' or relationship.target_type == 'BusinessRule':
            return 'HIGH'
        elif relationship.relationship_type == 'CALLS_SERVICE':
            return 'MEDIUM'
        elif relationship.source_type == 'CORBAInterface' or relationship.target_type == 'CORBAInterface':
            return 'HIGH'
        else:
            return 'LOW'


# Export classes for use by other modules
__all__ = [
    'CrossRepositoryAnalyzer',
    'CrossRepoRelationship',
    'RepositoryMigrationProfile',
    'CrossRepoAnalysisResult'
]