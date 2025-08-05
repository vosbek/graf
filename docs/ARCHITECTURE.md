# GraphRAG Chat Architecture (Strands Agent + Code-Aware Retrieval + Bedrock Sonnet 3.7)

Purpose
Enable engineers and architects to converse with large, multi-repo codebases using a rock-solid, no-fallback pipeline: in-process Strands Agent orchestrating deterministic, code-aware retrieval across Chroma (semantic code vectors) and Neo4j (structural/relationship graph), with synthesis via AWS Bedrock Sonnet 3.7. Security (auth, strict CORS), observability, and fail-fast configuration are mandatory.

## Redis for Task Status and Persistence
- **Role:** Redis is used as a high-performance, in-memory data store for persistent task status tracking of repository indexing jobs.
- **Persistence:** It ensures that indexing task statuses, progress, and errors are not lost if the API service restarts, providing resilience and continuity.
- **Real-time Updates:** Redis's pub/sub capabilities (though not directly exposed in this architecture diagram, implied by `StatusUpdateManager`) facilitate real-time updates to connected WebSocket clients for live progress monitoring.
- **Data Model:** Stores `EnhancedIndexingStatus` objects, including stage history, embedding progress, and error details.

## Redis for Task Status and Persistence
- **Role:** Redis is used as a high-performance, in-memory data store for persistent task status tracking of repository indexing jobs.
- **Persistence:** It ensures that indexing task statuses, progress, and errors are not lost if the API service restarts, providing resilience and continuity.
- **Real-time Updates:** Redis's pub/sub capabilities (though not directly exposed in this architecture diagram, implied by `StatusUpdateManager`) facilitate real-time updates to connected WebSocket clients for live progress monitoring.
- **Data Model:** Stores `EnhancedIndexingStatus` objects, including stage history, embedding progress, and error details.

## Redis for Task Status and Persistence
- **Role:** Redis is used as a high-performance, in-memory data store for persistent task status tracking of repository indexing jobs.
- **Persistence:** It ensures that indexing task statuses, progress, and errors are not lost if the API service restarts, providing resilience and continuity.
- **Real-time Updates:** Redis's pub/sub capabilities (though not directly exposed in this architecture diagram, implied by `StatusUpdateManager`) facilitate real-time updates to connected WebSocket clients for live progress monitoring.
- **Data Model:** Stores `EnhancedIndexingStatus` objects, including stage history, embedding progress, and error details.

Target Architecture (Textual Diagram)
UI (React ChatInterface)
  → FastAPI Chat Router (/api/v1/chat/ask, feature-flagged by Bedrock config)
    → Strands Agent (in-process)
      → Code-Aware Retrieval Service (deterministic plan)
        → ChromaDBClient (semantic top-k, repository-scoped)
        → Neo4jClient (structural expansion: callers/callees, domains, cross-repo flows)
      → Prompt Builder (size-capped, deterministic)
      → Bedrock LLM Provider (Sonnet 3.7)
  ← Answer + Citations (chunk_id, file_path, repository) + Diagnostics

Indexing Pipeline (Asynchronous, Redis-backed)
  → FastAPI Indexing Router (/api/v1/index/*)
    → Background Task (RepositoryProcessor)
      → Redis (Persistent Task Status, Logs, Metrics)
      → Git Client (Cloning)
      → File Parsers (Java, XML, etc.)
      → Embedding Model (CodeBERT)
      → ChromaDB (Vector Store)
      → Neo4j (Knowledge Graph)
  ← Initial Task ID (for status tracking)

Key Principles
- No fallbacks. If Bedrock credentials, model, or region are invalid, chat is not registered; rest of the API remains unaffected.
- Deterministic retrieval. Fixed plan per request: (1) semantic top-k with filters; (2) minimal graph expansions; (3) priority-based truncation for context fitting.
- Strict security. Auth required for chat; CORS restricted to known origins; read-only allowlisted graph queries.
- Observability. Trace IDs, per-step latency, retrieval counts, LLM tokens in/out.

Components and Responsibilities
- React UI
  - Collects question and repository scope
  - Displays answer and “sources” (citations)
- FastAPI Chat Router (src/api/routes/chat.py)
  - Validates payload, enforces auth, reads DI clients, invokes Agent
  - Feature-flagged by verified Bedrock config (never registers if invalid)
- Strands Agent (strands/agents/chat_agent.py)
  - Orchestrates tool calls and LLM step
  - Enforces no-fallback policy and strict timeouts
- Code-Aware Retrieval Service (within the Agent layer)
  - Executes deterministic retrieval plan:
    1) Chroma semantic search: repository_scope + min_score
    2) Neo4j structural expansion: CALLS/CALLED_BY, BELONGS_TO domain, selective flows for architecture queries
    3) Role-aware filtering based on query intent (“architecture” vs “code fix”)
- Chroma Tool (strands/tools/chroma_tool.py)
  - Wraps ChromaDBClient.search(SearchQuery)
  - Returns normalized items (chunk_id, file_path, repository, language, name, score, snippet)
- Neo4j Tool (strands/tools/neo4j_tool.py)
  - Exposes curated, read-only query functions only (no arbitrary Cypher)
  - Provides code relationships, domain dependencies, cross-repo flows
- Prompt Builder
  - Deterministic, size-capped, citation-enforcing format
  - Prioritizes chunks by semantic score and structural centrality
- Bedrock LLM Provider
  - Single model (Sonnet 3.7) with strict validation at startup
  - No retries that mask errors; clear error codes on failure

Configuration and Feature Flag
- Settings
  - AWS_REGION, AWS_PROFILE or AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
  - BEDROCK_MODEL_ID (Sonnet 3.7 exact per region)
  - Timeouts and maximum tokens
- Validation
  - Performed during app startup
  - Chat router registers only if validation passes (feature flag “chat_enabled”=true)

Security Posture
- Authentication: JWT or API key middleware required for /api/v1/chat/*
- CORS: allow only known frontend origin(s)
- Input validation: strict bounds on top_k, min_score, mode
- Resource limits: chunk truncation; LLM token limit and timeout enforced

Observability
- Structured logging: request_id, steps (chroma, neo4j, prompt, llm), latencies, counts, tokens
- Optional performance middleware integration

Rollout Strategy
- Phase 1: Non-streaming chat endpoint behind feature flag
- Phase 2: SSE streaming after stability proven
- Phase 3: Hybrid retrieval tuning and re-ranking using graph signals

Decision Records
- DR-001: In-process Strands Agent orchestration with curated tool surface
- DR-002: LLM Provider is AWS Bedrock Sonnet 3.7 only, no fallbacks
- DR-003: Fail-fast configuration: do not register chat without valid Bedrock config
- DR-004: Strict security for chat endpoints (auth, CORS)
- DR-005: Deterministic retrieval plan for consistent expert-grade answers