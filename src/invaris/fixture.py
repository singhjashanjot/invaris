from __future__ import annotations

import atexit
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

SCENARIOS = (
    "wrong_active_group", "disk_runtime_mismatch", "one_shot_action_failure", "already_compliant",
    "impossible_client_requirement", "missing_probe_evidence", "held_out_config",
)


class FixtureError(RuntimeError):
    pass


class DockerFixture:
    def __init__(self, root: Path, project: str = "invaris-local", timeout: int = 60) -> None:
        self.root = root.resolve()
        if not re.fullmatch(r"invaris-[a-z0-9-]{1,40}", project):
            raise ValueError("project must be a scoped invaris-* identifier")
        if not (self.root / "compose.yaml").is_file():
            raise ValueError("repository compose.yaml not found")
        self.project = project
        self.timeout = timeout
        self._keepalive = None
        if shutil.which("docker"):
            self.prefix = ["docker", "compose", "-p", project, "-f", str(self.root / "compose.yaml")]
        elif os.name == "nt" and shutil.which("wsl"):
            drive = self.root.drive.rstrip(":").lower()
            if not re.fullmatch("[a-z]", drive):
                raise ValueError("WSL bridge requires a local drive workspace")
            linux_root = "/mnt/" + drive + self.root.as_posix()[2:]
            self.prefix = ["wsl", "--", "docker", "compose", "-p", project, "-f", linux_root + "/compose.yaml"]
        else:
            raise FixtureError("Docker Compose is required")

    def _command(self, arguments: list[str], *, timeout: int | None = None) -> subprocess.CompletedProcess:
        if self.prefix[0] == "wsl" and (self._keepalive is None or self._keepalive.poll() is not None):
            self._keepalive = subprocess.Popen(["wsl", "--", "sh", "-c", "read invaris_keepalive"],
                                               stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            atexit.register(self.close)
        result = subprocess.run(self.prefix + arguments, cwd=self.root, capture_output=True, text=True,
                                timeout=timeout or self.timeout, encoding="utf-8", errors="replace", check=False)
        if len(result.stdout) > 1_000_000 or len(result.stderr) > 1_000_000:
            raise FixtureError("fixture output exceeded limit")
        return result

    def close(self) -> None:
        if self._keepalive is not None and self._keepalive.poll() is None:
            if self._keepalive.stdin is not None:
                self._keepalive.stdin.close()
            try:
                self._keepalive.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._keepalive.terminate()
                self._keepalive.wait(timeout=5)

    def build(self) -> None:
        result = self._command(["build", "init"], timeout=1800)
        if result.returncode:
            raise FixtureError("image build failed: " + result.stderr[-2000:])

    def up(self) -> None:
        result = self._command(["up", "-d", "--wait", "fixture"], timeout=120)
        if result.returncode:
            raise FixtureError("fixture startup failed: " + result.stderr[-2000:])

    def down(self, *, delete_volumes: bool = False) -> None:
        args = ["down", "--remove-orphans"]
        if delete_volumes:
            args.append("--volumes")
        result = self._command(args)
        if result.returncode:
            raise FixtureError("owned fixture cleanup failed")

    def control(self, operation: str, **arguments: str) -> dict[str, Any]:
        if operation not in {"inspect", "reset", "stage", "apply", "restart", "restore"}:
            raise ValueError("unsupported fixture operation")
        command = ["exec", "-T", "fixture", "python3", "/opt/invaris/control.py", operation]
        expected_instance = arguments.get("expected_instance_id")
        if expected_instance is not None:
            if not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", expected_instance):
                raise ValueError("invalid expected fixture identity")
            command += ["--expected-instance", expected_instance]
        expected_candidate = arguments.get("expected_candidate_id")
        if expected_candidate is not None:
            if not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", expected_candidate):
                raise ValueError("invalid approved candidate identity")
            command += ["--expected-candidate", expected_candidate]
        if operation == "reset":
            scenario = arguments.get("scenario", "wrong_active_group")
            if scenario not in SCENARIOS:
                raise ValueError("unknown scenario")
            command += ["--scenario", scenario]
        elif operation == "stage":
            group = arguments.get("group", "")
            if group not in {"X25519", "X25519MLKEM768"}:
                raise ValueError("unsupported group")
            command += ["--group", group]
        result = self._command(command)
        try:
            value = json.loads(result.stdout)
        except (json.JSONDecodeError, TypeError) as error:
            raise FixtureError("fixture returned invalid JSON") from error
        if not isinstance(value, dict) or type(value.get("ok")) is not bool:
            raise FixtureError("fixture receipt schema invalid")
        if result.returncode != 0 and value["ok"]:
            raise FixtureError("fixture receipt contradicts failed process exit")
        return value

    def probe(self, group: str = "X25519MLKEM768:X25519", *, ca: str = "/pki/ca.crt") -> dict[str, Any]:
        if group not in {"X25519", "X25519MLKEM768", "X25519MLKEM768:X25519"}:
            raise ValueError("unsupported client group")
        if ca not in {"/pki/ca.crt", "/pki/unknown.crt"}:
            raise ValueError("unapproved certificate path")
        started = time.monotonic()
        result = self._command(["run", "--rm", "--no-deps", "probe", group, ca], timeout=30)
        try:
            value = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise FixtureError("probe returned invalid or missing evidence") from error
        if not isinstance(value, dict):
            raise FixtureError("probe returned non-object evidence")
        if any(type(value.get(field)) is not bool for field in ("connected", "verify_ok")):
            raise FixtureError("probe receipt has invalid boolean evidence")
        if value["connected"]:
            if result.returncode != 0:
                raise FixtureError("successful probe contradicts failed process exit")
            if any(type(value.get(field)) is not bool for field in ("fresh", "session_reused")):
                raise FixtureError("probe receipt has invalid freshness evidence")
            if not isinstance(value.get("application"), dict):
                raise FixtureError("probe receipt lacks application evidence")
        elif result.returncode == 0 or not isinstance(value.get("error"), str) or not value["error"]:
            raise FixtureError("failed probe lacks consistent failure evidence")
        value.update(duration_seconds=time.monotonic() - started, exit_code=result.returncode)
        return value
