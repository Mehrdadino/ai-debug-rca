"""Normalize validated traces: defaults, ordering hints (no heavy transforms in v1)."""

from __future__ import annotations

from datetime import timezone

from app.models.trace import Trace


def normalize_trace(trace: Trace) -> Trace:
    """Return a copy-safe normalized trace (UTC normalization, schema defaults)."""
    data = trace.model_dump(mode="json")
    # Re-parse ensures consistent serialization and TZ handling
    t = Trace.model_validate(data)
    # Normalize datetimes to UTC for storage
    started = t.started_at.astimezone(timezone.utc)
    ended = t.ended_at.astimezone(timezone.utc) if t.ended_at else None
    return t.model_copy(update={"started_at": started, "ended_at": ended})
