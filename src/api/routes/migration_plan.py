"""
Migration Plan API router

Provides a clean GET /api/v1/migration-plan endpoint that returns a canonical
multi-repository migration plan schema. This router delegates to the same
planner service logic used by POST /api/v1/query/multi-repo/migration-impact
to keep a single source of truth.

Architectural notes:
- Keep imports light and avoid heavy side effects at import time.
- Use dependency injection for clients via src/dependencies.
- Define strict Pydantic models for the canonical response schema.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from typing_extensions import Annotated

from ...dependencies import get_neo4j_client, get_chroma_client  # DI clients


router = APIRouter()


# -------- Canonical Response Models --------

class PlanScope(BaseModel):
    repositories: Annotated[List[str], Field(min_length=1)] = Field(..., description="Repositories in scope for this plan")
    coverage: Dict[str, Optional[int]] = Field(
        default_factory=lambda: {"indexed_count": None, "total_repos": None}
    )


class Totals(BaseModel):
    actions: int = 0
    forms: int = 0
    jsps: int = 0
    services: int = 0
    corba_interfaces: int = 0
    data_models: int = 0


class Complexity(BaseModel):
    coupling_index: float = 0.0
    hotspots: int = 0
    avg_cyclomatic: Optional[float] = None


class Summary(BaseModel):
    totals: Totals = Field(default_factory=Totals)
    complexity: Complexity = Field(default_factory=Complexity)
    risk_score: float = 0.0  # 0-100
    effort_score: float = 0.0  # 0-100


class CrossRepoDependency(BaseModel):
    from_repo: str
    to_repo: str
    weight: float = 0.0
    types: List[str] = Field(default_factory=list)


class SharedArtifact(BaseModel):
    artifact: str
    repos: Annotated[List[str], Field(min_length=1)]
    type: str


class Hotspot(BaseModel):
    repo: str
    reason: str
    evidence: Dict[str, Any] = Field(default_factory=dict)
    severity: str = "medium"  # low|medium|high|critical


class CrossRepo(BaseModel):
    dependencies: List[CrossRepoDependency] = Field(default_factory=list)
    shared_artifacts: List[SharedArtifact] = Field(default_factory=list)
    hotspots: List[Hotspot] = Field(default_factory=list)


class SliceItem(BaseModel):
    name: str
    repos: Annotated[List[str], Field(min_length=1)]
    features: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    effort: int = 3  # 1-5
    risk: int = 3    # 1-5
    rationale: str = ""


class Slices(BaseModel):
    items: List[SliceItem] = Field(default_factory=list)
    sequence: List[str] = Field(default_factory=list)


class GraphQLPlan(BaseModel):
    recommended_types: List[str] = Field(default_factory=list)
    recommended_queries: List[str] = Field(default_factory=list)
    recommended_mutations: List[str] = Field(default_factory=list)
    sdl_preview: Optional[str] = None
    notes: List[str] = Field(default_factory=list)


class RoadmapPhase(BaseModel):
    name: str
    goals: List[str] = Field(default_factory=list)
    exit_criteria: List[str] = Field(default_factory=list)
    suggested_epics: List[Dict[str, str]] = Field(default_factory=list)


class Roadmap(BaseModel):
    phases: List[RoadmapPhase] = Field(default_factory=list)
    steps: List[str] = Field(default_factory=list)


class Diagnostics(BaseModel):
    data_sources: Dict[str, bool] = Field(default_factory=lambda: {"neo4j": False, "chroma": False})
    generated_at: str


class MultiRepoPlan(BaseModel):
    plan_scope: PlanScope
    summary: Summary
    cross_repo: CrossRepo
    slices: Slices
    graphql: GraphQLPlan
    roadmap: Roadmap
    diagnostics: Diagnostics


# -------- Router --------

@router.get("", response_model=MultiRepoPlan)
async def get_migration_plan(
    repositories: str = Query(..., description="Comma-separated list of repository names, e.g. repo1,repo2"),
    neo4j_client: Any = Depends(get_neo4j_client),
    chroma_client: Any = Depends(get_chroma_client),
):
    """
    Return a canonical multi-repo migration plan for the given repositories.
    Delegates to the same planning logic used by POST /api/v1/query/multi-repo/migration-impact.
    No fallbacks: raises 400/503 on errors.
    """
    repo_list = [r.strip() for r in repositories.split(",") if r.strip()]
    if not repo_list:
        raise HTTPException(status_code=400, detail="At least one repository must be specified")

    # Late import to avoid heavy deps at import time. We standardize by delegating to the existing
    # multi-repo planning logic in the Query router/service. If not present, the call should fail,
    # as we do not use fallbacks.
    try:
        from ..query import router as query_router  # for discovery via same module
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Planner service unavailable: {e}")

    # We need a callable that executes the planning for multi-repo impact.
    # The query router should expose a function or we reach the service layer directly.
    # Prefer service layer if available.
    try:
        from ...services.migration_planner import MultiRepoPlanner  # type: ignore
        planner = MultiRepoPlanner(neo4j_client=neo4j_client, chroma_client=chroma_client)
        plan = await planner.plan_multi_repo(repo_list)
        # Expect plan already in canonical shape (dict compatible with MultiRepoPlan)
        return MultiRepoPlan(**plan)
    except ModuleNotFoundError:
        # Fallback to query endpoint handler import within same codebase (no HTTP round-trip).
        # NOTE: This expects a function `plan_migration_impact` to exist; if not, raise 503.
        try:
            # Attempt to import an internal handler from query routes/services
            from ..query import plan_migration_impact as internal_plan  # type: ignore
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Planner function not found: {e}")

        try:
            # Call internal plan function; it should return canonical dict
            plan = await internal_plan({"repository_names": repo_list})
            return MultiRepoPlan(**plan)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Planning failed: {e}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Planner invocation failed: {e}")