from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    """Single piece of support for a hypothesis (rule hit)."""

    rule_id: str = Field(..., description="Stable id of the rule that fired")
    step_id: Optional[str] = Field(None, description="Relevant step, if any")
    message: str = Field(..., description="Human-readable explanation")


class Diagnosis(BaseModel):
    """Structured diagnosis (hypotheses, not oracle truth)."""

    schema_version: str = "1.0"
    trace_id: UUID
    primary_hypothesis: str = Field(
        ...,
        description="Rule id for the ranked primary explanation (e.g. step_error)",
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: List[EvidenceItem] = Field(default_factory=list)
    secondary_hypotheses: List[str] = Field(
        default_factory=list,
        description="Other rule ids that fired, lower priority",
    )
