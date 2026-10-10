import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from invaris.fixture import DockerFixture, FixtureError


def test_unowned_project_rejected():
    with pytest.raises(ValueError):
        DockerFixture(Path.cwd(), project="someone-elses-stack")


def test_unsafe_probe_inputs_rejected():
    fixture = DockerFixture(Path.cwd())
    with pytest.raises(ValueError):
        fixture.probe("X25519; rm -rf /")
    with pytest.raises(ValueError):
        fixture.probe(ca="/pki/server.key")
    with pytest.raises(ValueError):
        fixture.control("shell")


def mocked_fixture(value, exit_code=0):
    fixture = object.__new__(DockerFixture)
    fixture._command = Mock(return_value=SimpleNamespace(stdout=json.dumps(value), returncode=exit_code))
    return fixture


@pytest.mark.parametrize("value,exit_code", [({}, 0), ({"ok": "false"}, 0), ({"ok": True}, 1)])
def test_control_rejects_missing_coerced_or_contradictory_success(value, exit_code):
    with pytest.raises(FixtureError):
        mocked_fixture(value, exit_code).control("inspect")


def test_mutation_carries_approved_identity_to_locked_controller():
    fixture = mocked_fixture({"ok": True})
    fixture.control("restart", expected_instance_id="approved-instance")
    command = fixture._command.call_args.args[0]
    assert command[-2:] == ["--expected-instance", "approved-instance"]


def test_build_uses_quiet_compose_flag():
    fixture = object.__new__(DockerFixture)
    fixture._command = Mock(return_value=SimpleNamespace(stdout="", stderr="", returncode=0))
    fixture.build()
    assert fixture._command.call_args.args[0] == ["build", "--quiet", "init"]


@pytest.mark.parametrize("value,exit_code", [
    ({"connected": "false", "verify_ok": True}, 0),
    ({"connected": True, "verify_ok": True, "fresh": "true", "session_reused": False, "application": {}}, 0),
    ({"connected": True, "verify_ok": True, "fresh": True, "session_reused": False, "application": {}}, 1),
    ({"connected": False, "verify_ok": False, "error": "handshake_rejected"}, 0),
    ({"connected": False, "verify_ok": False}, 1),
])
def test_probe_rejects_malformed_or_contradictory_receipts(value, exit_code):
    with pytest.raises(FixtureError):
        mocked_fixture(value, exit_code).probe()


def test_probe_preserves_transport_failure_without_policy_rejection():
    result = mocked_fixture({"connected": False, "verify_ok": False, "error": "handshake_transport_error"}, 1).probe("X25519")
    assert result["error"] == "handshake_transport_error"
    assert result["exit_code"] == 1
