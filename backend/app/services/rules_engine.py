"""Deterministic rule evaluation over a canonical Trace (v1)."""

from __future__ import annotations

from typing import List, Optional, Tuple

from app.models.diagnosis import Diagnosis, EvidenceItem
from app.models.trace import Trace, TraceStatus

# Higher = more severe for ranking primary hypothesis.
RULE_WEIGHTS: dict[str, int] = {
    "trace_status_error": 100,
    "step_error": 95,
    "empty_tool_output": 78,
    "empty_retrieval": 72,
    "high_latency_llm": 55,
    "trace_status_partial": 45,
}

HIGH_LATENCY_MS = 5_000


def _retrieval_empty(output: dict) -> bool:
    if not output:
        return True
    for key in ("chunks", "documents", "results", "hits", "records"):
        v = output.get(key)
        if v is not None:
            if isinstance(v, list):
                return len(v) == 0
            return False
    # No known list field — treat as unknown, not empty
    return False


def _tool_output_empty(output: dict) -> bool:
    if not output:
        return True
    return all(
        v in (None, "", [], {}) for v in output.values()
    )


def _latency_ms(metadata: dict) -> Optional[int]:
    raw = metadata.get("latency_ms")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _collect_evidence(trace: Trace) -> List[Tuple[str, int, EvidenceItem]]:
    """Returns list of (rule_id, weight, evidence)."""
    out: List[Tuple[str, int, EvidenceItem]] = []

    if trace.status == TraceStatus.ERROR:
        out.append(
            (
                "trace_status_error",
                RULE_WEIGHTS["trace_status_error"],
                EvidenceItem(
                    rule_id="trace_status_error",
                    message="Trace status is error",
                ),
            )
        )
    elif trace.status == TraceStatus.PARTIAL:
        out.append(
            (
                "trace_status_partial",
                RULE_WEIGHTS["trace_status_partial"],
                EvidenceItem(
                    rule_id="trace_status_partial",
                    message="Trace completed with partial status",
                ),
            )
        )

    for step in trace.steps:
        if step.error:
            out.append(
                (
                    "step_error",
                    RULE_WEIGHTS["step_error"],
                    EvidenceItem(
                        rule_id="step_error",
                        step_id=step.step_id,
                        message=f"Step reported error: {step.error[:500]}",
                    ),
                )
            )

        if step.type == "retrieval" and _retrieval_empty(step.output):
            out.append(
                (
                    "empty_retrieval",
                    RULE_WEIGHTS["empty_retrieval"],
                    EvidenceItem(
                        rule_id="empty_retrieval",
                        step_id=step.step_id,
                        message="Retrieval returned no documents/chunks",
                    ),
                )
            )

        if step.type == "tool_call" and _tool_output_empty(step.output):
            out.append(
                (
                    "empty_tool_output",
                    RULE_WEIGHTS["empty_tool_output"],
                    EvidenceItem(
                        rule_id="empty_tool_output",
                        step_id=step.step_id,
                        message="Tool call produced empty output",
                    ),
                )
            )

        if step.type == "llm_call":
            lat = _latency_ms(step.metadata)
            if lat is not None and lat > HIGH_LATENCY_MS:
                out.append(
                    (
                        "high_latency_llm",
                        RULE_WEIGHTS["high_latency_llm"],
                        EvidenceItem(
                            rule_id="high_latency_llm",
                            step_id=step.step_id,
                            message=f"LLM call latency {lat}ms exceeds {HIGH_LATENCY_MS}ms threshold",
                        ),
                    )
                )

    return out


def evaluate_trace(trace: Trace) -> Diagnosis:
    """
    Run all v1 rules; rank primary by weight; confidence derived from primary weight.
    If nothing fired, emit a low-confidence 'no_rules_fired' diagnosis.
    """
    raw = _collect_evidence(trace)
    if not raw:
        return Diagnosis(
            trace_id=trace.trace_id,
            primary_hypothesis="no_rules_fired",
            confidence=0.15,
            evidence=[],
            secondary_hypotheses=[],
        )

    # Sort by weight desc, then stable by step_id for ties
    raw.sort(key=lambda x: (-x[1], x[2].step_id or ""))

    top_w = raw[0][1]
    primary_hypothesis = raw[0][0]
    evidence_list: List[EvidenceItem] = [t[2] for t in raw]

    seen_rules: set[str] = {primary_hypothesis}
    secondary_ids: List[str] = []
    for rule_id, _w, _ev in raw[1:]:
        if rule_id not in seen_rules:
            seen_rules.add(rule_id)
            secondary_ids.append(rule_id)

    max_w = max(RULE_WEIGHTS.values())
    conf = 0.2 + (top_w / max_w) * 0.75
    conf = min(0.95, max(0.2, conf))

    return Diagnosis(
        trace_id=trace.trace_id,
        primary_hypothesis=primary_hypothesis,
        confidence=round(conf, 3),
        evidence=evidence_list,
        secondary_hypotheses=secondary_ids,
    )
