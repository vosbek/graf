# GraphRAG Requirements (Kiro-style)

Purpose
Define what must be true for a stable local-first GraphRAG with CodeBERT-only embeddings, clear APIs, and deterministic startup using Podman.

1. Scope and Goals
- In-scope
  - Local development on Windows + Podman with ChromaDB, Neo4j, API
  - CodeBERT-only embeddings end-to-end (no fallbacks)
  - API mounted under /api/v1 with health/readiness
  - Minimal repo indexing workflow (single-repo) for smoke validation
  - Deterministic bring-up using a single dev compose file
- Out-of-scope (for this iteration)
  - Production TLS, SSO, API key lifecycle, multi-tenancy
  - Large-scale performance tuning and distributed scaling
  - Full observability stack (Prometheus/Grafana/Jaeger)
  - Elasticsearch/Kibana

2. Functional Requirements
- R1: CodeBERT-only embeddings
  - All vector operations use microsoft/codebert-base (768 dims)
  - No sentence-transformers dependency at runtime or in requirements.txt
- R2: ChromaDB integration
  - Chroma collection created with a CodeBERT-backed embedding function adapter
  - If an existing collection has mismatched dimensions, system recreates it in dev
- R3: Graph DB (Neo4j)
  - API can connect and execute a trivial Cypher query (RETURN 1)
  - Basic schema/init available (indices optional for smoke run)
- R4: API interface
  - All public routes namespaced under /api/v1
  - Health endpoints:
    - /api/v1/health/live: process alive
    - /api/v1/health/ready: Neo4j ok, Chroma ok, CodeBERT ok (dimension=768)
  - Semantic search endpoint: POST /api/v1/query/semantic returns 200
- R5: Indexing smoke
  - POST /api/v1/index/repository accepts a basic repository config and returns a task id
  - GET /api/v1/index/status/{task_id} returns progressing/completed/failed
- R6: Dev ergonomics
  - podman-compose.dev.yml starts ChromaDB, Neo4j, API; all reach healthy state under 3 minutes on a 16GB machine
  - Logs are accessible and include request IDs, and CodeBERT readiness

3. Non-Functional Requirements
- N1: Reliability (local)
  - Startup resiliency: containers have healthchecks with start_period >= 120s
  - API won’t route traffic until readiness passes
- N2: Performance (local smoke)
  - CodeBERT initialization completes within 90s on first load (cold)
  - Semantic search endpoint responds within 5s under empty/small data
- N3: Security (dev)
  - Auth disabled by default in dev (no token required)
  - CORS permissive in dev
- N4: Maintainability
  - Single source of truth for embedding model (no divergent code paths)
  - Clear dev documentation (horizonrecommendation.md) with exact steps

4. Constraints and Assumptions
- Windows host with Podman installed and at least 16GB RAM
- Developer can pre-build images locally
- No external network restrictions blocking image pulls
- Minimal seed data or empty stores acceptable for smoke tests

5. Acceptance Criteria
- AC1: podman-compose -f podman-compose.dev.yml up -d brings all services to healthy
- AC2: GET /api/v1/health/ready returns pass for neo4j, chroma, codebert (dimension=768)
- AC3: POST /api/v1/query/semantic with {"query":"test","limit":1} returns HTTP 200
- AC4: No references to sentence-transformers in code or requirements.txt
- AC5: Optional: a minimal indexing request completes and increases DB stats

6. Risks
- Podman build context/path mismatch causing API image build failures
- Service initialization times on Windows; solved via longer start_period
- Mixed-dimension collections in Chroma; mitigated by collection recreation

7. Deliverables
- podman-compose.dev.yml (working dev orchestration)
- CodeBERT embedding adapter wired into Chroma
- Health/readiness endpoints and API namespace alignment
- Documentation in horizonrecommendation.md and this RDT set