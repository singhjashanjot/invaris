import pytest
from pydantic import ValidationError

from invaris.contracts import MigrationContract, ResultStatus, ToolCall


def contract_data():
    return {
        "identity": {"instance_id": "fixture-1", "run_id": "run-1", "candidate_id": "candidate-1"},
        "clients": [{"name": "supported"}],
        "scope": {"endpoint": "https://fixture.test", "allowed_tools": ["probe_connection"]},
        "approval_candidate_id": "candidate-1",
    }


def test_contract_requires_fixed_hybrid_group_and_strict_fields():
    with pytest.raises(ValidationError):
        MigrationContract.model_validate({**contract_data(), "target_group": "X25519"})
    with pytest.raises(ValidationError):
        MigrationContract.model_validate({**contract_data(), "unexpected": True})


def test_scope_rejects_parent_paths():
    data = contract_data()
    data["scope"] = {"endpoint": "local", "writable_paths": ["../policy.json"]}
    with pytest.raises(ValidationError):
        MigrationContract.model_validate(data)


def test_budget_requires_finite_positive_duration_and_bounded_cost():
    data = contract_data()
    data["budgets"] = {"max_duration_seconds": 0, "max_cost_usd": 1}
    with pytest.raises(ValidationError):
        MigrationContract.model_validate(data)
    data["budgets"] = {"max_duration_seconds": 10, "max_cost_usd": -1}
    with pytest.raises(ValidationError):
        MigrationContract.model_validate(data)


def test_tool_call_requires_typed_arguments():
    call = ToolCall.model_validate({"id": "t1", "name": "inspect", "arguments": {"depth": 2}})
    assert call.arguments == {"depth": 2}
    assert ResultStatus.VERIFIED.value == "VERIFIED"
