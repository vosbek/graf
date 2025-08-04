"""
Chroma Tool interface (feature-flagged, import-safe)

Thin wrapper around src/core/chromadb_client.ChromaDBClient providing a stable,
read-only interface for semantic search used by the Strands Chat Agent.

Do not import heavyweight modules at import time. Real client is injected by caller.
"""

from typing import Any, Dict, List, Optional


class ChromaTool:
    """
    Minimal interface for semantic search over code chunks.

    The concrete chroma_client should be an instance of src.core.chromadb_client.ChromaDBClient,
    injected by the application only when configuration validation passes.
    """

    def __init__(self, chroma_client: Any):
        self._client = chroma_client

    async def semantic_search(
        self,
        query: str,
        *,
        repository_filter: Optional[List[str]] = None,
        language: Optional[str] = None,
        domain: Optional[str] = None,
        chunk_type: Optional[str] = None,
        limit: int = 8,
        min_score: float = 0.0,
        include_metadata: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Execute semantic search and return normalized results:
        [
          {
            "chunk_id": str,
            "file_path": str,
            "repository": str,
            "language": str,
            "name": str,
            "score": float,
            "content": str
          },
          ...
        ]
        """
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query is required")

        # Late import to avoid heavy imports at module import time
        from src.core.chromadb_client import SearchQuery  # type: ignore

        # Build filters
        filters: Dict[str, Any] = {}
        if language:
            filters["language"] = language
        if domain:
            filters["business_domain"] = domain
        if chunk_type:
            filters["chunk_type"] = chunk_type

        sq = SearchQuery(
            query=query,
            filters=filters,
            limit=max(1, min(int(limit), 100)),
            min_score=float(min_score),
            include_metadata=include_metadata,
            repository_filter=repository_filter[0] if repository_filter and len(repository_filter) == 1 else None,
            language_filter=language,
            domain_filter=domain,
            chunk_type_filter=chunk_type,
        )

        results = await self._client.search(sq)

        normalized: List[Dict[str, Any]] = []
        for r in results:
            md = getattr(r, "metadata", {}) or {}
            normalized.append(
                {
                    "chunk_id": getattr(r, "chunk_id", md.get("chunk_id", "")),
                    "file_path": md.get("file_path", ""),
                    "repository": md.get("repository", ""),
                    "language": md.get("language", ""),
                    "name": md.get("name", ""),
                    "score": float(getattr(r, "score", 0.0)),
                    "content": getattr(r, "content", ""),
                }
            )
        return normalized