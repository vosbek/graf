# DESIGN-CHAT: Strands Agent + Code-Aware Retrieval + Bedrock Sonnet 3.7

Objective
Deliver a rock-solid, no-fallback “Ask the Codebase” chat that enables engineers and architects to converse with multi-repo systems. The design uses an in-process Strands Agent that orchestrates deterministic retrieval: semantic top-k from Chroma and structural expansion from Neo4j, then synthesizes with AWS Bedrock Sonnet 3.7, returning answers with verifiable citations.

Scope
- Feature-flagged chat router (disabled unless Bedrock config validates)
- Strands Agent in-process orchestration
- Code-Aware Retrieval Service (deterministic steps)
- Curated tool interfaces for Chroma and Neo4j (read-only, allowlisted)
- Prompt builder contract (deterministic, size-capped, citations)
- LLM provider abstraction (Bedrock Sonnet 3.7 only)
- Security, validation, and observability

1) API Contract

Endpoint
POST /api/v1/chat/ask

Request (Pydantic model)
{
  "question": "string (required)",
  "repository_scope": ["repo1", "repo2"],   // optional; when omitted, server may use all repos if authorized
  "top_k": 8,                                // optional int, 1..20 (default 8)
  "min_score": 0.0,                          // optional float 0.0..1.0 (default 0.0)
  "mode": "semantic"                         // enum: "semantic" | "hybrid" (default "semantic")
}

Response
{
  "answer": "string",
  "citations": [
    {
      "chunk_id": "repo:file:path:lineStart-lineEnd",
      "repository": "repo",
      "file_path": "src/path/file.py",
      "score": 0.87
    }
  ],
  "diagnostics": {
    "retrieval": { "count": 8, "time_ms": 120 },
    "graph": { "queries": 2, "time_ms": 45 },
    "llm": { "model_id": "bedrock-sonnet-3.7", "tokens_in": 2100, "tokens_out": 650, "time_ms": 1700 }
  }
}

HTTP Codes
- 200: Success
- 400: Validation error (bad parameters)
- 401/403: Unauthorized/Forbidden
- 503: Service unavailable (e.g., Chroma/Neo4j down, Bedrock not configured)
- 504: LLM timeout

2) Strands Agent Orchestration

Agent responsibilities
- Validate inputs (bounds checks, scope shape)
- Execute deterministic retrieval plan
- Build prompt deterministically; enforce citation policy
- Call Bedrock Sonnet 3.7 with strict timeouts; no retries that hide errors
- Return answer, citations, and diagnostics

Feature flag
- Chat router registers only if Bedrock config validates at startup (model id, region, credentials). Otherwise chat remains disabled and existing APIs are untouched.

3) Code-Aware Retrieval Service (Deterministic Plan)

Inputs
- question: string
- repository_scope: []string | null
- top_k: int
- min_score: float
- mode: "semantic" | "hybrid"

Steps
1) Semantic top-k via Chroma
   - Build SearchQuery with repository_filter = repository_scope (if provided)
   - Use question as query_text; include_metadata=true
   - Retrieve top_k results; drop below min_score
2) Structural expansion via Neo4j (bounded)
   - For each top result (up to N_structural, e.g., 5):
     - Fetch immediate CALLS/CALLED_BY
     - Fetch BELONGS_TO domain
   - If mode==hybrid or the query contains architecture/cross-repo terms:
     - Fetch cross-repo flows or high-level repo health (bounded single query)
3) Role-aware filtering (heuristic)
   - If “architecture”/“flow”: prioritize repo/domain facts; keep only top few chunks
   - Else: prioritize code-level chunks; include CALLS/CALLED_BY bullets
4) Assembly and capping
   - Assemble primary chunk snippets (trim to per-snippet budget)
   - Include structural bullets (domains, callers/callees) per chunk
   - Ensure token budget fit: prioritize by (semantic score, then structural centrality)
5) Output structures
   - retrieved_chunks: normalized list for prompt and citations
   - graph_facts: concise bullets per chunk

4) Tools Interfaces (Strands)

Chroma Tool (strands/tools/chroma_tool.py)
Interface (Python sketch)
class ChromaTool:
    def __init__(self, chroma_client):  # src/core/chromadb_client.ChromaDBClient
        ...

    def semantic_search(self, query: str, *, repository_filter=None, language=None, domain=None,
                        chunk_type=None, limit=8, min_score=0.0) -> list[dict]:
        """
        Returns list of dicts:
        { "chunk_id", "file_path", "repository", "language", "name", "score", "content" }
        """

Behavior
- Calls ChromaDBClient.search(SearchQuery)
- Applies filters; normalizes outputs
- Truncates content for snippets at a safe length for prompt context

Neo4j Tool (strands/tools/neo4j_tool.py)
Interface (Python sketch)
class Neo4jTool:
    def __init__(self, neo4j_client):  # src/core/neo4j_client.Neo4jClient
        ...

    def code_relationships(self, chunk_id: str) -> dict:
        """Return callers, callees, domains for a given chunk_id (bounded)."""

    def repo_flows_summary(self, repository_names: list[str]) -> dict:
        """Return concise summary of cross-repo flows when needed (bounded)."""

Behavior
- Wraps allowlisted, parameterized read-only queries only
- Drops or truncates overly large results
- Never executes arbitrary Cypher

5) Prompt Builder Contract

Input
- question: string
- chunks: [ {chunk_id, file_path, repository, name, language, score, snippet, domains?, callers?, callees?} ]
- repo_summary?: structured facts for architecture mode
- policy: always cite sources by chunk_id and file_path; never fabricate

Output
- prompt: string (deterministic layout)
- token_estimate: int

Layout (example)
System:
You are an expert assistant for large legacy codebases. Answer with precision and cite sources using [chunk_id | file_path].

User:
Question:
{question}

Context (Top {N} code snippets):
1) {file_path} ({repository}) — {name} — score {score}
Snippet:
{snippet}

Relationships:
- Domains: {domains}
- Calls: {callers} → this; this → {callees}

[repeat for a few items, then stop]

{if architecture mode}
Repository/Flow Summary:
- {bullet}
- {bullet}

Answer policy:
- Do not fabricate. If unsure, say what is missing.
- Cite sources inline like: [chunk: CHUNK_ID | path: FILE_PATH].

6) LLM Provider Abstraction

Interface
class LLMProvider:
    def validate(self) -> None: ...
    def generate(self, prompt: str, *, max_tokens: int, temperature: float = 0.2,
                 stop: list[str] | None = None, timeout_s: float = 30.0) -> dict:
        """
        Returns: {
          "text": str, "tokens_in": int, "tokens_out": int, "time_ms": int, "model_id": str
        }
        """

Bedrock Implementation
- Reads from Settings: BEDROCK_MODEL_ID (sonnet-3.7), AWS_REGION, credential source
- validate(): checks env/profile and model ID
- generate(): single attempt, strict timeout; returns structured stats
- No fallback to other models

7) Settings and Validation

Settings additions
- AWS_REGION
- AWS_PROFILE or AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
- BEDROCK_MODEL_ID (exact)
- CHAT_ENABLED (derived at runtime by validation)
- LLM timeouts and token limits

Startup validation
- On app startup (lifespan or background task), attempt LLMProvider.validate()
- If success: set CHAT_ENABLED true; router registers
- If failure: CHAT_ENABLED false; router not registered; app logs explicit reason

8) Security and Stability

- Auth: enable JWT or API key middleware for /api/v1/chat/*
- CORS: restrict to known origins in FastAPI init
- Input bounds: enforce top_k [1..20], min_score [0..1], mode ∈ {semantic, hybrid}
- Resource limits:
  - Chroma: limit results; snippet truncation
  - Neo4j: limit expansions and payload sizes
  - LLM: token budget and timeout strict
- Errors: raise 4xx/5xx with clear details; no hidden retries or fallbacks

9) Observability

- Logging fields: request_id, user/principal (if available), retrieval counts, per-step latencies, model id, tokens in/out
- Optional: expose recent chat diagnostics via existing logs endpoint

10) Implementation Steps (summary)
- Create scaffolds: strands/agents/chat_agent.py, strands/tools/chroma_tool.py, strands/tools/neo4j_tool.py, src/api/routes/chat.py (feature-flagged)
- Extend Settings and validation
- Implement tools and deterministic retrieval service
- Implement LLM provider (Bedrock)
- Implement prompt builder
- Enable auth/CORS
- Update frontend to call /api/v1/chat/ask and show citations
- Add tests and documentation

Non-Goals
- No streaming in v1 (can be Phase 2)
- No model fallbacks
- No arbitrary Cypher execution