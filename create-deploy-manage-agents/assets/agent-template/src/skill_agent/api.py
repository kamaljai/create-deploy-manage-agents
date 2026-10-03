"""FastAPI transport."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import FastAPI, HTTPException

from .config import ConfigurationError, Settings
from .providers import HttpModelGateway, ModelGateway, ModelProviderError
from .schemas import HealthResponse, InvokeRequest, InvokeResponse
from .service import AgentService


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in ("job_id", "provider", "model", "duration_ms", "outcome"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload, separators=(",", ":"))


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


def create_app(
    settings: Settings | None = None, gateway: ModelGateway | None = None
) -> FastAPI:
    runtime_settings = settings or Settings.from_env()
    configure_logging(runtime_settings.log_level)
    service = AgentService(runtime_settings, gateway or HttpModelGateway(runtime_settings))
    app = FastAPI(title="__AGENT_NAME__", version="0.1.0")
    logger = logging.getLogger("skill_agent")

    @app.get("/healthz", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.get("/readyz", response_model=HealthResponse)
    async def ready() -> HealthResponse:
        try:
            runtime_settings.validate()
        except ConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return HealthResponse(status="ready")

    @app.post("/v1/invoke", response_model=InvokeResponse)
    async def invoke(request: InvokeRequest) -> InvokeResponse:
        try:
            response = await service.invoke(request)
        except ConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ModelProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        logger.info(
            "agent invocation completed",
            extra={
                "job_id": response.job_id,
                "provider": response.provider,
                "model": response.model,
                "duration_ms": response.duration_ms,
                "outcome": "succeeded",
            },
        )
        return response

    return app


app = create_app()
