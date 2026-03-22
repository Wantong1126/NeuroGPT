# SPDX-License-Identifier: MIT
"""
NeuroGPT v2 — LLM Client
Single interface for all LLM calls.
Currently uses OpenAI-compatible API. To switch provider,
only change the imports and the `call` function.
"""
from __future__ import annotations
import os, json, httpx
from typing import Optional

# ── API Configuration ──────────────────────────────────
# Set these via environment variables or .env file:
#   NEUROGPT_LLM_API_KEY
#   NEUROGPT_LLM_BASE_URL   (default: https://api.openai.com/v1)
#   NEUROGPT_LLM_MODEL      (default: gpt-4o-mini)

API_KEY = os.environ.get("NEUROGPT_LLM_API_KEY", "")
BASE_URL = os.environ.get("NEUROGPT_LLM_BASE_URL", "https://api.openai.com/v1")
MODEL   = os.environ.get("NEUROGPT_LLM_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT_DEFAULT = (
    "You are a medical education assistant. "
    "You provide clear, accurate, plain-language health information. "
    "You are empathetic, calm, and never provide diagnostic conclusions. "
    "When uncertain, always recommend seeking professional care."
)

def call(
    user_message: str,
    system_prompt: str = SYSTEM_PROMPT_DEFAULT,
    model: Optional[str] = None,
    json_mode: bool = False,
    temperature: float = 0.3,
) -> str:
    """
    Make an LLM API call. Returns the assistant's text response.

    Args:
        user_message: The user prompt.
        system_prompt: System-level instructions.
        model: Override the default model.
        json_mode: If True, request structured JSON output.
        temperature: Lower = more deterministic (0.1-0.3 recommended for medical).
    """
    if not API_KEY:
        raise RuntimeError(
            "NEUROGPT_LLM_API_KEY is not set. "
            "Please set your API key in .env or environment variable."
        )

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model or MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": temperature,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    with httpx.Client(timeout=60.0) as client:
        response = client.post(
            f"{BASE_URL.rstrip('/')}/chat/completions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


def call_structured(
    user_message: str,
    system_prompt: str,
    schema: str,
) -> dict:
    """Call LLM and parse JSON response matching the provided schema description."""
    full_system = (
        system_prompt
        + f"\n\nIMPORTANT: Your response MUST be valid JSON conforming to this schema:\n{schema}"
        + "\nReturn ONLY the JSON object, no additional text."
    )
    raw = call(user_message, system_prompt=full_system, json_mode=True)
    # Strip markdown code fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw)
