from invaris.business import build_business_assumptions
from invaris.evaluation import EvaluationRun


def test_measured_costs_and_unprovided_business_assumptions_stay_separate():
    artifact = build_business_assumptions([
        EvaluationRun("r1", "wrong_active_group", "V2", "verified", input_tokens=100,
                      output_tokens=20, estimated_cost=0.12, duration_seconds=5),
    ], {"pricing": "hypothesis: $X"})
    assert artifact["measured_attempt_costs"]["input_tokens"] == 100
    assert artifact["commercial_assumptions"]["pricing"] == "hypothesis: $X"
    assert artifact["commercial_assumptions"]["customers"] is None
    assert artifact["actual_cfo_export"] is False


def test_product_reference_uses_only_explicit_live_v2_attempts():
    artifact = build_business_assumptions([
        EvaluationRun("live-ok", "wrong_active_group", "V2", "verified", verified=True,
                      input_tokens=100, estimated_cost=1.0, billed_cost=0.8,
                      metadata={"mode": "live-model"}),
        EvaluationRun("live-failed", "impossible_client_requirement", "V2", "blocked",
                      input_tokens=20, estimated_cost=0.2, metadata={"mode": "live-model"}),
        EvaluationRun("live-noop", "already_compliant", "V2", "verified", verified=True,
                      input_tokens=10, estimated_cost=0.1, metadata={"mode": "live-model"}),
        EvaluationRun("script", "wrong_active_group", "Fixed script", "verified",
                      verified=True, input_tokens=900, estimated_cost=9.0,
                      metadata={"mode": "offline-smoke-not-LLM"}),
        EvaluationRun("unknown-mode", "wrong_active_group", "V2", "verified",
                      verified=True, input_tokens=500, estimated_cost=5.0),
    ])

    reference = artifact["product_inference_reference"]
    assert artifact["measured_attempt_costs"]["input_tokens"] == 1530
    assert artifact["measured_attempt_costs_label"].startswith("Evaluation aggregate")
    assert artifact["measured_costs_by_arm"]["Fixed script"]["attempts"] == 1
    assert reference["available"] is True
    assert reference["workload_size"] == 3
    assert reference["input_tokens"] == 130
    assert reference["estimated_cost"] == 1.3
    assert reference["billed_cost"] == 0.8
    assert reference["verified_migrations"] == 1
    assert reference["verified_migration_denominator"] == 1
    assert "failed, blocked, and no-op" in reference["attempt_retention_note"]
    assert "not all delivery COGS" in reference["scope_note"]


def test_product_reference_is_unavailable_without_explicit_live_v2_rows():
    artifact = build_business_assumptions([
        EvaluationRun("unknown", "wrong_active_group", "V2", "verified",
                      input_tokens=10, estimated_cost=1.0),
        EvaluationRun("script", "wrong_active_group", "V1", "verified",
                      input_tokens=20, estimated_cost=2.0,
                      metadata={"mode": "offline"}),
    ])

    reference = artifact["product_inference_reference"]
    assert reference["available"] is False
    assert reference["workload_size"] == 0
    assert reference["estimated_cost"] is None
    assert reference["billed_cost"] is None
    assert reference["input_tokens"] is None
