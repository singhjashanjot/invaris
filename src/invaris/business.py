"""Business-plan assumptions assembled from measured attempts and labeled inputs."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from .evaluation import EvaluationRun, summarize_runs


def build_business_assumptions(
    runs: Iterable[EvaluationRun | Mapping[str, Any]],
    assumptions: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Separate measured inference evidence from commercial planning assumptions.

    This helper does not generate or imply a cfo.ai export. Commercial fields are
    user-supplied hypotheses and remain unset when not supplied.
    """
    run_list = list(runs)
    summary = summarize_runs(run_list)
    supplied = dict(assumptions or {})
    measured = {
        "attempt_count": summary["attempts"],
        "valid_attempt_count": summary["valid_runs"],
        "input_tokens": summary["input_tokens"],
        "output_tokens": summary["output_tokens"],
        "cache_tokens": summary["cache_tokens"],
        "estimated_inference_cost": summary["estimated_cost"],
        "billed_inference_cost": summary["billed_cost"],
        "wall_time_seconds": summary["wall_time_seconds"],
        "recovery_input_tokens": summary["recovery_input_tokens"],
        "recovery_output_tokens": summary["recovery_output_tokens"],
        "recovery_estimated_cost": summary["recovery_estimated_cost"],
        "recovery_billed_cost": summary["recovery_billed_cost"],
        "recovery_wall_time_seconds": summary["recovery_wall_time_seconds"],
        "cost_per_verified_migration": summary["cost_per_verified_migration"],
        "verified_migrations": summary["verified_migrations"],
        "cost_note": "Use billed cost when present; estimates are model/accounting estimates, not invoices.",
    }
    commercial_fields = (
        "pricing", "included_verification_allowance", "extra_usage_price", "customers",
        "migrations_per_customer", "conversion_rate", "churn_rate", "human_review_cost",
        "onboarding_cost", "adapter_upkeep_cost", "support_cost", "sales_acquisition_cost",
        "fixed_expenses", "storage_cost", "scenario_assumptions",
    )
    commercial = {key: supplied.get(key) for key in commercial_fields}
    return {
        "artifact_type": "business_assumptions_template",
        "actual_cfo_export": False,
        "measured_attempt_costs": measured,
        "commercial_assumptions": commercial,
        "assumptions_label": "User-supplied planning assumptions; unprovided values are not fabricated.",
        "scenarios": {key: supplied.get(key) for key in ("base_case", "high_retry_high_support", "slower_sales")},
    }
