"""
Migration Planner service.

Produces a canonical multi-repository migration plan used by:
- GET /api/v1/migration-plan
- POST /api/v1/query/multi-repo/migration-impact

Canonical schema keys (dict returned):
{
  "plan_scope": { "repositories": [...], "coverage": { "indexed_count": int|null, "total_repos": int|null } },
  "summary": {
    "totals": {
      "actions": int, "forms": int, "jsps": int, "services": int,
      "corba_interfaces": int, "data_models": int
    },
    "complexity": { "coupling_index": float, "hotspots": int, "avg_cyclomatic": float|null },
    "risk_score": float, "effort_score": float
  },
  "cross_repo": {
    "dependencies": [ { "from_repo": str, "to_repo": str, "weight": float, "types": [str] } ],
    "shared_artifacts": [ { "artifact": str, "repos": [str], "type": str } ],
    "hotspots": [ { "repo": str, "reason": str, "evidence": { "file": str, "line": int|null }, "severity": str } ]
  },
  "slices": {
    "items": [
      { "name": str, "repos": [str], "features": [str], "dependencies": [str], "effort": int, "risk": int, "rationale": str }
    ],
    "sequence": [str]
  },
  "graphql": {
    "recommended_types": [str],
    "recommended_queries": [str],
    "recommended_mutations": [str],
    "sdl_preview": str|null,
    "notes": [str]
  },
  "roadmap": {
    "phases": [
      { "name": str, "goals": [str], "exit_criteria": [str],
        "suggested_epics": [ { "key": str|null, "title": str, "desc": str } ] }
    ],
    "steps": [str]
  },
  "diagnostics": { "data_sources": { "neo4j": bool, "chroma": bool }, "generated_at": str }
}
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class PlannerInputs:
    repositories: List[str]


class MultiRepoPlanner:
    """
    Multi-repository Migration Planner.
    Composes Neo4j-derived facts + light heuristics into a canonical plan.
    """

    def __init__(self, neo4j_client: Any, chroma_client: Any = None) -> None:
        self.neo4j = neo4j_client
        self.chroma = chroma_client

    async def plan_multi_repo(self, repositories: List[str]) -> Dict[str, Any]:
        if not repositories:
            raise ValueError("plan_multi_repo requires at least one repository")

        # Diagnostics
        diagnostics = {
            "data_sources": {"neo4j": bool(self.neo4j), "chroma": bool(self.chroma)},
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        # Compute cross-repo dependencies and shared artifacts (strictly from Neo4j)
        cross_deps = await self._get_cross_repo_dependencies(repositories)
        shared_artifacts = await self._get_shared_artifacts(repositories)

        # Compute simple totals and complexity heuristics
        totals = await self._compute_totals(repositories)
        coupling_index, hotspots = self._compute_coupling_and_hotspots(cross_deps, shared_artifacts)

        summary = {
            "totals": totals,
            "complexity": {
                "coupling_index": coupling_index,
                "hotspots": len(hotspots),
                "avg_cyclomatic": None,  # Optional: can be added later
            },
            "risk_score": self._score_risk(totals, coupling_index, len(hotspots)),
            "effort_score": self._score_effort(totals, coupling_index),
        }

        # Build slices and sequence using clustering heuristic
        slices_items, slice_sequence = self._cluster_slices_and_sequence(
            repositories=repositories,
            cross_deps=cross_deps,
            shared_artifacts=shared_artifacts,
            totals=totals,
        )

        # GraphQL suggestions inferred from DTOs/Entities (with fallbacks)
        graphql = await self._graphql_suggestions(repositories, totals)

        # Roadmap phases and steps (deterministic)
        roadmap = self._build_roadmap_phases_and_steps(slices_items)

        plan = {
            "plan_scope": {
                "repositories": repositories,
                "coverage": {"indexed_count": None, "total_repos": None},
            },
            "summary": summary,
            "cross_repo": {
                "dependencies": cross_deps,
                "shared_artifacts": shared_artifacts,
                "hotspots": hotspots,
            },
            "slices": {
                "items": slices_items,
                "sequence": slice_sequence,
            },
            "graphql": graphql,
            "roadmap": roadmap,
            "diagnostics": diagnostics,
        }
        return plan

    async def _get_cross_repo_dependencies(self, repositories: List[str]) -> List[Dict[str, Any]]:
        try:
            recs = await self.neo4j.find_cross_repository_dependencies(repositories)
        except Exception:
            recs = []
        deps: List[Dict[str, Any]] = []
        for r in recs:
            # Attempt to normalize common field names
            fr = r.get("from_repo") or r.get("source_repo") or r.get("source") or r.get("from")
            to = r.get("to_repo") or r.get("target_repo") or r.get("target") or r.get("to")
            wt = r.get("weight") or r.get("count") or r.get("dependency_count") or 1
            ty = r.get("types") or r.get("edge_types") or []
            deps.append(
                {
                    "from_repo": str(fr) if fr is not None else "",
                    "to_repo": str(to) if to is not None else "",
                    "weight": float(wt) if wt is not None else 1.0,
                    "types": list(ty) if isinstance(ty, list) else ([] if ty is None else [str(ty)]),
                }
            )
        # Filter invalid
        deps = [d for d in deps if d["from_repo"] and d["to_repo"] and d["from_repo"] != d["to_repo"]]
        return deps

    async def _get_shared_artifacts(self, repositories: List[str]) -> List[Dict[str, Any]]:
        try:
            recs = await self.neo4j.find_shared_db_artifacts(repositories)
        except Exception:
            recs = []
        shared: List[Dict[str, Any]] = []
        for r in recs:
            shared.append(
                {
                    "artifact": str(r.get("artifact", "")),
                    "repos": [str(x) for x in (r.get("repos") or [])],
                    "type": str(r.get("type", "Unknown")),
                }
            )
        return [s for s in shared if s["artifact"] and len(s["repos"]) > 1]

    async def _compute_totals(self, repositories: List[str]) -> Dict[str, int]:
        """
        Compute totals from Neo4j, scoped to provided repositories.
        This uses defensive Cypher to tolerate partial schemas/labels.
        """
        from typing import Any as _Any, Dict as _Dict  # local aliases to avoid shadowing

        def _safe_int(val: _Any) -> int:
            try:
                return max(0, int(val))
            except Exception:
                return 0

        totals: _Dict[str, int] = {
            "actions": 0,
            "forms": 0,
            "jsps": 0,
            "services": 0,
            "corba_interfaces": 0,
            "data_models": 0,
        }

        async def _count(cypher: str, params: _Dict[str, _Any]) -> int:
            try:
                from ..core.neo4j_client import GraphQuery  # type: ignore
                q = GraphQuery(cypher=cypher, parameters=params, read_only=True)
                res = await self.neo4j.execute_query(q)
                if res and getattr(res, "records", None):
                    rec = res.records[0] if res.records else {}
                    for k in ("cnt", "count", "total", "n"):
                        if k in rec:
                            return _safe_int(rec[k])
                return 0
            except Exception:
                return 0

        params: _Dict[str, _Any] = {"repos": repositories}

        # Actions (Struts-like)
        cypher_actions = """
        UNWIND $repos AS repo
        MATCH (r:Repository {name: repo})-[:CONTAINS]->(c:Class)
        WHERE coalesce(c.is_action,false) = true
           OR c.stereotype = 'Action'
           OR c.name ENDS WITH 'Action'
        RETURN count(DISTINCT c) AS cnt
        """
        totals["actions"] = await _count(cypher_actions, params)

        # Forms (ActionForm / FormBean)
        cypher_forms = """
        UNWIND $repos AS repo
        MATCH (r:Repository {name: repo})-[:CONTAINS]->(c:Class)
        WHERE coalesce(c.is_formbean,false) = true
           OR c.stereotype = 'Form'
           OR c.name ENDS WITH 'Form' OR c.name ENDS WITH 'FormBean'
        RETURN count(DISTINCT c) AS cnt
        """
        totals["forms"] = await _count(cypher_forms, params)

        # JSP files
        cypher_jsps = """
        UNWIND $repos AS repo
        MATCH (r:Repository {name: repo})-[:CONTAINS]->(f:File)
        WHERE coalesce(f.extension,'') = '.jsp'
           OR toLower(f.path) ENDS WITH '.jsp'
        RETURN count(DISTINCT f) AS cnt
        """
        totals["jsps"] = await _count(cypher_jsps, params)

        # Services
        cypher_services = """
        UNWIND $repos AS repo
        MATCH (r:Repository {name: repo})-[:CONTAINS]->(c:Class)
        WHERE c.stereotype = 'Service' OR c.name ENDS WITH 'Service'
        RETURN count(DISTINCT c) AS cnt
        """
        totals["services"] = await _count(cypher_services, params)

        # Data models (DTO/Entity/Model)
        cypher_models = """
        UNWIND $repos AS repo
        MATCH (r:Repository {name: repo})-[:CONTAINS]->(c:Class)
        WHERE c.stereotype IN ['Entity','DTO','Model']
           OR c.name ENDS WITH 'DTO' OR c.name ENDS WITH 'Entity'
           OR coalesce(c.package,'') CONTAINS '.model.'
        RETURN count(DISTINCT c) AS cnt
        """
        totals["data_models"] = await _count(cypher_models, params)

        # CORBA interfaces (IDL)
        cypher_corba = """
        UNWIND $repos AS repo
        MATCH (r:Repository {name: repo})-[:CONTAINS]->(c:Class)
        WHERE coalesce(c.is_corba,false) = true
           OR coalesce(c.package,'') CONTAINS '.idl'
           OR coalesce(c.package,'') CONTAINS '.corba'
           OR c.name ENDS WITH 'Operations' OR c.name ENDS WITH 'Helper'
        RETURN count(DISTINCT c) AS cnt
        """
        totals["corba_interfaces"] = await _count(cypher_corba, params)

        return totals

    def _compute_coupling_and_hotspots(
        self,
        cross_deps: List[Dict[str, Any]],
        shared_artifacts: List[Dict[str, Any]],
    ) -> Tuple[float, List[Dict[str, Any]]]:
        total_weight = sum(d.get("weight", 0.0) for d in cross_deps)
        # Normalize coupling index to 0..100 heuristic
        coupling_index = float(min(100.0, total_weight)) if total_weight > 0 else 0.0

        # Hotspots: top 5 edges + top 5 shared artifacts
        edges_sorted = sorted(cross_deps, key=lambda d: d.get("weight", 0.0), reverse=True)[:5]
        hot_edges = [
            {
                "repo": f'{e.get("from_repo", "")}→{e.get("to_repo", "")}',
                "reason": "High cross-repo dependency weight",
                "evidence": {"file": "", "line": None},
                "severity": "high" if e.get("weight", 0) >= 5 else "medium",
            }
            for e in edges_sorted
        ]
        shared_sorted = sorted(shared_artifacts, key=lambda s: len(s.get("repos", [])), reverse=True)[:5]
        hot_shared = [
            {
                "repo": ",".join(s.get("repos", [])),
                "reason": f'Shared {s.get("type", "Artifact")} {s.get("artifact","")}',
                "evidence": {"file": "", "line": None},
                "severity": "medium",
            }
            for s in shared_sorted
        ]
        return coupling_index, hot_edges + hot_shared

    def _cluster_slices_and_sequence(
        self,
        repositories: List[str],
        cross_deps: List[Dict[str, Any]],
        shared_artifacts: List[Dict[str, Any]],
        totals: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Cluster repositories by weakly connected components using cross_deps and
        derive a slice sequence with a condensed DAG. Effort/risk heuristics are computed
        from coupling and shared artifacts.
        """
        # Build adjacency and coupling weights
        adj: Dict[str, set] = {r: set() for r in repositories}
        inbound_w: Dict[str, float] = {r: 0.0 for r in repositories}
        outbound_w: Dict[str, float] = {r: 0.0 for r in repositories}
        for d in cross_deps:
            fr, to = d.get("from_repo"), d.get("to_repo")
            if fr in adj and to in adj:
                adj[fr].add(to)
                adj[to].add(fr)  # weakly connected components
                w = float(d.get("weight", 1.0))
                inbound_w[to] += w
                outbound_w[fr] += w

        # BFS components
        visited = set()
        components: List[List[str]] = []
        for r in repositories:
            if r in visited:
                continue
            comp = []
            queue = [r]
            visited.add(r)
            while queue:
                cur = queue.pop(0)
                comp.append(cur)
                for nb in adj[cur]:
                    if nb not in visited:
                        visited.add(nb)
                        queue.append(nb)
            components.append(comp)

        # Shared artifact density per repo
        shared_density: Dict[str, int] = {r: 0 for r in repositories}
        for s in shared_artifacts:
            for rr in s.get("repos", []) or []:
                if rr in shared_density:
                    shared_density[rr] += 1

        # Build slice items with heuristics
        items: List[Dict[str, Any]] = []
        idx = 1
        for comp in components:
            size = len(comp)
            comp_in = sum(inbound_w.get(r, 0.0) for r in comp)
            comp_out = sum(outbound_w.get(r, 0.0) for r in comp)
            comp_shared = sum(shared_density.get(r, 0) for r in comp)

            # Normalize to 1..5 buckets
            effort = min(5, max(1, int(round((size + comp_in / max(1.0, size)) / 2))))
            risk = min(5, max(1, int(round((comp_shared + comp_out / max(1.0, size)) / 3))))

            items.append(
                {
                    "name": f"slice-{idx}",
                    "repos": comp,
                    "features": [],
                    "dependencies": list(
                        {
                            d["from_repo"]
                            for d in cross_deps
                            if d.get("to_repo") in comp and d.get("from_repo") not in comp
                        }
                    ),
                    "effort": effort,
                    "risk": risk,
                    "rationale": "Clustered by cross-repo connectivity; refine with domain labels when available",
                }
            )
            idx += 1

        # Slice DAG and sequence (Kahn + tie-break by risk, then effort)
        repo_to_slice: Dict[str, str] = {}
        for it in items:
            for r in it["repos"]:
                repo_to_slice[r] = it["name"]

        edges: Dict[str, set] = {it["name"]: set() for it in items}
        indeg: Dict[str, int] = {it["name"]: 0 for it in items}
        for d in cross_deps:
            a, b = d.get("from_repo"), d.get("to_repo")
            if a in repo_to_slice and b in repo_to_slice:
                sa, sb = repo_to_slice[a], repo_to_slice[b]
                if sa != sb and sb not in edges[sa]:
                    edges[sa].add(sb)

        for s, outs in edges.items():
            for t in outs:
                indeg[t] += 1

        risk_map = {it["name"]: it["risk"] for it in items}
        effort_map = {it["name"]: it["effort"] for it in items}
        sequence: List[str] = []
        frontier = [s for s, deg in indeg.items() if deg == 0]
        frontier.sort(key=lambda s: (risk_map[s], effort_map[s]))

        while frontier:
            cur = frontier.pop(0)
            sequence.append(cur)
            for nb in list(edges[cur]):
                indeg[nb] -= 1
                if indeg[nb] == 0:
                    frontier.append(nb)
            frontier.sort(key=lambda s: (risk_map[s], effort_map[s]))

        if len(sequence) < len(items):
            remaining = [it["name"] for it in items if it["name"] not in sequence]
            remaining.sort(key=lambda s: (risk_map[s], effort_map[s]))
            sequence.extend(remaining)

        return items, sequence

    async def _graphql_suggestions(self, repositories: List[str], totals: Dict[str, int]) -> Dict[str, Any]:
        """
        Infer GraphQL suggestions using DTO/Entity shapes where available,
        with safe fallbacks to generic suggestions.
        """
        from typing import Tuple as _Tuple

        recommended_types: List[str] = []
        recommended_queries: List[str] = []
        recommended_mutations: List[str] = []
        sdl_preview = ""
        notes = [
            "Ensure field-level authorization checks.",
            "Add pagination for list queries.",
            "Refine types by inferring DTOs and ActionForms.",
        ]

        inferred_types: List[Dict[str, Any]] = []
        try:
            from ..core.neo4j_client import GraphQuery  # type: ignore
            cypher = """
            UNWIND $repos AS repo
            MATCH (r:Repository {name: repo})-[:CONTAINS]->(c:Class)
            WHERE c.stereotype IN ['Entity','DTO','Model'] OR c.name ENDS WITH 'DTO' OR c.name ENDS WITH 'Entity'
            WITH DISTINCT c LIMIT 5
            RETURN c.name AS name, c.fields AS fields
            """
            q = GraphQuery(cypher=cypher, parameters={"repos": repositories}, read_only=True)
            res = await self.neo4j.execute_query(q)
            for rec in (getattr(res, "records", []) or []):
                name = rec.get("name") or "Entity"
                fields = rec.get("fields") or []
                norm_fields: List[_Tuple[str, str]] = []
                if isinstance(fields, list):
                    for f in fields:
                        if isinstance(f, dict):
                            norm_fields.append((str(f.get("name", "id")), str(f.get("type", "String"))))
                        else:
                            norm_fields.append((str(f), "String"))
                inferred_types.append({"name": name, "fields": norm_fields})
        except Exception:
            pass

        if inferred_types:
            for t in inferred_types:
                recommended_types.append(t["name"])
                recommended_queries.extend([f"get{t['name']}", f"list{t['name']}s"])
                recommended_mutations.extend([f"create{t['name']}", f"update{t['name']}"])
            # Deduplicate and sort
            recommended_types = sorted(list(dict.fromkeys(recommended_types)))
            recommended_queries = sorted(list(dict.fromkeys(recommended_queries)))
            recommended_mutations = sorted(list(dict.fromkeys(recommended_mutations)))

            # SDL preview from the first inferred type
            first = inferred_types[0]
            fields_sdl = "\n".join([f"  {fname}: {self._map_field_type(ftype)}" for fname, ftype in first["fields"][:8]]) or "  id: ID!\n  name: String!"
            sdl_preview = f"type {first['name']} {{\n{fields_sdl}\n}}\n\ntype Query {{\n  get{first['name']}(id: ID!): {first['name']}\n  list{first['name']}s: [{first['name']}]!\n}}\n"
        else:
            # Fallback if no inferred types
            if totals.get("data_models", 0) > 0:
                recommended_types.extend(["Entity"])
            recommended_queries.extend(["getEntity", "listEntities"])
            recommended_mutations.extend(["createEntity", "updateEntity"])
            sdl_preview = "type Entity {\n  id: ID!\n  name: String!\n}\n\ntype Query {\n  getEntity(id: ID!): Entity\n  listEntities: [Entity!]!\n}\n"

        return {
            "recommended_types": recommended_types,
            "recommended_queries": recommended_queries,
            "recommended_mutations": recommended_mutations,
            "sdl_preview": sdl_preview,
            "notes": notes,
        }

    def _map_field_type(self, t: str) -> str:
        t = (t or "").lower()
        if t in ("long", "int", "integer", "short", "byte"):
            return "Int"
        if t in ("double", "float", "decimal", "bigdecimal"):
            return "Float"
        if t in ("bool", "boolean"):
            return "Boolean"
        if t in ("id", "uuid"):
            return "ID"
        return "String"

    def _build_roadmap_phases_and_steps(self, slices_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        phases = [
            {
                "name": "Discovery Hardening",
                "goals": [
                    "Verify repository coverage and indexing",
                    "Validate cross-repo dependency graph",
                ],
                "exit_criteria": [
                    "Coverage > 90%",
                    "Cross-repo edges computed",
                ],
                "suggested_epics": [{"key": None, "title": "Hardening", "desc": "Improve inventory and graph coverage"}],
            },
            {
                "name": "First Slices",
                "goals": ["Deliver first vertical slices with GraphQL façade", "Stabilize adapters"],
                "exit_criteria": ["2–3 slices in production", "Contract tests green"],
                "suggested_epics": [{"key": None, "title": "Slice-1", "desc": "Implement first slice"}],
            },
            {
                "name": "Parallel Tracks",
                "goals": ["Scale up slice teams", "Introduce federation if applicable"],
                "exit_criteria": ["Slices scaled", "Latency within SLO"],
                "suggested_epics": [{"key": None, "title": "Scale", "desc": "Enable parallelization"}],
            },
            {
                "name": "Core Refactors",
                "goals": ["Extract shared services", "Reduce coupling hotspots"],
                "exit_criteria": ["Hotspot index reduced by 50%"],
                "suggested_epics": [{"key": None, "title": "Core", "desc": "Refactor shared core modules"}],
            },
            {
                "name": "Cutover",
                "goals": ["Finalize GraphQL adoption", "Retire legacy paths"],
                "exit_criteria": ["Legacy disabled", "Regression suite green"],
                "suggested_epics": [{"key": None, "title": "Cutover", "desc": "Full transition"}],
            },
        ]
        steps = [
            "1. Validate inventory and dependency graph",
            "2. Infer initial GraphQL types for key domains",
            "3. Implement first slices and resolvers",
            "4. Add contract/regression tests",
            "5. Scale slices and reduce hotspots",
            "6. Execute cutover plan",
        ]
        return {"phases": phases, "steps": steps}