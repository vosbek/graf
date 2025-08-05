"""
Cross-Repository Analysis API Routes
====================================

API endpoints for cross-repository analysis, batch processing,
and enterprise-scale legacy migration analysis.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query as QueryParam
from pydantic import BaseModel, Field
from pathlib import Path

from ...services.cross_repository_analyzer import (
    CrossRepositoryAnalyzer, CrossRepoAnalysisResult, 
    CrossRepoRelationship, RepositoryMigrationProfile
)
from ...services.batch_repository_processor import (
    BatchRepositoryProcessor, RepositoryBatchItem, ProcessingStatus, BatchProcessingResult
)
from ...services.shared_dependency_analyzer import (
    SharedDependencyAnalyzer, SharedDependencyAnalysisResult
)
from ...core.neo4j_client import Neo4jClient, GraphQuery
from ...core.chromadb_client import ChromaDBClient
from ...services.repository_processor_v2 import RepositoryProcessor
from ...dependencies import get_neo4j_client, get_chroma_client, get_repository_processor


logger = logging.getLogger(__name__)
router = APIRouter()

# Global batch processor instance
batch_processor: Optional[BatchRepositoryProcessor] = None


class CrossRepoAnalysisRequest(BaseModel):
    """Request model for cross-repository analysis."""
    repository_names: List[str] = Field(..., description="List of repository names to analyze")
    include_business_context: bool = Field(default=True, description="Include business rule analysis")
    max_depth: int = Field(default=3, ge=1, le=5, description="Maximum dependency traversal depth")
    
    class Config:
        schema_extra = {
            "example": {
                "repository_names": ["customer-service", "order-service", "inventory-service"],
                "include_business_context": True,
                "max_depth": 3
            }
        }


class BatchProcessingRequest(BaseModel):
    """Request model for batch repository processing."""
    repositories: List[Dict[str, Any]] = Field(..., description="List of repositories to process")
    batch_id: Optional[str] = Field(None, description="Optional batch identifier")
    max_concurrent: int = Field(default=8, ge=1, le=20, description="Maximum concurrent processes")
    priority_mode: bool = Field(default=True, description="Process high-priority repositories first")
    resume_from_checkpoint: bool = Field(default=False, description="Resume from previous checkpoint")
    
    class Config:
        schema_extra = {
            "example": {
                "repositories": [
                    {"repo_name": "customer-service", "repo_path": "/path/to/customer-service", "priority": 10},
                    {"repo_name": "order-service", "repo_path": "/path/to/order-service", "priority": 8}
                ],
                "batch_id": "migration_batch_2024",
                "max_concurrent": 8,
                "priority_mode": True
            }
        }


class MigrationPlanRequest(BaseModel):
    """Request model for migration planning."""
    repository_names: List[str] = Field(..., description="Repositories to include in migration plan")
    target_architecture: str = Field(default="microservices", description="Target architecture pattern")
    risk_tolerance: str = Field(default="medium", description="Risk tolerance: low, medium, high")
    timeline_months: int = Field(default=12, ge=1, le=60, description="Target timeline in months")
    
    class Config:
        schema_extra = {
            "example": {
                "repository_names": ["customer-service", "order-service"],
                "target_architecture": "microservices",
                "risk_tolerance": "medium",
                "timeline_months": 18
            }
        }


def get_batch_processor(
    repository_processor: RepositoryProcessor = Depends(get_repository_processor),
    neo4j_client: Neo4jClient = Depends(get_neo4j_client),
    chroma_client: ChromaDBClient = Depends(get_chroma_client)
) -> BatchRepositoryProcessor:
    """Get or create batch processor instance."""
    global batch_processor
    if batch_processor is None:
        batch_processor = BatchRepositoryProcessor(
            repository_processor=repository_processor,
            neo4j_client=neo4j_client,
            chroma_client=chroma_client,
            max_concurrent=8,
            max_memory_mb=4096
        )
    return batch_processor


def get_cross_repo_analyzer(
    neo4j_client: Neo4jClient = Depends(get_neo4j_client),
    chroma_client: ChromaDBClient = Depends(get_chroma_client),
    repository_processor: RepositoryProcessor = Depends(get_repository_processor)
) -> CrossRepositoryAnalyzer:
    """Get cross-repository analyzer instance."""
    return CrossRepositoryAnalyzer(
        neo4j_client=neo4j_client,
        chroma_client=chroma_client,
        repository_processor=repository_processor
    )


def get_shared_dependency_analyzer(
    neo4j_client: Neo4jClient = Depends(get_neo4j_client)
) -> SharedDependencyAnalyzer:
    """Get shared dependency analyzer instance."""
    return SharedDependencyAnalyzer(neo4j_client=neo4j_client)


@router.post("/analyze", response_model=Dict[str, Any])
async def analyze_cross_repository_relationships(
    request: CrossRepoAnalysisRequest,
    analyzer: CrossRepositoryAnalyzer = Depends(get_cross_repo_analyzer)
):
    """
    Analyze business relationships and dependencies across multiple repositories.
    
    This endpoint performs comprehensive cross-repository analysis to identify:
    - Business rule dependencies across repositories
    - Struts action service calls between systems
    - CORBA interface relationships
    - Migration complexity scoring
    - Optimal migration order recommendations
    """
    try:
        logger.info(f"Starting cross-repository analysis for {len(request.repository_names)} repositories")
        
        result = await analyzer.analyze_cross_repository_relationships(
            repository_names=request.repository_names,
            include_business_context=request.include_business_context,
            max_depth=request.max_depth
        )
        
        # Convert result to serializable format
        return {
            "analysis_id": f"cross_repo_{int(time.time())}",
            "total_repositories": result.total_repositories,
            "total_relationships": result.total_relationships,
            "analysis_time": result.analysis_time,
            "migration_order": result.migration_order,
            "critical_paths": result.critical_paths,
            "business_domains": result.business_domains,
            "recommendations": result.recommendations,
            "cross_repo_relationships": [
                {
                    "source_repo": rel.source_repo,
                    "source_component": rel.source_component,
                    "source_type": rel.source_type,
                    "target_repo": rel.target_repo,
                    "target_component": rel.target_component,
                    "target_type": rel.target_type,
                    "relationship_type": rel.relationship_type,
                    "confidence_score": rel.confidence_score,
                    "migration_impact": rel.migration_impact,
                    "business_context": rel.business_context
                }
                for rel in result.cross_repo_relationships
            ],
            "repository_profiles": {
                name: {
                    "repo_name": profile.repo_name,
                    "total_components": profile.total_components,
                    "business_rules_count": profile.business_rules_count,
                    "struts_actions_count": profile.struts_actions_count,
                    "corba_interfaces_count": profile.corba_interfaces_count,
                    "jsp_components_count": profile.jsp_components_count,
                    "external_dependencies": profile.external_dependencies,
                    "internal_dependencies": profile.internal_dependencies,
                    "migration_complexity": profile.migration_complexity,
                    "migration_priority": profile.migration_priority,
                    "estimated_effort_days": profile.estimated_effort_days,
                    "blockers": profile.blockers,
                    "dependencies_on": profile.dependencies_on,
                    "dependents": profile.dependents
                }
                for name, profile in result.repository_profiles.items()
            }
        }
        
    except Exception as e:
        logger.error(f"Cross-repository analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/batch-process")
async def start_batch_processing(
    request: BatchProcessingRequest,
    background_tasks: BackgroundTasks,
    processor: BatchRepositoryProcessor = Depends(get_batch_processor)
):
    """
    Start batch processing of multiple repositories for enterprise-scale analysis.
    
    This endpoint handles processing of 50-100 repositories with:
    - Concurrent processing with resource management
    - Progress tracking and checkpointing
    - Error recovery and retry logic
    - Performance monitoring
    """
    try:
        # Convert request to batch items
        batch_items = []
        for repo_data in request.repositories:
            item = RepositoryBatchItem(
                repo_name=repo_data["repo_name"],
                repo_path=repo_data["repo_path"],
                priority=repo_data.get("priority", 5)
            )
            batch_items.append(item)
        
        # Start batch processing in background
        batch_id = request.batch_id or f"batch_{int(time.time())}"
        
        async def progress_callback(progress: float, item: RepositoryBatchItem):
            logger.info(f"Batch {batch_id}: {progress:.1f}% complete - {item.repo_name} {item.status.value}")
        
        # Store batch processing task
        background_tasks.add_task(
            processor.process_repository_batch,
            batch_items,
            batch_id,
            request.resume_from_checkpoint,
            progress_callback
        )
        
        return {
            "batch_id": batch_id,
            "status": "started",
            "total_repositories": len(batch_items),
            "max_concurrent": request.max_concurrent,
            "message": f"Batch processing started for {len(batch_items)} repositories",
            "status_endpoint": f"/api/v1/cross-repository/batch-status/{batch_id}"
        }
        
    except Exception as e:
        logger.error(f"Batch processing startup failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Batch processing failed: {str(e)}")


@router.get("/batch-status/{batch_id}")
async def get_batch_status(
    batch_id: str,
    processor: BatchRepositoryProcessor = Depends(get_batch_processor)
):
    """
    Get status of a running or completed batch processing operation.
    
    Returns detailed progress information including:
    - Overall progress percentage
    - Individual repository status
    - Error information
    - Performance metrics
    """
    try:
        status = await processor.get_batch_status(batch_id)
        
        if not status:
            raise HTTPException(status_code=404, detail=f"Batch not found: {batch_id}")
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get batch status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Status retrieval failed: {str(e)}")


@router.get("/migration-plan")
async def generate_migration_plan(
    request: MigrationPlanRequest,
    analyzer: CrossRepositoryAnalyzer = Depends(get_cross_repo_analyzer)
):
    """
    Generate a comprehensive migration plan for selected repositories.
    
    Creates a detailed migration roadmap including:
    - Phase-based migration approach
    - Risk assessment and mitigation strategies
    - Resource requirements and timeline
    - Dependencies and critical paths
    """
    try:
        # First perform cross-repository analysis
        analysis_result = await analyzer.analyze_cross_repository_relationships(
            repository_names=request.repository_names,
            include_business_context=True,
            max_depth=3
        )
        
        # Generate migration phases based on dependencies
        migration_phases = []
        remaining_repos = set(request.repository_names)
        phase_num = 1
        
        while remaining_repos:
            # Find repositories with no remaining dependencies
            phase_repos = []
            for repo in list(remaining_repos):
                profile = analysis_result.repository_profiles.get(repo)
                if profile:
                    # Check if all dependencies are already migrated
                    unresolved_deps = set(profile.dependencies_on) & remaining_repos
                    if not unresolved_deps:
                        phase_repos.append(repo)
            
            # If no repos can be migrated (circular dependency), pick lowest complexity
            if not phase_repos and remaining_repos:
                repo_complexities = [
                    (repo, analysis_result.repository_profiles[repo].migration_complexity)
                    for repo in remaining_repos
                    if repo in analysis_result.repository_profiles
                ]
                if repo_complexities:
                    phase_repos = [min(repo_complexities, key=lambda x: x[1])[0]]
            
            if phase_repos:
                # Calculate phase effort and timeline
                phase_effort = sum(
                    analysis_result.repository_profiles.get(repo, RepositoryMigrationProfile(
                        repo_name=repo, total_components=0, business_rules_count=0,
                        struts_actions_count=0, corba_interfaces_count=0, jsp_components_count=0,
                        external_dependencies=0, internal_dependencies=0, migration_complexity=0,
                        migration_priority="LOW", estimated_effort_days=0
                    )).estimated_effort_days
                    for repo in phase_repos
                )
                
                migration_phases.append({
                    "phase": phase_num,
                    "repositories": phase_repos,
                    "estimated_effort_days": phase_effort,
                    "estimated_duration_weeks": max(1, phase_effort // 5),  # Assuming 5 days per week
                    "parallel_execution": len(phase_repos) > 1,
                    "risk_level": "HIGH" if any(
                        analysis_result.repository_profiles.get(repo, RepositoryMigrationProfile(
                            repo_name=repo, total_components=0, business_rules_count=0,
                            struts_actions_count=0, corba_interfaces_count=0, jsp_components_count=0,
                            external_dependencies=0, internal_dependencies=0, migration_complexity=0,
                            migration_priority="CRITICAL", estimated_effort_days=0
                        )).migration_priority == "CRITICAL"
                        for repo in phase_repos
                    ) else "MEDIUM"
                })
                
                remaining_repos -= set(phase_repos)
                phase_num += 1
            else:
                break  # Safety break
        
        # Calculate overall timeline and resource requirements
        total_effort_days = sum(phase["estimated_effort_days"] for phase in migration_phases)
        total_timeline_weeks = sum(phase["estimated_duration_weeks"] for phase in migration_phases)
        
        # Generate risk assessment
        risk_factors = []
        high_complexity_repos = [
            repo for repo, profile in analysis_result.repository_profiles.items()
            if profile.migration_complexity > 70
        ]
        if high_complexity_repos:
            risk_factors.append(f"High complexity repositories: {', '.join(high_complexity_repos)}")
        
        if len(analysis_result.critical_paths) > 3:
            risk_factors.append(f"Multiple critical dependency paths ({len(analysis_result.critical_paths)})")
        
        # Generate recommendations
        plan_recommendations = list(analysis_result.recommendations)
        if total_timeline_weeks > request.timeline_months * 4:
            plan_recommendations.append(f"Timeline may be optimistic - estimated {total_timeline_weeks} weeks vs target {request.timeline_months * 4} weeks")
        
        return {
            "migration_plan_id": f"plan_{int(time.time())}",
            "target_architecture": request.target_architecture,
            "timeline_months": request.timeline_months,
            "risk_tolerance": request.risk_tolerance,
            "migration_phases": migration_phases,
            "overall_metrics": {
                "total_repositories": len(request.repository_names),
                "total_effort_days": total_effort_days,
                "estimated_timeline_weeks": total_timeline_weeks,
                "estimated_team_size": max(1, total_effort_days // (request.timeline_months * 20)),
                "complexity_score": sum(
                    profile.migration_complexity 
                    for profile in analysis_result.repository_profiles.values()
                ) / len(analysis_result.repository_profiles)
            },
            "risk_assessment": {
                "overall_risk": "HIGH" if len(risk_factors) > 2 else "MEDIUM",
                "risk_factors": risk_factors,
                "critical_paths": analysis_result.critical_paths,
                "mitigation_strategies": [
                    "Implement comprehensive testing strategy",
                    "Plan for rollback procedures",
                    "Establish cross-team communication protocols",
                    "Consider feature flags for gradual rollout"
                ]
            },
            "recommendations": plan_recommendations,
            "dependencies_graph": {
                "repositories": list(request.repository_names),
                "relationships": [
                    {
                        "source": rel.source_repo,
                        "target": rel.target_repo,
                        "type": rel.relationship_type,
                        "impact": rel.migration_impact
                    }
                    for rel in analysis_result.cross_repo_relationships
                    if rel.migration_impact in ["HIGH", "CRITICAL"]
                ]
            }
        }
        
    except Exception as e:
        logger.error(f"Migration plan generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Migration plan failed: {str(e)}")


@router.get("/repository-profiles")
async def get_repository_profiles(
    repository_names: List[str] = QueryParam(..., description="Repository names to get profiles for"),
    neo4j_client: Neo4jClient = Depends(get_neo4j_client)
):
    """
    Get detailed migration profiles for specified repositories.
    
    Returns component counts, complexity metrics, and migration readiness
    for each repository in the enterprise portfolio.
    """
    try:
        profiles = {}
        
        for repo_name in repository_names:
            # Query repository components and metrics
            query = GraphQuery(
                cypher="""
                MATCH (repo:Repository {name: $repo_name})
                OPTIONAL MATCH (repo)-[:CONTAINS]->(br:BusinessRule)
                OPTIONAL MATCH (repo)-[:CONTAINS]->(sa:StrutsAction)
                OPTIONAL MATCH (repo)-[:CONTAINS]->(ci:CORBAInterface)
                OPTIONAL MATCH (repo)-[:CONTAINS]->(jsp:JSPComponent)
                OPTIONAL MATCH (repo)-[:CONTAINS]->(f:File)
                
                WITH repo,
                     count(DISTINCT br) as business_rules,
                     count(DISTINCT sa) as struts_actions,
                     count(DISTINCT ci) as corba_interfaces,
                     count(DISTINCT jsp) as jsp_components,
                     count(DISTINCT f) as files
                
                OPTIONAL MATCH (repo)-[:CONTAINS]->()-[r]->()
                
                RETURN repo,
                       business_rules,
                       struts_actions,
                       corba_interfaces,
                       jsp_components,
                       files,
                       count(DISTINCT r) as relationships
                """,
                parameters={"repo_name": repo_name},
                read_only=True
            )
            
            result = await neo4j_client.execute_query(query)
            
            if result.records:
                record = result.records[0]
                
                # Calculate complexity score
                business_rules = record["business_rules"]
                struts_actions = record["struts_actions"]
                corba_interfaces = record["corba_interfaces"]
                jsp_components = record["jsp_components"]
                files = record["files"]
                relationships = record["relationships"]
                
                complexity = (
                    business_rules * 2 +
                    struts_actions * 1.5 +
                    corba_interfaces * 3 +
                    jsp_components * 1 +
                    files * 0.1 +
                    relationships * 0.5
                )
                
                profiles[repo_name] = {
                    "repo_name": repo_name,
                    "component_counts": {
                        "business_rules": business_rules,
                        "struts_actions": struts_actions,
                        "corba_interfaces": corba_interfaces,
                        "jsp_components": jsp_components,
                        "files": files,
                        "relationships": relationships
                    },
                    "complexity_score": complexity,
                    "migration_priority": (
                        "CRITICAL" if complexity > 100 else
                        "HIGH" if complexity > 50 else
                        "MEDIUM" if complexity > 20 else
                        "LOW"
                    ),
                    "estimated_effort_days": int(complexity * 0.5),
                    "framework_analysis": {
                        "has_struts": struts_actions > 0,
                        "has_corba": corba_interfaces > 0,
                        "has_jsp": jsp_components > 0,
                        "legacy_framework_count": sum([
                            1 if struts_actions > 0 else 0,
                            1 if corba_interfaces > 0 else 0,
                            1 if jsp_components > 0 else 0
                        ])
                    }
                }
            else:
                profiles[repo_name] = {
                    "repo_name": repo_name,
                    "error": "Repository not found or not indexed"
                }
        
        return {
            "repository_profiles": profiles,
            "summary": {
                "total_repositories": len(repository_names),
                "profiles_found": len([p for p in profiles.values() if "error" not in p]),
                "average_complexity": sum(
                    p.get("complexity_score", 0) for p in profiles.values() if "error" not in p
                ) / max(1, len([p for p in profiles.values() if "error" not in p]))
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get repository profiles: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Profile retrieval failed: {str(e)}")


@router.get("/shared-dependencies")
async def analyze_shared_dependencies(
    repository_names: List[str] = QueryParam(..., description="Repository names to analyze shared dependencies"),
    analyzer: SharedDependencyAnalyzer = Depends(get_shared_dependency_analyzer)
):
    """
    Analyze shared libraries and dependencies across multiple repositories.
    
    Perfect for legacy migration analysis to identify:
    - Common Struts/CORBA/JSP versions across repositories
    - Shared utility libraries that need coordinated updates  
    - Version conflicts that need resolution
    - Consolidation opportunities for shared components
    """
    try:
        logger.info(f"Starting shared dependency analysis for {len(repository_names)} repositories")
        
        result = await analyzer.analyze_shared_dependencies(repository_names)
        
        return {
            "analysis_id": f"shared_deps_{int(time.time())}",
            "total_repositories": result.total_repositories,
            "total_dependencies": result.total_dependencies,
            "analysis_time": result.analysis_time,
            "framework_distribution": result.framework_distribution,
            "migration_recommendations": result.migration_recommendations,
            "shared_dependencies": [
                {
                    "artifact_id": dep.artifact_id,
                    "group_id": dep.group_id,
                    "versions": dep.versions,
                    "repositories": dep.repositories,
                    "usage_count": dep.usage_count,
                    "version_conflicts": dep.version_conflicts,
                    "latest_version": dep.latest_version,
                    "migration_priority": dep.migration_priority,
                    "framework_type": dep.framework_type
                }
                for dep in result.shared_dependencies
            ],
            "version_conflicts": [
                {
                    "artifact_id": conflict.artifact_id,
                    "group_id": conflict.group_id,
                    "conflicting_versions": conflict.conflicting_versions,
                    "affected_repositories": conflict.affected_repositories,
                    "severity": conflict.severity,
                    "resolution_strategy": conflict.resolution_strategy
                }
                for conflict in result.version_conflicts
            ],
            "consolidation_opportunities": result.consolidation_opportunities
        }
        
    except Exception as e:
        logger.error(f"Shared dependency analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Shared dependency analysis failed: {str(e)}")


@router.get("/business-domains")
async def get_business_domain_mapping(
    neo4j_client: Neo4jClient = Depends(get_neo4j_client)
):
    """
    Get business domain mapping across all repositories.
    
    Returns how repositories are grouped by business domains
    based on their business rules and component analysis.
    """
    try:
        # Query business domains from business rules
        query = GraphQuery(
            cypher="""
            MATCH (repo:Repository)-[:CONTAINS]->(br:BusinessRule)
            WHERE br.domain IS NOT NULL
            RETURN br.domain as domain, 
                   collect(DISTINCT repo.name) as repositories,
                   count(br) as business_rule_count
            ORDER BY business_rule_count DESC
            """,
            read_only=True
        )
        
        result = await neo4j_client.execute_query(query)
        
        domain_mapping = {}
        for record in result.records:
            domain = record["domain"]
            repositories = record["repositories"]
            rule_count = record["business_rule_count"]
            
            domain_mapping[domain] = {
                "repositories": repositories,
                "business_rule_count": rule_count,
                "repository_count": len(repositories)
            }
        
        # Get repositories without explicit domains
        orphan_query = GraphQuery(
            cypher="""
            MATCH (repo:Repository)
            WHERE NOT EXISTS((repo)-[:CONTAINS]->(:BusinessRule))
            OR NOT EXISTS((repo)-[:CONTAINS]->(:BusinessRule {domain: NOT NULL}))
            RETURN collect(repo.name) as orphan_repositories
            """,
            read_only=True
        )
        
        orphan_result = await neo4j_client.execute_query(orphan_query)
        orphan_repos = orphan_result.records[0]["orphan_repositories"] if orphan_result.records else []
        
        return {
            "business_domains": domain_mapping,
            "orphan_repositories": orphan_repos,
            "summary": {
                "total_domains": len(domain_mapping),
                "total_repositories_mapped": sum(d["repository_count"] for d in domain_mapping.values()),
                "orphan_repositories_count": len(orphan_repos)
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get business domain mapping: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Domain mapping failed: {str(e)}")


# Export router
__all__ = ['router']