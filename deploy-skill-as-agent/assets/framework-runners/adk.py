"""Run a packaged Google ADK agent for one request. Replace AgentService's model call with this."""

from __future__ import annotations

import importlib
import json
import os
from typing import Any

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types


class FrameworkRunner:
    def __init__(self) -> None:
        # Module that exposes `root_agent`, e.g. "my_agent.agent".
        module = importlib.import_module(os.environ["AGENT_MODULE"])
        self.app_name = os.getenv("AGENT_APP_NAME", "__AGENT_SLUG__")
        # In-memory sessions are per process. Swap for DatabaseSessionService(db_url=...)
        # or VertexAiSessionService when the contract needs sessions across requests.
        self.sessions = InMemorySessionService()
        self.runner = Runner(
            agent=module.root_agent, app_name=self.app_name, session_service=self.sessions
        )

    async def run(self, payload: Any, *, user_id: str = "api") -> str:
        session = await self.sessions.create_session(app_name=self.app_name, user_id=user_id)
        text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        message = types.Content(role="user", parts=[types.Part(text=text)])
        final = ""
        async for event in self.runner.run_async(
            user_id=user_id, session_id=session.id, new_message=message
        ):
            if event.is_final_response() and event.content and event.content.parts:
                final = "".join(part.text or "" for part in event.content.parts)
        return final
