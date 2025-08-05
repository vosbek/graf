"""
Graph visualization API routes.

Exposes GET /api/v1/graph/visualization to return a repository-centric subgraph
as normalized nodes/edges suitable for UI visualization. Supports depth/limit
controls, preserves original relationship types, and can emit a sequential-
thinking trace with knowledge graph MCP logging (local memory MCP) when
trace=true.

Nodes: { id, type, name, path, size, metadata }
Edges: { source, target, relationship_type, weight, metadata }

Industry-aligned slice for v1:
- Nodes: Repository, Directory, File, Class, Function, MavenArtifact, Endpoint, Database
- Edges: CONTAINS, IMPORTS, CALLS, DEPENDS_ON, EXPOSES, READS_FROM, WRITES_TO
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Depends, Request
from pydantic import BaseModel, Field, conint

from ...dependencies import get_neo4j_client

# Ensure router is mounted under /api/v1/graph and add lightweight probes
router = APIRouter()

@router.get("/ping")
async def graph_ping():
    import time
    return {"ok": True, "ts": time.time()}

@router.get("/diag")
async def graph_diag(request: Request):
    try:
        app_state = getattr(request, "app").state
    except Exception:
        app_state = None
    is_ready = True
    init_err = None
    try:
        if app_state is not None:
            is_ready = bool(getattr(app_state, "is_ready", True))
            init_err = getattr(app_state, "initialization_error", None)
    except Exception:
        pass
    return {
        "router_alive": True,
        "app_ready": is_ready,
        "initialization_error": f"{init_err}" if init_err else None
    }

# Lightweight probes to verify router mount and app readiness without DB access
@router.get("/ping")
async def graph_ping():
    import time
    return {"ok": True, "ts": time.time()}

@router.get("/diag")
async def graph_diag(request: Request):
    try:
        app_state = getattr(request, "app").state
    except Exception:
        app_state = None
    is_ready = True
    init_err = None
    try:
        if app_state is not None:
            is_ready = bool(getattr(app_state, "is_ready", True))
            init_err = getattr(app_state, "initialization_error", None)
    except Exception:
        pass
    return {
        "router_alive": True,
        "app_ready": is_ready,
        "initialization_error": f"{init_err}" if init_err else None
    }


# ---------- Models ----------

class VizNode(BaseModel):
    id: str
    type: str
    name: Optional[str] = None
    path: Optional[str] = None
    size: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VizEdge(BaseModel):
    source: str
    target: str
    relationship_type: str
    weight: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VizResponse(BaseModel):
    nodes: List[VizNode]
    edges: List[VizEdge]
    diagnostics: Optional[Dict[str, Any]] = None


# ---------- Utilities ----------

_ALLOWED_NODE_LABELS = {
    "Repository", "Directory", "File", "Class", "Function",
    "MavenArtifact", "Endpoint", "Database"
}

_ALLOWED_REL_TYPES = {
    "CONTAINS", "IMPORTS", "CALLS", "DEPENDS_ON",
    "EXPOSES", "READS_FROM", "WRITES_TO"
}


def _coerce_label(label: str) -> str:
    # Ensure the label is within our allowed set; otherwise map to 'Unknown'
    return label if label in _ALLOWED_NODE_LABELS else "Unknown"


def _coerce_rel(rel_type: str) -> str:
    return rel_type if rel_type in _ALLOWED_REL_TYPES else rel_type


def _build_trace(repository: str, depth: int, limit_nodes: int, limit_edges: int, counts: Dict[str, int]) -> Dict[str, Any]:
    # Simple sequential thinking trace
    trace = {
        "thoughts": [
            {
                "step": 1,
                "content": f"Start visualization for repository={repository}, depth={depth}, limits nodes={limit_nodes}, edges={limit_edges}"
            },
            {
                "step": 2,
                "content": "Fetch subgraph via Neo4j using constrained expand up to specified depth, filtering labels/relations"
            },
            {
                "step": 3,
                "content": f"Normalize records into nodes/edges; preserve relationship_type; enriched metadata added"
            },
            {
                "step": 4,
                "content": f"Result size nodes={counts.get('nodes', 0)}, edges={counts.get('edges', 0)}"
            }
        ],
        "result_summary": {
            "nodes": counts.get("nodes", 0),
            "edges": counts.get("edges", 0)
        }
    }
    return trace


async def _log_to_memory_mcp(trace: Dict[str, Any], repository: str, depth: int, limit_nodes: int, limit_edges: int, counts: Dict[str, int]) -> None:
    """
    Best-effort logging to the local memory MCP server.

    Creates:
      - Entity: VisualizationRequest (observations: repo, depth, limits)
      - Entity: VisualizationResult (observations: counts, summary)
      - Relation: VisualizationRequest PRODUCED VisualizationResult
    """
    try:
        from .. import mcp  # optional: if you have a wrapper; otherwise use the tool directly if available
    except Exception:
        # Fallback: try using the MCP tool directly if exposed in this runtime (optional no-op here)
        return

    try:
        request_obs = [
            f"repository={repository}",
            f"depth={depth}",
            f"limit_nodes={limit_nodes}",
            f"limit_edges={limit_edges}"
        ]
        result_obs = [
            f"nodes={counts.get('nodes', 0)}",
            f"edges={counts.get('edges', 0)}",
            f"trace_summary={trace.get('result_summary', {})}"
        ]

        # Create entities
        try:
            await mcp.memory.create_entities([
                {
                    "name": "VisualizationRequest",
                    "entityType": "event",
                    "observations": request_obs,
                },
                {
                    "name": "VisualizationResult",
                    "entityType": "event",
                    "observations": result_obs,
                }
            ])
        except Exception:
            # If your MCP wrapper isn't async or signatures differ, ignore silently
            pass

        # Create relation
        try:
            await mcp.memory.create_relations([
                {
                    "from": "VisualizationRequest",
                    "to": "VisualizationResult",
                    "relationType": "PRODUCED"
                }
            ])
        except Exception:
            pass
    except Exception:
        # MCP logging is best-effort and non-blocking
        return


# ---------- Route ----------

@router.get("/visualization")
async def get_visualization(
    request: Request,
    repository: str = Query(..., description="Repository name to visualize"),
    depth: conint(ge=1, le=4) = Query(2, description="Traversal depth from repository"),
    limit_nodes: conint(ge=50, le=500) = Query(300, description="Max nodes to return"),
    limit_edges: conint(ge=100, le=1000) = Query(800, description="Max edges to return"),
    trace: bool = Query(False, description="Include sequential-thinking trace and log to memory MCP"),
    neo4j_client: Any = Depends(get_neo4j_client),
):
    """
    Return a normalized subgraph for a repository suitable for UI visualization.

    Strategy:
    - Start from (r:Repository {name: $repository})
    - Expand variable length up to 'depth' following allowed relationships
    - Filter node labels to allowed set, and relationships to allowed set
    - Deduplicate nodes/edges and respect limits
    """
    
    # Readiness guard - always emit JSON body, never bare 503
    try:
        is_ready = bool(getattr(request.app.state, "is_ready", True))
    except Exception:
        is_ready = True
    if not is_ready:
        return {
            "nodes": [],
            "edges": [],
            "diagnostics": {
                "status": "not_ready",
                "message": "Application still initializing, please wait",
                "retry_after": 30
            }
        }

    init_err = getattr(request.app.state, "initialization_error", None)
    if init_err:
        return {
            "nodes": [],
            "edges": [],
            "diagnostics": {
                "status": "initialization_failed",
                "message": f"System initialization failed: {init_err}",
                "error": f"{init_err}"
            }
        }
    
    # Validate required dependencies are available
    if not neo4j_client:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "service_unavailable",
                "message": "Neo4j client not available",
                "component": "neo4j"
            }
        )

    # ENHANCED: Multi-hop business-aware Cypher query for deep relationship visualization
    cypher = """
    MATCH (r:Repository {name: $repository})
    WITH r
    
    // Get all business components and their relationships
    OPTIONAL MATCH (r)-[:CONTAINS_STRUTS_ACTION]->(sa:StrutsAction)
    OPTIONAL MATCH (r)-[:CONTAINS_CORBA_INTERFACE]->(ci:CORBAInterface)  
    OPTIONAL MATCH (r)-[:CONTAINS_JSP_COMPONENT]->(jsp:JSPComponent)
    OPTIONAL MATCH (r)-[:CONTAINS]->(f:File)
    OPTIONAL MATCH (br:BusinessRule)
    WHERE br.file_path STARTS WITH f.path OR EXISTS {
        MATCH (f)-[:IMPLEMENTS_BUSINESS_RULE]->(br)
    }
    
    // Get business relationships (up to specified depth)
    OPTIONAL MATCH path = (sa)-[:IMPLEMENTS_BUSINESS_RULE|CALLS_SERVICE|USES_DATA*1..$depth]-(target)
    WHERE target <> sa
    
    // Collect all nodes with business context
    WITH r, 
         collect(DISTINCT sa) as struts_actions,
         collect(DISTINCT ci) as corba_interfaces,
         collect(DISTINCT jsp) as jsp_components,
         collect(DISTINCT f) as files,
         collect(DISTINCT br) as business_rules,
         collect(DISTINCT target) as connected_targets,
         collect(DISTINCT path) as business_paths
    
    // Build comprehensive node list
    WITH collect(DISTINCT {
      id: coalesce(r.id, toString(id(r))),
      labels: labels(r),
      name: coalesce(r.name, toString(id(r))),
      path: coalesce(r.path, ''),
      size: coalesce(r.size, 0),
      type: 'repository',
      business_context: {
        struts_actions: size(struts_actions),
        corba_interfaces: size(corba_interfaces),
        jsp_components: size(jsp_components),
        business_rules: size(business_rules)
      }
    }) AS repoNodes,
    
    // Struts Action nodes
    [sa IN struts_actions | {
      id: coalesce(sa.path, toString(id(sa))),
      labels: labels(sa),
      name: coalesce(sa.path, toString(id(sa))),
      path: coalesce(sa.file_path, ''),
      size: 1,
      type: 'struts_action',
      business_purpose: coalesce(sa.business_purpose, ''),
      migration_complexity: 'medium'
    }][0..$limit_nodes] AS strutsNodes,
    
    // CORBA Interface nodes  
    [ci IN corba_interfaces | {
      id: coalesce(ci.name, toString(id(ci))),
      labels: labels(ci),
      name: coalesce(ci.name, toString(id(ci))),
      path: coalesce(ci.file_path, ''),
      size: size(coalesce(ci.operations, [])),
      type: 'corba_interface',
      operations: coalesce(ci.operations, []),
      migration_complexity: 'high'
    }][0..$limit_nodes] AS corbaNodes,
    
    // JSP Component nodes
    [jsp IN jsp_components | {
      id: coalesce(jsp.id, toString(id(jsp))),
      labels: labels(jsp),
      name: coalesce(jsp.id, toString(id(jsp))),
      path: coalesce(jsp.file_path, ''),
      size: 1,
      type: 'jsp_component',
      business_purpose: coalesce(jsp.business_purpose, ''),
      migration_notes: coalesce(jsp.migration_notes, [])
    }][0..$limit_nodes] AS jspNodes,
    
    // Business Rule nodes
    [br IN business_rules | {
      id: coalesce(br.id, toString(id(br))),
      labels: labels(br),
      name: coalesce(br.rule_text, toString(id(br)))[0..50] + '...',
      path: coalesce(br.file_path, ''),
      size: 1,
      type: 'business_rule',
      domain: coalesce(br.domain, 'general'),
      complexity: coalesce(br.complexity, 'medium'),
      rule_type: coalesce(br.rule_type, 'validation')
    }][0..$limit_nodes] AS businessRuleNodes
    
    // Get all relationships between business components
    WITH repoNodes + strutsNodes + corbaNodes + jspNodes + businessRuleNodes AS allNodes
    
    MATCH (r:Repository {name: $repository})
    OPTIONAL MATCH (r)-[e1]-(n1)
    WHERE n1:StrutsAction OR n1:CORBAInterface OR n1:JSPComponent OR n1:BusinessRule OR n1:File
    
    OPTIONAL MATCH (n1)-[e2]-(n2) 
    WHERE n2:StrutsAction OR n2:CORBAInterface OR n2:JSPComponent OR n2:BusinessRule
    
    WITH allNodes,
    collect(DISTINCT {
      source: coalesce(startNode(e1).id, startNode(e1).path, startNode(e1).name, toString(id(startNode(e1)))),
      target: coalesce(endNode(e1).id, endNode(e1).path, endNode(e1).name, toString(id(endNode(e1)))),
      type: type(e1),
      relationship_type: type(e1)
    }) + collect(DISTINCT {
      source: coalesce(startNode(e2).id, startNode(e2).path, startNode(e2).name, toString(id(startNode(e2)))),
      target: coalesce(endNode(e2).id, endNode(e2).path, endNode(e2).name, toString(id(endNode(e2)))),
      type: type(e2),
      relationship_type: type(e2)
    }) AS allEdges
    
    RETURN allNodes[0..$limit_nodes] AS nodes, allEdges[0..$limit_edges] AS edges
    """

    # Normalize/validate params to primitives to avoid driver coercion issues
    params = {
        "repository": str(repository).strip(),
        "depth": int(depth),
        "allowed_node_labels": list(_ALLOWED_NODE_LABELS),
        "allowed_rel_types": list(_ALLOWED_REL_TYPES),
        "limit_nodes": int(limit_nodes),
        "limit_edges": int(limit_edges),
    }

    try:
        # Check if repository exists first
        repo_check_cypher = "MATCH (r:Repository {name: $repository}) RETURN count(r) as count"
        try:
            repo_result = await neo4j_client.execute_query_dict(repo_check_cypher, {"repository": repository})
        except AttributeError:
            # Fallback for raw query with parameters bound
            from ...core.neo4j_client import GraphQuery
            repo_query = GraphQuery(cypher=repo_check_cypher, parameters={"repository": repository}, read_only=True)
            repo_result_raw = await neo4j_client.execute_query(repo_query)
            repo_count = repo_result_raw.records[0]["count"] if getattr(repo_result_raw, "records", None) else 0
        else:
            repo_count = repo_result.get("count", 0) if isinstance(repo_result, dict) else 0
        
        # Return empty graph if repository doesn't exist (graceful handling)
        if repo_count == 0:
            return VizResponse(
                nodes=[],
                edges=[],
                diagnostics={
                    "repository": repository,
                    "depth": depth,
                    "limits": {"nodes": limit_nodes, "edges": limit_edges},
                    "counts": {"nodes": 0, "edges": 0},
                    "message": f"Repository '{repository}' not found - returning empty graph"
                }
            )
        
        # Execute main visualization query
        try:
            result = await neo4j_client.execute_query_dict(cypher, params)
        except AttributeError:
            # Fallback to generic execute_query returning records with .records
            # HARDEN: ensure parameters are bound to avoid ParameterMissing errors
            from ...core.neo4j_client import GraphQuery
            graph_query = GraphQuery(
                cypher=cypher,
                parameters=params,
                read_only=True
            )
            query_result = await neo4j_client.execute_query(graph_query)
            # Normalize (implementation-specific; adjust if your client differs)
            if query_result.records:
                first = query_result.records[0] if isinstance(query_result.records, list) else {}
                result = {
                    "nodes": first.get("nodes", []) if isinstance(first, dict) else [],
                    "edges": first.get("edges", []) if isinstance(first, dict) else [],
                }
            else:
                result = {"nodes": [], "edges": []}
                
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Convert all other exceptions into a 200 response with diagnostics to guarantee a JSON body
        import traceback
        return {
            "nodes": [],
            "edges": [],
            "diagnostics": {
                "status": "query_failed",
                "message": f"Graph database query failed: {str(e)}",
                "repository": repository,
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc() if trace else None
            }
        }

    # Result normalization
    raw_nodes = result.get("nodes", []) or []
    raw_edges = result.get("edges", []) or []

    nodes: List[VizNode] = []
    edges: List[VizEdge] = []

    # Deduplicate by id
    seen_node_ids = set()
    for n in raw_nodes:
        nid = str(n.get("id"))
        if not nid or nid in seen_node_ids:
            continue
        seen_node_ids.add(nid)

        labels = n.get("labels") or []
        # Prefer the most specific label in allowed set
        node_type = next((l for l in labels if l in _ALLOWED_NODE_LABELS), labels[0] if labels else "Unknown")
        node_type = _coerce_label(node_type)

        nodes.append(VizNode(
            id=nid,
            type=node_type,
            name=n.get("name"),
            path=n.get("path"),
            size=int(n.get("size") or 0),
            metadata={"labels": labels}
        ))

    # Deduplicate edges by composite key
    seen_edge_keys = set()
    for e in raw_edges:
        src = str(e.get("source"))
        tgt = str(e.get("target"))
        rel_type = _coerce_rel(str(e.get("type")))
        key = (src, tgt, rel_type)
        if not src or not tgt or key in seen_edge_keys:
            continue
        seen_edge_keys.add(key)
        edges.append(VizEdge(
            source=src,
            target=tgt,
            relationship_type=rel_type,
            weight=None,
            metadata={}
        ))

    counts = {"nodes": len(nodes), "edges": len(edges)}

    diagnostics: Dict[str, Any] = {
        "repository": repository,
        "depth": depth,
        "limits": {"nodes": limit_nodes, "edges": limit_edges},
        "counts": counts
    }

    # Optional sequential thinking trace and memory MCP logging
    if trace:
        seq = _build_trace(repository, depth, limit_nodes, limit_edges, counts)
        diagnostics["trace"] = seq
        # Best-effort MCP log (non-blocking)
        try:
            await _log_to_memory_mcp(seq, repository, depth, limit_nodes, limit_edges, counts)
        except Exception:
            pass

    return VizResponse(nodes=nodes, edges=edges, diagnostics=diagnostics)