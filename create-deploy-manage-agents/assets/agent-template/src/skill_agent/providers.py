"""Provider-independent model gateway using direct HTTP APIs."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import quote

import httpx

from .config import Settings


class ModelProviderError(RuntimeError):
    """A normalized provider failure safe to expose without response bodies."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class ModelResult:
    text: str
    usage: dict[str, int | float | str | None] = field(default_factory=dict)


class ModelGateway(Protocol):
    async def complete(self, *, system_prompt: str, user_prompt: str) -> ModelResult: ...


class HttpModelGateway:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._client = client

    async def complete(self, *, system_prompt: str, user_prompt: str) -> ModelResult:
        self.settings.validate()
        last_error: ModelProviderError | None = None
        for attempt in range(self.settings.retry_attempts + 1):
            try:
                return await self._request(system_prompt=system_prompt, user_prompt=user_prompt)
            except ModelProviderError as exc:
                last_error = exc
                if not exc.retryable or attempt >= self.settings.retry_attempts:
                    raise
                delay = min(2**attempt, 4) + random.uniform(0, 0.25)
                await asyncio.sleep(delay)
        raise last_error or ModelProviderError("Model request failed")

    async def _request(self, *, system_prompt: str, user_prompt: str) -> ModelResult:
        request = self._build_request(system_prompt=system_prompt, user_prompt=user_prompt)
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self.settings.timeout_seconds)
        try:
            response = await client.request(**request)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ModelProviderError("Model provider connection failed", retryable=True) from exc
        finally:
            if owns_client:
                await client.aclose()

        if response.status_code >= 400:
            retryable = response.status_code == 429 or response.status_code >= 500
            raise ModelProviderError(
                f"Model provider returned HTTP {response.status_code}", retryable=retryable
            )
        try:
            return self._parse_response(response.json())
        except (KeyError, TypeError, ValueError) as exc:
            raise ModelProviderError("Model provider returned an unexpected response") from exc

    def _build_request(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        provider = self.settings.provider
        if provider == "openai":
            return {
                "method": "POST",
                "url": f"{self.settings.base_url}/responses",
                "headers": {"Authorization": f"Bearer {self.settings.api_key}"},
                "json": {
                    "model": self.settings.model,
                    "instructions": system_prompt,
                    "input": user_prompt,
                    "max_output_tokens": self.settings.max_output_tokens,
                },
            }
        if provider == "anthropic":
            return {
                "method": "POST",
                "url": f"{self.settings.base_url}/messages",
                "headers": {
                    "x-api-key": self.settings.api_key,
                    "anthropic-version": "2023-06-01",
                },
                "json": {
                    "model": self.settings.model,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                    "max_tokens": self.settings.max_output_tokens,
                },
            }
        if provider == "gemini":
            model = quote(self.settings.model, safe="-_.")
            return {
                "method": "POST",
                "url": f"{self.settings.base_url}/models/{model}:generateContent",
                "headers": {"x-goog-api-key": self.settings.api_key},
                "json": {
                    "systemInstruction": {"parts": [{"text": system_prompt}]},
                    "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
                    "generationConfig": {"maxOutputTokens": self.settings.max_output_tokens},
                },
            }
        if provider == "ollama":
            return {
                "method": "POST",
                "url": f"{self.settings.base_url}/api/chat",
                "json": {
                    "model": self.settings.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "stream": False,
                    "options": {"num_predict": self.settings.max_output_tokens},
                },
            }
        raise ModelProviderError(f"Unsupported model provider: {provider}")

    def _parse_response(self, data: dict[str, Any]) -> ModelResult:
        provider = self.settings.provider
        if provider == "openai":
            text = data.get("output_text")
            if not text:
                text = "".join(
                    item.get("text", "")
                    for output in data.get("output", [])
                    for item in output.get("content", [])
                    if item.get("type") in {"output_text", "text"}
                )
            return ModelResult(text=text, usage=data.get("usage", {}))
        if provider == "anthropic":
            text = "".join(
                item.get("text", "")
                for item in data.get("content", [])
                if item.get("type") == "text"
            )
            return ModelResult(text=text, usage=data.get("usage", {}))
        if provider == "gemini":
            text = "".join(
                part.get("text", "")
                for candidate in data.get("candidates", [])[:1]
                for part in candidate.get("content", {}).get("parts", [])
            )
            return ModelResult(text=text, usage=data.get("usageMetadata", {}))
        if provider == "ollama":
            message = data.get("message", {})
            usage = {
                "input_tokens": data.get("prompt_eval_count"),
                "output_tokens": data.get("eval_count"),
            }
            return ModelResult(text=message.get("content", ""), usage=usage)
        raise ModelProviderError(f"Unsupported model provider: {provider}")
