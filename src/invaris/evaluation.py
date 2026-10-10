"""Pure evaluation and comparison helpers for Invaris run records."""

from __future__ import annotations

import csv
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SCENARIOS: dict[str, dict[str, Any]] = {
    "wrong_active_group": {"expected": "verified", "migration_feasible": True},
    "disk_runtime_mismatch": {"expected": "verified", "migration_feasible": True},
    "one_shot_action_failure": {"expected": "verified", "migration_feasible": True},
    "already_compliant": {"expected": "verified", "migration_feasible": True, "noop": True},
    "impossible_client_requirement": {"expected": "blocked", "migration_feasible": False},
    "missing_probe_evidence": {"expected": "unverified", "migration_feasible": None},
    "held_out_config": {"expected": "verified", "migration_feasible": True},
}


@dataclass(frozen=True)
class EvaluationRun:
    run_id: str
    scenario_id: str
    version: str
    status: str
    policy_id: str = ""
    model_id: str = ""
    budget_id: str = ""
    infrastructure_valid: bool = True
    false_readiness: bool = False
    changed_files: int = 0
    recovery_attempted: bool = False
    recovery_succeeded: bool = False
    recovery_input_tokens: int | None = None
    recovery_output_tokens: int | None = None
    recovery_estimated_cost: float | None = None
    recovery_billed_cost: float | None = None
    recovery_duration_seconds: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_tokens: int | None = None
    estimated_cost: float | None = None
    billed_cost: float | None = None
    duration_seconds: float | None = None
    model_calls: int | None = None
    tool_calls: int | None = None
    unnecessary_mutations: int = 0
    metadata: Mapping[str, Any] = field(default_factory=dict)
    verified: bool | None = None
    evaluator_status: str | None = None
    policy_conflict_evidence: bool = False
    claims_readiness: bool = False


def _value(run: EvaluationRun | Mapping[str, Any], name: str, default: Any = None) -> Any:
    return getattr(run, name, run.get(name, default) if isinstance(run, Mapping) else default)


def evaluate_run(run: EvaluationRun | Mapping[str, Any], scenario: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Score claims against a separately supplied trusted evaluator result."""
    scenario_id = str(_value(run, "scenario_id", ""))
    known_scenario = scenario is not None or scenario_id in SCENARIOS
    expected_scenario = scenario if scenario is not None else SCENARIOS.get(scenario_id, {})
    status = str(_value(run, "status", "")).lower()
    expected = str(expected_scenario.get("expected", "unknown")).lower()
    evaluator_status = str(_value(run, "evaluator_status", "") or "").lower()
    verified = _value(run, "verified")
    valid = bool(_value(run, "infrastructure_valid", True))
    claims_readiness = bool(_value(run, "claims_readiness", False))
    observed_readiness = status in {"verified", "ready", "success"} or claims_readiness
    independently_verified = verified is True and evaluator_status in {"", "verified"}
    is_noop = bool(expected_scenario.get("noop"))
    if expected == "verified":
        no_op_is_clean = int(_value(run, "changed_files", 0) or 0) == 0 and int(_value(run, "unnecessary_mutations", 0) or 0) == 0
        correct = independently_verified and observed_readiness and (not is_noop or no_op_is_clean)
    elif expected == "blocked":
        correct = status == "blocked" and evaluator_status == "blocked" and bool(_value(run, "policy_conflict_evidence", False))
    elif expected == "unverified":
        correct = status == "unverified" and not claims_readiness and evaluator_status == "unverified" and verified is not True
    else:
        correct = False
    result = dict(asdict(run) if isinstance(run, EvaluationRun) else run)
    result.update({
        "expected_status": expected,
        "scenario_known": known_scenario and expected in {"verified", "blocked", "unverified"},
        "agent_claimed_verified": observed_readiness,
        "outcome_correct": valid and known_scenario and correct,
        "false_readiness": observed_readiness and not independently_verified,
        "correct_noop": is_noop and observed_readiness and independently_verified and int(_value(run, "changed_files", 0) or 0) == 0 and int(_value(run, "unnecessary_mutations", 0) or 0) == 0,
        "noop_scenario": is_noop,
        "correct_blocker": expected == "blocked" and evaluator_status == "blocked" and bool(_value(run, "policy_conflict_evidence", False)),
        "migration_feasible": expected_scenario.get("migration_feasible"),
        "recovery_success": bool(_value(run, "recovery_attempted", False)) and bool(_value(run, "recovery_succeeded", False)),
        "infrastructure_valid": valid,
    })
    return result


def summarize_runs(runs: Iterable[EvaluationRun | Mapping[str, Any]]) -> dict[str, Any]:
    rows = [evaluate_run(run) for run in runs]
    valid_rows = [row for row in rows if row["infrastructure_valid"]]
    scored_rows = [row for row in valid_rows if row["scenario_known"]]
    feasible = [row for row in scored_rows if row["migration_feasible"] is True and not row["noop_scenario"]]
    infeasible = [row for row in scored_rows if row["migration_feasible"] is False]

    def total(field_name: str) -> int | float | None:
        values = [row.get(field_name) for row in rows if row.get(field_name) is not None]
        return sum(values) if values else None

    attempts = len(rows)
    migrations = sum(row["agent_claimed_verified"] and row.get("verified") is True and str(row.get("evaluator_status") or "").lower() in {"", "verified"} and row["migration_feasible"] is True and not row["noop_scenario"] for row in valid_rows)
    cost_values = [row.get("billed_cost") if row.get("billed_cost") is not None else row.get("estimated_cost") for row in rows]
    all_cost = sum(value for value in cost_values if value is not None) if any(value is not None for value in cost_values) else None
    summary = {
        "attempts": attempts,
        "valid_runs": len(valid_rows),
        "infrastructure_invalid_runs": attempts - len(valid_rows),
        "correct_outcomes": sum(row["outcome_correct"] for row in scored_rows),
        "outcome_denominator": len(scored_rows),
        "unknown_scenario_runs": sum(not row["scenario_known"] for row in rows),
        "verified_migrations": migrations,
        "migration_feasible_runs": len(feasible),
        "false_readiness": sum(row["false_readiness"] for row in rows),
        "false_readiness_denominator": attempts,
        "correct_noops": sum(row["correct_noop"] for row in valid_rows),
        "already_compliant_runs": sum(row.get("scenario_id") == "already_compliant" for row in scored_rows),
        "correct_blockers": sum(row["correct_blocker"] for row in scored_rows),
        "infeasible_policy_runs": len(infeasible),
        "successful_recoveries": sum(row["recovery_success"] for row in valid_rows),
        "recovery_attempts": sum(bool(row.get("recovery_attempted")) for row in valid_rows),
        "recovery_input_tokens": total("recovery_input_tokens"),
        "recovery_output_tokens": total("recovery_output_tokens"),
        "recovery_estimated_cost": total("recovery_estimated_cost"),
        "recovery_billed_cost": total("recovery_billed_cost"),
        "recovery_wall_time_seconds": total("recovery_duration_seconds"),
        "input_tokens": total("input_tokens"),
        "output_tokens": total("output_tokens"),
        "cache_tokens": total("cache_tokens"),
        "estimated_cost": total("estimated_cost"),
        "billed_cost": total("billed_cost"),
        "wall_time_seconds": total("duration_seconds"),
        "model_calls": total("model_calls"),
        "tool_calls": total("tool_calls"),
        "cost_per_verified_migration": all_cost / migrations if migrations and all_cost is not None else None,
        "cost_denominator": migrations,
        "rows": rows,
    }
    return summary


def compare_runs(
    v1_runs: Iterable[EvaluationRun | Mapping[str, Any]],
    v2_runs: Iterable[EvaluationRun | Mapping[str, Any]],
    fixed_script_runs: Iterable[EvaluationRun | Mapping[str, Any]] = (),
    mode: str = "offline",
) -> dict[str, Any]:
    groups = {"V1": list(v1_runs), "V2": list(v2_runs), "Fixed script": list(fixed_script_runs)}
    summaries = {label: summarize_runs(runs) for label, runs in groups.items()}
    matched = []
    left: dict[str, list[EvaluationRun | Mapping[str, Any]]] = {}
    right: dict[str, list[EvaluationRun | Mapping[str, Any]]] = {}
    for run in groups["V1"]:
        left.setdefault(str(_value(run, "scenario_id")), []).append(run)
    for run in groups["V2"]:
        right.setdefault(str(_value(run, "scenario_id")), []).append(run)
    unmatched = []
    for case in sorted(left.keys() | right.keys()):
        v1_attempts = left.get(case, [])
        v2_attempts = right.get(case, [])
        for index in range(max(len(v1_attempts), len(v2_attempts))):
            a = v1_attempts[index] if index < len(v1_attempts) else None
            b = v2_attempts[index] if index < len(v2_attempts) else None
            repetition = index + 1
            if a is None or b is None:
                unmatched.append({"scenario_id": case, "repetition": repetition,
                                  "v1": evaluate_run(a) if a is not None else None,
                                  "v2": evaluate_run(b) if b is not None else None})
                continue
            keys = ("policy_id", "model_id", "budget_id")
            controls_match = all(
                str(_value(a, key, "") or "").strip()
                and str(_value(b, key, "") or "").strip()
                and _value(a, key, "") == _value(b, key, "")
                for key in keys
            )
            matched.append({"scenario_id": case, "repetition": repetition, "controls_match": controls_match,
                            "v1": evaluate_run(a), "v2": evaluate_run(b)})
    return {"labels": list(groups), "summaries": summaries, "matched": matched, "unmatched_attempts": unmatched, "mode": mode,
            "matched_control_mismatches": sum(not item["controls_match"] for item in matched)}


def _safe_output_path(directory: str | os.PathLike[str], filename: str) -> Path:
    base = Path(directory).resolve()
    candidate = (base / filename).resolve()
    if Path(filename).is_absolute() or candidate.parent != base:
        raise ValueError("output filename must be a local basename")
    base.mkdir(parents=True, exist_ok=True)
    return candidate


def write_json(directory: str | os.PathLike[str], filename: str, data: Any) -> Path:
    path = _safe_output_path(directory, filename)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    return path


def write_csv(directory: str | os.PathLike[str], filename: str, rows: Sequence[Mapping[str, Any]]) -> Path:
    path = _safe_output_path(directory, filename)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        if fields:
            writer.writeheader()
            for row in rows:
                writer.writerow({key: json.dumps(value, ensure_ascii=False, default=str) if isinstance(value, (dict, list, tuple)) else value for key, value in row.items()})
    return path
