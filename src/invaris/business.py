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
    arms: dict[str, list[EvaluationRun | Mapping[str, Any]]] = {}
    for run in run_list:
        version = run.version if isinstance(run, EvaluationRun) else run.get("version")
        label = str(version) if version is not None else "unknown"
        arms.setdefault(label, []).append(run)

    summary_fields = (
        "attempts", "valid_runs", "input_tokens", "output_tokens", "cache_tokens",
        "estimated_cost", "billed_cost", "model_calls", "tool_calls",
        "cost_per_verified_migration", "cost_denominator", "verified_migrations",
        "recovery_input_tokens", "recovery_output_tokens", "recovery_estimated_cost",
        "recovery_billed_cost",
    )

    def measured_summary(rows: Iterable[EvaluationRun | Mapping[str, Any]]) -> dict[str, Any]:
        aggregate = summarize_runs(rows)
        return {field: aggregate[field] for field in summary_fields}

    live_v2_runs = [
        run for run in run_list
        if (run.version if isinstance(run, EvaluationRun) else run.get("version")) == "V2"
        and isinstance(run.metadata if isinstance(run, EvaluationRun) else run.get("metadata"), Mapping)
        and (run.metadata if isinstance(run, EvaluationRun) else run.get("metadata")).get("mode") == "live-model"
    ]
    live_summary = measured_summary(live_v2_runs)
    product_reference = {
        "available": bool(live_v2_runs),
        "workload_size": live_summary["attempts"],
        "verified_migrations": live_summary["verified_migrations"],
        "verified_migration_denominator": live_summary["cost_denominator"],
        **{field: live_summary[field] for field in summary_fields if field not in {
            "attempts", "verified_migrations", "cost_denominator",
        }},
        "attempt_retention_note": "All matching attempts remain in cost and token totals, including failed, blocked, and no-op attempts.",
        "cost_distinction_note": "Estimated inference cost is an estimate; billed inference cost is reported separately when available. Cost per verified migration uses billed cost when present and estimated cost otherwise.",
        "scope_note": "Inference cost is not all delivery COGS; delivery, review, onboarding, support, and other operating costs are separate.",
    }
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
        "measured_attempt_costs_label": "Evaluation aggregate across all supplied rows; not a product unit cost.",
        "measured_costs_by_arm": {arm: measured_summary(rows) for arm, rows in arms.items()},
        "product_inference_reference": product_reference,
        "commercial_assumptions": commercial,
        "assumptions_label": "User-supplied planning assumptions; unprovided values are not fabricated.",
        "scenarios": {key: supplied.get(key) for key in ("base_case", "high_retry_high_support", "slower_sales")},
    }
