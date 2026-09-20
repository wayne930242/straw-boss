"""Shared benchmark fields with explicit copied-resume measurement semantics."""
from __future__ import annotations

from straw_boss.jev_codex import measurement
from straw_boss.jev_storage import criteria_version


def benchmark_record(run_id: str, criteria: dict, policy: dict, decisions: list[dict],
                     *, source: dict, request_metrics: list[dict],
                     before: dict | None = None, after: dict | None = None,
                     context_window: int | None = None) -> dict:
    gate = {"tokens_before": None, "tokens_after": None, "reduction_pct": None,
            "gate_reduction_pct": None, "decision": "fallback",
            "fallback_reason": "backend-measurement-unavailable"}
    if before is not None and after is not None:
        gate = measurement(before, after, policy)
    models = sorted({item["model"] for item in request_metrics})
    return {
        "schema_version": 2, "provider": "codex", "run_id": run_id,
        "trigger": "manual-copied-history-replay", "context_window": context_window,
        "criteria_version": criteria_version(criteria), "policy_version": criteria_version(policy),
        "policy": policy, "decisions": decisions, **gate,
        "jev": {"model": models[0] if len(models) == 1 else models or None,
                "requests": len(request_metrics),
                "input_tokens": sum(item["input_tokens"] for item in request_metrics),
                "latency_ms": sum(item["latency_ms"] for item in request_metrics),
                "request_metrics": request_metrics},
        "source": source,
        "measurement": {
            "source": "codex-resume-token-count" if before is not None and after is not None else None,
            "backend_model": "gpt-6-astra" if before is not None and after is not None else None,
            "effort": "low" if before is not None and after is not None else None,
            "cache_hits_before": before.get("cached_input_tokens") if before else None,
            "cache_hits_after": after.get("cached_input_tokens") if after else None,
            "tokens_after_semantics": "candidate-copy-resume-input; independent of gate selection",
            "candidate_resume_usage": after, "baseline_resume_usage": before,
            "actual_session_tokens_after": None,
            "fallback_usage": None,
            "gate_execution": "offline-candidate-decision; built-in fallback not invoked",
            "latency_definition": "sum of individual Jev HTTP request elapsed milliseconds; wall time recorded separately",
        },
        "byte_measurement": "UTF-8 canonical JSON of invocation id/tool/input and one result id/text/isError; excludes duplicated host metadata and image bytes.",
        "outcome": None,
        "application": {"status": "diagnostic-copy-only", "live_application_supported": False,
                        "provider_gap": "Codex 0.155.1 exposes no live replacement-history hook output"},
        "qualitative_outcome": {"status": "not-assessed", "findings": []},
    }
