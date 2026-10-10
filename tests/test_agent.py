import json

import pytest

from invaris.agent import Agent, DeterministicOfflineModel
from invaris.contracts import AgentVersion, MigrationContract, ResultStatus
from invaris.state import save_checkpoint


class Executor:
    def __init__(self):
        self.calls = []
        self.probe_result = None
        self.inspection_result = None

    def tool_specs(self):
        return [
            {"name": "probe_connection", "description": "Make a fresh TLS connection", "parameters": {"type": "object", "properties": {}}},
            {"name": "check_application", "description": "Check the application response", "parameters": {"type": "object", "properties": {}}},
            {"name": "inspect_capabilities", "description": "Inspect client and runtime capabilities", "parameters": {"type": "object", "properties": {}}},
            {"name": "inspect_service", "description": "Inspect current fixture identity and digests", "parameters": {"type": "object", "properties": {}}},
            {"name": "stage_config_change", "description": "Stage an approved configuration edit", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}},
        ]

    def execute(self, name, args):
        self.calls.append((name, args))
        identity = {"instance_id": "fixture-1", "run_id": "run-1", "candidate_id": "candidate-1"}
        if name == "inspect_service":
            if self.inspection_result is not None:
                return self.inspection_result
            return {**identity, "ok": True, "data": {"disk_config_digest": "sha256:abc", "loaded_config_digest": "sha256:abc"}}
        if name == "probe_connection":
            if self.probe_result is not None:
                result, self.probe_result = self.probe_result, None
                if isinstance(result, Exception):
                    raise result
                return result
            return {**identity, "ok": True, "probe_kind": "connection", "fresh": True,
                    "observed_group": "X25519MLKEM768",
                    "data": {"disk_config_digest": "sha256:abc", "loaded_config_digest": "sha256:abc"}}
        if name == "inspect_capabilities":
            return {**identity, "ok": True, "policy_feasible": False}
        return {**identity, "ok": True, "probe_kind": "application", "fresh": True, "app_valid": True,
                "observed_group": "X25519MLKEM768"}


def make_contract():
    return MigrationContract.model_validate({
        "identity": {"instance_id": "fixture-1", "run_id": "run-1", "candidate_id": "candidate-1"},
        "clients": [{"name": "supported"}],
        "scope": {"endpoint": "local", "allowed_tools": ["probe_connection", "check_application", "inspect_capabilities", "inspect_service", "stage_config_change"],
                  "writable_paths": ["config.json"]},
        "approval_candidate_id": "candidate-1",
    })


def test_v2_requires_fresh_matching_probe_and_application_evidence():
    executor = Executor()
    model = DeterministicOfflineModel([
        {"tool_calls": [{"id": "1", "name": "probe_connection", "arguments": {}}], "content": "", "usage": {"total_tokens": 1}},
        {"tool_calls": [{"id": "2", "name": "check_application", "arguments": {}}], "content": "", "usage": {"total_tokens": 1}},
        {"tool_calls": [], "content": "done", "usage": {"total_tokens": 1}},
    ])
    result = Agent(make_contract(), executor, model, AgentVersion.V2).run()
    assert result.status == ResultStatus.VERIFIED
    assert model.label in result.reason or result.verification_status == ResultStatus.VERIFIED


def test_v2_does_not_trust_final_model_claim():
    model = DeterministicOfflineModel([{"tool_calls": [], "content": "VERIFIED", "usage": {}}])
    result = Agent(make_contract(), Executor(), model, AgentVersion.V2).run()
    assert result.status == ResultStatus.UNVERIFIED
    assert "DETERMINISTIC_OFFLINE_TEST_MODEL" == model.label


def test_v2_missing_probe_evidence_claim_remains_unverified_after_probe_failure():
    executor = Executor()
    executor.probe_result = {"ok": False, "error": "probe evidence unavailable",
                             "instance_id": "fixture-1", "run_id": "run-1", "candidate_id": "candidate-1"}
    model = DeterministicOfflineModel([
        {"tool_calls": [{"id": "probe", "name": "probe_connection", "arguments": {}}], "content": "", "usage": {}},
        {"tool_calls": [], "content": "UNVERIFIED: fresh probe evidence is unavailable", "usage": {}},
    ])
    result = Agent(make_contract(), executor, model, AgentVersion.V2).run()
    assert result.status == ResultStatus.UNVERIFIED
    assert result.claimed_status == ResultStatus.UNVERIFIED


def test_v1_preserves_claim_separately_from_observed_verification():
    model = DeterministicOfflineModel([{"tool_calls": [], "content": "VERIFIED: migration complete", "usage": {}}])
    result = Agent(make_contract(), Executor(), model, AgentVersion.V1).run()
    assert result.claimed_status == ResultStatus.VERIFIED
    assert result.model_claim == "VERIFIED: migration complete"
    assert result.verification_status == ResultStatus.UNVERIFIED


def test_blocked_claim_needs_independent_infeasibility_receipt():
    model = DeterministicOfflineModel([{"tool_calls": [], "content": "BLOCKED: impossible policy", "usage": {}}])
    result = Agent(make_contract(), Executor(), model, AgentVersion.V2).run()
    assert result.status == ResultStatus.UNVERIFIED
    assert result.claimed_status == ResultStatus.BLOCKED

    model = DeterministicOfflineModel([
        {"tool_calls": [{"id": "cap", "name": "inspect_capabilities", "arguments": {}}], "content": "", "usage": {}},
        {"tool_calls": [], "content": "BLOCKED: unsupported client requirement", "usage": {}},
    ])
    result = Agent(make_contract(), Executor(), model, AgentVersion.V2).run()
    assert result.status == ResultStatus.BLOCKED


@pytest.mark.parametrize("content, expected", [
    ("VERIFIED: complete", ResultStatus.VERIFIED),
    ("BLOCKED: infeasible", ResultStatus.BLOCKED),
    ("UNVERIFIED: missing evidence", ResultStatus.UNVERIFIED),
    ("FAILED: action failed", ResultStatus.FAILED),
    (" BLOCKED: infeasible", ResultStatus.BLOCKED),
    ("  VERIFIED: complete", ResultStatus.VERIFIED),
    ("   UNVERIFIED: missing evidence", ResultStatus.UNVERIFIED),
    ("\n---\n\n**BLOCKED:**\npolicy cannot be met", ResultStatus.BLOCKED),
    ("### BLOCKED: unsupported policy", ResultStatus.BLOCKED),
    ("## **FAILED:** action failed", ResultStatus.FAILED),
    ("  ### **BLOCKED:** unsupported policy", ResultStatus.BLOCKED),
])
def test_claimed_status_accepts_first_line_status_forms(content, expected):
    assert Agent._claimed_status(content) == expected


@pytest.mark.parametrize("content", [
    "The result is BLOCKED: infeasible",
    "> BLOCKED: quoted claim",
    "A heading\n\nBLOCKED: later paragraph",
    "First paragraph\n\nVERIFIED: later paragraph",
    "```text\nBLOCKED: code sample\n```",
    "---\n\n\nQuoted or ordinary text before status\nBLOCKED: later line",
    "BLOCKEDLY: not a status token",
    ("\tBLOCKED: tab indentation"),
    ("    BLOCKED: code indentation"),
    ("    ### **BLOCKED:** indented heading"),
])
def test_claimed_status_rejects_nonleading_or_embedded_status(content):
    assert Agent._claimed_status(content) is None


def test_formatted_blocked_status_still_requires_infeasibility_receipt():
    content = "\n---\n\n**BLOCKED:**\npolicy cannot be met"
    model = DeterministicOfflineModel([
        {"tool_calls": [{"id": "cap", "name": "inspect_capabilities", "arguments": {}}], "content": "", "usage": {}},
        {"tool_calls": [], "content": content, "usage": {}},
    ])
    result = Agent(make_contract(), Executor(), model, AgentVersion.V2).run()
    assert result.status == ResultStatus.BLOCKED
    assert result.claimed_status is None

    model = DeterministicOfflineModel([{"tool_calls": [], "content": content, "usage": {}}])
    result = Agent(make_contract(), Executor(), model, AgentVersion.V2).run()
    assert result.status == ResultStatus.UNVERIFIED
    assert result.claimed_status == ResultStatus.BLOCKED


@pytest.mark.parametrize("content", ["Inspection summary: the client requirements conflict.", "VERIFIED: the migration is complete."])
def test_v2_policy_evidence_stops_before_later_model_status(content):
    model = DeterministicOfflineModel([
        {"tool_calls": [{"id": "cap", "name": "inspect_capabilities", "arguments": {}}], "content": "", "usage": {}},
        {"tool_calls": [], "content": content, "usage": {}},
    ])
    result = Agent(make_contract(), Executor(), model, AgentVersion.V2).run()
    assert result.status == ResultStatus.BLOCKED
    assert result.model_claim is None
    assert next(model._replies)["content"] == content
    assert result.reason == "independent policy evidence shows infeasibility"


def test_v2_infeasibility_cancels_remaining_tools_in_the_same_turn(tmp_path):
    executor = Executor()
    model = DeterministicOfflineModel([
        {"tool_calls": [
            {"id": "cap", "name": "inspect_capabilities", "arguments": {}},
            {"id": "stage", "name": "stage_config_change", "arguments": {"path": "config.json"}},
        ], "content": "", "usage": {}},
    ])
    checkpoint = tmp_path / "checkpoint.json"
    result = Agent(make_contract(), executor, model, AgentVersion.V2, checkpoint_path=checkpoint).run()
    assert result.status == ResultStatus.BLOCKED
    assert executor.calls == [("inspect_capabilities", {})]
    assert len(result.receipts) == 1
    assert json.loads(checkpoint.read_text())["pending_calls"] is None


def test_v2_does_not_infer_blocked_status_from_unstructured_prose_without_evidence():
    model = DeterministicOfflineModel([
        {"tool_calls": [], "content": "Inspection summary: migration appears infeasible.", "usage": {}}
    ])
    result = Agent(make_contract(), Executor(), model, AgentVersion.V2).run()
    assert result.status == ResultStatus.UNVERIFIED


def test_formatted_verified_status_without_probes_remains_unverified():
    model = DeterministicOfflineModel([
        {"tool_calls": [], "content": "\n---\n\n**VERIFIED:** migration complete", "usage": {}}
    ])
    result = Agent(make_contract(), Executor(), model, AgentVersion.V2).run()
    assert result.status == ResultStatus.UNVERIFIED
    assert result.claimed_status == ResultStatus.VERIFIED


def test_v2_rejects_mismatched_identity_or_config_digests():
    executor = Executor()
    executor.probe_result = {"tool_call_id": "ignored", "name": "probe_connection", "ok": True,
        "instance_id": "other-instance", "run_id": "run-1", "candidate_id": "candidate-1",
        "probe_kind": "connection", "fresh": True, "observed_group": "X25519MLKEM768",
        "data": {"disk_config_digest": "sha256:abc", "loaded_config_digest": "sha256:def"}}
    model = DeterministicOfflineModel([
        {"tool_calls": [{"id": "p", "name": "probe_connection", "arguments": {}}], "content": "", "usage": {}},
        {"tool_calls": [{"id": "a", "name": "check_application", "arguments": {}}], "content": "", "usage": {}},
        {"tool_calls": [], "content": "VERIFIED", "usage": {}},
    ])
    result = Agent(make_contract(), executor, model, AgentVersion.V2).run()
    assert result.status == ResultStatus.UNVERIFIED


def test_v2_recovers_after_executor_error_then_verifies():
    executor = Executor()
    executor.probe_result = RuntimeError("transient probe failure")
    model = DeterministicOfflineModel([
        {"tool_calls": [{"id": "p1", "name": "probe_connection", "arguments": {}}], "content": "", "usage": {}},
        {"tool_calls": [{"id": "p2", "name": "probe_connection", "arguments": {}}], "content": "", "usage": {}},
        {"tool_calls": [{"id": "a", "name": "check_application", "arguments": {}}], "content": "", "usage": {}},
        {"tool_calls": [], "content": "VERIFIED", "usage": {}},
    ])
    result = Agent(make_contract(), executor, model, AgentVersion.V2).run()
    assert result.status == ResultStatus.VERIFIED


def test_agent_uses_executor_tool_schemas_and_filters_unapproved_tools():
    executor = Executor()

    class CapturingModel(DeterministicOfflineModel):
        received_tools = None

        def next(self, messages, tools):
            self.received_tools = tools
            return {"tool_calls": [], "content": "", "usage": {}}

    model = CapturingModel([])
    Agent(make_contract(), executor, model, AgentVersion.V2).run()
    assert any(tool["description"] == "Make a fresh TLS connection" for tool in model.received_tools)
    assert all(tool["name"] != "unapproved" for tool in model.received_tools)


def test_live_provider_stub_tool_turns_integrate_with_agent():
    from invaris.providers import OpenAICompatibleProvider

    class StubCompletions:
        def __init__(self, responses):
            self.responses = iter(responses)

        def create(self, **kwargs):
            return next(self.responses)

    def response(content=None, tool_calls=()):
        return {"choices": [{"message": {"content": content, "tool_calls": list(tool_calls)}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 2, "total_tokens": 14}}

    responses = [
        response(tool_calls=[{"id": "probe", "function": {"name": "probe_connection", "arguments": "{}"}}]),
        response(tool_calls=[{"id": "app", "function": {"name": "check_application", "arguments": "{}"}}]),
        response(content="VERIFIED: fresh checks passed"),
    ]
    client = type("Client", (), {"chat": type("Chat", (), {"completions": StubCompletions(responses)})()})()
    provider = OpenAICompatibleProvider("stub-model", client=client, spend_limit_usd="1",
                                        input_usd_per_million="1", output_usd_per_million="2")
    result = Agent(make_contract(), Executor(), provider, AgentVersion.V2).run()
    assert result.status == ResultStatus.VERIFIED
    assert result.model_claim == "VERIFIED: fresh checks passed"


def test_live_provider_missing_usage_stops_before_tool_execution():
    from invaris.providers import OpenAICompatibleProvider

    class StubCompletions:
        def create(self, **kwargs):
            return {"choices": [{"message": {"content": None, "tool_calls": [{
                "id": "probe", "function": {"name": "probe_connection", "arguments": "{}"}
            }]}}], "usage": None}

    client = type("Client", (), {"chat": type("Chat", (), {"completions": StubCompletions()})()})()
    provider = OpenAICompatibleProvider("stub-model", client=client, spend_limit_usd="1",
                                        input_usd_per_million="1", output_usd_per_million="2")
    executor = Executor()
    result = Agent(make_contract(), executor, provider, AgentVersion.V2).run()
    assert result.status == ResultStatus.UNVERIFIED
    assert "usage is missing" in result.reason
    assert executor.calls == []


def test_live_model_malformed_usage_stops_without_coercing_or_executing():
    class LiveModel:
        mode = "live"

        def next(self, messages, tools):
            return {"content": None,
                    "tool_calls": [{"id": "probe", "name": "probe_connection", "arguments": {}}],
                    "usage": {"input_tokens": "12", "output_tokens": None}}

    executor = Executor()
    result = Agent(make_contract(), executor, LiveModel(), AgentVersion.V2).run()
    assert result.status == ResultStatus.UNVERIFIED
    assert "usage is missing or malformed" in result.reason
    assert executor.calls == []


def test_v1_and_v2_share_required_status_prefix_and_approved_summary():
    contract = make_contract()
    expected_prefix = "Start every final response with exactly one status prefix: VERIFIED:, BLOCKED:, UNVERIFIED:, or FAILED:."
    v1_prompt = Agent(contract, Executor(), DeterministicOfflineModel([]), AgentVersion.V1)._instructions()
    v2_prompt = Agent(contract, Executor(), DeterministicOfflineModel([]), AgentVersion.V2)._instructions()
    assert expected_prefix in v1_prompt and expected_prefix in v2_prompt
    assert '"endpoint": "local"' in v1_prompt and '"endpoint": "local"' in v2_prompt
    assert "hidden scenario identifier" in v1_prompt and "hidden scenario identifier" in v2_prompt


def test_checkpoint_resume_inspects_fixture_and_requires_fresh_probes(tmp_path):
    data = make_contract().model_dump(mode="json")
    data["budgets"]["max_steps"] = 5
    contract = MigrationContract.model_validate(data)
    checkpoint = tmp_path / "run.json"
    first = DeterministicOfflineModel([
        {"tool_calls": [{"id": "old-probe", "name": "probe_connection", "arguments": {}}], "content": "", "usage": {}}
    ])
    result = Agent(contract, Executor(), first, AgentVersion.V2, checkpoint_path=checkpoint).run()
    assert result.status == ResultStatus.UNVERIFIED

    continuation = DeterministicOfflineModel([
        {"tool_calls": [{"id": "new-probe", "name": "probe_connection", "arguments": {}}], "content": "", "usage": {}},
        {"tool_calls": [{"id": "new-app", "name": "check_application", "arguments": {}}], "content": "", "usage": {}},
        {"tool_calls": [], "content": "VERIFIED", "usage": {}},
    ])
    resumed = Agent(contract, Executor(), continuation, AgentVersion.V2, checkpoint_path=checkpoint).run(resume=True)
    assert resumed.status == ResultStatus.VERIFIED
    assert all(not receipt.fresh for receipt in resumed.receipts[:1])
    assert any(receipt.fresh and receipt.probe_kind == "connection" for receipt in resumed.receipts)


def test_resume_never_replays_pending_mutation(tmp_path):
    contract = make_contract()
    checkpoint = tmp_path / "pending.json"
    save_checkpoint(checkpoint, {
        "contract": contract.model_dump(mode="json"), "version": "V2",
        "identity": contract.identity.model_dump(mode="json"), "messages": [], "receipts": [],
        "usage": {}, "errors": 0, "calls": 1, "step": 1, "elapsed_seconds": 0,
        "fixture_digest": "sha256:abc",
        "pending_calls": [{"id": "write", "name": "stage_config_change", "arguments": {"path": "config.json"}}],
    })
    executor = Executor()
    result = Agent(contract, executor, DeterministicOfflineModel([]), AgentVersion.V2,
                   checkpoint_path=checkpoint).run(resume=True)
    assert result.status == ResultStatus.UNVERIFIED
    assert executor.calls == [("inspect_service", {})]


def test_resume_rejects_changed_live_fixture_digest(tmp_path):
    contract = make_contract()
    checkpoint = tmp_path / "changed.json"
    save_checkpoint(checkpoint, {
        "contract": contract.model_dump(mode="json"), "version": "V2",
        "identity": contract.identity.model_dump(mode="json"), "messages": [], "receipts": [],
        "usage": {}, "errors": 0, "calls": 0, "step": 1, "elapsed_seconds": 0,
        "fixture_digest": "sha256:old", "pending_calls": None,
    })
    executor = Executor()
    executor.inspection_result = {
        "instance_id": "fixture-1", "run_id": "run-1", "candidate_id": "candidate-1", "ok": True,
        "data": {"disk_config_digest": "sha256:new", "loaded_config_digest": "sha256:new"},
    }
    result = Agent(contract, executor, DeterministicOfflineModel([]), AgentVersion.V2,
                   checkpoint_path=checkpoint).run(resume=True)
    assert result.status == ResultStatus.UNVERIFIED
    assert "digests differ" in result.reason
    assert executor.calls == [("inspect_service", {})]


def test_controller_blocks_out_of_scope_tools_and_paths():
    from invaris.contracts import ToolCall
    from invaris.controller import Controller

    executor = Executor()
    controller = Controller(make_contract(), executor)
    assert not controller.execute(ToolCall(id="x", name="shell", arguments={})).ok
    assert not controller.execute(ToolCall(id="y", name="stage_config_change", arguments={"path": "other.json"})).ok
    assert executor.calls == []
