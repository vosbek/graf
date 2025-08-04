import asyncio
import types
import pytest

from typing import Any, Dict, List

# Import planner class under test
from src.services.migration_planner import MultiRepoPlanner


class _MockNeo4jResult:
    def __init__(self, records: List[Dict[str, Any]]):
        self.records = records


class MockNeo4jClient:
    """
    Minimal async-capable mock for the Neo4j client used by MultiRepoPlanner.
    Implements:
      - find_cross_repository_dependencies
      - find_shared_db_artifacts
      - execute_query(GraphQuery)
    """

    async def find_cross_repository_dependencies(self, repositories: List[str]) -> List[Dict[str, Any]]:
        # Deterministic small graph
        if len(repositories) >= 2:
            return [
                {"from_repo": repositories[0], "to_repo": repositories[1], "weight": 3, "types": ["CALLS"]},
                {"from_repo": repositories[1], "to_repo": repositories[0], "weight": 1, "types": ["IMPORTS"]},
            ]
        return []

    async def find_shared_db_artifacts(self, repositories: List[str]) -> List[Dict[str, Any]]:
        if len(repositories) >= 2:
            return [
                {"artifact": "customer_table", "repos": repositories[:2], "type": "DB_TABLE"},
            ]
        return []

    async def execute_query(self, graph_query: Any) -> _MockNeo4jResult:
        """
        Return counts based on simple cypher matching to simulate totals:
          - actions/forms/jsps/services/data_models/corba_interfaces
        """
        cypher = getattr(graph_query, "cypher", "") or ""
        # Invent simple count mapping by keyword to have non-zero totals
        if "WHERE coalesce(c.is_action" in cypher or "stereotype = 'Action'" in cypher:
            return _MockNeo4jResult([{"cnt": 5}])
        if "is_formbean" in cypher or "stereotype = 'Form'" in cypher:
            return _MockNeo4jResult([{"cnt": 3}])
        if "f.extension" in cypher or "ENDS WITH '.jsp'" in cypher:
            return _MockNeo4jResult([{"cnt": 7}])
        if "stereotype = 'Service'" in cypher or "ENDS WITH 'Service'" in cypher:
            return _MockNeo4jResult([{"cnt": 4}])
        if "stereotype IN ['Entity','DTO','Model']" in cypher:
            return _MockNeo4jResult([{"cnt": 6}])
        if "is_corba" in cypher or "CONTAINS '.idl'" in cypher or "CONTAINS '.corba'" in cypher:
            return _MockNeo4jResult([{"cnt": 2}])

        # DTO inference query (name/fields)
        if "RETURN c.name AS name, c.fields AS fields" in cypher:
            return _MockNeo4jResult([
                {"name": "Customer", "fields": [{"name": "id", "type": "Long"}, {"name": "name", "type": "String"}]},
                {"name": "Order", "fields": [{"name": "id", "type": "Long"}, {"name": "total", "type": "BigDecimal"}]},
            ])

        # Default empty
        return _MockNeo4jResult([{"cnt": 0}])


@pytest.mark.asyncio
async def test_plan_multi_repo_canonical_shape():
    neo4j = MockNeo4jClient()
    planner = MultiRepoPlanner(neo4j_client=neo4j, chroma_client=None)

    repos = ["repoA", "repoB"]
    plan = await planner.plan_multi_repo(repositories=repos)

    # Canonical top-level keys
    for key in ("plan_scope", "summary", "cross_repo", "slices", "graphql", "roadmap", "diagnostics"):
        assert key in plan, f"Missing key: {key}"

    # Plan scope
    assert plan["plan_scope"]["repositories"] == repos

    # Totals
    totals = plan["summary"]["totals"]
    assert isinstance(totals["actions"], int) and totals["actions"] >= 0
    assert isinstance(totals["forms"], int) and totals["forms"] >= 0
    assert isinstance(totals["jsps"], int) and totals["jsps"] >= 0
    assert isinstance(totals["services"], int) and totals["services"] >= 0
    assert isinstance(totals["data_models"], int) and totals["data_models"] >= 0
    assert isinstance(totals["corba_interfaces"], int) and totals["corba_interfaces"] >= 0

    # Cross repo dependencies
    deps = plan["cross_repo"]["dependencies"]
    assert isinstance(deps, list) and len(deps) > 0
    assert all("from_repo" in d and "to_repo" in d for d in deps)

    # Slices
    slices = plan["slices"]
    assert isinstance(slices.get("items"), list)
    assert isinstance(slices.get("sequence"), list)

    # GraphQL suggestions
    graphql = plan["graphql"]
    assert isinstance(graphql.get("recommended_types"), list)
    assert isinstance(graphql.get("recommended_queries"), list)
    assert isinstance(graphql.get("recommended_mutations"), list)
    assert isinstance(graphql.get("sdl_preview"), (str, type(None)))

    # Roadmap
    roadmap = plan["roadmap"]
    assert isinstance(roadmap.get("steps"), list)

