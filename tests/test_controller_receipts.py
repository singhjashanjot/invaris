from unittest.mock import Mock

import pytest

from invaris.contracts import MigrationContract, ToolCall
from invaris.controller import Controller


def controller(reply):
    contract = MigrationContract.model_validate({
        "identity": {"instance_id": "owned", "run_id": "run", "candidate_id": "target"},
        "scope": {"endpoint": "local", "allowed_tools": ["inspect_service"]},
        "clients": [{"name": "hybrid"}],
        "approval_candidate_id": "target",
    })
    executor = Mock()
    executor.execute.return_value = reply
    return Controller(contract, executor)


@pytest.mark.parametrize("reply", [{}, {"ok": "true"}, {"ok": 1}, {"ok": True, "fresh": "false"}, {"ok": True, "app_valid": "true"}])
def test_missing_or_coerced_boolean_evidence_fails_closed(reply):
    receipt = controller(reply).execute(ToolCall(id="read", name="inspect_service", arguments={}))
    assert receipt.ok is False
    assert "explicit boolean" in receipt.error


def test_nested_data_cannot_override_failed_action():
    receipt = controller({"ok": False, "error": "write failed", "data": {"ok": True}}).execute(
        ToolCall(id="read", name="inspect_service", arguments={})
    )
    assert receipt.ok is False
    assert receipt.error == "write failed"


def test_application_evidence_must_report_target_group():
    instance = controller({"ok": True})
    from invaris.contracts import ToolReceipt

    receipts = [
        ToolReceipt(tool_call_id="connection", name="probe_connection", ok=True, instance_id="owned",
                    run_id="run", candidate_id="target", probe_kind="connection", fresh=True,
                    observed_group="X25519MLKEM768", data={"disk_config_digest": "target", "loaded_config_digest": "target"}),
        ToolReceipt(tool_call_id="application", name="check_application", ok=True, instance_id="owned",
                    run_id="run", candidate_id="target", probe_kind="application", fresh=True,
                    app_valid=True, observed_group="X25519"),
    ]
    assert instance.verification_gate(receipts) is False
