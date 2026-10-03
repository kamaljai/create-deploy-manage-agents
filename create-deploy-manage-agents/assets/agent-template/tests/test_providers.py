from __future__ import annotations

from skill_agent.config import ConfigurationError, Settings
from skill_agent.providers import HttpModelGateway


def settings(provider: str, api_key: str | None = "secret") -> Settings:
    return Settings(
        provider=provider,
        model="test-model",
        api_key=api_key,
        base_url="https://provider.test/v1",
    )


def test_gemini_key_is_sent_in_header_not_url() -> None:
    request = HttpModelGateway(settings("gemini"))._build_request(
        system_prompt="system", user_prompt="user"
    )
    assert request["headers"] == {"x-goog-api-key": "secret"}
    assert "secret" not in request["url"]


def test_selected_cloud_provider_requires_key() -> None:
    try:
        settings("openai", None).validate()
    except ConfigurationError as exc:
        assert "OPENAI_API_KEY" in str(exc)
    else:
        raise AssertionError("Expected missing credential to fail")

