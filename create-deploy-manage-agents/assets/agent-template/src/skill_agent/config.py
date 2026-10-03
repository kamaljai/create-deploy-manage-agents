"""Environment-derived runtime configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass

PROVIDERS = {"gemini", "ollama", "openai", "anthropic"}
DEFAULT_BASE_URLS = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "ollama": "http://host.docker.internal:11434",
}
KEY_VARIABLES = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


class ConfigurationError(ValueError):
    """Raised when runtime configuration is incomplete or invalid."""


@dataclass(frozen=True, slots=True)
class Settings:
    provider: str
    model: str
    api_key: str | None
    base_url: str
    timeout_seconds: float = 60.0
    retry_attempts: int = 1
    max_input_chars: int = 100_000
    max_output_tokens: int = 2_048
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> Settings:
        provider = os.getenv("LLM_PROVIDER", "__DEFAULT_PROVIDER__").lower().strip()
        model = os.getenv("LLM_MODEL", "__DEFAULT_MODEL__").strip()
        key_variable = KEY_VARIABLES.get(provider)
        base_variable = f"{provider.upper()}_BASE_URL"
        return cls(
            provider=provider,
            model=model,
            api_key=os.getenv(key_variable) if key_variable else None,
            base_url=os.getenv(base_variable, DEFAULT_BASE_URLS.get(provider, "")).rstrip("/"),
            timeout_seconds=float(os.getenv("MODEL_TIMEOUT_SECONDS", "60")),
            retry_attempts=int(os.getenv("MODEL_RETRY_ATTEMPTS", "1")),
            max_input_chars=int(os.getenv("MAX_INPUT_CHARS", "100000")),
            max_output_tokens=int(os.getenv("MAX_OUTPUT_TOKENS", "2048")),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )

    def validate(self) -> None:
        if self.provider not in PROVIDERS:
            raise ConfigurationError(f"Unsupported LLM_PROVIDER: {self.provider}")
        if not self.model:
            raise ConfigurationError("LLM_MODEL is required")
        if self.provider != "ollama" and not self.api_key:
            raise ConfigurationError(f"{KEY_VARIABLES[self.provider]} is required")
        if not self.base_url:
            raise ConfigurationError(f"Base URL is required for provider {self.provider}")
        if self.timeout_seconds <= 0 or self.retry_attempts not in range(0, 4):
            raise ConfigurationError("Timeout must be positive and retries must be between 0 and 3")
        if self.max_input_chars <= 0 or self.max_output_tokens <= 0:
            raise ConfigurationError("Input and output limits must be positive")
