"""Command-line transport."""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from .config import Settings
from .providers import HttpModelGateway
from .schemas import InvokeRequest
from .service import AgentService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run __AGENT_NAME__ once")
    parser.add_argument("--input", required=True, help="JSON value or plain text")
    return parser.parse_args()


def parse_input(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


async def run(raw_input: str) -> None:
    settings = Settings.from_env()
    settings.validate()
    service = AgentService(settings, HttpModelGateway(settings))
    response = await service.invoke(InvokeRequest(input=parse_input(raw_input)))
    print(response.model_dump_json(indent=2))


def main() -> None:
    args = parse_args()
    asyncio.run(run(args.input))


if __name__ == "__main__":
    main()

