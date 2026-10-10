from unittest.mock import Mock, patch

import pytest

from invaris.cli import main


@pytest.mark.parametrize(
    ("command", "workflow"),
    [("run", "tls-migration"), ("evaluate", "migration-comparison")],
)
def test_cli_flushes_and_shuts_down_after_failure(command, workflow, capsys):
    fixture = Mock()
    fixture.up.side_effect = RuntimeError("synthetic startup failure")
    lifecycle = Mock()
    with (
        patch("invaris.cli.DockerFixture", return_value=fixture),
        patch("invaris.cli.load_dotenv"),
        patch("invaris.tracing.configure_tracing", lifecycle.configure),
        patch("invaris.tracing.flush_tracing", lifecycle.flush),
        patch("invaris.tracing.shutdown_tracing", lifecycle.shutdown),
    ):
        assert main([command, "--offline", "--approve-sandbox"]) == 2
    lifecycle.configure.assert_called_once_with(workflow_name=workflow)
    assert [entry[0] for entry in lifecycle.mock_calls] == ["configure", "flush", "shutdown"]
    assert "synthetic startup failure" in capsys.readouterr().out


@pytest.mark.parametrize("explicit", [False, True])
def test_artifact_environment_default_and_cli_override(tmp_path, monkeypatch, explicit):
    monkeypatch.setenv("INVARIS_ARTIFACTS", str(tmp_path / "environment"))
    arguments = ["run", "--offline", "--approve-sandbox"]
    expected = tmp_path / "environment"
    if explicit:
        expected = tmp_path / "explicit"
        arguments += ["--artifacts", str(expected)]
    with (
        patch("invaris.cli.DockerFixture"),
        patch("invaris.cli.load_dotenv"),
        patch("invaris.tracing.configure_tracing"),
        patch("invaris.tracing.flush_tracing"),
        patch("invaris.tracing.shutdown_tracing"),
        patch("invaris.cli.run_scenario", return_value={"verified": True}) as run,
    ):
        assert main(arguments) == 0
    assert run.call_args.args[5] == expected.resolve()
