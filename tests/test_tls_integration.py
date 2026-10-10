from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

from invaris.fixture import DockerFixture
from invaris.verifier import verify_fixture

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("INVARIS_RUN_INTEGRATION") != "1",
        reason="set INVARIS_RUN_INTEGRATION=1 to run real Docker integration tests",
    ),
]


@pytest.fixture(scope="session")
def docker_fixture() -> DockerFixture:
    fixture = DockerFixture(Path(__file__).resolve().parents[1], f"invaris-tests-{uuid.uuid4().hex}")
    try:
        fixture.build()
        fixture.up()
        yield fixture
    finally:
        try:
            fixture.down(delete_volumes=True)
        finally:
            fixture.close()


def _identity(fixture: DockerFixture, scenario: str) -> dict[str, str]:
    reset = fixture.control("reset", scenario=scenario)
    assert reset["ok"]
    return {
        "instance_id": reset["instance_id"],
        "run_id": str(uuid.uuid4()),
        "candidate_id": fixture.control("inspect")["config_digest"],
    }


def test_ca_signing_key_is_absent_from_fixture_and_probe(docker_fixture: DockerFixture) -> None:
    fixture_check = docker_fixture._command([
        "exec", "-T", "fixture", "python3", "-c",
        "from pathlib import Path; assert not Path('/pki/ca.key').exists()",
    ])
    probe_check = docker_fixture._command([
        "run", "--rm", "--no-deps", "--entrypoint", "python3", "probe", "-c",
        "from pathlib import Path; assert sorted(p.name for p in Path('/pki').iterdir()) == ['ca.crt']",
    ])
    assert fixture_check.returncode == 0, fixture_check.stderr
    assert probe_check.returncode == 0, probe_check.stderr


def test_real_classical_baseline_and_hybrid_verified_migration(docker_fixture: DockerFixture) -> None:
    identity = _identity(docker_fixture, "wrong_active_group")
    baseline = docker_fixture.probe("X25519")
    assert baseline["connected"] is True
    assert baseline["verify_ok"] is True
    assert baseline["observed_group"] == "X25519"
    assert baseline["application"]["status"] == "ok"

    assert docker_fixture.control("stage", group="X25519MLKEM768")["ok"]
    assert docker_fixture.control("apply")["ok"]
    assert docker_fixture.control("restart")["ok"]
    result = verify_fixture(docker_fixture, {**identity, "candidate_id": docker_fixture.control("inspect")["config_digest"]})
    assert result["status"] == "VERIFIED"
    assert result["connection"]["observed_group"] == "X25519MLKEM768"
    assert result["connection"]["verify_ok"] is True
    assert result["connection"]["application"]["status"] == "ok"


def test_strict_classical_client_is_rejected(docker_fixture: DockerFixture) -> None:
    _identity(docker_fixture, "already_compliant")
    result = docker_fixture.probe("X25519")
    assert result["connected"] is False
    assert result["error"] == "handshake_rejected"


def test_wrong_ca_does_not_pass(docker_fixture: DockerFixture) -> None:
    _identity(docker_fixture, "already_compliant")
    result = docker_fixture.probe(ca="/pki/unknown.crt")
    assert result["connected"] is False
    assert result["verify_ok"] is False


def test_stale_disk_runtime_is_not_ready_until_restart(docker_fixture: DockerFixture) -> None:
    identity = _identity(docker_fixture, "disk_runtime_mismatch")
    current = docker_fixture.control("inspect")
    assert current["config_digest"] != current["loaded_digest"]
    assert verify_fixture(docker_fixture, identity)["status"] == "FAILED"

    assert docker_fixture.control("restart")["ok"]
    result = verify_fixture(docker_fixture, identity)
    assert result["status"] == "VERIFIED"


def test_one_shot_action_failure_recovers(docker_fixture: DockerFixture) -> None:
    _identity(docker_fixture, "one_shot_action_failure")
    failed = docker_fixture.control("restart")
    assert failed["ok"] is False
    assert failed["error"] == "seeded_one_shot_restart_failure"

    recovered = docker_fixture.control("restart")
    assert recovered["ok"] is True
    assert recovered["restart_attempts"] == 2


def test_rollback_restores_fresh_baseline(docker_fixture: DockerFixture) -> None:
    _identity(docker_fixture, "wrong_active_group")
    baseline = docker_fixture.control("inspect")
    assert docker_fixture.control("stage", group="X25519MLKEM768")["ok"]
    assert docker_fixture.control("apply")["ok"]
    assert docker_fixture.control("restart")["ok"]
    assert docker_fixture.probe()["observed_group"] == "X25519MLKEM768"

    restored = docker_fixture.control("restore")
    assert restored["ok"] is True
    assert restored["config_digest"] == baseline["config_digest"]
    assert restored["loaded_digest"] == baseline["loaded_digest"]
    baseline_probe = docker_fixture.probe()
    assert baseline_probe["connected"] is True
    assert baseline_probe["verify_ok"] is True
    assert baseline_probe["fresh"] is True
    assert baseline_probe["application"]["candidate_digest"] == baseline["config_digest"]
    assert baseline_probe["observed_group"] == "X25519"


def test_missing_probe_is_unverified(docker_fixture: DockerFixture) -> None:
    identity = _identity(docker_fixture, "missing_probe_evidence")
    result = verify_fixture(docker_fixture, identity)
    assert result["verified"] is False
    assert result["status"] == "UNVERIFIED"
    assert "probe evidence unavailable" in result["reason"]
