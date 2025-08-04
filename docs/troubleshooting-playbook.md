# GraphRAG Troubleshooting Playbook (for Claude Code)

Purpose
A concise, deterministic runbook to diagnose and recover a broken GraphRAG stack. Optimized for agentic execution by Claude Code. Use this to:
- Identify which subsystem failed (API, Neo4j, Chroma, Processor, Embeddings).
- Validate readiness and connectivity without guesswork.
- Run ingestion smoke tests safely (dry-run first).
- Produce actionable evidence to fix the root cause.

System Overview
- API: FastAPI at http://localhost:8080 with routers:
  - /api/v1/health, /api/v1/query, /api/v1/index, /api/v1/admin, /api/v1/graph
- Datastores: Neo4j (bolt://localhost:7687), ChromaDB (HTTP v2).
- Processor: EnhancedRepositoryProcessor v2.0 uses Neo4j+Chroma; must be initialized for indexing to work.
- Embeddings: CodeBERT client (async) is optional for readiness but required for semantic quality.

Golden Signals
- API live: GET /api/v1/health/ → {status: "alive"}
- API ready: GET /api/v1/health/ready → {status: "ready" | "degraded" | "not_ready"}
- Graph router sanity: GET /api/v1/graph/ping → {ok: true}
- Processor present: repository_processor=true in state diagnostics
- Ingestion dry-run: non-zero processed_files and generated_chunks without writes
- Visualization: nodes > 0 and edges >= 0
- Semantic: POST /api/v1/query/semantic returns 200, results >= 0

Primary Failure Modes
1) Processor Not Initialized → 503 errors from /api/v1/index/*
   - Cause: app.state.repository_processor is None (dependency failed).
   - Check:
     - GET /api/v1/health/ready
     - GET /api/v1/health/enhanced/state (if available)
     - GET /api/v1/graph/diag (router-specific readiness)
   - Fix: Identify which component is false (chroma_client, neo4j_client). Resolve that subsystem until processor can be constructed.

2) Chroma 409 on collection creation → readiness stuck not_ready
   - Symptom: /graph/diag shows initialization_error about 409 “collection already exists”.
   - Fix: Treat 409 as success in any collection-ensure path. Do not set initialization_error for 409. Processor can proceed.

3) Neo4j readiness regressions on newer versions
   - Symptom: “Procedure not found: db.indexes”.
   - Fix: Use portable probes only:
     - RETURN 1 as connectivity
     - MATCH (n) RETURN count(n) as total_nodes LIMIT 1
     - Optional: CALL dbms.components() guarded

4) UI shows blank graph or errors without network failures
   - Symptom: Visualization responses contain Unknown/None nodes/edges.
   - Fix options:
     - Backend: filter null nodes/edges and coerce IDs/types in /api/v1/graph/visualization.
     - Frontend: show empty-state message; accept schema with id/type/name; render minimal graphs.

Step-by-Step Diagnostics

A) Health and Readiness
1. GET /api/v1/health/
   Expect: {"status":"alive", ...}
2. GET /api/v1/health/ready
   Expect: {"status":"ready"} or {"status":"degraded"}; never “not_ready” for long-running instance.
3. Enhanced diagnostics (if available):
   - GET /api/v1/health/enhanced/state
     Expect:
     {
       "is_ready": true,
       "initialization_error": null,
       "components": {
         "chroma_client": true,
         "neo4j_client": true,
         "repository_processor": true,
         "embedding_client": (true|false)
       }
     }
4. Graph router
   - GET /api/v1/graph/ping → {ok:true}
   - GET /api/v1/graph/diag → {router_alive:true, app_ready:true, initialization_error:null}

If not_ready:
- If chroma_client=false:
  - Verify Chroma container is reachable; inspect /api/v2/healthcheck.
  - Ensure tenant/database exist; get_or_create_collection must not treat 409 as fatal.
- If neo4j_client=false:
  - Verify credentials and URI; run RETURN 1 test via client.
- If processor=false while clients true:
  - Processor construction failed; view /api/v1/logs/errors and API console for stacktrace.

B) Ingestion Checks
1. Use scripts/ingestion-validate.ps1 (mode-driven) to avoid race conditions:
   - Mode=health: prints /health, /ready, comprehensive diag. Safe.
   - Mode=dry-run: runs prepare→analyze→process code without writing; polls /index/status.
   - Mode=live: runs full ingestion; validates visualization and semantic search.
   Notes:
   - The script auto-retries 503/502/transient errors and polls readiness up to 120s.
   - It exits non-zero if ingestion fails.

2. Manual API smoke (if script not used):
   - POST /api/v1/index/repository/local?dry_run=true
     Body:
     {
       "name":"REPO_NAME",
       "local_path":"C:\\path\\to\\repo"
     }
   Expect: IndexingStatusResponse with status "in_progress" then "completed" via:
   - GET /api/v1/index/status → find repo in task_statuses
   Success: processed_files > 0, generated_chunks > 0.

3. Post-ingestion validation:
   - GET /api/v1/graph/visualization?repository=REPO_NAME&depth=2&limit_nodes=300&limit_edges=800
     Expect: nodes >= 1; edges >= 0; avoid null/None entries.
   - POST /api/v1/query/semantic
     Body: {"query":"repo:REPO_NAME","limit":3,"min_score":0.1}
     Expect: 200; results >= 0.

Decision Tree for Common Failures

Case 503 on /api/v1/index/*
- Check state: GET /api/v1/health/enhanced/state
  - repository_processor=false:
    - If chroma_client=false:
      - Fix Chroma connectivity; ensure collection ensure path treats 409 as success.
    - If neo4j_client=false:
      - Fix Neo4j connectivity/credentials.
    - If both true:
      - The processor constructor threw; see /api/v1/logs/errors and server logs.

Case /graph/diag shows initialization_error with Chroma 409
- Update any diagnostics/initialization path to classify 409 “already exists” as success.
- Do not set initialization_error on 409; leave app_ready unaffected.

Case /health/ready “not_ready” persists beyond 2 minutes
- It’s always a dependency failure:
  - Use enhanced/state to identify which client is false.
  - Resolve that system; do not retry ingestion until ready flips.

Minimal Safe Patches (if needed)
- Neo4j health: ensure no usage of CALL db.indexes(), only safe Cypher.
- Chroma collection ensure: wrap get_or_create_collection with try/except; treat 409 as pass.

Evidence to Capture for Root Cause
- /api/v1/health/ready JSON
- /api/v1/health/enhanced/state JSON (if present)
- /api/v1/graph/diag JSON
- /api/v1/logs/errors (last 100)
- For ingestion failures: contents of /api/v1/index/status (for the repo) and any final error_message

Success Criteria
- UI no longer shows 503 “Repository processor not initialized”.
- /api/v1/index/repositories returns 200 JSON.
- Ingestion dry-run shows non-zero processed_files and generated_chunks.
- Visualization returns non-null nodes/edges.
- Semantic query returns 200 with results list (possibly empty if content is small).

Appendix: Endpoints Reference
- Health:
  - GET /api/v1/health/
  - GET /api/v1/health/ready
  - GET /api/v1/health/enhanced/state (optional diagnostics endpoint)
- Graph:
  - GET /api/v1/graph/ping
  - GET /api/v1/graph/diag
  - GET /api/v1/graph/visualization?repository=<name>&depth=<n>&limit_nodes=300&limit_edges=800
- Indexing:
  - POST /api/v1/index/repository
  - POST /api/v1/index/repository/local
  - GET /api/v1/index/status
  - GET /api/v1/index/status/{task_id}
  - GET /api/v1/index/repositories
- Query:
  - POST /api/v1/query/graph
  - POST /api/v1/query/semantic

Agent Usage Guidance
- Always check /health/ready and /health/enhanced/state before any ingestion attempt.
- Never start ingestion when repository_processor=false; fix dependencies first.
- Prefer scripts/ingestion-validate.ps1 Mode=health or Mode=dry-run to gather facts without side effects.
- When changing code, start with minimal, reversible patches (e.g., classify Chroma 409 as success).
