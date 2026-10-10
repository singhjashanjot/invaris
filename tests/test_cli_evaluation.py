import hashlib
import json
import os
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
    assert set(manifest["files"]) == {"config.json", "runs.json", "comparison.json", "runs.csv", "report.html"}
    assert manifest["complete"] is True
    assert verify_manifest(evaluation_dir, manifest)


def test_evaluate_resume_continues_missing_attempts_and_rejects_changed_config(tmp_path, capsys):
    class FakeFixture:
        def __init__(self, root, project):
            pass

        def up(self):
            pass

    calls = 0

    def interrupted_run(root, fixture, scenario, version, model, artifacts, *, offline):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise RuntimeError("simulated interruption")
        arm = getattr(model, "comparison_arm", version)
        return {"run_id": str(calls), "scenario_id": scenario, "version": arm, "verified": False,
                "evaluator_status": "UNVERIFIED", "infrastructure_valid": False}

    with (
        patch("invaris.cli.load_dotenv"), patch.object(cli, "DockerFixture", FakeFixture),
        patch.object(cli, "run_scenario", side_effect=interrupted_run),
        patch("invaris.tracing.configure_tracing"), patch("invaris.tracing.flush_tracing"),
        patch("invaris.tracing.shutdown_tracing"),
    ):
        args = ["--root", str(tmp_path), "evaluate", "--offline", "--approve-sandbox", "--artifacts", str(tmp_path / "artifacts")]
        assert cli.main(args) == 2
        destination = next((tmp_path / "artifacts" / "evaluations").iterdir())
        assert len(json.loads((destination / "runs.json").read_text(encoding="utf-8"))) == 2
        assert json.loads((destination / "manifest.json").read_text(encoding="utf-8"))["complete"] is False

    resumed_calls = []

    def finish_run(root, fixture, scenario, version, model, artifacts, *, offline):
        arm = getattr(model, "comparison_arm", version)
        resumed_calls.append((arm, scenario))
        return {"run_id": f"resumed-{len(resumed_calls)}", "scenario_id": scenario, "version": arm,
                "verified": False, "evaluator_status": "UNVERIFIED", "infrastructure_valid": False}

    with (
        patch("invaris.cli.load_dotenv"), patch.object(cli, "DockerFixture", FakeFixture),
        patch.object(cli, "run_scenario", side_effect=finish_run),
        patch("invaris.tracing.configure_tracing"), patch("invaris.tracing.flush_tracing"),
        patch("invaris.tracing.shutdown_tracing"),
    ):
        assert cli.main([*args, "--resume-evaluation", str(destination)]) == 0

    all_rows = json.loads((destination / "runs.json").read_text(encoding="utf-8"))
    assert len(all_rows) == 3 * len(SCENARIOS[:-1])
    assert len(resumed_calls) == len(all_rows) - 2
    assert json.loads((destination / "manifest.json").read_text(encoding="utf-8"))["complete"] is True

    with (
        patch("invaris.cli.load_dotenv"), patch.object(cli, "DockerFixture", FakeFixture),
        patch("invaris.tracing.configure_tracing"), patch("invaris.tracing.flush_tracing"),
        patch("invaris.tracing.shutdown_tracing"),
    ):
        assert cli.main(["--root", str(tmp_path), "evaluate", "--approve-sandbox", "--resume-evaluation", str(destination)]) == 2


def test_resume_rejects_changed_effective_model_from_environment(tmp_path):
    environment = {"INVARIS_MODEL": "model-a", "OPENAI_BASE_URL": "https://provider.example/v1",
                   "INVARIS_MAX_SPEND_USD": "12", "INVARIS_INPUT_USD_PER_MILLION": "1.2",
                   "INVARIS_OUTPUT_USD_PER_MILLION": "3.4"}
    arguments = SimpleNamespace(offline=False, model=None, repetitions=1, include_held_out=False)
    destination = tmp_path / "evaluation"

    with patch.dict(os.environ, environment, clear=False):
        config = cli._evaluation_config(tmp_path, arguments, SCENARIOS[:-1])
        cli._checkpoint_evaluation(destination, [], config, False)
    with (
        patch.dict(os.environ, {**environment, "INVARIS_MODEL": "model-b"}, clear=False), patch("invaris.cli.load_dotenv"),
        patch("invaris.tracing.configure_tracing"), patch("invaris.tracing.flush_tracing"),
        patch("invaris.tracing.shutdown_tracing"),
    ):
        assert cli.main(["evaluate", "--approve-sandbox", "--resume-evaluation", str(destination)]) == 2


def test_evaluation_config_fingerprints_path_url_without_persisting_it(tmp_path):
    secret_path = "private-path-credential"
    base_url = f"https://provider.example/v1/{secret_path}"
    environment = {"INVARIS_MODEL": "model-a", "OPENAI_BASE_URL": base_url,
                   "INVARIS_MAX_SPEND_USD": "12", "INVARIS_INPUT_USD_PER_MILLION": "1.2",
                   "INVARIS_OUTPUT_USD_PER_MILLION": "3.4"}
    arguments = SimpleNamespace(offline=False, model=None, repetitions=1, include_held_out=False)
    with patch.dict(os.environ, environment, clear=False):
        config = cli._evaluation_config(tmp_path, arguments, SCENARIOS[:-1])
    destination = tmp_path / "evaluation"
    cli._checkpoint_evaluation(destination, [], config, False)
    persisted = (destination / "config.json").read_text(encoding="utf-8")

    assert secret_path not in persisted
    assert base_url not in persisted
    assert config["live_settings"]["base_url_sha256"] == hashlib.sha256(base_url.encode()).hexdigest()
    assert config["live_settings"]["base_url_origin"] == "https://provider.example"


def test_query_url_is_rejected_before_evaluation_artifacts_are_written(tmp_path, capsys):
    secret_query = "query-credential"
    environment = {"INVARIS_MODEL": "model-a", "OPENAI_BASE_URL": f"https://provider.example/v1?api_key={secret_query}"}
    with (
        patch.dict(os.environ, environment, clear=False), patch("invaris.cli.load_dotenv"),
        patch.object(cli, "DockerFixture"), patch("invaris.tracing.configure_tracing"),
        patch("invaris.tracing.flush_tracing"), patch("invaris.tracing.shutdown_tracing"),
    ):
        assert cli.main(["--root", str(tmp_path), "evaluate", "--approve-sandbox", "--artifacts", str(tmp_path / "artifacts")]) == 2

    assert secret_query not in capsys.readouterr().out
    assert not (tmp_path / "artifacts" / "evaluations").exists()


def test_resume_accepts_same_endpoint_and_rejects_changed_endpoint(tmp_path):
    class FakeFixture:
        def __init__(self, root, project):
            pass

        def up(self):
            pass

    environment = {"INVARIS_MODEL": "model-a", "OPENAI_BASE_URL": "https://provider.example/v1",
                   "INVARIS_MAX_SPEND_USD": "12", "INVARIS_INPUT_USD_PER_MILLION": "1.2",
                   "INVARIS_OUTPUT_USD_PER_MILLION": "3.4"}
    arguments = SimpleNamespace(offline=False, model=None, repetitions=1, include_held_out=False)
    with patch.dict(os.environ, environment, clear=False):
        config = cli._evaluation_config(tmp_path, arguments, SCENARIOS[:-1])
    destination = tmp_path / "evaluation"
    cli._checkpoint_evaluation(destination, [], config, False)
    run_calls = []

    def fake_run(root, fixture, scenario, version, model, artifacts, *, offline):
        arm = getattr(model, "comparison_arm", version)
        run_calls.append(arm)
        return {"run_id": str(len(run_calls)), "scenario_id": scenario, "version": arm,
                "status": "UNVERIFIED", "verified": False, "evaluator_status": "UNVERIFIED",
                "infrastructure_valid": False, "claims_readiness": False}

    with (
        patch.dict(os.environ, environment, clear=False), patch("invaris.cli.load_dotenv"),
        patch.object(cli, "DockerFixture", FakeFixture), patch.object(cli, "_model", return_value=SimpleNamespace()),
        patch.object(cli, "run_scenario", side_effect=fake_run), patch("invaris.tracing.configure_tracing"),
        patch("invaris.tracing.flush_tracing"), patch("invaris.tracing.shutdown_tracing"),
    ):
        assert cli.main(["--root", str(tmp_path), "evaluate", "--approve-sandbox", "--resume-evaluation", str(destination)]) == 0

    assert len(run_calls) == 3 * len(SCENARIOS[:-1])
    with (
        patch.dict(os.environ, {**environment, "OPENAI_BASE_URL": "https://other.example/v1"}, clear=False),
        patch("invaris.cli.load_dotenv"), patch.object(cli, "DockerFixture", FakeFixture),
        patch("invaris.tracing.configure_tracing"), patch("invaris.tracing.flush_tracing"),
        patch("invaris.tracing.shutdown_tracing"),
    ):
        assert cli.main(["--root", str(tmp_path), "evaluate", "--approve-sandbox", "--resume-evaluation", str(destination)]) == 2


def test_resume_rejects_tampered_rows_before_reuse(tmp_path):
    arguments = SimpleNamespace(offline=True, model=None, repetitions=1, include_held_out=False)
    config = cli._evaluation_config(tmp_path, arguments, SCENARIOS[:-1])
    destination = tmp_path / "evaluation"
    cli._checkpoint_evaluation(destination, [], config, False)
    (destination / "runs.json").write_text('[{"version":"V1","scenario_id":"wrong_active_group","run_id":"edited"}]', encoding="utf-8")

    with (
        patch("invaris.cli.load_dotenv"), patch("invaris.tracing.configure_tracing"),
        patch("invaris.tracing.flush_tracing"), patch("invaris.tracing.shutdown_tracing"),
    ):
        assert cli.main(["evaluate", "--offline", "--approve-sandbox", "--resume-evaluation", str(destination)]) == 2


def test_evaluation_row_validation_rejects_duplicates_and_overcounts():
    row = {"version": "V1", "scenario_id": "wrong_active_group", "run_id": "same"}
    with pytest.raises(ValueError, match="unique"):
        cli._validate_evaluation_rows([row, dict(row)], SCENARIOS[:-1], 2)
    with pytest.raises(ValueError, match="more attempts"):
        cli._validate_evaluation_rows([row, {**row, "run_id": "other"}], SCENARIOS[:-1], 1)
