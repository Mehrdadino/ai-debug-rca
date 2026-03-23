from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from threading import Lock
from time import monotonic

from app.config import settings
from app.repositories.tenant_limits import TenantLimits


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int = 0
    reason: str = "ok"


class TenantIngestLimiter:
    """In-process best-effort limiter for per-tenant ingest controls."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._rps_events: dict[str, deque[float]] = defaultdict(deque)
        self._daily_counts: dict[str, tuple[date, int]] = {}

    def reset(self) -> None:
        with self._lock:
            self._rps_events.clear()
            self._daily_counts.clear()

    def check_and_consume(
        self,
        tenant_id: str,
        traces: int,
        *,
        rps_limit: int,
        daily_quota: int,
    ) -> RateLimitResult:
        with self._lock:
            if rps_limit > 0:
                now = monotonic()
                q = self._rps_events[tenant_id]
                while q and now - q[0] >= 1.0:
                    q.popleft()
                if len(q) >= rps_limit:
                    retry = max(1, int(1.0 - (now - q[0])) + 1)
                    return RateLimitResult(
                        allowed=False,
                        retry_after_seconds=retry,
                        reason="rps_limit_exceeded",
                    )
                q.append(now)

            if daily_quota > 0:
                today = datetime.now(timezone.utc).date()
                current_day, current_count = self._daily_counts.get(tenant_id, (today, 0))
                if current_day != today:
                    current_count = 0
                if current_count + traces > daily_quota:
                    return RateLimitResult(
                        allowed=False,
                        retry_after_seconds=self._seconds_until_utc_day_end(),
                        reason="daily_trace_quota_exceeded",
                    )
                self._daily_counts[tenant_id] = (today, current_count + traces)

        return RateLimitResult(allowed=True)

    @staticmethod
    def _seconds_until_utc_day_end() -> int:
        now = datetime.now(timezone.utc)
        tomorrow = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) + timedelta(days=1)
        return max(1, int((tomorrow - now).total_seconds()))


def resolve_effective_limits(override: TenantLimits | None) -> TenantLimits:
    """Use per-tenant override when present; otherwise fall back to global settings."""
    if override is not None:
        return override
    return TenantLimits(
        ingest_rate_limit_rps=max(0, settings.ingest_rate_limit_rps),
        ingest_daily_trace_quota=max(0, settings.ingest_daily_trace_quota),
    )

tenant_ingest_limiter = TenantIngestLimiter()
