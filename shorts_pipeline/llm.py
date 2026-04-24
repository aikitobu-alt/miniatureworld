"""Pluggable LLM wrapper. Dispatches to the configured provider.

Providers:
  - openai (gpt-4o-mini etc.) - needs OPENAI_API_KEY
  - gemini (gemini-2.0-flash etc.) - needs GEMINI_API_KEY, FREE tier available
"""

from __future__ import annotations

import json
import re
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from .config import env, load_config


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _openai_chat_json(system: str, user: str, model: str, temperature: float) -> dict[str, Any]:
    from openai import OpenAI

    key = env().openai_api_key
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    client = OpenAI(api_key=key)
    resp = client.chat.completions.create(
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


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _gemini_chat_json(system: str, user: str, model: str, temperature: float) -> dict[str, Any]:
    import google.generativeai as genai

    key = env().gemini_api_key
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    genai.configure(api_key=key)
    m = genai.GenerativeModel(
        model_name=model,
        system_instruction=system,
        generation_config={
            "temperature": temperature,
            "response_mime_type": "application/json",
        },
    )
    resp = m.generate_content(user)
    text = resp.text or "{}"
    # Strip markdown fences if the model adds them (older Gemini does this)
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def chat_json(
    system: str,
    user: str,
    *,
    model: str | None = None,
    temperature: float = 0.8,
) -> dict[str, Any]:
    cfg = load_config().providers.llm
    provider = cfg.provider.lower()
    model = model or cfg.model
    if provider == "openai":
        return _openai_chat_json(system, user, model, temperature)
    if provider == "gemini":
        return _gemini_chat_json(system, user, model, temperature)
    raise ValueError(f"Unknown LLM provider: {provider}")
