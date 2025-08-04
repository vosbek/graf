import json
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services.migration_planner import MultiRepoPlanner


class _MockNeo4jResult:
    def __init__(self, records):
        self.records = records


class MockNeo4jClient:
    async def find_cross_repository_dependencies(self, repositories):
        if len(repositories) >= 2:
            return [
                {"from_repo": repositories[0], "to_repo": repositories[1], "weight": 2, "types": ["CALLS"]},
                {"from_repo": repositories[1], "to_repo": repositories[0], "weight": 1, "types": ["IMPORTS"]},
            ]
        return []

    async def find_shared_db_artifacts(self, repositories):
        if len(repositories) >= 2:
            return [{"artifact": "shared_table", "repos": repositories[:2], "type": "DB_TABLE"}]
        return []

    async def execute_query(self, graph_query):
        cypher = getattr(graph_query, "cypher", "") or ""
        if "WHERE coalesce(c.is_action" in cypher or "stereotype = 'Action'" in cypher:
            return _MockNeo4jResult([{"cnt": 2}])
        if "is_formbean" in cypher or "stereotype = 'Form'" in cypher:
            return _MockNeo4jResult([{"cnt": 1}])
        if "f.extension" in cypher or "ENDS WITH '.jsp'" in cypher:
            return _MockNeo4jResult([{"cnt": 3}])
        if "stereotype = 'Service'" in cypher or "ENDS WITH 'Service'" in cypher:
            return _MockNeo4jResult([{"cnt": 4}])
        if "stereotype IN ['Entity','DTO','Model']" in cypher:
            return _MockNeo4jResult([{"cnt": 5}])
        if "is_corba" in cypher or "CONTAINS '.idl'" in cypher or "CONTAINS '.corba'" in cypher:
            return _MockNeo4jResult([{"cnt": 1}])
        if "RETURN c.name AS name, c.fields AS fields" in cypher:
            return _MockNeo4jResult([
                {"name": "Customer", "fields": [{"name": "id", "type": "Long"}, {"name": "name", "type": "String"}]}
            ])
        return _MockNeo4jResult([{"cnt": 0}])


@pytest.fixture(autouse=True)
def inject_mock_clients(monkeypatch):
    """
    Inject mock neo4j client into the app dependencies so routes can resolve it.
    """
    mock_neo4j = MockNeo4jClient()

    # Patch dependencies.get_neo4j_client to return our mock
    import src.dependencies as deps

    async def _get_neo4j_client_override():
        return mock_neo4j

    monkeypatch.setattr(deps, "get_neo4j_client", lambda: mock_neo4j, raising=False)
    # Also patch state to avoid None checks
    app.state.neo4j_client = mock_neo4j

    yield


def _assert_canonical_shape(plan: dict):
    assert isinstance(plan, dict)
    for key in ("plan_scope", "summary", "cross_repo", "slices", "graphql", "roadmap", "diagnostics"):
        assert key in plan, f"missing {key}"

    totals = plan["summary"]["totals"]
    assert all(k in totals for k in ("actions", "forms", "jsps", "services", "data_models", "corba_interfaces"))
    assert isinstance(plan["slices"].get("items"), list)
    assert isinstance(plan["slices"].get("sequence"), list)
    assert isinstance(plan["graphql"].get("recommended_types"), list)
    assert isinstance(plan["roadmap"].get("steps"), list)


def test_get_migration_plan_equivalence_with_post():
    client = TestClient(app)

    repos = ["repoA", "repoB"]
    # GET endpoint
    resp_get = client.get("/api/v1/migration-plan", params={"repositories": ",".join(repos)})
    assert resp_get.status_code == 200, resp_get.text
    plan_get = resp_get.json()
    _assert_canonical_shape(plan_get)

    # POST endpoint (standardized)
    # Align payload name used in ApiService: repository_names
    resp_post = client.post(
        "/api/v1/query/multi-repo/migration-impact",
        json={"repository_names": repos},
    )
    assert resp_post.status_code == 200, resp_post.text
    plan_post = resp_post.json()
    _assert_canonical_shape(plan_post)

    # Compare key structures (allow ordering differences)
    for key in ("summary", "slices", "graphql", "roadmap"):
        assert key in plan_get and key in plan_post

    # Totals should be integers and non-negative in both
    for plan in (plan_get, plan_post):
        totals = plan["summary"]["totals"]
        for k, v in totals.items():
            assert isinstance(v, int) and v >= 0

    # Sanity: repositories echoed
    assert plan_get["plan_scope"]["repositories"] == repos
    assert plan_post["plan_scope"]["repositories"] == repos