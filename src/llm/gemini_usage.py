from __future__ import annotations

import logging

from google.genai.types import GenerateContentResponse

from core.types import Usage


def extract_gemini_usage(
    response: GenerateContentResponse,
    usage: Usage,
    *,
    logger: logging.Logger,
) -> None:
    """Extract token usage from Gemini responses into a provider-agnostic Usage object.

    The helper is intentionally Gemini-specific because it depends on
    ``GenerateContentResponse.usage_metadata``.
    """
    meta = response.usage_metadata
    if meta is None:
        logger.warning("Gemini response missing usage_metadata")
        return

    usage.record(
        prompt_tokens=meta.prompt_token_count or 0,
        completion_tokens=getattr(meta, "candidates_token_count", None) or 0,
        total_tokens=meta.total_token_count or 0,
    )