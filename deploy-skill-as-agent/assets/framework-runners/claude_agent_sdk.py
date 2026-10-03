"""Run a packaged Claude Agent SDK agent for one request. Replace AgentService's model call."""

from __future__ import annotations

import importlib
import json
import os
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query


def load_options() -> ClaudeAgentOptions:
    # "package.module:factory" returning the source agent's ClaudeAgentOptions.
    module_name, _, factory = os.environ["AGENT_OPTIONS_FACTORY"].partition(":")
    options: ClaudeAgentOptions = getattr(importlib.import_module(module_name), factory)()
    # Container guardrails: fixed writable workdir and bounded turns. Keep the source
    # agent's allowed_tools list; never widen it or use permission_mode="bypassPermissions"
    # with Bash/Write unless the user approved it for an isolated (microVM) runtime.
    options.cwd = os.getenv("AGENT_WORKDIR", "/tmp/agent-work")
    options.max_turns = options.max_turns or int(os.getenv("AGENT_MAX_TURNS", "20"))
    return options


class FrameworkRunner:
    def __init__(self) -> None:
        self.options = load_options()

    async def run(self, payload: Any) -> str:
        os.makedirs(self.options.cwd, exist_ok=True)
        prompt = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        result: ResultMessage | None = None
        async for message in query(prompt=prompt, options=self.options):
            if isinstance(message, ResultMessage):
                result = message
        if result is None or result.is_error:
            raise RuntimeError("Agent run did not complete successfully")
        return result.result or ""
