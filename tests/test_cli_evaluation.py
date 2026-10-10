import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from invaris import cli
from invaris.evidence import verify_manifest
from invaris.fixture import SCENARIOS


@pytest.mark.parametrize("offline", [False, True])
def test_evaluate_dispatches_every_arm_and_writes_complete_manifest(tmp_path, capsys, offline):
    repetitions = 2
    scenarios = list(SCENARIOS)
    expected_calls = []
    model_calls = []
    fixture_calls = []
    fake_live_model = SimpleNamespace(label="mock-live-model")

    class FakeFixture:
        def __init__(self, root, project):
            fixture_calls.append((root, project))

        def up(self):
            fixture_calls.append("up")

    def fake_run_scenario(root, fixture, scenario, version, model, artifacts, *, offline):
        arm = getattr(model, "comparison_arm", version)
        expected_calls.append((arm, version, scenario, offline))
        return {
            "run_id": f"{arm}-{scenario}-{len(expected_calls)}",
            "scenario_id": scenario,
            "version": arm,
            "status": "VERIFIED",
            "verified": True,
            "evaluator_status": "VERIFIED",
            "infrastructure_valid": True,
            "claims_readiness": True,
            "policy_id": "policy",
            "model_id": "model",
            "budget_id": "budget",
            "metadata": {"offline": offline},
        }

    def fake_model(arguments, version):
        model_calls.append((arguments.offline, version))
        return fake_live_model

    with (
        patch("invaris.cli.load_dotenv") as load_dotenv,
        patch.object(cli, "DockerFixture", FakeFixture),
        patch.object(cli, "run_scenario", side_effect=fake_run_scenario) as run_scenario_mock,
        patch.object(cli, "_model", side_effect=fake_model),
        patch("invaris.tracing.configure_tracing") as configure_tracing,
        patch("invaris.tracing.flush_tracing") as flush_tracing,
        patch("invaris.tracing.shutdown_tracing") as shutdown_tracing,
    ):
        argv = ["--root", str(tmp_path), "evaluate", "--approve-sandbox", "--include-held-out",
                "--repetitions", str(repetitions), "--artifacts", str(tmp_path / "artifacts")]
        if offline:
            argv.append("--offline")

        assert cli.main(argv) == 0

    load_dotenv.assert_called_once()
    configure_tracing.assert_called_once_with(workflow_name="migration-comparison")
    flush_tracing.assert_called_once()
    shutdown_tracing.assert_called_once()
    assert fixture_calls[-1] == "up"
    assert model_calls == ([] if offline else [(False, "V1")])

    expected = [
        (arm, "V2" if arm == "Fixed script" else arm, scenario,
         offline or arm == "Fixed script")
        for arm in ("V1", "V2", "Fixed script")
        for scenario in scenarios
        for _ in range(repetitions)
    ]
    assert expected_calls == expected
    if not offline:
        fixed_models = [call.args[4] for call in run_scenario_mock.call_args_list
                        if call.args[3] == "V2" and getattr(call.args[4], "comparison_arm", None) == "Fixed script"]
        assert len(fixed_models) == len(scenarios) * repetitions
        assert all(isinstance(model, cli.FixedBaselineModel) for model in fixed_models)
        assert all(model is not fake_live_model for model in fixed_models)

    payload = json.loads(capsys.readouterr().out)
    evaluation_dir = Path(payload["output"])
    rows = json.loads((evaluation_dir / "runs.json").read_text(encoding="utf-8"))
    assert len(rows) == 3 * len(scenarios) * repetitions
    assert [row["version"] for row in rows] == [call[0] for call in expected]
    assert [row["scenario_id"] for row in rows] == [call[2] for call in expected]
    manifest = json.loads((evaluation_dir / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["files"]) == {"runs.json", "comparison.json", "runs.csv", "report.html"}
    assert verify_manifest(evaluation_dir, manifest)
