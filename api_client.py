"""
AgentForge — Unified LLM API Client
Supports: Anthropic (Claude), OpenAI (GPT), Google Gemini, DeepSeek

Each provider implements a common interface so the executor doesn't
need to know which provider it's talking to.
"""

import os
from abc import ABC, abstractmethod
from typing import Optional

import httpx

# ── Provider registry ──
# Maps forge.yaml "provider" values to their classes.
# New providers just register here — no other code changes needed.

_PROVIDER_REGISTRY: dict[str, type["BaseProvider"]] = {}


def register_provider(name: str):
    """Class decorator: registers a provider class under `name`."""
    def dec(cls: type["BaseProvider"]):
        _PROVIDER_REGISTRY[name] = cls
        return cls
    return dec


def create_provider(
    provider_name: str,
    api_key: str,
    model: str,
    system_prompt: Optional[str] = None,
    timeout: int = 120,
    base_delay_ms: int = 500,
    max_retries: int = 2,
) -> "BaseProvider":
    """
    Factory: returns an initialized provider instance.
    Looks up `provider_name` in the registry and instantiates.
    """
    cls = _PROVIDER_REGISTRY.get(provider_name)
    if cls is None:
        available = list(_PROVIDER_REGISTRY.keys()) or ["(none registered)"]
        raise ValueError(
            f"Unknown provider '{provider_name}'. Available: {available}"
        )
    return cls(
        api_key=api_key,
        model=model,
        system_prompt=system_prompt,
        timeout=timeout,
        base_delay_ms=base_delay_ms,
        max_retries=max_retries,
    )


# ═══════════════════════════════════════════════════════════════
# Abstract base
# ═══════════════════════════════════════════════════════════════

class BaseProvider(ABC):
    """Every LLM provider must implement this interface."""

    def __init__(
        self,
        api_key: str,
        model: str,
        system_prompt: Optional[str] = None,
        timeout: int = 120,
        base_delay_ms: int = 500,
        max_retries: int = 2,
    ):
        self.api_key = api_key
        self.model = model
        self.system_prompt = system_prompt
        self.timeout = timeout
        self.base_delay_ms = base_delay_ms
        self.max_retries = max_retries

    @abstractmethod
    def chat(self, task: str) -> str:
        """
        Send a task to the LLM and return its response text.
        Must raise on failure — callers catch and convert to result dicts.
        """
        ...

    # ── shared HTTP helpers ──

    def _post_json(self, url: str, payload: dict, headers: dict) -> httpx.Response:
        """POST with retry logic for transient failures."""
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = httpx.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
                # 429 / 5xx → retry
                if resp.status_code in (429, 500, 502, 503, 504):
                    if attempt < self.max_retries:
                        import time
                        delay = self.base_delay_ms * (2 ** attempt) / 1000.0
                        time.sleep(delay)
                        continue
                return resp
            except httpx.TimeoutException as e:
                last_exc = RuntimeError(f"Request timed out after {self.timeout}s")
                if attempt < self.max_retries:
                    import time
                    time.sleep(self.base_delay_ms / 1000.0)
                    continue
                raise last_exc from e
            except httpx.RequestError as e:
                last_exc = RuntimeError(f"Network error: {e}")
                if attempt < self.max_retries:
                    import time
                    time.sleep(self.base_delay_ms / 1000.0)
                    continue
                raise last_exc from e
        # Ran out of retries
        raise RuntimeError(
            f"HTTP {resp.status_code}: {resp.text[:500]}"
        )

    @staticmethod
    def _resolve_api_key(key_or_env: str) -> str:
        """
        Accept either a raw API key or an environment variable name.
        - If the value looks like an env var name (no common key prefix), look it up.
        - Otherwise, use it directly.
        """
        if not key_or_env:
            raise ValueError("API key is empty — set api_key or api_key_env in forge.yaml")

        if any(
            key_or_env.startswith(p)
            for p in ("sk-", "AIza", "sk-ant-", "dsk-")
        ):
            return key_or_env

        val = os.getenv(key_or_env, "")
        if val:
            return val

        raise ValueError(
            f"Environment variable '{key_or_env}' is not set.\n"
            f"  Option 1: export {key_or_env}=<your-key>\n"
            f"  Option 2: set api_key directly in forge.yaml (not recommended for shared configs)"
        )


# ═══════════════════════════════════════════════════════════════
# Anthropic (Claude) — Messages API
# ═══════════════════════════════════════════════════════════════

@register_provider("anthropic")
class AnthropicProvider(BaseProvider):
    """Claude models via Anthropic Messages API."""

    BASE_URL = "https://api.anthropic.com/v1/messages"

    def chat(self, task: str) -> str:
        api_key = self._resolve_api_key(self.api_key)
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = self._build_request(task)
        resp = self._post_json(self.BASE_URL, payload, headers)
        return self._handle_response(resp)

    def _build_request(self, task: str) -> dict:
        body: dict = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": task}],
        }
        if self.system_prompt:
            body["system"] = self.system_prompt
        return body

    def _handle_response(self, resp: httpx.Response) -> str:
        if resp.status_code == 401:
            raise RuntimeError("Anthropic API: invalid API key (401)")
        if resp.status_code == 403:
            raise RuntimeError("Anthropic API: access denied (403) — check your account/permissions")
        if resp.status_code != 200:
            raise RuntimeError(f"Anthropic API error {resp.status_code}: {resp.text[:500]}")

        data = resp.json()
        try:
            blocks = data.get("content", [])
            text = "\n".join(
                block.get("text", "") for block in blocks if block.get("type") == "text"
            )
            return text.strip()
        except (KeyError, TypeError) as e:
            raise RuntimeError(f"Unexpected Anthropic response format: {e}")


# ═══════════════════════════════════════════════════════════════
# OpenAI (GPT) — Chat Completions API
# ═══════════════════════════════════════════════════════════════

@register_provider("openai")
class OpenAIProvider(BaseProvider):
    """GPT models via OpenAI Chat Completions API."""

    BASE_URL = "https://api.openai.com/v1/chat/completions"

    def chat(self, task: str) -> str:
        api_key = self._resolve_api_key(self.api_key)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "content-type": "application/json",
        }
        payload = self._build_request(task)
        resp = self._post_json(self.BASE_URL, payload, headers)
        return self._handle_response(resp)

    def _build_request(self, task: str) -> dict:
        messages: list = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": task})
        return {
            "model": self.model,
            "messages": messages,
            "max_tokens": 4096,
        }

    def _handle_response(self, resp: httpx.Response) -> str:
        if resp.status_code == 401:
            raise RuntimeError("OpenAI API: invalid API key (401)")
        if resp.status_code == 403:
            raise RuntimeError("OpenAI API: access denied (403) — check your billing/region")
        if resp.status_code != 200:
            raise RuntimeError(f"OpenAI API error {resp.status_code}: {resp.text[:500]}")

        data = resp.json()
        try:
            choices = data.get("choices", [])
            if not choices:
                raise RuntimeError("OpenAI returned no choices")
            return (choices[0].get("message", {}).get("content", "")).strip()
        except (KeyError, TypeError, IndexError) as e:
            raise RuntimeError(f"Unexpected OpenAI response format: {e}")


# ═══════════════════════════════════════════════════════════════
# Google Gemini — generateContent API
# ═══════════════════════════════════════════════════════════════

@register_provider("gemini")
class GeminiProvider(BaseProvider):
    """Gemini models via Google AI Studio / Vertex-compatible generateContent."""

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"

    def chat(self, task: str) -> str:
        api_key = self._resolve_api_key(self.api_key)
        url = self.BASE_URL.format(self.model) + f"?key={api_key}"
        headers = {"content-type": "application/json"}
        payload = self._build_request(task)
        resp = self._post_json(url, payload, headers)
        return self._handle_response(resp)

    def _build_request(self, task: str) -> dict:
        body: dict = {
            "contents": [
                {"role": "user", "parts": [{"text": task}]}
            ],
            "generationConfig": {
                "maxOutputTokens": 4096,
            },
        }
        if self.system_prompt:
            body["systemInstruction"] = {
                "parts": [{"text": self.system_prompt}]
            }
        return body

    def _handle_response(self, resp: httpx.Response) -> str:
        if resp.status_code in (401, 403):
            raise RuntimeError(f"Gemini API: authentication failed ({resp.status_code}) — check your API key")
        if resp.status_code != 200:
            raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text[:500]}")

        data = resp.json()
        try:
            candidates = data.get("candidates", [])
            if not candidates:
                feedback = data.get("promptFeedback", {})
                block_reason = feedback.get("blockReason", "")
                if block_reason:
                    raise RuntimeError(f"Gemini blocked the request: {block_reason}")
                raise RuntimeError("Gemini returned no candidates")
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "\n".join(p.get("text", "") for p in parts)
            return text.strip()
        except (KeyError, TypeError, IndexError) as e:
            raise RuntimeError(f"Unexpected Gemini response format: {e}")


# ═══════════════════════════════════════════════════════════════
# DeepSeek — OpenAI-compatible Chat Completions
# ═══════════════════════════════════════════════════════════════

@register_provider("deepseek")
class DeepSeekProvider(OpenAIProvider):
    """DeepSeek models via OpenAI-compatible Chat Completions API."""

    BASE_URL = "https://api.deepseek.com/v1/chat/completions"

    def _handle_response(self, resp: httpx.Response) -> str:
        if resp.status_code == 401:
            raise RuntimeError("DeepSeek API: invalid API key (401)")
        if resp.status_code == 402:
            raise RuntimeError("DeepSeek API: insufficient balance (402)")
        if resp.status_code != 200:
            raise RuntimeError(f"DeepSeek API error {resp.status_code}: {resp.text[:500]}")

        data = resp.json()
        try:
            choices = data.get("choices", [])
            if not choices:
                raise RuntimeError("DeepSeek returned no choices")
            return (choices[0].get("message", {}).get("content", "")).strip()
        except (KeyError, TypeError, IndexError) as e:
            raise RuntimeError(f"Unexpected DeepSeek response format: {e}")
