import importlib.util
import json
import subprocess
import sys
import types
import uuid
from pathlib import Path

import pytest


@pytest.fixture
def control(tmp_path, monkeypatch):
    source = Path(__file__).parents[1] / "fixture" / "control.py"
    name = f"fixture_control_{uuid.uuid4().hex}"
    monkeypatch.setitem(sys.modules, "fcntl", types.SimpleNamespace(LOCK_EX=1, LOCK_UN=2, flock=lambda *_: None))
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path / "work")
    monkeypatch.setattr(module, "PKI", tmp_path / "pki")
    monkeypatch.setattr(module, "TRUST", tmp_path / "trust")
    module.ROOT.mkdir()
    module.PKI.mkdir()
    module.TRUST.mkdir()
    monkeypatch.setattr(module.os, "chown", lambda *_: None, raising=False)
    monkeypatch.setattr(module, "running", lambda _pid: True)
    monkeypatch.setattr(module, "stop_server", lambda _state: None)

    def start_server(state, config):
        state.update(pid=1234, loaded_config=config, loaded_digest=module.digest(config))
        module.write_json(module.ROOT / "state.json", state)
        return state

    monkeypatch.setattr(module, "start_server", start_server)
    return module


def test_initialize_reuses_valid_certificates_without_ca_key_and_removes_stale_key(control, monkeypatch):
    for name in ("ca.crt", "server.crt", "server.key", "ca.key"):
        (control.PKI / name).write_text(name, encoding="utf-8")
    stale = control.TRUST / "stale"
    stale.mkdir()
    (stale / "old.crt").write_text("old", encoding="utf-8")
    calls = []
    trust_modes = []
    original_chmod = control.os.chmod

    def record_chmod(path, mode):
        if Path(path) == control.TRUST / "ca.crt":
            trust_modes.append(mode)
        original_chmod(path, mode)

    def successful_check(command, **_kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(control.subprocess, "run", successful_check)
    monkeypatch.setattr(control.os, "chmod", record_chmod)
    control.initialize()

    assert len(calls) == 2
    assert not (control.PKI / "ca.key").exists()
    assert sorted(path.name for path in control.TRUST.iterdir()) == ["ca.crt"]
    assert (control.TRUST / "ca.crt").read_text(encoding="utf-8") == "ca.crt"
    assert trust_modes == [0o644]


def test_initialize_generates_ca_key_restrictively_then_deletes_it(control, monkeypatch):
    ownership = []
    monkeypatch.setattr(control.os, "chown", lambda path, uid, gid: ownership.append((Path(path), uid, gid)))
    generated_modes = []
    original_chmod = control.os.chmod

    def record_chmod(path, mode):
        if Path(path) == control.PKI / "ca.key":
            generated_modes.append(mode)
        original_chmod(path, mode)

    monkeypatch.setattr(control.os, "chmod", record_chmod)

    def generate(command, **_kwargs):
        if "-keyout" in command:
            key_path = Path(command[command.index("-keyout") + 1])
            key_path.write_text("private", encoding="utf-8")
            if key_path.name == "ca.key":
                Path(command[command.index("-out") + 1]).write_text("ca", encoding="utf-8")
            else:
                Path(command[command.index("-out") + 1]).write_text("csr", encoding="utf-8")
        elif "-CAkey" in command:
            Path(command[command.index("-out") + 1]).write_text("server cert", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(control.subprocess, "run", generate)
    control.initialize()

    assert not (control.PKI / "ca.key").exists()
    assert generated_modes == [0o600]
    assert (control.PKI / "ca.key", 0, 0) in ownership
    assert (control.PKI / "server.key").exists()
    assert (control.TRUST / "ca.crt").read_text(encoding="utf-8") == "ca"


def test_initialize_removes_ca_key_when_leaf_issuance_fails(control, monkeypatch):
    def fail_leaf_issue(command, **kwargs):
        if "-keyout" in command:
            Path(command[command.index("-keyout") + 1]).write_text("private", encoding="utf-8")
            Path(command[command.index("-out") + 1]).write_text("generated", encoding="utf-8")
        if "-CAkey" in command:
            raise subprocess.CalledProcessError(1, command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(control.subprocess, "run", fail_leaf_issue)

    with pytest.raises(subprocess.CalledProcessError):
        control.initialize()

    assert not (control.PKI / "ca.key").exists()


def test_restore_preserves_disk_and_runtime_snapshot(control):
    control.reset("disk_runtime_mismatch")
    control.write_json(control.ROOT / "config.json", {"group": "X25519"})

    result = control.operate("restore", None, None)

    assert result["config"] == {"group": "X25519MLKEM768"}
    assert result["loaded_config"] == {"group": "X25519"}
    assert result["config_digest"] != result["loaded_digest"]
    assert result["rollback"] is True


def test_reset_already_compliant_keeps_disk_and_runtime_equal(control):
    result = control.reset("already_compliant")

    assert result["ok"] is True
    assert control.read_json(control.ROOT / "config.json") == {"group": "X25519MLKEM768"}
    state = control.read_json(control.ROOT / "state.json")
    assert state["loaded_config"] == {"group": "X25519MLKEM768"}


def test_seeded_restart_fails_once_then_starts(control):
    control.reset("one_shot_action_failure")

    first = control.operate("restart", None, None)
    second = control.operate("restart", None, None)

    assert first == {"ok": False, "error": "seeded_one_shot_restart_failure", "retryable": True}
    assert second["running"] is True
    assert second["restart_attempts"] == 2


def test_malformed_config_never_launches_server(control, monkeypatch):
    state = {"instance_id": "test", "loaded_config": {"group": "X25519"}, "restart_attempts": 0}
    control.write_json(control.ROOT / "state.json", state)
    (control.ROOT / "config.json").write_text("{invalid", encoding="utf-8")
    launches = []
    monkeypatch.setattr(control, "start_server", lambda *_: launches.append(True))
    monkeypatch.setattr(control, "stop_server", lambda *_: launches.append("stop"))

    with pytest.raises(json.JSONDecodeError):
        control.operate("restart", None, None)

    assert launches == []


@pytest.mark.parametrize("command", ["stage", "apply", "restart", "restore"])
def test_mutation_refuses_stale_approval_inside_lock(control, monkeypatch, command):
    control.reset("wrong_active_group")
    (control.ROOT / "control.lock").touch()
    before = {path.name: path.read_bytes() for path in control.ROOT.iterdir() if path.is_file()}
    mutations = []
    monkeypatch.setattr(control, "start_server", lambda *_: mutations.append("start"))
    monkeypatch.setattr(control, "stop_server", lambda *_: mutations.append("stop"))
    result = control.operate(command, "X25519MLKEM768", None, "stale-instance")
    after = {path.name: path.read_bytes() for path in control.ROOT.iterdir() if path.is_file()}
    assert result["ok"] is False
    assert "approval invalidated" in result["error"]
    assert before == after
    assert mutations == []


@pytest.mark.parametrize("command", ["stage", "apply", "restart"])
def test_candidate_digest_is_checked_before_any_mutation(control, monkeypatch, command):
    reset = control.reset("wrong_active_group")
    control.write_json(control.ROOT / "candidate.json", {"group": "X25519"})
    (control.ROOT / "control.lock").touch()
    before = {path.name: path.read_bytes() for path in control.ROOT.iterdir() if path.is_file()}
    transitions = []
    monkeypatch.setattr(control, "start_server", lambda *_: transitions.append("start"))
    monkeypatch.setattr(control, "stop_server", lambda *_: transitions.append("stop"))
    result = control.operate(command, "X25519", None, reset["instance_id"], control.digest({"group": "X25519MLKEM768"}))
    after = {path.name: path.read_bytes() for path in control.ROOT.iterdir() if path.is_file()}
    assert result["ok"] is False
    assert "candidate_digest_mismatch" in result["error"]
    assert before == after
    assert transitions == []


@pytest.mark.parametrize("config", [{"group": "X25519", "extra": True}, {"group": []}, {}, {"group": "unapproved"}])
def test_invalid_restart_config_does_not_stop_running_service(control, monkeypatch, config):
    control.reset("wrong_active_group")
    control.write_json(control.ROOT / "config.json", config)
    transitions = []
    monkeypatch.setattr(control, "stop_server", lambda *_: transitions.append("stop"))
    monkeypatch.setattr(control, "start_server", lambda *_: transitions.append("start"))
    with pytest.raises(ValueError):
        control.operate("restart", None, None)
    assert transitions == []


def test_control_cli_forwards_approval_identity_and_digest(control, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(control, "operate", lambda *arguments: calls.append(arguments) or {"ok": True})
    monkeypatch.setattr(sys, "argv", ["control.py", "restart", "--expected-instance", "owned", "--expected-candidate", "target"])
    control.main()
    assert calls == [("restart", None, None, "owned", "target")]
    assert json.loads(capsys.readouterr().out)["ok"] is True
