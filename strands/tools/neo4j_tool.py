"""
Neo4j Tool interface (feature-flagged, import-safe)

Curated, read-only query surface over src/core/neo4j_client.Neo4jClient for the
Strands Chat Agent. This module avoids heavyweight imports at import time.
The real neo4j_client instance is injected only when configuration validation passes.
"""

from typing import Any, Dict, List


class Neo4jTool:
    """
    Minimal curated interface for graph lookups used by the chat agent.

    The concrete neo4j_client should be an instance of src.core.neo4j_client.Neo4jClient,
    injected by the application only when configuration validation passes.
    """

    def __init__(self, neo4j_client: Any):
        self._client = neo4j_client

    async def code_relationships(self, chunk_id: str) -> Dict[str, Any]:
        """
        Return immediate relationships for a code chunk (bounded):
          {
            "chunk_id": str,
            "callers": [ { "id": str, "name": str } ],
            "callees": [ { "id": str, "name": str } ],
            "domains": [ { "name": str } ]
          }

        Uses allowlisted, parameterized read-only Cypher via the client's helper methods.
        """
        if not isinstance(chunk_id, str) or not chunk_id.strip():
            raise ValueError("chunk_id is required")

        # Late import to avoid heavy imports at module import time
        # Expect the client to expose a suitable helper; otherwise use a narrow GraphQuery
        try:
            # Preferred: dedicated helper on the client if available
            rels = await self._client.find_code_relationships(chunk_id)  # type: ignore[attr-defined]
            # Expected shape from existing API: list[Dict[str, Any]] with callers/callees keys
            if isinstance(rels, list) and rels:
                return {"chunk_id": chunk_id, **rels[0]}
        except Exception:
            # Fall through to explicit read-only query using GraphQuery wrapper
            pass

        from src.core.neo4j_client import GraphQuery  # type: ignore

        cypher = """
        MATCH (c:CodeChunk {id: $chunk_id})
        OPTIONAL MATCH (caller:CodeChunk)-[:CALLS]->(c)
        OPTIONAL MATCH (c)-[:CALLS]->(callee:CodeChunk)
        OPTIONAL MATCH (c)-[:BELONGS_TO]->(d:Domain)
        RETURN
          collect(DISTINCT {id: caller.id, name: caller.name}) as callers,
          collect(DISTINCT {id: callee.id, name: callee.name}) as callees,
          collect(DISTINCT {name: d.name}) as domains
        """
        q = GraphQuery(cypher=cypher, parameters={"chunk_id": chunk_id}, read_only=True)
        res = await self._client.execute_query(q)
        if res.records:
            rec = res.records[0]
            return {
                "chunk_id": chunk_id,
                "callers": rec.get("callers", []),
                "callees": rec.get("callees", []),
                "domains": rec.get("domains", []),
            }
        return {"chunk_id": chunk_id, "callers": [], "callees": [], "domains": []}

    async def repo_flows_summary(self, repository_names: List[str]) -> Dict[str, Any]:
        """
        Return a concise cross-repository flows summary for architecture questions:
          {
            "repositories": [...],
            "flows": [ { "name": str, "repositories_involved": [str], "business_value": str } ],
            "integration_points": [ { "source": str, "target": str, "count": int } ]
          }

        Uses allowlisted helper methods when available.
        """
        if not repository_names or not all(isinstance(r, str) and r.strip() for r in repository_names):
            raise ValueError("repository_names must be a non-empty list of strings")

        flows = []
        integrations = []

        # Prefer schema manager helpers exposed via the client, if present
        try:
            flows = await self._client.find_business_flows_for_repositories(repository_names)  # type: ignore[attr-defined]
        except Exception:
            flows = []

        try:
            integrations = await self._client.find_integration_points(repository_names)  # type: ignore[attr-defined]
        except Exception:
            integrations = []

        return {
            "repositories": repository_names,
            "flows": flows or [],
            "integration_points": integrations or [],
        }