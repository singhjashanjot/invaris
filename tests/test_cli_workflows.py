import json
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from invaris import cli
from invaris.evidence import verify_manifest


class Status(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"


class FakeResult:
    status = Status.VERIFIED
    claimed_status = Status.VERIFIED
    model_usage = {"input_tokens": 12, "output_tokens": 4}
    steps = 3
    receipts = ()
    reason = "test agent"

    def model_dump(self, mode=None):
        return {
            "status": self.status.value,
            "claimed_status": self.claimed_status.value,
            "model_usage": self.model_usage,
            "steps": self.steps,
            "receipts": list(self.receipts),
            "reason": self.reason,
        }


class FakeFixture:
    def __init__(self, fail_reset=False):
        self.fail_reset = fail_reset
        self.group = "X25519"
        self.operations = []

    def control(self, operation, **arguments):
        self.operations.append((operation, arguments))
        if operation == "reset":
            if self.fail_reset:
                raise RuntimeError("reset unavailable")
            return {"ok": True, "instance_id": "fixture-1", "baseline_digest": "baseline"}
        if operation == "inspect":
            digest = "target" if self.group == "X25519MLKEM768" else "baseline"
            return {
                "ok": True,
                "instance_id": "fixture-1",
                "config": {"group": self.group},
                "config_digest": digest,
                "loaded_digest": digest,
            }
        if operation == "restore":
            self.group = "X25519"
            return {"ok": True, "loaded_digest": "baseline", "config_digest": "baseline"}
        if operation == "stage":
            self.group = arguments["group"]
        return {"ok": True}

    def probe(self):
        return {
            "verify_ok": True,
            "application": {"candidate_digest": "baseline"},
        }


def verified_evidence(*, verified=True):
    return {"verified": verified, "status": "VERIFIED" if verified else "FAILED"}


def run_with_mocks(tmp_path, fixture, verifier_results, *, offline=True):
    snapshots = {"schema": "invaris.implementation/v1", "files": {"src/example.py": {"sha256_original": "abc"}}}
    with (
        patch("invaris.cli.implementation_snapshot", return_value=snapshots),
        patch("invaris.cli.Agent") as agent_class,
        patch("invaris.cli.verify_fixture", side_effect=verifier_results),
        patch("invaris.tracing.traced_operation", _traced_operation),
    ):
        def run_agent():
            fixture.group = "X25519MLKEM768"
            return FakeResult()

        agent_class.return_value.run.side_effect = run_agent
        row = cli._run_scenario(
            Path("."), fixture, "wrong_active_group", "V2", SimpleNamespace(label="fake-model"),
            tmp_path, offline=offline,
        )
    return row


class FakeSpan:
    trace_id = "trace-test"

    def set_output(self, output):
        self.output = output

    def set_error(self, error):
        self.error = error


class _traced_operation:
    def __init__(self, *args, **kwargs):
        self.span = FakeSpan()

    def __enter__(self):
        return self.span

    def __exit__(self, *args):
        return False


def test_verified_workflow_writes_verifiable_bundle_with_snapshot(tmp_path):
    fixture = FakeFixture()
    row = run_with_mocks(tmp_path, fixture, [verified_evidence(), verified_evidence()])
    artifact_dir = next((tmp_path / "runs").iterdir())
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))

    assert row["verified"] is True
    assert row["evaluator_status"] == "VERIFIED"
    assert manifest["files"]["implementation.json"]
    assert verify_manifest(artifact_dir, manifest)
    bundle = json.loads((artifact_dir / "bundle.json").read_text(encoding="utf-8"))
    assert bundle["mode"] == "offline-smoke-not-LLM"
    assert (artifact_dir / "implementation.json").is_file()


def test_invalid_infrastructure_attempt_is_preserved(tmp_path):
    row = cli.run_scenario(Path("."), FakeFixture(fail_reset=True), "wrong_active_group", "V2",
                           SimpleNamespace(label="fake-model"), tmp_path, offline=False)
    invalid_path = tmp_path / "runs" / row["run_id"] / "invalid-run.json"

    assert row["infrastructure_valid"] is False
    assert row["verified"] is False
    assert row["metadata"]["mode"] == "live-model"
    assert json.loads(invalid_path.read_text(encoding="utf-8"))["scenario_id"] == "wrong_active_group"


def test_failed_rollback_reverification_removes_verified_claim(tmp_path):
    row = run_with_mocks(tmp_path, FakeFixture(), [verified_evidence(), verified_evidence(verified=False)])

    assert row["verified"] is False
    assert row["evaluator_status"] == "FAILED"
    bundle_path = next((tmp_path / "runs").iterdir()) / "bundle.json"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert bundle["evaluation"]["verified"] is False
    assert bundle["independent_verification"]["reason"] == "rollback/reapplication check failed"


def test_offline_result_labels_fixed_script_mode(tmp_path):
    row = run_with_mocks(tmp_path, FakeFixture(), [verified_evidence(), verified_evidence()])

    assert row["metadata"]["mode"] == "offline-smoke-not-LLM"
    assert json.loads((next((tmp_path / "runs").iterdir()) / "result.json").read_text(encoding="utf-8"))["metadata"]["mode"] == "offline-smoke-not-LLM"
    assert row["input_tokens"] == row["output_tokens"] == row["model_calls"] == 0
    assert row["estimated_cost"] == 0


def test_live_report_is_not_mislabeled_as_offline(tmp_path):
    run_with_mocks(tmp_path, FakeFixture(), [verified_evidence(), verified_evidence()], offline=False)
    report = next((tmp_path / "runs").iterdir()) / "report.html"
    assert "Run mode: live-model" in report.read_text(encoding="utf-8")
