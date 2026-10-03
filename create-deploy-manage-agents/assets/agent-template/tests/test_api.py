from __future__ import annotations

from fastapi.testclient import TestClient

from skill_agent.api import create_app
from skill_agent.config import Settings
from skill_agent.providers import ModelResult


class FakeGateway:
    async def complete(self, *, system_prompt: str, user_prompt: str) -> ModelResult:
        return ModelResult(text="ok")


def test_health_and_invoke() -> None:
    settings = Settings(
        provider="ollama",
        model="test-model",
        api_key=None,
        base_url="http://ollama.test",
    )
    client = TestClient(create_app(settings, FakeGateway()))
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json() == {"status": "ready"}
    response = client.post("/v1/invoke", json={"input": {"message": "hello"}})
    assert response.status_code == 200
    assert response.json()["output"] == "ok"

