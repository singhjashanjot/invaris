"""Policy boundary around untrusted model-selected tool calls."""

from __future__ import annotations

import re
from typing import Any

from .contracts import MigrationContract, ToolCall, ToolReceipt


class Controller:
    def __init__(self, contract: MigrationContract, executor: Any) -> None:
        self.contract = contract
        self.executor = executor

    def execute(self, call: ToolCall) -> ToolReceipt:
        if call.name not in self.contract.scope.allowed_tools:
            return ToolReceipt(tool_call_id=call.id, name=call.name, ok=False, error="tool is outside approved scope")
        lowered = call.name.lower()
        if any(word in lowered for word in ("policy", "evaluator", "probe_code", "client_expectation")):
            return ToolReceipt(tool_call_id=call.id, name=call.name, ok=False, error="trusted evaluation and policy are immutable")
        if "restart" in lowered and not self.contract.scope.allow_restart:
            return ToolReceipt(tool_call_id=call.id, name=call.name, ok=False, error="restart is not approved")
        if ("rollback" in lowered or "restore" in lowered) and not self.contract.scope.allow_rollback:
            return ToolReceipt(tool_call_id=call.id, name=call.name, ok=False, error="rollback is not approved")
        paths = [call.arguments[key] for key in ("path", "file", "file_path", "paths", "files")
                 if key in call.arguments]
        if "stage" in lowered and not paths:
            return ToolReceipt(tool_call_id=call.id, name=call.name, ok=False, error="configuration writes require an explicit approved path")
        changes = call.arguments.get("changes")
        if isinstance(changes, dict):
            paths.extend(changes.keys())
        flattened = [item for value in paths for item in (value if isinstance(value, (list, tuple)) else [value])]
        for requested in flattened:
            normalized = str(requested).replace("\\", "/")
            if normalized.startswith("/") or ".." in normalized.split("/"):
                return ToolReceipt(tool_call_id=call.id, name=call.name, ok=False, error="unsafe path")
            if re.search(r"(^|/)(evaluator|policy|probes?)(/|$)", normalized, re.I):
                return ToolReceipt(tool_call_id=call.id, name=call.name, ok=False, error="trusted files are immutable")
            if any(word in lowered for word in ("write", "stage", "change", "apply")):
                if normalized not in self.contract.scope.writable_paths:
                    return ToolReceipt(tool_call_id=call.id, name=call.name, ok=False, error="path is outside approved write scope")
        result = self.executor.execute(call.name, call.arguments)
        if not isinstance(result, dict):
            return ToolReceipt(tool_call_id=call.id, name=call.name, ok=False, error="executor must return a dictionary")
        payload = dict(result)
        payload.pop("tool_call_id", None)
        payload.pop("name", None)
        nested_data = payload.pop("data", {})
        if not isinstance(nested_data, dict):
            return ToolReceipt(tool_call_id=call.id, name=call.name, ok=False, error="receipt data must be a dictionary")
        payload = {**nested_data, **payload}
        known = {key: payload.pop(key) for key in list(payload) if key in {
            "ok", "error", "instance_id", "run_id", "candidate_id", "probe_kind", "fresh", "app_valid", "observed_group", "policy_feasible"
        }}
        if type(known.get("ok")) is not bool or any(
            key in known and known[key] is not None and type(known[key]) is not bool
            for key in ("fresh", "app_valid", "policy_feasible")
        ):
            return ToolReceipt(tool_call_id=call.id, name=call.name, ok=False, error="receipt requires explicit boolean evidence")
        return ToolReceipt(tool_call_id=call.id, name=call.name, data=payload,
                           ok=known["ok"], error=known.get("error"),
                           instance_id=known.get("instance_id"), run_id=known.get("run_id"),
                           candidate_id=known.get("candidate_id"), probe_kind=known.get("probe_kind"),
                           fresh=known.get("fresh") is True, app_valid=known.get("app_valid"),
                           observed_group=known.get("observed_group"), policy_feasible=known.get("policy_feasible"))

    def verification_gate(self, receipts: list[ToolReceipt]) -> bool:
        identity = self.contract.identity
        mutations = [i for i, receipt in enumerate(receipts)
                    if any(word in receipt.name.lower() for word in ("stage", "apply", "restart", "rollback", "restore"))]
        fresh_after_change = max(mutations, default=-1)
        probe = any(i > fresh_after_change and r.ok and r.probe_kind == "connection" and r.fresh
                    and r.instance_id == identity.instance_id and r.run_id == identity.run_id
                    and r.candidate_id == identity.candidate_id and r.observed_group == self.contract.target_group
                    and bool(r.data.get("disk_config_digest"))
                    and r.data.get("disk_config_digest") == r.data.get("loaded_config_digest")
                    for i, r in enumerate(receipts))
        app = any(i > fresh_after_change and r.ok and r.probe_kind == "application" and r.fresh and r.app_valid is True
                  and r.instance_id == identity.instance_id and r.run_id == identity.run_id
                  and r.candidate_id == identity.candidate_id and r.observed_group == self.contract.target_group
                  for i, r in enumerate(receipts))
        return probe and app

    def infeasibility_gate(self, receipts: list[ToolReceipt]) -> bool:
        identity = self.contract.identity
        return any(r.ok and r.name in {"inspect_capabilities", "check_policy"}
                   and r.policy_feasible is False
                   and r.instance_id == identity.instance_id and r.run_id == identity.run_id
                   and r.candidate_id == identity.candidate_id for r in receipts)
