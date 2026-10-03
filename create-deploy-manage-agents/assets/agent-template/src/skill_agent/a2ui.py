"""A2UI v0.9 task surface: render a form for the agent and run tasks from user actions.

The server builds every component from a fixed template with the basic catalog, so the model
never authors UI. User actions are untrusted input and go through the same request validation
as POST /v1/invoke.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

from .schemas import InvokeRequest
from .service import AgentService

VERSION = "v0.9"
CATALOG_ID = "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"
SURFACE_ID = "agent_task"
RUN_ACTION = "run_task"
MAX_CONTEXT_CHARS = 200_000
logger = logging.getLogger("skill_agent.a2ui")


@dataclass(frozen=True, slots=True)
class FormField:
    """One input on the task form. `variant` is a basic-catalog TextField variant."""

    name: str
    label: str
    variant: str = "shortText"


# Replace with one field per property of the agreed request contract. A single field named
# "input" is sent as InvokeRequest.input (parsed as JSON when it is valid JSON).
FORM_FIELDS: tuple[FormField, ...] = (FormField("input", "Input", "longText"),)


class ActionEvent(BaseModel):
    name: str
    surfaceId: str  # noqa: N815 - A2UI wire names
    sourceComponentId: str  # noqa: N815
    timestamp: str
    context: dict[str, Any] = {}


class ClientMessage(BaseModel):
    version: str
    action: ActionEvent


def _message(kind: str, body: dict[str, Any]) -> dict[str, Any]:
    return {"version": VERSION, kind: {"surfaceId": SURFACE_ID, **body}}


def _set(path: str, value: Any) -> dict[str, Any]:
    return _message("updateDataModel", {"path": path, "value": value})


def surface_messages(title: str) -> list[dict[str, Any]]:
    """Messages that create the task surface and its initial data model."""
    field_ids = [f"field_{field.name}" for field in FORM_FIELDS]
    components: list[dict[str, Any]] = [
        {
            "id": "root",
            "component": "Column",
            "children": ["title", *field_ids, "run_button", "divider", "status", "result"],
        },
        {"id": "title", "component": "Text", "text": title, "variant": "h2"},
        *(
            {
                "id": f"field_{field.name}",
                "component": "TextField",
                "label": field.label,
                "value": {"path": f"/input/{field.name}"},
                "variant": field.variant,
            }
            for field in FORM_FIELDS
        ),
        {
            "id": "run_button",
            "component": "Button",
            "child": "run_label",
            "variant": "primary",
            "action": {
                "event": {
                    "name": RUN_ACTION,
                    "context": {
                        field.name: {"path": f"/input/{field.name}"} for field in FORM_FIELDS
                    },
                }
            },
        },
        {"id": "run_label", "component": "Text", "text": "Run task"},
        {"id": "divider", "component": "Divider"},
        {"id": "status", "component": "Text", "text": {"path": "/status"}, "variant": "caption"},
        {"id": "result", "component": "Text", "text": {"path": "/result"}},
    ]
    return [
        _message("createSurface", {"catalogId": CATALOG_ID}),
        _message("updateComponents", {"components": components}),
        _set("/", {"input": {f.name: "" for f in FORM_FIELDS}, "status": "Ready", "result": ""}),
    ]


def _request_from_context(context: dict[str, Any]) -> InvokeRequest:
    if len(json.dumps(context, default=str)) > MAX_CONTEXT_CHARS:
        raise ValueError("Form input is too large")
    values = {f.name: context.get(f.name, "") for f in FORM_FIELDS}
    if len(FORM_FIELDS) == 1 and FORM_FIELDS[0].name == "input":
        raw = values["input"]
        try:
            payload: Any = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            payload = raw
    else:
        payload = values
    if payload in ("", None, {}):
        raise ValueError("Enter an input before running the task")
    return InvokeRequest(input=payload, metadata={"channel": "a2ui"})


def _render_output(output: Any) -> str:
    if isinstance(output, str):
        return output
    return "```json\n" + json.dumps(output, indent=2, ensure_ascii=False, default=str) + "\n```"


async def handle_action(message: ClientMessage, service: AgentService) -> AsyncIterator[str]:
    """Yield A2UI messages as JSON lines: a running status first, then the result."""

    def line(payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False) + "\n"

    action = message.action
    if action.surfaceId != SURFACE_ID or action.name != RUN_ACTION:
        yield line(_set("/status", f"Unsupported action: {action.name}"))
        return

    started = datetime.now(UTC).strftime("%H:%M:%S")
    yield line(_set("/status", f"Running (started {started} UTC)…"))
    yield line(_set("/result", ""))
    try:
        response = await service.invoke(_request_from_context(action.context))
    except (ValueError, ValidationError) as exc:
        yield line(_set("/status", f"Invalid input: {exc}"))
        return
    except Exception as exc:  # noqa: BLE001 - show a safe message; details stay in server logs
        logger.exception("a2ui task failed (%s)", type(exc).__name__)
        yield line(_set("/status", "Failed: the agent could not complete this task."))
        return
    yield line(_set("/result", _render_output(response.output)))
    yield line(_set("/status", f"Done in {response.duration_ms} ms · job {response.job_id}"))


def mount_ui(app: FastAPI, service: AgentService, *, title: str) -> None:
    """Add the A2UI endpoints and, when built, the web client at /ui."""

    @app.get("/a2ui/surface")
    async def a2ui_surface() -> list[dict[str, Any]]:
        return surface_messages(title)

    @app.post("/a2ui/action")
    async def a2ui_action(message: ClientMessage) -> StreamingResponse:
        return StreamingResponse(handle_action(message, service), media_type="application/jsonl")

    dist = Path(os.getenv("UI_DIST", str(Path(__file__).resolve().parents[2] / "ui" / "dist")))
    if dist.is_dir():
        app.mount("/ui/assets", StaticFiles(directory=dist / "assets"), name="ui-assets")

        @app.get("/ui", include_in_schema=False)
        async def ui() -> FileResponse:
            return FileResponse(dist / "index.html")
