from invaris.evaluation import EvaluationRun, compare_runs
from invaris.report import render_comparison_report, render_report


def test_report_escapes_all_untrusted_content_and_has_no_script():
    markup = render_report({"rows": []},
                           [{"scenario_id": "</td><script>alert(1)</script><img src=x onerror=alert(1)>"}],
                           title="<b>report</b>")
    assert "<script>" not in markup
    assert "&lt;script&gt;" in markup
    assert "&lt;img" in markup
    assert "&lt;b&gt;report" in markup


def test_comparison_report_is_dark_responsive_comparison_and_offline():
    first = EvaluationRun("r1", "wrong_active_group", "V1", "verified", verified=True,
                          evaluator_status="verified", estimated_cost=1)
    second = EvaluationRun("r2", "wrong_active_group", "V2", "verified", verified=True,
                           evaluator_status="verified", billed_cost=2)
    comparison = compare_runs([first], [second])
    markup = render_comparison_report(comparison)
    assert "Run mode: offline" in markup
    assert ".compare{" in markup and "@media" in markup
    assert "V1" in markup and "V2" in markup
    assert "Fixed script" in markup
    assert "<script" not in markup
    assert "https://" not in markup


def test_comparison_report_escapes_labels_mode_and_verdict_fields():
    malicious = {
        "mode": "live<script>alert(1)</script>",
        "labels": ["<svg/onload=alert(1)>"] ,
        "summaries": {"<svg/onload=alert(1)>": {"rows": [{"scenario_id": "<img src=x>",
                     "status": "<script>bad</script>", "evaluator_status": "<b>unknown</b>",
                     "verified": False, "outcome_correct": False}]}},
        "matched_control_mismatches": 0,
    }
    markup = render_comparison_report(malicious)
    assert "<script" not in markup and "<svg" not in markup and "<img" not in markup
    assert "&lt;script&gt;" in markup and "&lt;svg" in markup and "&lt;img" in markup


def test_report_distinguishes_model_claim_from_agent_status_and_retains_denominators():
    summary = {"correct_outcomes": 0, "outcome_denominator": 1, "rows": [
        {"scenario_id": "wrong_active_group", "status": "UNVERIFIED", "claims_readiness": True, "evaluator_status": "FAILED", "outcome_correct": False}
    ]}
    markup = render_report(summary)
    assert "Agent status" in markup and "Readiness claim" in markup
    assert "Evaluated runs" in markup
    assert "<td>UNVERIFIED</td><td>True</td>" in markup
