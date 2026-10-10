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
