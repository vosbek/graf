# GraphRAG Design (Kiro-style)

Purpose
Define how we will satisfy the requirements with a clear, testable design for local-first stability and CodeBERT-only embeddings.

1. Architecture Overview
- Components
  - API (FastAPI): Exposes /api/v1 endpoints, health/readiness, semantic search, indexing control
  - ChromaDB: Vector store; collection backed by CodeBERT embeddings (768-d)
  - Neo4j: Graph store for code chunks, dependencies, Maven artifacts
  - Optional: Worker (deferred in dev bring-up to simplify)
- Data flow (simplified)
  - Indexing: API triggers processing → chunks generated → vectors added to ChromaDB → nodes/relationships upserted in Neo4j
  - Query: API receives query → ChromaDB semantic search → optionally merges with Neo4j graph results → returns combined payload

2. Key Design Decisions
- D1: CodeBERT-only embeddings
  - Use AsyncEnhancedEmbeddingClient from [src/core/embedding_config.py](src/core/embedding_config.py:80) as single source of truth
  - Provide a small Chroma embedding function adapter that is synchronous and returns python lists
  - Remove sentence-transformers usage and dependencies entirely
- D2: Dev-first orchestration
  - Use podman-compose.dev.yml with prebuilt images and extended start_period to accommodate Windows startup slowness
  - Start core services only (Chroma, Neo4j, API). Add Worker later after base system is stable
- D3: API readiness gating
  - /api/v1/health/ready checks:
    - Chroma heartbeat (HTTP 200)
    - Neo4j trivial query (RETURN 1)
    - CodeBERT health including dimension=768 and model/device
  - API container healthcheck uses readiness; depends_on waits for DBs healthy before starting API
- D4: Namespace alignment
  - All routes under /api/v1; OpenAPI /docs reachable under root and reflects /api/v1 paths
  - Frontend during dev calls API directly using REACT_APP_API_URL=http://localhost:8080
- D5: Idempotency and schema
  - Dev: accept minimal schema/init for speed
  - Chroma collection created or re-created if the stored dimension does not match 768 (dev-only behavior to avoid mixed-dimension failures)

3. Interfaces and Contracts
- API Surface (selected)
  - GET /api/v1/health/live → {status}
  - GET /api/v1/health/ready → {status, checks: {chroma, neo4j, codebert}}
  - POST /api/v1/query/semantic → {results, total_results, query_time, metadata}
  - POST /api/v1/index/repository → {task_id, status: started}
  - GET /api/v1/index/status/{task_id} → {status, progress, error_message?}
  - GET /api/v1/query/statistics → {chromadb_statistics, neo4j_statistics}
- Embedding Adapter contract
  - __call__(texts: list[str]) → list[list[float]]
  - Returns python lists (not numpy), len==768 per vector
- Readiness contract
  - chroma: 200 from /api/v1/heartbeat
  - neo4j: success executing “RETURN 1”
  - codebert: health_check returns status healthy and dimension 768

4. Deployment Topology (Dev)
- Podman network: single bridge network
- Services:
  - chroma: chromadb/chroma:latest, http 8000, no ClickHouse in dev
  - neo4j: neo4j:5.15-enterprise, heap 2G, pagecache 4G
  - api: codebase-rag-api (prebuilt), http 8080
- Volumes: logs and data bind-mounted for diagnostics and persistence in dev

5. Configuration
- Environment
  - EMBEDDING_MODEL=microsoft/codebert-base
  - AUTH_ENABLED=false (dev)
  - CHROMA_HOST=chromadb, CHROMA_PORT=8000
  - NEO4J_URI=bolt://neo4j:7687, credentials via env
- Health thresholds
  - start_period: 120s; retries: 10; interval: 30s
- Logging
  - Structured (json) or default format per [src/config/settings.py](src/config/settings.py:142)
  - Include X-Request-ID from middleware

6. Failure Modes and Handling
- Chroma returns 410 during warmup → healthcheck tolerates until 200; start_period extended
- Neo4j slow first-run initialization → extended start_period and retries
- CodeBERT model load failure → readiness = fail (explicit error surfaced)
- Mixed-dimension Chroma collection → dev auto-recreate with warning log

7. Testing Strategy
- Unit-ish:
  - CodeBERT adapter returns list[float] vectors with len 768
- Integration:
  - Health/ready returns pass after startup
  - Semantic search POST returns 200
- E2E smoke:
  - Index a small repo (or stub) → status progresses → stats increment in both stores

8. Future Considerations
- Reintroduce Worker with simplified queue semantics for indexing throughput
- Observability (Prometheus/Grafana/Jaeger) after base stability
- Production security (TLS, authN/Z, JWKS) and k8s deployment profiles