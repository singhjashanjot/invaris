import pytest

from invaris.evidence import (
    build_manifest,
    content_sha256,
    implementation_snapshot,
    redact_secrets,
    validate_evidence,
    verify_manifest,
)


def test_receipt_revisions_and_freshness_are_checked():
    bundle = {
        "revisions": {"candidate": "c2", "baseline": "c1"},
        "receipts": {
            "candidate": {"revision": "c2"},
            "probe": {"candidate_revision": "old", "fresh": False},
            "application": {"candidate_revision": "c2"},
            "rollback": {"candidate_revision": "c1"},
        },
        "integrations": {"Neatlogs": {"status": "unavailable", "evidence": []}},
    }
    result = validate_evidence(bundle)
    assert not result["valid"]
    assert {issue["code"] for issue in result["issues"]} >= {"revision_mismatch", "probe_not_fresh"}
    assert result["integrations"][0]["status"] == "unavailable"


def test_targeted_redaction_and_hash_limitation():
    cleaned = redact_secrets({"message": "Authorization: Bearer abc.def", "api_key": "secret", "ordinary": "visible"})
    assert "abc.def" not in str(cleaned)
    assert cleaned["ordinary"] == "visible"
    assert len(content_sha256("artifact")) == 64


def test_integration_claim_requires_evidence():
    result = validate_evidence({"integrations": {"Entire": {"status": "integrated"}}}, required_receipts=())
    assert any(issue["code"] == "integration_unsubstantiated" for issue in result["issues"])


def test_manifest_detects_changed_and_missing_artifacts(tmp_path):
    artifact = tmp_path / "result.json"
    artifact.write_text("{}", encoding="utf-8")
    manifest = build_manifest(tmp_path, ("result.json",))
    assert verify_manifest(tmp_path, manifest)
    artifact.write_text("changed", encoding="utf-8")
    assert not verify_manifest(tmp_path, manifest)
    artifact.unlink()
    assert not verify_manifest(tmp_path, manifest)


@pytest.mark.parametrize("filename", ["../secret", "..\\secret", "/secret", "", "."])
def test_manifest_rejects_nonlocal_paths(tmp_path, filename):
    with pytest.raises(ValueError):
        build_manifest(tmp_path, (filename,))


def test_manifest_rejects_invalid_schema_and_empty_manifest(tmp_path):
    assert not verify_manifest(tmp_path, {"schema": "other", "files": {}})
    assert not verify_manifest(tmp_path, {"schema": "invaris.evidence-manifest/v1", "files": {}})


def test_implementation_snapshot_excludes_local_credentials():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    snapshot = implementation_snapshot(root)
    assert "src/invaris/agent.py" in snapshot["files"]
    assert "fixture/probe.c" in snapshot["files"]
    assert ".env" not in snapshot["files"]
    assert all(len(entry["sha256_original"]) == 64 for entry in snapshot["files"].values())
