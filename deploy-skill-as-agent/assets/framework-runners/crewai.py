"""Run a packaged CrewAI crew for one request. Replace AgentService's model call with this."""

from __future__ import annotations

import importlib
import os
from typing import Any

from starlette.concurrency import run_in_threadpool


class FrameworkRunner:
    def __init__(self) -> None:
        # "package.module:CrewClass" for a @CrewBase class, e.g. "my_crew.crew:MyCrew".
        module_name, _, class_name = os.environ["CREW_CLASS"].partition(":")
        self.crew_class = getattr(importlib.import_module(module_name), class_name)

    async def run(self, payload: Any) -> str:
        if not isinstance(payload, dict):
            raise ValueError("CrewAI kickoff inputs must be a JSON object")
        # Build a fresh crew per request; crews hold per-run state. kickoff() blocks,
        # so keep it off the event loop.
        result = await run_in_threadpool(
            lambda: self.crew_class().crew().kickoff(inputs=payload)
        )
        return result.raw
