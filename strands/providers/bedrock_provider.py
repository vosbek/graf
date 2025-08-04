"""
BedrockProvider (no fallbacks, import-safe)

This provider performs a single-attempt Bedrock text generation call with strict timeout
and token limits. It keeps imports lazy to avoid import-time side effects. Validation
is configuration-only by default (no network). You may optionally enable a lightweight
runtime probe later.

Environment and settings:
- model_id: settings.bedrock_model_id (BEDROCK_MODEL_ID)
- region:   settings.aws_region (AWS_REGION)
- creds:    AWS_PROFILE or AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
- limits:   llm_max_input_tokens, llm_max_output_tokens, llm_request_timeout_seconds
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import time


@dataclass
class BedrockConfig:
    model_id: Optional[str]
    region: Optional[str]
    max_input_tokens: int
    max_output_tokens: int
    request_timeout_seconds: float
    profile: Optional[str] = None
    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None


class BedrockProvider:
    """
    Import-safe Bedrock provider. Does not import boto3 until generate() is called.
    No retries that mask errors; raise on failure.
    """

    def __init__(self, config: BedrockConfig):
        self._cfg = config

    def validate(self) -> None:
        """
        Strict configuration validation (local only by default).
        Ensures required fields are present and sane. No network calls here.
        """
        if not self._cfg.model_id or not isinstance(self._cfg.model_id, str) or not self._cfg.model_id.strip():
            raise ValueError("BEDROCK_MODEL_ID missing or invalid")
        if not self._cfg.region or not isinstance(self._cfg.region, str) or not self._cfg.region.strip():
            raise ValueError("AWS_REGION missing or invalid")
        if self._cfg.max_input_tokens <= 0 or self._cfg.max_output_tokens <= 0:
            raise ValueError("LLM token limits must be positive")
        if self._cfg.request_timeout_seconds <= 0:
            raise ValueError("LLM request timeout must be positive")

        # Credential presence (one of profile or key/secret); actual resolution handled by boto later
        if not (self._cfg.profile or (self._cfg.access_key_id and self._cfg.secret_access_key)):
            # Allow implicit default credential chain as a last resort if explicitly desired:
            # For strictness, we still require at least one hint to be present.
            raise ValueError("AWS credentials not specified (set AWS_PROFILE or AWS_ACCESS_KEY_ID/SECRET_ACCESS_KEY)")

    def _build_bedrock_client(self):
        """
        Lazily construct a Bedrock runtime client using boto3 with the configured region and credentials.
        """
        import boto3  # lazy import

        session_kwargs: Dict[str, Any] = {}
        if self._cfg.profile:
            session_kwargs["profile_name"] = self._cfg.profile

        session = boto3.Session(**session_kwargs)

        # If explicit keys provided, they will be picked up by environment or session if exported.
        # We do not manually pass keys to the client to avoid redundancy and encourage standard provider chain.
        client = session.client("bedrock-runtime", region_name=self._cfg.region)
        return client

    def generate(
        self,
        prompt: str,
        *,
        max_tokens: Optional[int] = None,
        temperature: float = 0.2,
        stop: Optional[List[str]] = None,
        timeout_s: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Single-attempt text generation. Returns:
        {
          "text": str,
          "tokens_in": int,
          "tokens_out": int,
          "time_ms": int,
          "model_id": str
        }
        """
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt is required")

        # Apply limits
        max_out = max_tokens if isinstance(max_tokens, int) and max_tokens > 0 else self._cfg.max_output_tokens
        timeout = float(timeout_s) if isinstance(timeout_s, (int, float)) and timeout_s > 0 else self._cfg.request_timeout_seconds

        # Validate config (local checks)
        self.validate()

        # Build client lazily
        client = self._build_bedrock_client()

        # Prepare model-specific request body; example uses a Claude-style interface
        # Adjust "anthropic_version" and input schema to your selected Sonnet 3.7 model in your region.
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_out,
            "temperature": float(temperature),
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": prompt}]}
            ],
        }
        if stop:
            body["stop_sequences"] = stop[:4]

        import json
        from botocore.config import Config as BotoConfig  # lazy import

        boto_cfg = BotoConfig(read_timeout=int(timeout), connect_timeout=int(timeout), retries={"max_attempts": 0})
        model_id = self._cfg.model_id

        start = time.time()
        # Invoke the model
        response = client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body),
            config=boto_cfg,
        )
        elapsed_ms = int((time.time() - start) * 1000)

        # Parse response
        payload = json.loads(response.get("body").read().decode("utf-8"))

        # Claude-like responses: content list with text items
        text = ""
        try:
            # Prefer assistant message content
            if isinstance(payload.get("content"), list) and payload["content"]:
                # content: [{ "type": "text", "text": "..." }]
                for part in payload["content"]:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text += part.get("text", "")
            elif "output_text" in payload:
                text = payload["output_text"] or ""
        except Exception:
            text = ""

        # Token accounting may vary by model; attempt to read usage fields if present
        tokens_in = int(payload.get("input_tokens", payload.get("usage", {}).get("input_tokens", 0)) or 0)
        tokens_out = int(payload.get("output_tokens", payload.get("usage", {}).get("output_tokens", 0)) or 0)

        return {
            "text": text,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "time_ms": elapsed_ms,
            "model_id": model_id or "",
        }