"""OpenAI wrapper. All LLM calls in the pipeline go through here."""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import env, load_config


def _client() -> OpenAI:
    key = env().openai_api_key
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return OpenAI(api_key=key)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def chat_json(
    system: str,
    user: str,
    *,
    model: str | None = None,
    temperature: float = 0.8,
) -> dict[str, Any]:
    """Call chat completions with JSON response format and return parsed dict."""
    model = model or load_config().providers.llm.model
    resp = _client().chat.completions.create(
        model=model,
        temperature=temperature,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    content = resp.choices[0].message.content or "{}"
    return json.loads(content)
