from __future__ import annotations

import time
from typing import Any

from .fixture import DockerFixture


def verify_fixture(fixture: DockerFixture, identity: Any, *, impossible_policy: bool = False) -> dict[str, Any]:
    expected = identity.model_dump() if hasattr(identity, "model_dump") else dict(identity)
    current = fixture.control("inspect")
    receipt: dict[str, Any] = {"verified": False, "status": "UNVERIFIED", "observed_at": time.time(),
                               "instance_id": current.get("instance_id"), "expected_identity": expected,
                               "certificate_authentication": "classical RSA fixture CA; no PQ signature claim"}
    if current.get("ok") is not True:
        return {**receipt, "reason": "current fixture inspection failed"}
    if current.get("instance_id") != expected["instance_id"]:
        return {**receipt, "reason": "fixture instance changed"}
    if impossible_policy:
        return {**receipt, "status": "BLOCKED", "policy_conflict_evidence": True,
                "reason": "hybrid-only policy contradicts mandatory classical-only client connectivity"}
    if current.get("probe_missing"):
        return {**receipt, "reason": "seeded probe evidence unavailable; not inferred from configuration"}
    hybrid = fixture.probe()
    classical = fixture.probe("X25519")
    application = hybrid.get("application") or {}
    checks = {
        "connected": hybrid.get("connected") is True,
        "certificate_verified": hybrid.get("verify_ok") is True,
        "fresh_full_handshake": hybrid.get("fresh") is True and hybrid.get("session_reused") is False,
        "protocol": hybrid.get("protocol") == "TLSv1.3",
        "target_group": hybrid.get("observed_group") == "X25519MLKEM768",
        "application": isinstance(application, dict) and application.get("status") == "ok",
        "instance_bound": isinstance(application, dict) and application.get("instance_id") == expected["instance_id"],
        "candidate_bound": isinstance(application, dict) and application.get("candidate_digest") == expected["candidate_id"],
        "active_disk_match": current.get("config_digest") == current.get("loaded_digest") == expected["candidate_id"],
        "strict_classical_rejected": classical.get("connected") is False and classical.get("error") == "handshake_rejected",
    }
    verified = all(checks.values())
    return {**receipt, "status": "VERIFIED" if verified else "FAILED", "verified": verified,
            "checks": checks, "connection": hybrid, "classical_client": classical,
            "reason": "fresh scoped contract verified" if verified else "one or more independent checks failed"}
