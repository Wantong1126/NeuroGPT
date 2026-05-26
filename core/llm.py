# SPDX-License-Identifier: MIT
"""
NeuroGPT v2 — LLM Client
Single interface for all LLM calls.
Currently uses OpenAI-compatible API. To switch provider,
only change the imports and the `call` function.
"""
from __future__ import annotations
import os, json, time, httpx
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is optional at runtime.
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

# ── API Configuration ──────────────────────────────────
# Set these via environment variables or .env file:
#   NEUROGPT_LLM_API_KEY
#   NEUROGPT_LLM_BASE_URL   (default: https://api.openai.com/v1)
#   NEUROGPT_LLM_MODEL      (default: gpt-4o-mini)

API_KEY = os.environ.get("NEUROGPT_LLM_API_KEY", "")
BASE_URL = os.environ.get("NEUROGPT_LLM_BASE_URL", "https://api.openai.com/v1")
MODEL   = os.environ.get("NEUROGPT_LLM_MODEL", "gpt-4o-mini")

MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = (1, 2, 4)
TRANSIENT_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}
TRANSIENT_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.ReadError,
    httpx.RemoteProtocolError,
    httpx.TimeoutException,
)
RETRYABLE_EXCEPTION_TYPES = TRANSIENT_EXCEPTIONS + (httpx.HTTPStatusError,)
LAST_CALL_ATTEMPTS = 0


class LLMAPIError(Exception):
    """Raised when a transient LLM API failure exhausts retry attempts."""

    def __init__(self, message: str, *, attempts: int) -> None:
        super().__init__(message)
        self.attempts = attempts


def get_last_call_attempt_count() -> int:
    return LAST_CALL_ATTEMPTS


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def get_runtime_config(
    *,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
) -> dict:
    """Return non-secret LLM runtime config for diagnostics and tests."""
    return {
        "base_url": _env("NEUROGPT_LLM_BASE_URL", base_url or BASE_URL),
        "model": _env("NEUROGPT_LLM_MODEL", model or MODEL),
        "api_key_configured": bool(_env("NEUROGPT_LLM_API_KEY", API_KEY)),
    }


def _is_transient_status_error(exc: httpx.HTTPStatusError) -> bool:
    return exc.response.status_code in TRANSIENT_STATUS_CODES


def _should_retry(exc: Exception) -> bool:
    if isinstance(exc, TRANSIENT_EXCEPTIONS):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return _is_transient_status_error(exc)
    return False


def _attempt_label(attempts: int) -> str:
    return "attempt" if attempts == 1 else "attempts"

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
    base_url: Optional[str] = None,
    json_mode: bool = False,
    temperature: float = 0.3,
) -> str:
    """
    Make an LLM API call. Returns the assistant's text response.

    Args:
        user_message: The user prompt.
        system_prompt: System-level instructions.
        model: Override the default model.
        base_url: Override the default OpenAI-compatible base URL.
        json_mode: If True, request structured JSON output.
        temperature: Lower = more deterministic (0.1-0.3 recommended for medical).
    """
    global LAST_CALL_ATTEMPTS
    LAST_CALL_ATTEMPTS = 0

    api_key = _env("NEUROGPT_LLM_API_KEY", API_KEY)
    resolved_base_url = _env("NEUROGPT_LLM_BASE_URL", base_url or BASE_URL)
    resolved_model = _env("NEUROGPT_LLM_MODEL", model or MODEL)

    if not api_key:
        raise RuntimeError(
            "NEUROGPT_LLM_API_KEY is not set. "
            "Please set your API key in .env or environment variable."
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": resolved_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": temperature,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    with httpx.Client(timeout=60.0) as client:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            LAST_CALL_ATTEMPTS = attempt
            try:
                response = client.post(
                    f"{resolved_base_url.rstrip('/')}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except RETRYABLE_EXCEPTION_TYPES as exc:
                if not _should_retry(exc):
                    raise
                if attempt >= MAX_ATTEMPTS:
                    raise LLMAPIError(
                        f"LLM API call failed after {attempt} {_attempt_label(attempt)}: {exc}",
                        attempts=attempt,
                    ) from exc
                time.sleep(RETRY_BACKOFF_SECONDS[attempt - 1])


def call_structured(
    user_message: str,
    system_prompt: str,
    schema: str,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
) -> dict:
    """Call LLM and parse JSON response matching the provided schema description."""
    full_system = (
        system_prompt
        + f"\n\nIMPORTANT: Your response MUST be valid JSON conforming to this schema:\n{schema}"
        + "\nReturn ONLY the JSON object, no additional text."
    )
    raw = call(
        user_message,
        system_prompt=full_system,
        model=model,
        base_url=base_url,
        json_mode=True,
    )
    # Strip markdown code fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw)
