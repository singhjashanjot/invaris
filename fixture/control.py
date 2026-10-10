from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import signal
import socket
import subprocess
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

ROOT = Path("/work")
PKI = Path("/pki")
TRUST = Path("/trust")
GROUPS = {"X25519", "X25519MLKEM768"}
SCENARIOS = {"wrong_active_group", "disk_runtime_mismatch", "one_shot_action_failure", "already_compliant", "impossible_client_requirement", "missing_probe_evidence", "held_out_config"}


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(config: dict) -> str:
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def validate_config(config: dict) -> dict:
    if not isinstance(config, dict) or set(config) != {"group"} or not isinstance(config["group"], str) or config["group"] not in GROUPS:
        raise ValueError("configuration must contain exactly one supported group")
    return config


@contextmanager
def locked():
    with (ROOT / "control.lock").open("a") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def running(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        stat = Path(f"/proc/{pid}/stat").read_text()
        return stat.split()[2] != "Z"
    except (ProcessLookupError, FileNotFoundError):
        return False


def stop_server(state: dict) -> None:
    pid = state.get("pid")
    if not running(pid):
        return
    command = Path(f"/proc/{pid}/cmdline").read_bytes()
    if b"/opt/openssl/bin/invaris-server" not in command:
        raise RuntimeError("process identity mismatch")
    os.kill(pid, signal.SIGTERM)
    for _ in range(40):
        if not running(pid):
            return
        time.sleep(0.05)
    raise RuntimeError("server did not stop")


def start_server(state: dict, config: dict) -> dict:
    with (ROOT / "server.log").open("ab") as logfile:
        process = subprocess.Popen([
            "/opt/openssl/bin/invaris-server", config["group"], digest(config), state["instance_id"],
            str(PKI / "server.crt"), str(PKI / "server.key"),
        ], stdin=subprocess.DEVNULL, stdout=logfile, stderr=logfile, start_new_session=True)
    state.update(pid=process.pid, loaded_config=config, loaded_digest=digest(config))
    write_json(ROOT / "state.json", state)
    for _ in range(60):
        if not running(process.pid):
            raise RuntimeError("server startup failed")
        try:
            with socket.create_connection(("127.0.0.1", 8443), timeout=0.2):
                return state
        except OSError:
            time.sleep(0.05)
    raise RuntimeError("server readiness timed out")


def initialize() -> dict:
    ROOT.mkdir(exist_ok=True)
    PKI.mkdir(exist_ok=True)
    TRUST.mkdir(exist_ok=True)
    ca_key = PKI / "ca.key"
    complete = all((PKI / name).is_file() for name in ("ca.crt", "server.crt", "server.key"))
    valid = complete and subprocess.run(["openssl", "x509", "-checkend", "86400", "-noout", "-in", str(PKI / "server.crt")], capture_output=True, timeout=10).returncode == 0
    valid = valid and subprocess.run(["openssl", "verify", "-CAfile", str(PKI / "ca.crt"), str(PKI / "server.crt")], capture_output=True, timeout=10).returncode == 0
    if not valid:
        ca_key.unlink(missing_ok=True)
        commands = [
            ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-sha256", "-nodes", "-days", "7", "-subj", "/CN=Invaris Fixture CA", "-keyout", str(ca_key), "-out", str(PKI / "ca.crt")],
            ["openssl", "req", "-new", "-newkey", "rsa:2048", "-nodes", "-subj", "/CN=fixture", "-addext", "subjectAltName=DNS:fixture", "-keyout", str(PKI / "server.key"), "-out", str(PKI / "server.csr")],
            ["openssl", "x509", "-req", "-in", str(PKI / "server.csr"), "-CA", str(PKI / "ca.crt"), "-CAkey", str(ca_key), "-CAcreateserial", "-days", "7", "-sha256", "-copy_extensions", "copy", "-out", str(PKI / "server.crt")],
        ]
        try:
            for index, command in enumerate(commands):
                if index == 0:
                    prior_umask = os.umask(0o077)
                    try:
                        subprocess.run(command, check=True, capture_output=True, timeout=30)
                    finally:
                        os.umask(prior_umask)
                    os.chown(ca_key, 0, 0)
                    os.chmod(ca_key, 0o600)
                else:
                    subprocess.run(command, check=True, capture_output=True, timeout=30)
        finally:
            ca_key.unlink(missing_ok=True)
    else:
        ca_key.unlink(missing_ok=True)
    for directory in (ROOT, PKI):
        os.chown(directory, 10001, 10001)
        for path in directory.iterdir():
            if path.is_file():
                os.chown(path, 10001, 10001)
                os.chmod(path, 0o600 if path.suffix == ".key" else 0o640)
    for path in TRUST.iterdir():
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    os.chown(TRUST, 10001, 10001)
    os.chmod(TRUST, 0o755)
    shutil.copyfile(PKI / "ca.crt", TRUST / "ca.crt")
    os.chown(TRUST / "ca.crt", 10001, 10001)
    os.chmod(TRUST / "ca.crt", 0o644)
    return {"ok": True, "initialized": True}


def reset(scenario: str) -> dict:
    if scenario not in SCENARIOS:
        raise ValueError("unknown scenario")
    prior = read_json(ROOT / "state.json") if (ROOT / "state.json").exists() else {}
    stop_server(prior)
    baseline_group = "X25519MLKEM768" if scenario == "already_compliant" else "X25519"
    active = {"group": baseline_group}
    desired = {"group": "X25519MLKEM768"} if scenario in {"disk_runtime_mismatch", "held_out_config"} else active
    state = {
        "instance_id": str(uuid.uuid4()), "loaded_config": active,
        "restart_failures_remaining": 2 if scenario == "held_out_config" else int(scenario == "one_shot_action_failure"), "probe_missing": scenario == "missing_probe_evidence",
        "snapshot": {"disk_config": desired, "loaded_config": active}, "restart_attempts": 0,
    }
    write_json(ROOT / "config.json", desired)
    write_json(ROOT / "snapshot.json", {"disk_config": desired, "loaded_config": active})
    candidate = ROOT / "candidate.json"
    if candidate.exists():
        candidate.unlink()
    state = start_server(state, active)
    return {"ok": True, "instance_id": state["instance_id"], "baseline_digest": digest(active)}


def inspect() -> dict:
    state = read_json(ROOT / "state.json")
    config = read_json(ROOT / "config.json")
    return {"ok": True, "instance_id": state["instance_id"], "config": config, "config_digest": digest(config),
            "loaded_config": state["loaded_config"], "loaded_digest": state["loaded_digest"],
            "running": running(state.get("pid")), "restart_attempts": state.get("restart_attempts", 0),
            "probe_missing": state.get("probe_missing", False), "runtime": subprocess.check_output(["openssl", "version"], text=True).strip()}


def operate(command: str, group: str | None, scenario: str | None, expected_instance: str | None = None, expected_candidate: str | None = None) -> dict:
    with locked():
        if expected_instance is not None:
            current = read_json(ROOT / "state.json")
            if current.get("instance_id") != expected_instance:
                return {"ok": False, "error": "fixture_instance_changed; approval invalidated"}
        if command == "reset":
            return reset(scenario or "wrong_active_group")
        if command == "inspect":
            return inspect()
        state = read_json(ROOT / "state.json")
        if command == "stage":
            if group not in GROUPS:
                raise ValueError("unsupported group")
            candidate = {"group": group}
            if expected_candidate is not None and digest(candidate) != expected_candidate:
                return {"ok": False, "error": "candidate_digest_mismatch; approval invalidated"}
            write_json(ROOT / "candidate.json", candidate)
            return {"ok": True, "candidate_digest": digest(candidate), "group": group}
        if command == "apply":
            candidate = validate_config(read_json(ROOT / "candidate.json"))
            if expected_candidate is not None and digest(candidate) != expected_candidate:
                return {"ok": False, "error": "candidate_digest_mismatch; approval invalidated"}
            write_json(ROOT / "config.json", candidate)
            return {"ok": True, "config_digest": digest(candidate), "restart_required": state["loaded_digest"] != digest(candidate)}
        if command == "restart":
            config = validate_config(read_json(ROOT / "config.json"))
            if expected_candidate is not None and digest(config) != expected_candidate:
                return {"ok": False, "error": "candidate_digest_mismatch; approval invalidated"}
            state["restart_attempts"] = state.get("restart_attempts", 0) + 1
            if state.get("restart_failures_remaining", 0):
                state["restart_failures_remaining"] -= 1
                write_json(ROOT / "state.json", state)
                return {"ok": False, "error": "seeded_one_shot_restart_failure", "retryable": True}
            stop_server(state)
            start_server(state, config)
            return inspect()
        if command == "restore":
            snapshot = read_json(ROOT / "snapshot.json")
            disk_config = validate_config(snapshot["disk_config"])
            loaded_config = validate_config(snapshot["loaded_config"])
            stop_server(state)
            write_json(ROOT / "config.json", disk_config)
            start_server(state, loaded_config)
            return {**inspect(), "rollback": True}
        raise ValueError("unsupported command")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["initialize", "serve", "reset", "inspect", "stage", "apply", "restart", "restore", "health"])
    parser.add_argument("--group")
    parser.add_argument("--scenario")
    parser.add_argument("--expected-instance")
    parser.add_argument("--expected-candidate")
    args = parser.parse_args()
    try:
        if args.command == "initialize":
            result = initialize()
        elif args.command == "serve":
            signal.signal(signal.SIGCHLD, signal.SIG_IGN)
            with locked():
                reset("wrong_active_group")
            while True:
                time.sleep(1)
        elif args.command == "health":
            with socket.create_connection(("127.0.0.1", 8443), timeout=1):
                result = {"ok": True}
        else:
            result = operate(args.command, args.group, args.scenario, args.expected_instance, args.expected_candidate)
        print(json.dumps(result, sort_keys=True))
    except Exception as error:
        print(json.dumps({"ok": False, "error": type(error).__name__ + ": " + str(error)}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
