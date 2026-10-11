from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from dotenv import load_dotenv

from .agent import Agent
from .contracts import AgentVersion, ApprovedScope, Budgets, ClientProfile, Identity, MigrationContract
from .evaluation import compare_runs, summarize_runs, write_csv, write_json
from .evidence import build_manifest, implementation_snapshot, redact_secrets, verify_manifest
from .fixture import SCENARIOS, DockerFixture
from .providers import _validate_base_url
from .report import render_comparison_report, render_report
from .smoke import FixedBaselineModel, FixtureSmokeModel
from .tools import TOOLS, MigrationTools
from .verifier import verify_fixture

ROOT = Path(__file__).resolve().parents[2]
TARGET_DIGEST = hashlib.sha256(json.dumps({"group": "X25519MLKEM768"}, sort_keys=True).encode()).hexdigest()


def _json(value: Any) -> None:
    print(json.dumps(redact_secrets(value), indent=2, default=str))


def _root(arguments: argparse.Namespace) -> Path:
    return Path(arguments.root).resolve() if arguments.root else ROOT


def _execution_mode(model: Any, offline: bool) -> str:
    if isinstance(model, FixedBaselineModel):
        return "fixed-script-baseline-not-LLM"
    return "offline-smoke-not-LLM" if offline else "live-model"


def _model(arguments: argparse.Namespace, version: str):
    if arguments.offline:
        return FixtureSmokeModel(version)
    if not os.getenv("INVARIS_MAX_SPEND_USD"):
        raise ValueError("Live requests require an explicitly authorized INVARIS_MAX_SPEND_USD and model rates in .env")
    from .budget import ProjectBudgetedProvider
    return ProjectBudgetedProvider(_root(arguments), arguments.model or None, float(os.environ["INVARIS_MAX_SPEND_USD"]))


def _evaluation_config(root: Path, arguments: argparse.Namespace, scenarios: tuple[str, ...]) -> dict[str, Any]:
    sources = ("agent.py", "providers.py", "budget.py", "controller.py", "tools.py", "verifier.py", "fixture.py")
    package = Path(__file__).parent
    hashes = {name: hashlib.sha256((package / name).read_bytes()).hexdigest() for name in sources}
    fixture_sources = ("fixture/Dockerfile", "fixture/server.c", "fixture/probe.c", "fixture/control.py")
    fixture_root = root if all((root / name).is_file() for name in fixture_sources) else ROOT
    hashes.update({name: hashlib.sha256((fixture_root / name).read_bytes()).hexdigest() for name in fixture_sources})
    live_settings = {}
    if not arguments.offline:
        base_url = os.getenv("OPENAI_BASE_URL", "")
        base_url_sha256 = None
        base_url_origin = None
        if base_url:
            _validate_base_url(base_url)
            parsed_base_url = urlsplit(base_url)
            base_url_sha256 = hashlib.sha256(base_url.encode("utf-8")).hexdigest()
            base_url_origin = f"{parsed_base_url.scheme}://{parsed_base_url.netloc}"
        live_settings = {
            "model": (arguments.model or os.getenv("INVARIS_MODEL", "")).strip(),
            "base_url_sha256": base_url_sha256,
            "base_url_origin": base_url_origin,
            "max_spend_usd": os.getenv("INVARIS_MAX_SPEND_USD", ""),
            "input_usd_per_million": os.getenv("INVARIS_INPUT_USD_PER_MILLION", ""),
            "output_usd_per_million": os.getenv("INVARIS_OUTPUT_USD_PER_MILLION", ""),
        }
    return {"schema": "invaris.matched-evaluation/v1", "offline": arguments.offline,
            "model": "offline-smoke" if arguments.offline else live_settings["model"],
            "live_settings": live_settings,
            "repetitions": arguments.repetitions, "scenarios": list(scenarios),
            "policy": "strict-hybrid-v1", "budget": "16steps-24tools-64000tokens-600seconds",
            "include_held_out": arguments.include_held_out, "source_hashes": hashes}


def _validate_evaluation_rows(rows: Any, scenarios: tuple[str, ...], repetitions: int) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        raise ValueError("persisted evaluation runs.json must contain an array")
    allowed_arms = {"V1", "V2", "Fixed script"}
    counts: dict[tuple[str, str], int] = {}
    run_ids: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("persisted evaluation rows must be objects")
        arm = row.get("version")
        scenario = row.get("scenario_id")
        run_id = row.get("run_id")
        if arm not in allowed_arms or scenario not in scenarios:
            raise ValueError("persisted evaluation row has an unknown arm or scenario")
        if not isinstance(run_id, str) or not run_id.strip() or run_id in run_ids:
            raise ValueError("persisted evaluation rows require unique nonempty run IDs")
        run_ids.add(run_id)
        key = (arm, scenario)
        counts[key] = counts.get(key, 0) + 1
        if counts[key] > repetitions:
            raise ValueError("persisted evaluation has more attempts than configured")
    return rows


def _checkpoint_evaluation(destination: Path, rows: list[dict[str, Any]], config: dict[str, Any], complete: bool) -> dict[str, Any]:
    versions = {arm: [row for row in rows if row.get("version") == arm]
                for arm in ("V1", "V2", "Fixed script")}
    comparison = compare_runs(versions["V1"], versions["V2"], versions["Fixed script"])
    comparison["mode"] = "offline smoke, NOT evidence of live LLM improvement" if config["offline"] else "live model matched evaluation"
    write_json(destination, "runs.json", rows)
    write_json(destination, "comparison.json", comparison)
    write_csv(destination, "runs.csv", rows)
    (destination / "report.html").write_text(render_comparison_report(comparison), encoding="utf-8")
    write_json(destination, "config.json", config)
    write_json(destination, "manifest.json", {**build_manifest(destination, ("config.json", "runs.json", "comparison.json", "runs.csv", "report.html")), "complete": complete})
    return comparison


def _run_scenario(root: Path, fixture: DockerFixture, scenario: str, version: str, model: Any,
                 artifacts: Path, *, offline: bool) -> dict[str, Any]:
    from .tracing import traced_operation, tracing_status
    reset = fixture.control("reset", scenario=scenario)
    if not reset.get("ok"):
        raise RuntimeError("fixture reset failed")
    run_id = str(uuid.uuid4())
    directory = artifacts / "runs" / run_id
    directory.mkdir(parents=True, exist_ok=False)
    identity = Identity(instance_id=reset["instance_id"], run_id=run_id, candidate_id=TARGET_DIGEST)
    clients = (ClientProfile(name="hybrid-capable"), ClientProfile(name="classical-only", required=scenario == "impossible_client_requirement", expected_group="X25519"))
    contract = MigrationContract(identity=identity, clients=clients,
        scope=ApprovedScope(endpoint="https://fixture:8443/health", writable_paths=("config.json",),
                            allowed_tools=tuple(TOOLS), allow_restart=True, allow_rollback=True),
        budgets=Budgets(max_steps=16, max_errors=3, max_tool_calls=24, max_tokens=64000,
                        max_duration_seconds=600, max_cost_usd=float(os.getenv("INVARIS_MAX_SPEND_USD", "0"))),
        approval_candidate_id=TARGET_DIGEST)
    impossible_policy = any(client.required and client.expected_group != contract.target_group for client in contract.clients)
    executor = MigrationTools(fixture, identity, impossible_policy=impossible_policy, verbose=True)
    baseline = fixture.control("inspect")
    write_json(directory, "contract.json", contract.model_dump(mode="json"))
    write_json(directory, "baseline.json", baseline)
    write_json(directory, "implementation.json", implementation_snapshot(root))
    started = time.monotonic()
    with traced_operation("invaris.migration." + version, "WORKFLOW", {"contract": contract.model_dump(mode="json"), "mode": "offline" if offline else "live"}) as root_span:
        result = Agent(contract, executor, model, AgentVersion(version), checkpoint_path=directory / "checkpoint.json").run()
        independent = verify_fixture(fixture, identity, impossible_policy=impossible_policy)
        root_span.set_output({"agent_result": result.model_dump(mode="json"), "independent_verification": independent})
    final_config = fixture.control("inspect")
    rollback: dict[str, Any] = {"attempted": False}
    if independent.get("verified"):
        with traced_operation("invaris.rollback_and_reverify", "TOOL", {"candidate": TARGET_DIGEST}) as rollback_span:
            migrated = final_config["config"]
            restored = fixture.control("restore", expected_instance_id=identity.instance_id)
            baseline_probe = fixture.probe()
            rollback_ok = bool(restored.get("ok") and restored.get("loaded_digest") == reset["baseline_digest"] and restored.get("config_digest") == baseline["config_digest"]
                               and baseline_probe.get("verify_ok") and baseline_probe.get("application", {}).get("candidate_digest") == reset["baseline_digest"])
            rollback = {"attempted": True, "verified": rollback_ok, "restored": restored, "connection": baseline_probe}
            fixture.control("stage", group=migrated["group"], expected_instance_id=identity.instance_id, expected_candidate_id=identity.candidate_id)
            fixture.control("apply", expected_instance_id=identity.instance_id, expected_candidate_id=identity.candidate_id)
            fixture.control("restart", expected_instance_id=identity.instance_id, expected_candidate_id=identity.candidate_id)
            final_reverification = verify_fixture(fixture, identity)
            rollback["candidate_reverified"] = final_reverification
            rollback_span.set_output(rollback)
            if not rollback_ok or not final_reverification.get("verified"):
                independent = {**independent, "verified": False, "status": "FAILED", "reason": "rollback/reapplication check failed"}
                rollback_span.set_error(independent["reason"])
    usage = result.model_usage
    recovery_receipts = [event for event in executor.events if not event["receipt"].get("ok") and event["name"] == "restart_service"]
    row = {
        "run_id": run_id, "scenario_id": scenario, "version": getattr(model, "comparison_arm", version), "status": result.status.value,
        "claims_readiness": result.claimed_status is not None and result.claimed_status.value == "VERIFIED",
        "policy_id": "strict-hybrid-v1", "model_id": getattr(model, "model", getattr(model, "label", "unknown")),
        "budget_id": "16steps-24tools-64000tokens-600seconds", "infrastructure_valid": offline or ("input_tokens" in usage and "output_tokens" in usage and "model error budget" not in result.reason),
        "verified": independent.get("verified") is True, "evaluator_status": independent["status"],
        "policy_conflict_evidence": independent.get("policy_conflict_evidence", False),
        "changed_files": int(final_config["config_digest"] != baseline["config_digest"] or any(event["name"] == "apply_candidate" and event["receipt"].get("ok") for event in executor.events)),
        "unnecessary_mutations": sum(event["name"] in {"stage_config_change", "apply_candidate", "restart_service"} and bool(event["receipt"].get("ok")) for event in executor.events) if scenario == "already_compliant" else 0,
        "recovery_attempted": bool(recovery_receipts), "recovery_succeeded": bool(recovery_receipts and independent.get("verified")),
        "input_tokens": 0 if offline else usage.get("input_tokens"), "output_tokens": 0 if offline else usage.get("output_tokens"),
        "cache_tokens": 0 if offline else usage.get("cache_tokens"), "estimated_cost": 0.0 if offline else usage.get("estimated_cost_usd"),
        "billed_cost": None, "duration_seconds": time.monotonic() - started, "model_calls": 0 if offline else result.steps,
        "tool_calls": len(result.receipts), "metadata": {"mode": _execution_mode(model, offline),
            "agent_version": version, "script_turns": result.steps if offline else None,
            "trace_id": root_span.trace_id,
            "trace_state": tracing_status().state, "artifact_directory": str(directory), "rollback_verified": rollback.get("verified")},
    }
    bundle = {"project": "Invaris", "mode": row["metadata"]["mode"], "contract": contract.model_dump(mode="json"),
              "agent": result.model_dump(mode="json"), "independent_verification": independent,
              "baseline": baseline, "final": final_config, "events": executor.events, "rollback": rollback,
              "evaluation": row, "integration_claims": {"neatlogs": "configured-not-delivery-verified" if tracing_status().state == "configured" else "unavailable"}}
    write_json(directory, "bundle.json", redact_secrets(bundle))
    write_json(directory, "result.json", row)
    (directory / "report.html").write_text(render_report(summarize_runs([row]), title="Invaris Migration Evidence", mode=row["metadata"]["mode"]), encoding="utf-8")
    write_json(directory, "manifest.json", build_manifest(directory, ("contract.json", "baseline.json", "implementation.json", "bundle.json", "result.json", "report.html")))
    return row


def run_scenario(root: Path, fixture: DockerFixture, scenario: str, version: str, model: Any,
                 artifacts: Path, *, offline: bool) -> dict[str, Any]:
    from .tracing import traced_operation
    with traced_operation("invaris.run", "WORKFLOW", {"agent_version": version, "comparison_arm": getattr(model, "comparison_arm", version), "scenario_id": scenario, "mode": _execution_mode(model, offline)}) as span:
        try:
            result = _run_scenario(root, fixture, scenario, version, model, artifacts, offline=offline)
        except Exception as error:
            result = {"run_id": str(uuid.uuid4()), "scenario_id": scenario, "version": getattr(model, "comparison_arm", version),
                      "status": "UNVERIFIED", "evaluator_status": "UNVERIFIED", "verified": False,
                      "infrastructure_valid": False, "claims_readiness": False,
                      "metadata": {"mode": _execution_mode(model, offline), "error": type(error).__name__, "message": str(error)[:500]}}
            write_json(artifacts / "runs" / result["run_id"], "invalid-run.json", redact_secrets(result))
            span.set_error(type(error).__name__)
        span.set_output(result)
        return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="invaris", description="Verified cryptographic change in an authorized sandbox")
    parser.add_argument("--root", help="Repository containing compose.yaml")
    parser.add_argument("--project", default="invaris-local", help="Owned invaris-* Compose project")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("setup", help="Build and start the pinned TLS fixture")
    doctor = commands.add_parser("doctor", help="Check integrations without printing credentials")
    doctor.add_argument("--probe-neatlogs", action="store_true")
    for name in ("run", "evaluate"):
        command = commands.add_parser(name)
        command.add_argument("--offline", action="store_true", help="Explicit fixed-script smoke mode; NOT a live LLM evaluation")
        command.add_argument("--model")
        command.add_argument("--approve-sandbox", action="store_true", help="Authorize the documented scoped fixture changes/restarts/rollback")
        command.add_argument("--artifacts", help="Output directory; defaults to INVARIS_ARTIFACTS or artifacts")
        if name == "run":
            command.add_argument("--scenario", choices=SCENARIOS, default="wrong_active_group")
            command.add_argument("--version", choices=["V1", "V2"], default="V2")
        else:
            command.add_argument("--repetitions", type=int, choices=range(1, 6), default=1)
            command.add_argument("--include-held-out", action="store_true")
            command.add_argument("--resume-evaluation", type=Path, help="Resume a compatible persisted evaluation directory")
    business = commands.add_parser("business", help="Prepare measured assumptions for cfo.ai, not a fabricated export")
    business.add_argument("--results", type=Path, required=True)
    business.add_argument("--output", type=Path, default=Path("business/assumptions.json"))
    evidence_check = commands.add_parser("verify-bundle", help="Check artifact hashes; not authenticity or cryptographic correctness")
    evidence_check.add_argument("--directory", required=True, type=Path)
    trace_audit = commands.add_parser("trace-audit", help="Compare actual cloud span coverage with a local run; no network or model calls")
    trace_audit.add_argument("--expected", required=True, type=Path)
    trace_audit.add_argument("--readback", required=True, type=Path)
    trace_audit.add_argument("--project-id", required=True)
    cleanup = commands.add_parser("cleanup", help="Remove only the selected owned fixture")
    cleanup.add_argument("--delete-volumes", action="store_true", help="Delete owned test state/certificates")
    arguments = parser.parse_args(argv)
    root = _root(arguments)
    load_dotenv(root / ".env", override=False)
    if arguments.command in {"run", "evaluate"} and arguments.artifacts is None:
        arguments.artifacts = os.getenv("INVARIS_ARTIFACTS", "artifacts")
    tracing_started = False
    try:
        if arguments.command == "trace-audit":
            from .trace_audit import audit_trace_readback
            expected = json.loads(arguments.expected.read_text(encoding="utf-8"))
            readback = json.loads(arguments.readback.read_text(encoding="utf-8"))
            audit = audit_trace_readback(expected, readback, project_id=arguments.project_id)
            _json(audit)
            return 0 if audit["complete"] else 1
        if arguments.command == "verify-bundle":
            manifest = json.loads((arguments.directory / "manifest.json").read_text(encoding="utf-8"))
            valid = isinstance(manifest, dict) and verify_manifest(arguments.directory, manifest)
            _json({"integrity_valid": valid, "authenticity_verified": False})
            return 0 if valid else 1
        if arguments.command == "doctor":
            from .integrations import check_integrations
            evidence = {
                "entire": (root / "docs" / "evidence" / "entire-checkpoint.json",
                           root / "docs" / "evidence" / "entire-graph.json"),
                "cfo.ai": (root / "business" / "cfo-review.md", root / "business" / "README.md"),
            }
            _json([asdict(check) for check in check_integrations(evidence=evidence, neatlogs_probe=arguments.probe_neatlogs)])
            return 0
        if arguments.command == "business":
            from .business import build_business_assumptions
            rows = json.loads(arguments.results.read_text(encoding="utf-8"))
            if not isinstance(rows, list):
                raise ValueError("business --results requires a per-run JSON array")
            arguments.output.parent.mkdir(parents=True, exist_ok=True)
            write_json(arguments.output.parent, arguments.output.name, build_business_assumptions(rows))
            _json({"artifact": str(arguments.output), "actual_cfo_export": False})
            return 0
        fixture = DockerFixture(root, arguments.project)
        if arguments.command == "setup":
            fixture.build()
            fixture.up()
            _json(fixture.control("inspect"))
            return 0
        if arguments.command == "cleanup":
            fixture.down(delete_volumes=arguments.delete_volumes)
            _json({"removed_owned_project": arguments.project})
            return 0
        if not arguments.approve_sandbox:
            raise ValueError("Pass --approve-sandbox only after reviewing the README's scoped permissions")
        from .tracing import configure_tracing, flush_tracing, shutdown_tracing
        configure_tracing(workflow_name="tls-migration" if arguments.command == "run" else "migration-comparison")
        tracing_started = True
        artifacts = Path(arguments.artifacts).resolve()
        if arguments.command == "evaluate":
            scenarios = SCENARIOS if arguments.include_held_out else SCENARIOS[:-1]
            config = _evaluation_config(root, arguments, scenarios)
            if arguments.resume_evaluation:
                destination = arguments.resume_evaluation.resolve()
                manifest_path = destination / "manifest.json"
                if not manifest_path.is_file():
                    raise ValueError("persisted evaluation manifest is missing")
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if not isinstance(manifest, dict) or not verify_manifest(destination, manifest):
                    raise ValueError("persisted evaluation manifest is invalid")
                persisted = json.loads((destination / "config.json").read_text(encoding="utf-8"))
                if persisted != config:
                    raise ValueError("evaluation configuration is incompatible with this resume request")
                rows = _validate_evaluation_rows(json.loads((destination / "runs.json").read_text(encoding="utf-8")), scenarios, arguments.repetitions)
                if manifest.get("complete") is True:
                    raise ValueError("evaluation is already complete")
            else:
                destination = artifacts / "evaluations" / str(uuid.uuid4())
                rows = []
                write_json(destination, "config.json", config)
                _checkpoint_evaluation(destination, rows, config, False)
            fixture.up()
            live_model = None if arguments.offline else _model(arguments, "V1")
            for arm in ("V1", "V2", "Fixed script"):
                version = "V2" if arm == "Fixed script" else arm
                for scenario in scenarios:
                    existing = sum(row.get("version") == arm and row.get("scenario_id") == scenario for row in rows)
                    for _ in range(existing, arguments.repetitions):
                        scripted = arguments.offline or arm == "Fixed script"
                        model = FixedBaselineModel() if arm == "Fixed script" else FixtureSmokeModel(version) if arguments.offline else live_model
                        rows.append(run_scenario(root, fixture, scenario, version, model, artifacts, offline=scripted))
                        _checkpoint_evaluation(destination, rows, config, False)
            comparison = _checkpoint_evaluation(destination, rows, config, True)
            _json({"mode": comparison["mode"], "output": str(destination), "V1": {key: value for key, value in comparison["summaries"]["V1"].items() if key != "rows"},
                   "V2": {key: value for key, value in comparison["summaries"]["V2"].items() if key != "rows"},
                   "Fixed script": {key: value for key, value in comparison["summaries"]["Fixed script"].items() if key != "rows"}})
            return 0
        fixture.up()
        if arguments.command == "run":
            row = run_scenario(root, fixture, arguments.scenario, arguments.version, _model(arguments, arguments.version), artifacts, offline=arguments.offline)
            _json(row)
            return 0 if row["verified"] or row["evaluator_status"] in {"BLOCKED", "UNVERIFIED"} else 1
    except Exception as error:
        _json({"error": type(error).__name__, "message": str(error)[:1500]})
        return 2
    finally:
        if tracing_started:
            try:
                flush_tracing()
            finally:
                shutdown_tracing()


if __name__ == "__main__":
    raise SystemExit(main())
