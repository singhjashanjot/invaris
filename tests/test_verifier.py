from invaris.verifier import verify_fixture


class ProbeFixture:
    def __init__(self, group="X25519MLKEM768", digest="target", fresh=True):
        self.group = group
        self.digest = digest
        self.fresh = fresh

    def control(self, operation):
        return {"ok": True, "instance_id": "owned", "config_digest": self.digest, "loaded_digest": self.digest}

    def probe(self, group="auto"):
        if group == "X25519":
            return {"connected": False, "error": "handshake_rejected"}
        return {"connected": True, "verify_ok": True, "fresh": self.fresh, "session_reused": False,
                "protocol": "TLSv1.3", "observed_group": self.group,
                "application": {"status": "ok", "instance_id": "owned", "candidate_digest": self.digest}}


IDENTITY = {"instance_id": "owned", "run_id": "run", "candidate_id": "target"}


def test_real_values_required_not_configuration_claim():
    assert verify_fixture(ProbeFixture(), IDENTITY)["verified"]
    assert not verify_fixture(ProbeFixture(group="X25519"), IDENTITY)["verified"]
    assert not verify_fixture(ProbeFixture(digest="stale"), IDENTITY)["verified"]
    assert not verify_fixture(ProbeFixture(fresh=False), IDENTITY)["verified"]


def test_policy_conflict_blocker_is_independent():
    result = verify_fixture(ProbeFixture(), IDENTITY, impossible_policy=True)
    assert result["status"] == "BLOCKED"
    assert result["policy_conflict_evidence"]


def test_failed_inspection_is_not_independent_policy_evidence():
    class FailedInspection(ProbeFixture):
        def control(self, operation):
            return {**super().control(operation), "ok": False}

    result = verify_fixture(FailedInspection(), IDENTITY, impossible_policy=True)
    assert result["status"] == "UNVERIFIED"
    assert result["verified"] is False


def test_transport_failure_does_not_prove_strict_classical_rejection():
    class TransportFailure(ProbeFixture):
        def probe(self, group="auto"):
            if group == "X25519":
                return {"connected": False, "error": "handshake_transport_error"}
            return super().probe(group)

    result = verify_fixture(TransportFailure(), IDENTITY)
    assert result["verified"] is False
    assert result["checks"]["strict_classical_rejected"] is False
