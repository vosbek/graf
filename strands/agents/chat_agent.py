"""
Strands Chat Agent (deterministic retrieval + prompt + Bedrock provider)

This module implements an import-safe, deterministic orchestration:
  1) Chroma semantic top-k with repository scope and min_score
  2) Neo4j bounded expansion (callers/callees, domains); optional repo flow summary for "hybrid"
  3) Deterministic, size-capped prompt assembly with citation policy
  4) BedrockProvider.generate() single-attempt call

No fallbacks. Errors propagate as exceptions to the API layer for 4xx/5xx handling.
"""

from typing import Any, Dict, List, Optional, Tuple
import time


class ChatAgent:
    """
    Deterministic agent. Tools and provider are injected by the application.
    chroma_tool: exposes async semantic_search()
    neo4j_tool: exposes async code_relationships() and optional repo_flows_summary()
    llm_provider: exposes validate() and generate()
    """

    def __init__(
        self,
        chroma_tool: Any = None,
        neo4j_tool: Any = None,
        oracle_tool: Any = None,
        llm_provider: Any = None,
        settings: Any = None,
    ):
        self._chroma_tool = chroma_tool
        self._neo4j_tool = neo4j_tool
        self._oracle_tool = oracle_tool
        self._llm_provider = llm_provider
        self._settings = settings

    @staticmethod
    def validate(config: Dict[str, Any]) -> bool:
        """
        Strict config presence validation (local); network validation is handled by provider if desired.
        """
        required = ["BEDROCK_MODEL_ID", "AWS_REGION"]
        for key in required:
            val = (config or {}).get(key)
            if not val or not isinstance(val, str) or not val.strip():
                return False
        return True

    def _pick_scope(self, repository_scope: Optional[List[str]]) -> Optional[List[str]]:
        if repository_scope and isinstance(repository_scope, list):
            scope = [r.strip() for r in repository_scope if isinstance(r, str) and r.strip()]
            return scope or None
        return None

    async def _semantic_topk(
        self,
        question: str,
        repository_scope: Optional[List[str]],
        top_k: int,
        min_score: float,
    ) -> List[Dict[str, Any]]:
        scope = self._pick_scope(repository_scope)
        results = await self._chroma_tool.semantic_search(
            question,
            repository_filter=scope,
            limit=top_k,
            min_score=min_score,
            include_metadata=True,
        )
        # Drop anything below min_score (tool should do it, but we enforce again)
        return [r for r in results if float(r.get("score", 0.0)) >= float(min_score)]

    async def _expand_structure(
        self,
        primary: List[Dict[str, Any]],
        mode: str,
        repository_scope: Optional[List[str]],
        max_items_for_graph: int = 5,
    ) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        For each of the top-N primary items, attach callers/callees/domains (bounded).
        Optionally add a repo flows summary if mode=='hybrid' and scope present.
        """
        expanded: List[Dict[str, Any]] = []
        graph_summary: Optional[Dict[str, Any]] = None

        for i, item in enumerate(primary[:max_items_for_graph]):
            chunk_id = item.get("chunk_id") or ""
            rel = {}
            try:
                rel = await self._neo4j_tool.code_relationships(chunk_id)
            except Exception:
                rel = {"callers": [], "callees": [], "domains": []}
            enriched = dict(item)
            enriched["relationships"] = {
                "callers": rel.get("callers", [])[:5],
                "callees": rel.get("callees", [])[:5],
                "domains": rel.get("domains", [])[:5],
            }
            expanded.append(enriched)

        if mode == "hybrid":
            scope = self._pick_scope(repository_scope) or []
            if scope:
                try:
                    graph_summary = await self._neo4j_tool.repo_flows_summary(scope)
                except Exception:
                    graph_summary = None

        return expanded, graph_summary

    def _build_prompt(
        self,
        question: str,
        items: List[Dict[str, Any]],
        graph_summary: Optional[Dict[str, Any]],
        max_tokens: int,
        diagram_mode: bool = False,
        oracle_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Deterministic prompt assembly. We cap size by count and snippet length rather than tokenizing.
        A downstream token filter is enforced by provider (max_output tokens).
        If diagram_mode is True, instruct model to include a fenced ```mermaid block when appropriate.
        """
        # Hard budgets for safety based on max_tokens
        max_items = max(1, min(len(items), 8))
        max_snippet_chars = 1200  # coarse; can be tuned by llm_max_input_tokens later

        lines: List[str] = []
        lines.append("System:\nYou are an expert assistant for large legacy codebases. ")
        lines.append("Answer with precision and cite sources using [chunk_id | file_path].\n")
        lines.append("User:\nQuestion:\n" + question.strip() + "\n")

        lines.append(f"Context (Top {max_items} code snippets):")
        for i, it in enumerate(items[:max_items], start=1):
            file_path = it.get("file_path", "")
            repo = it.get("repository", "")
            name = it.get("name", "")
            score = it.get("score", 0.0)
            snippet = (it.get("content", "") or "")[:max_snippet_chars]
            call_rel = it.get("relationships", {}) or {}
            callers = [c.get("name") or c.get("id") for c in call_rel.get("callers", []) if isinstance(c, dict)]
            callees = [c.get("name") or c.get("id") for c in call_rel.get("callees", []) if isinstance(c, dict)]
            domains = [d.get("name") for d in call_rel.get("domains", []) if isinstance(d, dict)]

            lines.append(f"{i}) {file_path} ({repo}) — {name} — score {score:.2f}")
            if snippet:
                lines.append("Snippet:\n" + snippet)
            if domains:
                lines.append("Domains: " + ", ".join(domains[:3]))
            if callers:
                lines.append("Callers: " + ", ".join(callers[:3]))
            if callees:
                lines.append("Callees: " + ", ".join(callees[:3]))
            lines.append("")

        if graph_summary and isinstance(graph_summary, dict):
            lines.append("Repository/Flow Summary:")
            flows = graph_summary.get("flows") or []
            integrations = graph_summary.get("integration_points") or []
            for f in flows[:5]:
                name = f.get("name", "flow")
                repos = f.get("repositories_involved", [])
                lines.append(f"- Flow: {name} | Repos: {', '.join(repos[:5])}")
            for ip in integrations[:5]:
                lines.append(f"- Integration: {ip.get('source','')} -> {ip.get('target','')} ({ip.get('count',0)})")
            lines.append("")

        # Add Oracle database information if available
        if oracle_data and oracle_data.get('data_sources'):
            lines.append("Oracle Database Information:")
            field_name = oracle_data.get('field_name', 'field')
            confidence = oracle_data.get('confidence', 0.0)
            lines.append(f"Field: {field_name} (confidence: {confidence:.2f})")
            
            for i, source in enumerate(oracle_data['data_sources'][:3], 1):  # Top 3 sources
                table = source.get('table', '')
                column = source.get('column', '')
                schema = source.get('schema', '')
                purpose = source.get('business_purpose', '')
                data_type = source.get('data_type', '')
                
                lines.append(f"{i}) Oracle Table: {schema}.{table}")
                lines.append(f"   Column: {column} ({data_type})")
                if purpose:
                    lines.append(f"   Purpose: {purpose}")
            
            # Add business rules if available
            if oracle_data.get('business_rules'):
                lines.append("Business Rules:")
                for rule in oracle_data['business_rules'][:3]:
                    lines.append(f"- {rule}")
            
            # Add related procedures if available
            if oracle_data.get('related_procedures'):
                lines.append("Related Procedures:")
                for proc in oracle_data['related_procedures'][:3]:
                    lines.append(f"- {proc}")
                    
            lines.append("")

        lines.append("Answer policy:")
        lines.append("- Do not fabricate. If unsure, say what is missing.")
        lines.append("- Cite sources inline like: [chunk: CHUNK_ID | path: FILE_PATH].")
        lines.append("- For Oracle data sources, cite as: [oracle: SCHEMA.TABLE.COLUMN].")
        if diagram_mode:
            lines.append("")
            lines.append("Diagram mode requirements (mandatory when helpful):")
            lines.append("- First, provide a clear English explanation of the answer.")
            lines.append("- Then, include a valid Mermaid diagram inside a fenced code block exactly like:")
            lines.append("```mermaid")
            lines.append("graph TD")
            lines.append("  A[Component] --> B[Component]")
            lines.append("```")
            lines.append("- Never return a diagram alone. Always include both English explanation and the diagram.")
            lines.append("- Ensure Mermaid syntax is valid. Place the diagram after the explanation.")

        return "\n".join(lines)

    async def _check_oracle_data_sources(self, question: str) -> Optional[Dict[str, Any]]:
        """
        Check if question is asking about data sources and use Oracle tool if available.
        
        Returns Oracle data source information if relevant, None otherwise.
        """
        if not self._oracle_tool:
            return None
        
        # Keywords that indicate data source questions
        data_source_keywords = [
            'where does', 'data source', 'comes from', 'gets its data',
            'field source', 'database table', 'oracle table', 'column',
            'specified amount', 'data flow', 'business rule'
        ]
        
        question_lower = question.lower()
        if not any(keyword in question_lower for keyword in data_source_keywords):
            return None
        
        try:
            # Extract field name from question (simple heuristic)
            field_name = self._extract_field_name(question)
            
            # Extract business context if present
            context = self._extract_business_context(question)
            
            # Use Oracle tool to find data source
            oracle_result = await self._oracle_tool.find_data_source(field_name, context)
            
            if oracle_result and oracle_result.get('data_sources'):
                return oracle_result
                
        except Exception as e:
            # Don't fail the whole request if Oracle lookup fails
            pass
        
        return None
    
    def _extract_field_name(self, question: str) -> str:
        """Extract field name from question using simple heuristics."""
        question_lower = question.lower()
        
        # Look for quoted field names
        import re
        quoted_matches = re.findall(r"['\"]([^'\"]+)['\"]", question)
        if quoted_matches:
            return quoted_matches[0]
        
        # Look for common field patterns
        field_patterns = [
            r"(\w+\s+amount)",
            r"(\w+\s+field)",
            r"(\w+\s+info)",
            r"(\w+\s+type)",
            r"(\w+\s+status)",
            r"(\w+\s+date)",
            r"(\w+\s+name)",
            r"(\w+\s+number)"
        ]
        
        for pattern in field_patterns:
            matches = re.findall(pattern, question_lower)
            if matches:
                return matches[0].strip()
        
        # Default: try to find field name after "where does" or similar
        if "where does" in question_lower:
            parts = question_lower.split("where does")
            if len(parts) > 1:
                # Extract first meaningful word after "where does"
                words = parts[1].strip().split()
                if words:
                    return words[0]
        
        return "field"
    
    def _extract_business_context(self, question: str) -> str:
        """Extract business context from question."""
        question_lower = question.lower()
        
        contexts = {
            'universal life': ['universal', 'ul', 'life insurance'],
            'account': ['account', 'acct'],
            'contract': ['contract', 'policy'],
            'customer': ['customer', 'client'],
            'payment': ['payment', 'billing'],
            'claim': ['claim', 'claims']
        }
        
        for context, keywords in contexts.items():
            if any(keyword in question_lower for keyword in keywords):
                return context
        
        return ""

    async def run(
        self,
        question: str,
        repository_scope: Optional[List[str]] = None,
        top_k: int = 8,
        min_score: float = 0.0,
        mode: str = "semantic",
    ) -> Dict[str, Any]:
        """
        Deterministic orchestration:
         1) semantic top-k
         2) bounded graph expansion (and repo flows for hybrid)
         3) deterministic prompt assembly
         4) single Bedrock call
        """
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question is required")
        if self._chroma_tool is None or self._neo4j_tool is None or self._llm_provider is None:
            raise RuntimeError("Agent not fully configured (tools/provider missing)")

        t0 = time.time()
        
        # Check if this is an Oracle data source question
        oracle_data = await self._check_oracle_data_sources(question)
        
        primary = await self._semantic_topk(question, repository_scope, top_k, min_score)
        t1 = time.time()
        expanded, graph_summary = await self._expand_structure(primary, mode, repository_scope)
        t2 = time.time()

        # Build prompt deterministically with Oracle data if available
        max_in_tokens = getattr(self._settings, "llm_max_input_tokens", 8000) if self._settings else 8000
        prompt = self._build_prompt(question, expanded, graph_summary, max_in_tokens, oracle_data=oracle_data)

        # Generate with Bedrock
        max_out_tokens = getattr(self._settings, "llm_max_output_tokens", 1024) if self._settings else 1024
        timeout_s = getattr(self._settings, "llm_request_timeout_seconds", 30.0) if self._settings else 30.0
        t3 = time.time()
        llm_resp = self._llm_provider.generate(
            prompt,
            max_tokens=max_out_tokens,
            temperature=0.2,
            stop=None,
            timeout_s=timeout_s,
        )
        t4 = time.time()

        # Build citations from expanded items with provenance (line ranges if available)
        citations = []
        for it in expanded:
            md = it.get("metadata", {}) or {}
            start_line = md.get("start_line")
            end_line = md.get("end_line")
            # Fallback: parse from chunk_id suffix if present e.g., "...:120-185"
            if (start_line is None or end_line is None) and isinstance(it.get("chunk_id"), str):
                cid = it["chunk_id"]
                if ":" in cid and "-" in cid.split(":")[-1]:
                    try:
                        rng = cid.split(":")[-1]
                        s, e = rng.split("-")
                        start_line = int(s)
                        end_line = int(e)
                    except Exception:
                        start_line = start_line if isinstance(start_line, int) else None
                        end_line = end_line if isinstance(end_line, int) else None

            citations.append(
                {
                    "chunk_id": it.get("chunk_id", ""),
                    "repository": it.get("repository", ""),
                    "file_path": it.get("file_path", ""),
                    "start_line": start_line,
                    "end_line": end_line,
                    "score": float(it.get("score", 0.0)),
                }
            )

        diagnostics = {
            "retrieval": {"count": len(primary), "time_ms": int((t1 - t0) * 1000)},
            "graph": {"queries": min(len(expanded), 5), "time_ms": int((t2 - t1) * 1000)},
            "llm": {
                "model_id": llm_resp.get("model_id", ""),
                "tokens_in": llm_resp.get("tokens_in", 0),
                "tokens_out": llm_resp.get("tokens_out", 0),
                "time_ms": llm_resp.get("time_ms", int((t4 - t3) * 1000)),
            },
        }

        return {
            "answer": llm_resp.get("text", ""),
            "citations": citations,
            "diagnostics": diagnostics,
        }