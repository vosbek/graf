# Graf GraphRAG – End-to-End Tasks and Fresh Windows Install Guide

This document is the single source of truth for completing the project and standing it up on a fresh Windows 11 machine. It covers prerequisites, environment setup, container stack, API, frontend, diagnostics, and feature tasks to complete.

============================================================
1) System Prerequisites (Windows 11)
============================================================
- Windows 11 with Admin privileges
- PowerShell 7+ recommended (Windows PowerShell works but PS7 is better)
- Git for Windows
- Python 3.11.x on PATH
- Node.js 18+ and npm 9+ (for frontend dev server)
- Podman Desktop (or Podman CLI) with WSL2 backend enabled
  - Run once: podman machine init
  - Then: podman machine start

Verify:
- python --version
- node --version
- npm --version
- podman --version
- podman machine list
- git --version

============================================================
2) Clone Repository and Configure Environment
============================================================
- git clone https://your-repo-url graf
- cd graf
- Copy environment templates:
  - copy .env.template .env
  - Edit .env if needed (defaults are fine for local dev)
- Install Python deps into system pip or venv:
  - Option A (system): pip install -r requirements.txt
  - Option B (venv):
    - python -m venv .venv
    - .\.venv\Scripts\Activate.ps1
    - pip install -r requirements.txt

Note on dependency warnings: Some pinned versions are for runtime compatibility with our stack. Warnings from pip about unrelated libraries can be ignored for local dev, but prefer using a clean venv.

============================================================
3) Start Core Services with Podman (Chroma, Neo4j, Redis, Postgres)
============================================================
- Start services:
  podman-compose -f podman-compose.dev.yml up -d

- Verify containers:
  podman ps
  Expected services:
    - codebase-rag-chromadb (port 8000)
    - codebase-rag-neo4j (ports 7474, 7687)
    - codebase-rag-redis (port 6379)
    - codebase-rag-postgres (port 5432)

- Check Chroma v2 health:
  curl http://localhost:8000/api/v2/healthcheck
  Expect HTTP 200 JSON

- Check Neo4j bolt/HTTP:
  podman exec codebase-rag-neo4j cypher-shell -u neo4j -p codebase-rag-2024 "RETURN 1"
  curl http://localhost:7474

If Neo4j loops on config errors, restart with updated env in compose (already applied):
- NEO4J_server_config_strict__validation_enabled=false
- NEO4J_server_default__listen__address=0.0.0.0
- NEO4J_server_bolt_advertised__address=localhost:7687
- NEO4J_server_http_advertised__address=localhost:7474

If needed (rare), remove volumes and restart:
  podman-compose -f podman-compose.dev.yml down
  podman volume rm graf_neo4j_data graf_neo4j_logs 2>$null
  podman-compose -f podman-compose.dev.yml up -d

============================================================
4) Start the API (FastAPI/Uvicorn)
============================================================
Two options are provided. Use foreground first to surface errors clearly.

A) Foreground (recommended initial run)
  - powershell -ExecutionPolicy Bypass -File .\test\api-bootstrap.ps1
    - Adds env vars, installs deps (unless -SkipInstall), then runs uvicorn in foreground.

  Useful flags:
    -SkipInstall  (skip pip install)
    -UseVenv      (create/use .venv)
    -Port 8080    (custom port)

  Verify:
    curl http://localhost:8080/docs
    curl http://localhost:8080/api/v1/health/ready

B) Through start script (background or foreground sequence)
  - .\start-api.ps1
  - Script waits for Chroma/Neo4j, then starts API. You can modify to foreground if needed.

Notes:
- Development CORS is permissive.
- Pydantic v2 warnings about json_schema_extra can be ignored for dev.

============================================================
5) Start the Frontend (React)
============================================================
- cd frontend
- npm install
- npm start
- Open the URL shown (3000 or 3001)
- The dev proxy is configured to forward to http://localhost:8080

Verify network calls in DevTools:
- GET /api/v1/health/ready -> 200 JSON
- GET /api/v1/index/repositories -> 200 JSON (empty until you index)

============================================================
6) Diagnostics and Repair Scripts
============================================================
These are created under test/ to speed up troubleshooting.

- Startup diagnostics:
  powershell -ExecutionPolicy Bypass -File .\test\startup-diagnostics.ps1
  Options:
    -CheckFrontend       (probes dev proxy too)
    -StartApiIfMissing   (runs uvicorn in foreground)

- API bootstrap (foreground):
  powershell -ExecutionPolicy Bypass -File .\test\api-bootstrap.ps1 [-UseVenv] [-SkipInstall] [-Port 8080]

- Chroma repair (for v2 health confirmation, collection round-trip may be unsupported on your image):
  powershell -ExecutionPolicy Bypass -File .\test\chroma-repair.ps1

- Neo4j repair (logs, HTTP, bolt):
  powershell -ExecutionPolicy Bypass -File .\test\neo4j-repair.ps1

============================================================
7) Repository Indexing – Remote Git and Local Path Modes
============================================================
A) Remote Git (default)
POST /api/v1/index/repository
Body:
{
  "name": "user-service",
  "url": "https://github.com/org/repo",
  "branch": "main",
  "priority": "high",
  "maven_enabled": false,
  "business_domain": "payments",
  "team_owner": "platform",
  "is_golden_repo": false
}

B) Local Path (UI feature to add; API planned)
- Planned backend endpoint:
  POST /api/v1/index/repository/local
  Body:
  {
    "name": "local-repo",
    "local_path": "C:/path/to/repo",
    "priority": "high",
    "business_domain": "...",
    "team_owner": "...",
    "is_golden_repo": false
  }
- Processor v2 planned method:
  process_local_repository(LocalRepositoryConfig)

Status:
- Remote Git indexing is working (v2 processor wired).
- Local Path indexing is approved and planned below (see Task backlog).

Check indexing status:
- GET /api/v1/index/status
- GET /api/v1/index/status/{task_id}
List repositories:
- GET /api/v1/index/repositories

============================================================
8) Multi-Repo Analysis and Query
============================================================
- Health:
  GET /api/v1/health/ready -> 200 JSON (no required params)
- Multi-repo analysis:
  POST /api/v1/query/multi-repo/analyze
  {
    "repository_names": [],
    "analysis_type": "overview",
    "include_business_flows": true,
    "include_dependencies": true,
    "include_migration_impact": false
  }
- Graph query:
  POST /api/v1/query/graph
  {
    "cypher": "...",
    "parameters": {}
  }

============================================================
9) Known Behaviors and Notes
============================================================
- Chroma v2: Health endpoint is stable. Some tags don’t expose local collections management via HTTP; the Python client is used by the API and that’s sufficient.
- Pydantic v2: “schema_extra -> json_schema_extra” warnings are benign; a future cleanup can silence them.
- Neo4j 5.x: Uses server.* keys, strict validation disabled for dev; compose updated accordingly.
- Frontend proxy: CRA dev proxy is set to http://localhost:8080 via package.json.

============================================================
10) Backlog – Tasks to Complete the Project
============================================================
High-priority

A) Implement Strands Agent and Fix "Ask AI" (No fallbacks, feature-flagged)
1. Architecture & Design Artifacts
   - Ensure docs/ARCHITECTURE.md and docs/DESIGN-CHAT.md are present and accepted.
2. Settings & Validation (fail-fast)
   - Extend Settings to read:
     - AWS_REGION, AWS_PROFILE or AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY
     - BEDROCK_MODEL_ID (exact Sonnet 3.7 model id for region)
     - LLM timeouts, token limits
   - Add a validation method executed during app startup:
     - If validation fails, set CHAT_ENABLED=false; do not register chat router.
3. Strands scaffolds (no behavior change)
   - Create:
     - strands/agents/chat_agent.py (skeleton with validate() and run() signatures)
     - strands/tools/chroma_tool.py (interface with semantic_search())
     - strands/tools/neo4j_tool.py (interface with code_relationships(), repo_flows_summary())
4. Chat Router (feature-flagged)
   - Create src/api/routes/chat.py:
     - Registers only when CHAT_ENABLED=true.
     - POST /api/v1/chat/ask accepts {question, repository_scope?, top_k?, min_score?, mode?}.
     - Enforce auth and strict input bounds.
     - Invoke chat_agent.run() and return {answer, citations, diagnostics}.
5. Code-Aware Retrieval Service (deterministic)
   - Implement retrieval plan inside the agent:
     - Step 1: Chroma top-k with repository_scope and min_score via SearchQuery.
     - Step 2: Neo4j bounded expansion (CALLS/CALLED_BY, BELONGS_TO domain). Add repo flow summary for architecture queries or mode=hybrid.
     - Step 3: Role-aware filtering and capping by token budget.
6. LLM Provider (Bedrock only)
   - Implement Bedrock provider with:
     - validate() at startup
     - generate(prompt, ...) with strict timeouts and structured statistics
     - No retries that mask errors; raise on failure.
7. Prompt Builder (deterministic, size-capped)
   - Include question, prioritized snippets with file_path/name/score, structural bullets, and strict “cite sources” policy.
8. Security
   - Enable JWT or API key middleware for /api/v1/chat/*.
   - Restrict CORS allowed_origins to known frontend origin(s).
9. Frontend Integration
   - Update ApiService.askAgent() to POST /api/v1/chat/ask with repository_scope.
   - Update ChatInterface to render citations (file_path, repository, score) under answers.
10. Observability & Testing
   - Structured logging: request_id, retrieval counts, per-step latency, model id, tokens in/out.
   - Unit tests: Chroma tool, Neo4j tool, prompt builder, LLM provider (mocked).
   - Integration test: API boot, POST /chat/ask on sample data, verify 200 and citations.

B) Add Local Path Indexing end-to-end
  - Backend: New model LocalRepositoryIndexRequest and endpoint POST /api/v1/index/repository/local in src/api/routes/index.py
  - Processor v2 (src/services/repository_processor_v2.py):
    - LocalRepositoryConfig class
    - process_local_repository(config) reusing current chunking/push logic
    - Shared routine _index_repository_files(root_path, metadata)
  - Frontend:
    - RepositoryIndexer: mode toggle (Remote URL | Local Path)
    - ApiService.indexLocalRepository() for POST /index/repository/local

- Seed sample data flow
  - Add script or UI action to index a small public repo or a local sample dataset
  - Provide test fixtures under data/samples/ to validate UI and chat flows

- API readiness enhancements
  - Add /api/v1/health/ping that always returns 200 with initializing flag for better UX during warmup

- Authentication (optional/production)
  - Wire optional JWT auth and secure CORS (settings.auth_enabled)
  - Nginx + TLS for production installs

- Observability
  - Wire metrics endpoints to Prometheus (config/prometheus)
  - Optional: Jaeger tracing with OpenTelemetry

- Documentation
  - Update docs/installation/windows.md with Strands Agent steps
  - Add a quickstart “one-click” script wrapper that chains compose up + bootstrap + frontend launch

Medium-priority
- Cleanup pydantic v2 warnings (rename schema_extra -> json_schema_extra)
- Improve error surfaces on background initialization (explicit readiness state details)
- Add exponential backoff on frontend ApiService for startup warmup period
- Add Neo4j indices/constraints migration script invoked via admin endpoint
- Add minimal dataset to verify business flow queries
- Add SSE streaming endpoint for chat and wire frontend streaming UI

Low-priority / Future
- Containerize API dev image for parity with production
- Optional: replace CRA proxy with explicit REACT_APP_API_URL config for multi-env dev
- Optional: Add SBOM/SCA workflow and dependabot-like update tracking
- Optional: Full TLS and auth hardening via Nginx in dev

============================================================
11) Fresh Windows Machine – Step-by-Step Install
============================================================
1. Install prerequisites:
   - Python 3.11.x (Add to PATH)
   - Node.js 18+ (includes npm)
   - Git for Windows
   - Podman Desktop (WSL2 enabled); run:
     podman machine init
     podman machine start

2. Clone and configure repo:
   - git clone https://your-repo-url graf
   - cd graf
   - copy .env.template .env
   - pip install -r requirements.txt
     or create venv:
       python -m venv .venv
       .\.venv\Scripts\Activate.ps1
       pip install -r requirements.txt

3. Start services:
   - podman-compose -f podman-compose.dev.yml up -d
   - Verify:
       curl http://localhost:8000/api/v2/healthcheck
       podman exec codebase-rag-neo4j cypher-shell -u neo4j -p codebase-rag-2024 "RETURN 1"

4. Start API (foreground recommended):
   - powershell -ExecutionPolicy Bypass -File .\test\api-bootstrap.ps1
   - Verify:
       curl http://localhost:8080/docs
       curl http://localhost:8080/api/v1/health/ready

5. Start frontend:
   - cd frontend
   - npm install
   - npm start
   - Open shown URL (e.g., http://localhost:3000)

6. Index a repository (remote for now):
   - POST /api/v1/index/repository (see JSON body above)
   - Poll status and view results in UI

7. Troubleshoot (if needed):
   - powershell -ExecutionPolicy Bypass -File .\test\startup-diagnostics.ps1 -CheckFrontend
   - powershell -ExecutionPolicy Bypass -File .\test\neo4j-repair.ps1
   - powershell -ExecutionPolicy Bypass -File .\test\chroma-repair.ps1

============================================================
12) Acceptance Criteria for “Up and Running”
============================================================
- Chroma v2 health returns 200
- Neo4j cypher-shell RETURN 1 succeeds
- API:
  - /docs returns 200
  - /api/v1/health/ready returns 200 JSON without params
- Frontend:
  - Loads on 3000/3001
  - Proxies API calls to 8080 successfully
  - Multi-Repo page responds (empty until indexed)
- Indexing:
  - Remote repository indexing starts and completes (or Local Path after feature is implemented)
  - Repositories list shows entries
- Multi-Repo Analysis:
  - POST /api/v1/query/multi-repo/analyze returns structured JSON

============================================================
13) Change Log Summary (Recent Critical Fixes)
============================================================
- Updated Chroma health usage to /api/v2/healthcheck
- Fixed start-api.ps1 to suppress benign cleanup errors and use robust Neo4j check
- Added diagnostics scripts for startup and repair (Chroma, Neo4j, API)
- Implemented CHROMA_DISABLED env toggle in API background init
- Readiness endpoint fixed to not require params
- Frontend proxy verified; CRA proxy points to http://localhost:8080
- Processor v2 wired; remote indexing functional

============================================================
14) Ownership and Execution
============================================================
- Dev execution: Run scripts in test/; use foreground API for fast feedback.
- Horizon/Claude Code can execute the Podman + PowerShell commands as listed.
- Keep TASKS.md up to date with any new tasks and operational procedures.
