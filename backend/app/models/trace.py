from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class TraceStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"


class StepType(str, Enum):
    RETRIEVAL = "retrieval"
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    TRANSFORM = "transform"
    ROUTING = "routing"
    EMBEDDING = "embedding"
    GUARDRAIL = "guardrail"
    OTHER = "other"


class CorrelationIds(BaseModel):
    upstream_provider: Optional[str] = None
    upstream_trace_id: Optional[str] = None
    session_id: Optional[str] = None


class Step(BaseModel):
    step_id: str = Field(..., min_length=1, max_length=256)
    type: StepType
    parent_step_id: Optional[str] = None
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    span_id: Optional[str] = None
    traceparent: Optional[str] = None


class Edge(BaseModel):
    from_step_id: str = Field(..., min_length=1)
    to_step_id: str = Field(..., min_length=1)


class Trace(BaseModel):
    """Canonical execution graph (schema v1)."""

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    trace_id: UUID
    tenant_id: str = Field(..., min_length=1, max_length=256)
    started_at: datetime
    ended_at: Optional[datetime] = None
    status: TraceStatus
    correlation_ids: Optional[CorrelationIds] = None
    steps: list[Step] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)

    @field_validator("started_at", "ended_at", mode="after")
    @classmethod
    def coerce_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_graph(self) -> Trace:
        step_ids = [s.step_id for s in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("steps: step_id values must be unique")

        id_set = set(step_ids)
        for s in self.steps:
            if s.parent_step_id is not None and s.parent_step_id not in id_set:
                raise ValueError(
                    f"steps: parent_step_id {s.parent_step_id!r} not found for step {s.step_id!r}"
                )

        for e in self.edges:
            if e.from_step_id not in id_set or e.to_step_id not in id_set:
                raise ValueError(
                    f"edges: unknown step reference in {e.from_step_id!r} -> {e.to_step_id!r}"
                )

        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("ended_at must be >= started_at")

        return self
