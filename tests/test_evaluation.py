from invaris.evaluation import (
    SCENARIOS,
    EvaluationRun,
    compare_runs,
    evaluate_run,
    summarize_runs,
    write_csv,
    write_json,
)


def test_scenario_scoring_and_false_readiness():
    assert evaluate_run(EvaluationRun("a", "wrong_active_group", "V2", "verified", verified=True,
                                     evaluator_status="verified", claims_readiness=True))["outcome_correct"]
    scored = evaluate_run(EvaluationRun("b", "impossible_client_requirement", "V2", "verified",
                                         evaluator_status="blocked", policy_conflict_evidence=True))
    assert scored["false_readiness"]
    assert not scored["outcome_correct"]


def test_model_claim_alone_cannot_pass_and_unknown_scenario_is_unscored():
    claim_only = evaluate_run(EvaluationRun("a", "wrong_active_group", "V2", "verified"))
    unknown = evaluate_run(EvaluationRun("b", "invented_case", "V2", "verified", verified=True,
                                         evaluator_status="verified"))
    assert not claim_only["outcome_correct"]
    assert claim_only["false_readiness"]
    assert not unknown["outcome_correct"]
    assert not unknown["scenario_known"]
    assert "held_out_config" in SCENARIOS
    verifier_only = evaluate_run(EvaluationRun("c", "wrong_active_group", "V2", "unverified",
                                               verified=True, evaluator_status="verified"))
    assert not verifier_only["outcome_correct"]


def test_blocker_requires_trusted_conflict_evidence():
    no_evidence = evaluate_run(EvaluationRun("a", "impossible_client_requirement", "V2", "blocked",
                                             evaluator_status="blocked"))
    assert not no_evidence["outcome_correct"]
    assert not no_evidence["correct_blocker"]
    proven = evaluate_run(EvaluationRun("b", "impossible_client_requirement", "V2", "blocked",
                                        evaluator_status="blocked", policy_conflict_evidence=True))
    assert proven["outcome_correct"] and proven["correct_blocker"]


def test_missing_probe_requires_agent_unverified_and_no_readiness_claim():
    withheld = evaluate_run(EvaluationRun("a", "missing_probe_evidence", "V2", "unverified",
                                          evaluator_status="unverified", verified=False))
    false_ready = evaluate_run(EvaluationRun("b", "missing_probe_evidence", "V2", "unverified",
                                             evaluator_status="unverified", claims_readiness=True))
    assert withheld["outcome_correct"]
    assert not false_ready["outcome_correct"]
    assert false_ready["false_readiness"]


def test_summary_keeps_invalid_attempts_and_undefined_cost_denominator():
    rows = [
        EvaluationRun("a", "wrong_active_group", "V1", "verified", estimated_cost=3,
                      verified=True, evaluator_status="verified"),
        EvaluationRun("b", "one_shot_action_failure", "V1", "failed", infrastructure_valid=False,
                      recovery_attempted=True, recovery_input_tokens=9, recovery_billed_cost=0.2,
                      recovery_duration_seconds=2),
    ]
    summary = summarize_runs(rows)
    assert summary["attempts"] == 2
    assert summary["infrastructure_invalid_runs"] == 1
    assert summary["outcome_denominator"] == 1
    assert summary["attempts"] == 2
    assert summary["cost_per_verified_migration"] == 3
    assert summary["recovery_input_tokens"] == 9
    assert summary["recovery_billed_cost"] == 0.2
    assert summary["recovery_wall_time_seconds"] == 2
    assert summarize_runs([])["cost_per_verified_migration"] is None


def test_verified_migrations_normalize_cli_status_and_exclude_noops():
    rows = [
        EvaluationRun("a", "wrong_active_group", "V2", "VERIFIED", estimated_cost=4,
                      verified=True, evaluator_status="VERIFIED"),
        EvaluationRun("b", "already_compliant", "V2", "VERIFIED", estimated_cost=2,
                      verified=True, evaluator_status="VERIFIED"),
    ]
    summary = summarize_runs(rows)
    assert summary["verified_migrations"] == 1
    assert summary["migration_feasible_runs"] == 1
    assert summary["cost_denominator"] == 1
    assert summary["cost_per_verified_migration"] == 6
    assert summary["correct_noops"] == 1


def test_noop_with_unnecessary_mutation_is_not_correct_even_when_digest_unchanged():
    unnecessary_mutation = {
        "run_id": "a", "scenario_id": "already_compliant", "version": "V2",
        "status": "VERIFIED", "verified": True, "evaluator_status": "VERIFIED",
        "changed_files": 0, "unnecessary_mutations": 1,
    }
    changed_file = {**unnecessary_mutation, "run_id": "b", "changed_files": 1, "unnecessary_mutations": 0}
    assert not evaluate_run(unnecessary_mutation)["correct_noop"]
    assert not evaluate_run(unnecessary_mutation)["outcome_correct"]
    assert not evaluate_run(changed_file)["correct_noop"]
    assert not evaluate_run(changed_file)["outcome_correct"]
    assert summarize_runs([unnecessary_mutation])["correct_outcomes"] == 0


def test_comparison_checks_controls_and_fixed_label():
    a = EvaluationRun("a", "wrong_active_group", "V1", "verified", "p", "m", "b",
                      verified=True, evaluator_status="verified")
    b = EvaluationRun("b", "wrong_active_group", "V2", "verified", "p", "m", "different",
                      verified=True, evaluator_status="verified")
    comparison = compare_runs([a], [b], [a], mode="offline smoke")
    assert comparison["labels"] == ["V1", "V2", "Fixed script"]
    assert comparison["matched_control_mismatches"] == 1
    assert comparison["mode"] == "offline smoke"


def test_comparison_requires_controls_and_reports_unmatched_attempts():
    missing_controls = EvaluationRun("a", "wrong_active_group", "V1", "verified",
                                     verified=True, evaluator_status="verified")
    identified = EvaluationRun("b", "wrong_active_group", "V2", "verified", "p", "m", "b",
                               verified=True, evaluator_status="verified")
    comparison = compare_runs([missing_controls, missing_controls], [identified])
    assert not comparison["matched"][0]["controls_match"]
    assert comparison["matched_control_mismatches"] == 1
    assert len(comparison["unmatched_attempts"]) == 1
    assert comparison["unmatched_attempts"][0]["scenario_id"] == "wrong_active_group"
    assert comparison["unmatched_attempts"][0]["repetition"] == 2
    assert comparison["unmatched_attempts"][0]["v1"]["run_id"] == "a"
    assert comparison["unmatched_attempts"][0]["v2"] is None


def test_safe_local_json_csv_writers(tmp_path):
    write_json(tmp_path, "runs.json", {"a": 1})
    write_csv(tmp_path, "runs.csv", [{"a": 1, "detail": {"x": 2}}])
    assert '"a": 1' in (tmp_path / "runs.json").read_text()
    assert '""x"": 2' in (tmp_path / "runs.csv").read_text()
    try:
        write_json(tmp_path, "../escape.json", {})
    except ValueError:
        pass
    else:
        raise AssertionError("path traversal must be rejected")
