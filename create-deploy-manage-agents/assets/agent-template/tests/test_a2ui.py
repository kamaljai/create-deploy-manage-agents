from __future__ import annotations

import json

from fastapi.testclient import TestClient

from skill_agent import a2ui
from skill_agent.api import create_app
from skill_agent.config import Settings
from skill_agent.providers import ModelResult


class FakeGateway:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def complete(self, *, system_prompt: str, user_prompt: str) -> ModelResult:
        self.prompts.append(user_prompt)
        return ModelResult(text="task done")


def make_client(gateway: FakeGateway) -> TestClient:
    settings = Settings(provider="ollama", model="m", api_key=None, base_url="http://o.test")
    return TestClient(create_app(settings, gateway))


def action(context: dict[str, object], name: str = a2ui.RUN_ACTION) -> dict[str, object]:
    return {
        "version": a2ui.VERSION,
        "action": {
            "name": name,
            "surfaceId": a2ui.SURFACE_ID,
            "sourceComponentId": "run_button",
            "timestamp": "2026-01-01T00:00:00Z",
            "context": context,
        },
    }


def data_updates(body: str) -> dict[str, object]:
    updates: dict[str, object] = {}
    for line in body.splitlines():
        message = json.loads(line)
        assert message["version"] == a2ui.VERSION
        update = message["updateDataModel"]
        updates[update["path"]] = update["value"]
    return updates


def test_surface_has_root_form_and_run_action() -> None:
    messages = make_client(FakeGateway()).get("/a2ui/surface").json()
    assert [next(k for k in m if k != "version") for m in messages] == [
        "createSurface",
        "updateComponents",
        "updateDataModel",
    ]
    assert messages[0]["createSurface"]["catalogId"] == a2ui.CATALOG_ID
    components = {c["id"]: c for c in messages[1]["updateComponents"]["components"]}
    assert components["root"]["component"] == "Column"
    for child in components["root"]["children"]:
        assert child in components
    assert components["run_button"]["action"]["event"]["name"] == a2ui.RUN_ACTION


def test_run_action_streams_status_then_result() -> None:
    gateway = FakeGateway()
    response = make_client(gateway).post("/a2ui/action", json=action({"input": '{"q": 1}'}))
    assert response.status_code == 200
    updates = data_updates(response.text)
    assert updates["/result"] == "task done"
    assert str(updates["/status"]).startswith("Done")
    assert '"q": 1' in gateway.prompts[0]


def test_empty_input_and_unknown_action_do_not_call_agent() -> None:
    gateway = FakeGateway()
    client = make_client(gateway)
    empty = data_updates(client.post("/a2ui/action", json=action({"input": ""})).text)
    assert str(empty["/status"]).startswith("Invalid input")
    unknown = data_updates(client.post("/a2ui/action", json=action({}, name="drop_db")).text)
    assert "Unsupported action" in str(unknown["/status"])
    assert gateway.prompts == []
