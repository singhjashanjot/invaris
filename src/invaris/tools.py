from __future__ import annotations

import hashlib
import json
import sys
import time
from typing import Any

from .fixture import DockerFixture

TOOLS = {
    "inspect_service": ("Read disk and running-service group, configuration digests, runtime and restart count.", {}),
    "inspect_capabilities": ("Check supported group and whether approved client policy is feasible. Never relax policy.", {}),
    "stage_config_change": ("Stage a target group in the approved config.json; does not apply or restart.", {"group": {"type": "string", "enum": ["X25519MLKEM768"]}, "path": {"type": "string", "enum": ["config.json"]}}),
    "apply_candidate": ("Apply the staged config to disk. Running process may still need a restart.", {}),
    "restart_service": ("Restart the owned fixture to load its current on-disk config. Inspect/retry safely on error.", {}),
    "probe_connection": ("Fresh authenticated connection with actual negotiated TLS group; do not infer it from config.", {}),
    "check_application": ("Fresh TLS health request and identity/application checks; also checks strict classical rejection.", {}),
    "restore_snapshot": ("Restore and restart the saved baseline; invalidates migration-readiness evidence.", {}),
    "collect_evidence": ("Return accumulated sanitized action and probe receipts. Does not imply readiness.", {}),
}


class MigrationTools:
    def __init__(self, fixture: DockerFixture, identity: Any, *, impossible_policy: bool = False, tracer: Any = None, verbose: bool = False) -> None:
        self.fixture = fixture
        self.identity = identity
        self.impossible_policy = impossible_policy
        self.tracer = tracer
        self.verbose = verbose
        self.events: list[dict[str, Any]] = []

    def tool_specs(self) -> list[dict[str, Any]]:
        return [{"name": name, "description": description, "input_schema": {"type": "object", "properties": props,
                 "required": list(props), "additionalProperties": False}} for name, (description, props) in TOOLS.items()]

    def _identity(self) -> dict[str, str]:
        return self.identity.model_dump() if hasattr(self.identity, "model_dump") else dict(self.identity)

    def execute(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name not in TOOLS:
            return {"ok": False, "error": "unapproved tool"}
        if not isinstance(args, dict):
            return {"ok": False, "error": "tool arguments must be an object"}
        allowed = {"group", "path"} if name == "stage_config_change" else set()
        if set(args) - allowed or (name == "stage_config_change" and (args.get("group") != "X25519MLKEM768" or args.get("path") != "config.json")):
            return {"ok": False, "error": "arguments outside approved tool schema"}
        started = time.monotonic()
        from .tracing import traced_operation
        with traced_operation(name, "TOOL", {"arguments": args, "identity": self._identity()}) as recorder:
            try:
                current = self.fixture.control("inspect")
                if current.get("ok") is not True:
                    result = {"ok": False, "error": "current fixture inspection failed"}
                elif current.get("instance_id") != self._identity()["instance_id"]:
                    result = {"ok": False, "error": "fixture instance changed; approval and evidence invalidated"}
                else:
                    result = self._execute(name, args, current)
            except Exception as error:
                result = {"ok": False, "error": type(error).__name__ + ": " + str(error)[:500]}
            result = {**self._identity(), **result}
            recorder.set_output(result)
            if not result.get("ok"):
                recorder.set_error(str(result.get("error", "operation failed")))
            self.events.append({"name": name, "arguments": args, "receipt": result,
                                "trace_id": recorder.trace_id, "duration_seconds": time.monotonic() - started})
        if self.verbose:
            from .evidence import redact_secrets
            print(json.dumps(redact_secrets({"tool": name, "ok": result.get("ok"), "group": result.get("observed_group"), "error": result.get("error")})), file=sys.stderr)
        return result

    def _execute(self, name: str, args: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
        expected_instance = self._identity()["instance_id"]
        approved_candidate = self._identity()["candidate_id"]
        if name == "inspect_service":
            inspection = current
            return {"ok": True, "data": {**inspection, "disk_config_digest": inspection.get("config_digest"), "loaded_config_digest": inspection.get("loaded_digest")}}
        if name == "inspect_capabilities":
            return {"ok": True, "policy_feasible": not self.impossible_policy,
                    "data": {"runtime": current.get("runtime"), "supported_groups": ["X25519", "X25519MLKEM768"],
                             "reason": "strict hybrid-only and mandatory classical-only connectivity conflict" if self.impossible_policy else "supported controlled stack"}}
        if name == "stage_config_change":
            return self.fixture.control("stage", group=args["group"], expected_instance_id=expected_instance, expected_candidate_id=approved_candidate)
        if name == "apply_candidate":
            return self.fixture.control("apply", expected_instance_id=expected_instance, expected_candidate_id=approved_candidate)
        if name == "restart_service":
            return self.fixture.control("restart", expected_instance_id=expected_instance, expected_candidate_id=approved_candidate)
        if name == "restore_snapshot":
            return self.fixture.control("restore", expected_instance_id=expected_instance)
        if name in {"probe_connection", "check_application"}:
            if current.get("probe_missing"):
                return {"ok": False, "error": "seeded_missing_probe_evidence", "fresh": False}
            probe = self.fixture.probe()
            application = probe.get("application", {})
            identities_match = isinstance(application, dict) and application.get("instance_id") == current.get("instance_id") and application.get("candidate_digest") == current.get("loaded_digest")
            valid = bool(probe.get("connected") is True and probe.get("verify_ok") is True and probe.get("fresh") is True and probe.get("session_reused") is False and probe.get("protocol") == "TLSv1.3" and probe.get("observed_group") == "X25519MLKEM768" and identities_match)
            app_valid = bool(valid and application.get("status") == "ok")
            data = {**probe, "disk_config_digest": current.get("config_digest"), "loaded_config_digest": current.get("loaded_digest"),
                    "raw_output_digest": hashlib.sha256(json.dumps(probe, sort_keys=True).encode()).hexdigest(), "observed_at": time.time()}
            if name == "check_application":
                classical = self.fixture.probe("X25519")
                data["classical_client"] = classical
                app_valid = app_valid and classical.get("connected") is False and classical.get("error") == "handshake_rejected"
            return {"ok": valid if name == "probe_connection" else app_valid,
                    "candidate_id": application.get("candidate_digest") if isinstance(application, dict) else None,
                    "fresh": valid, "probe_kind": "connection" if name == "probe_connection" else "application",
                    "observed_group": probe.get("observed_group"), "app_valid": app_valid, "data": data}
        return {"ok": True, "data": {"events": list(self.events)}}
