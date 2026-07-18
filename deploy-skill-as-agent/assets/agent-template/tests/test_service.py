from __future__ import annotations

import asyncio

from skill_agent.config import Settings
from skill_agent.providers import ModelResult
from skill_agent.schemas import InvokeRequest
from skill_agent.service import AgentService


class FakeGateway:
    def __init__(self, text: str = "done") -> None:
        self.text = text
        self.user_prompt = ""

    async def complete(self, *, system_prompt: str, user_prompt: str) -> ModelResult:
        assert "Packaged skill file: SKILL.md" in system_prompt
        self.user_prompt = user_prompt
        return ModelResult(text=self.text, usage={"output_tokens": 1})


def settings() -> Settings:
    return Settings(
        provider="ollama",
        model="test-model",
        api_key=None,
        base_url="http://ollama.test",
        max_input_chars=100,
    )


def test_invoke_uses_fake_gateway() -> None:
    gateway = FakeGateway("expected")
    response = asyncio.run(AgentService(settings(), gateway).invoke(InvokeRequest(input="hello")))
    assert response.output == "expected"
    assert response.provider == "ollama"
    assert "hello" in gateway.user_prompt


def test_rejects_oversized_input() -> None:
    service = AgentService(settings(), FakeGateway())
    try:
        asyncio.run(service.invoke(InvokeRequest(input="x" * 101)))
    except ValueError as exc:
        assert "exceeds" in str(exc)
    else:
        raise AssertionError("Expected oversized input to fail")

