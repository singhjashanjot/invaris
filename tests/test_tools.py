from invaris.tools import MigrationTools


class StubFixture:
    def __init__(self, instance="owned"):
        self.instance = instance
        self.actions = []

    def control(self, operation, **kwargs):
        self.actions.append(operation)
        return {"ok": True, "instance_id": self.instance, "config": {"group": "X25519"}}


def tools(instance="owned"):
    return MigrationTools(StubFixture(instance), {"instance_id": "owned", "run_id": "run", "candidate_id": "digest"})


def test_reject_unknown_and_extra_arguments():
    executor = tools()
    assert not executor.execute("shell", {}).get("ok")
    assert not executor.execute("inspect_service", {"path": "../../secret"}).get("ok")
    assert not executor.execute("stage_config_change", {"group": "X25519"}).get("ok")
    assert executor.fixture.actions == []


def test_reject_changed_instance_before_mutation():
    executor = tools("another-instance")
    assert not executor.execute("restart_service", {}).get("ok")
    assert executor.fixture.actions == ["inspect"]


def test_tool_spec_exact_schemas():
    for spec in tools().tool_specs():
        assert spec["input_schema"]["additionalProperties"] is False


def test_mutation_passes_identity_to_fixture_for_atomic_approval():
    class IdentityFixture(StubFixture):
        def control(self, operation, **kwargs):
            if operation == "restart":
                assert kwargs == {"expected_instance_id": "owned", "expected_candidate_id": "digest"}
                return {"ok": False, "error": "fixture_instance_changed; approval invalidated"}
            return super().control(operation, **kwargs)

    executor = MigrationTools(IdentityFixture(), {"instance_id": "owned", "run_id": "run", "candidate_id": "digest"})
    assert executor.execute("restart_service", {})["ok"] is False


def test_failed_inspection_cannot_authorize_mutation():
    class FailedInspection(StubFixture):
        def control(self, operation, **kwargs):
            assert operation == "inspect"
            return {"ok": False, "instance_id": "owned"}

    executor = MigrationTools(FailedInspection(), {"instance_id": "owned", "run_id": "run", "candidate_id": "digest"})
    assert executor.execute("restart_service", {})["ok"] is False


def test_application_probe_requires_target_group():
    class ProbeFixture(StubFixture):
        def probe(self, group="auto"):
            return {"connected": True, "verify_ok": True, "fresh": True, "session_reused": False,
                    "protocol": "TLSv1.3", "observed_group": "X25519",
                    "application": {"status": "ok", "instance_id": "owned", "candidate_digest": "digest"}}

    result = MigrationTools(ProbeFixture(), {"instance_id": "owned", "run_id": "run", "candidate_id": "digest"}).execute(
        "check_application", {}
    )
    assert result["ok"] is False
    assert result["app_valid"] is False
