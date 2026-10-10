from __future__ import annotations

import json
from typing import Any


class FixtureSmokeModel:
    label = "OFFLINE_FIXED_REMEDIATION_SCRIPT_NOT_LLM"

    def __init__(self, version: str = "V2") -> None:
        self.version = version
        self.count = 0

    def next(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        receipts = []
        for message in messages:
            if message.get("role") == "tool":
                content = message.get("content")
                receipt = json.loads(content) if isinstance(content, str) else content
                if receipt.get("probe_kind") in {"connection", "application"} and not receipt.get("fresh"):
                    continue
                receipts.append(receipt)
        by_name = {receipt.get("name"): receipt for receipt in receipts}
        self.count += 1
        def call(name: str, arguments: dict | None = None) -> dict:
            return {"tool_calls": [{"id": f"smoke-{self.count}", "name": name, "arguments": arguments or {}}],
                    "content": "Offline smoke-test operation, not a language-model decision.", "usage": {}}
        if "inspect_capabilities" not in by_name:
            return call("inspect_capabilities")
        if by_name["inspect_capabilities"].get("policy_feasible") is False:
            return {"content": "BLOCKED: approved client and group constraints conflict.", "usage": {}}
        if "inspect_service" not in by_name:
            return call("inspect_service")
        inspection = by_name["inspect_service"].get("data", {})
        configured = inspection.get("config", {}).get("group") == "X25519MLKEM768"
        loaded = inspection.get("loaded_config", {}).get("group") == "X25519MLKEM768"
        if not configured and "stage_config_change" not in by_name:
            return call("stage_config_change", {"group": "X25519MLKEM768", "path": "config.json"})
        if "stage_config_change" in by_name and "apply_candidate" not in by_name:
            return call("apply_candidate")
        if self.version == "V1":
            return {"content": "VERIFIED: offline baseline configuration claim only; not independent evidence.", "usage": {}}
        if not loaded or "apply_candidate" in by_name:
            restarts = [receipt for receipt in receipts if receipt.get("name") == "restart_service"]
            if not restarts or not restarts[-1].get("ok"):
                return call("restart_service")
        if "probe_connection" not in by_name:
            return call("probe_connection")
        if not by_name["probe_connection"].get("ok"):
            return {"content": "UNVERIFIED: probe evidence unavailable.", "usage": {}}
        if "check_application" not in by_name:
            return call("check_application")
        return {"content": "VERIFIED: fresh fixture probes complete.", "usage": {}}


class FixedBaselineModel(FixtureSmokeModel):
    """Deterministic remediation baseline for the supported fixture, never an LLM."""

    label = "FIXED_SUPPORTED_REMEDIATION_SCRIPT_NOT_LLM"
    comparison_arm = "Fixed script"

    def __init__(self) -> None:
        super().__init__("V2")
