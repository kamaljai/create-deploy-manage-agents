"""Transport models. Replace generic fields with the agreed deployment contract."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class InvokeRequest(BaseModel):
    input: Any = Field(description="__INPUT_DESCRIPTION__")
    metadata: dict[str, str] = Field(default_factory=dict)


class InvokeResponse(BaseModel):
    job_id: str
    output: Any = Field(description="__OUTPUT_DESCRIPTION__")
    provider: str
    model: str
    duration_ms: int
    usage: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str
