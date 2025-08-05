"""
Chat API router (feature-flagged)

This router defines POST /api/v1/chat/ask but MUST be registered only when
chat is enabled (validated Bedrock config present). Keep imports light and
free of heavyweight side effects. Actual agent/tools are injected by the app.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, validator

# Dependencies are resolved by the application; they should be lightweight to import
from ...dependencies import get_chroma_client, get_neo4j_client, get_oracle_client  # type: ignore
from ...config.settings import settings  # to read Bedrock/LLM fields


router = APIRouter()


# ----- Models -----


class ChatAskRequest(BaseModel):
    question: str = Field(..., description="User question about the codebase")
    repository_scope: Optional[List[str]] = Field(
        default=None, description="Optional list of repository names to scope the analysis"
    )
    top_k: int = Field(default=8, ge=1, le=20, description="Number of results to retrieve from vector search")
    min_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum similarity score filter")
    mode: str = Field(default="semantic", description='Retrieval mode: "semantic" or "hybrid"')
    diagram_mode: bool = Field(default=False, description="If true, request a mermaid diagram block when appropriate")

    @validator("mode")
    def validate_mode(cls, v: str) -> str:
        allowed = {"semantic", "hybrid"}
        if v not in allowed:
            raise ValueError(f"mode must be one of {allowed}")
        return v


class Citation(BaseModel):
    chunk_id: str
    repository: str
    file_path: str
    score: float


class ChatAskResponse(BaseModel):
    answer: str
    citations: List[Citation]
    diagnostics: Dict[str, Any]


# ----- Route (must be registered conditionally by app/main) -----


@router.post("/ask", response_model=ChatAskResponse)
async def chat_ask(
    req: ChatAskRequest,
    chroma_client: Any = Depends(get_chroma_client),
    neo4j_client: Any = Depends(get_neo4j_client),
):
    """
    Feature-flagged chat endpoint. Builds tools and Bedrock provider, then invokes the deterministic agent.
    """
    # Late imports to keep module import light
    try:
        from strands.agents.chat_agent import ChatAgent  # type: ignore
        from strands.tools.chroma_tool import ChromaTool  # type: ignore
        from strands.tools.neo4j_tool import Neo4jTool  # type: ignore
        from strands.providers.bedrock_provider import BedrockProvider, BedrockConfig  # type: ignore
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Chat components unavailable: {e}")

    # Build tools (DI clients are already validated by app startup)
    chroma_tool = ChromaTool(chroma_client)
    neo4j_tool = Neo4jTool(neo4j_client)
    
    # Get Oracle client (optional - may be None if Oracle integration disabled)
    oracle_tool = None
    try:
        oracle_client = get_oracle_client()
        if oracle_client and oracle_client.enabled:
            from strands.tools.oracle_tool import OracleTool  # type: ignore
            oracle_tool = OracleTool(oracle_client)
    except Exception:
        # Oracle integration is optional - continue without it
        oracle_tool = None

    # Construct Bedrock provider from Settings and validate strictly (no fallbacks)
    cfg = BedrockConfig(
        model_id=settings.bedrock_model_id,
        region=settings.aws_region,
        max_input_tokens=settings.llm_max_input_tokens,
        max_output_tokens=settings.llm_max_output_tokens,
        request_timeout_seconds=settings.llm_request_timeout_seconds,
        profile=settings.aws_profile,
        access_key_id=settings.aws_access_key_id,
        secret_access_key=settings.aws_secret_access_key,
    )
    provider = BedrockProvider(cfg)
    try:
        provider.validate()
    except Exception as e:
        # Provider not valid; do not proceed (router should have been gated at startup, but double-check here)
        raise HTTPException(status_code=503, detail=f"Bedrock provider invalid: {e}")

    # Construct the deterministic agent with Oracle tool
    agent = ChatAgent(
        chroma_tool=chroma_tool,
        neo4j_tool=neo4j_tool,
        oracle_tool=oracle_tool,
        llm_provider=provider,
        settings=settings,
    )

    try:
        result = await agent.run(
            question=req.question,
            repository_scope=req.repository_scope,
            top_k=req.top_k,
            min_score=req.min_score,
            mode=req.mode,
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        # Do not mask errors; return a controlled 503 (no fallbacks)
        raise HTTPException(status_code=503, detail=f"Chat invocation failed: {e}")

    # Normalize result to API shape
    citations = [
        Citation(
            chunk_id=c.get("chunk_id", ""),
            repository=c.get("repository", ""),
            file_path=c.get("file_path", ""),
            score=float(c.get("score", 0.0)),
        )
        for c in result.get("citations", []) or []
    ]
    resp = ChatAskResponse(
        answer=result.get("answer", ""),
        citations=citations,
        diagnostics=result.get("diagnostics", {}),
    )
    return resp