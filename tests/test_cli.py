from invaris.cli import main
from invaris.evaluation import write_json
from invaris.evidence import build_manifest


def test_mutation_requires_explicit_scoped_approval(capsys):
    assert main(["run", "--offline"]) == 2
    assert "approve-sandbox" in capsys.readouterr().out


def test_verify_bundle_checks_hashes_without_starting_fixture(tmp_path, capsys):
    artifact = tmp_path / "result.json"
    artifact.write_text("{}", encoding="utf-8")
    write_json(tmp_path, "manifest.json", build_manifest(tmp_path, ("result.json",)))
    assert main(["verify-bundle", "--directory", str(tmp_path)]) == 0
    assert "\"authenticity_verified\": false" in capsys.readouterr().out
    artifact.write_text("tampered", encoding="utf-8")
    assert main(["verify-bundle", "--directory", str(tmp_path)]) == 1


def test_trace_audit_fails_closed_without_running_fixture(tmp_path, capsys, monkeypatch):
    def unexpected_fixture(*args, **kwargs):
        raise AssertionError("trace audit must not initialize Docker")

    monkeypatch.setattr("invaris.cli.DockerFixture", unexpected_fixture)
    expected = tmp_path / "expected.json"
    readback = tmp_path / "readback.json"
    expected.write_text("{}", encoding="utf-8")
    readback.write_text("{}", encoding="utf-8")
    assert main(["trace-audit", "--expected", str(expected), "--readback", str(readback),
                 "--project-id", "project"]) == 1
    assert '"complete": false' in capsys.readouterr().out


def test_trace_audit_accepts_matching_structural_coverage(tmp_path, capsys):
    expected = {"version": "V2", "model_calls": 1, "tool_calls": 0,
                "metadata": {"trace_id": "a" * 32, "rollback_verified": False}}
    readback = {"_id": "a" * 32, "projectId": "project", "spanCount": 3,
                "llmCalls": 1, "toolCalls": 0, "spans": [
                    {"span_id": "root", "parent_span_id": None,
                     "span_metadata": {"node_name": "invaris.run", "node_type": "workflow"}},
                    {"span_id": "migration", "parent_span_id": "root",
                     "span_metadata": {"node_name": "invaris.migration.V2", "node_type": "workflow"}},
                    {"span_id": "model", "parent_span_id": "migration",
                     "span_metadata": {"node_name": "model", "node_type": "llm"}},
                ]}
    write_json(tmp_path, "expected.json", expected)
    write_json(tmp_path, "readback.json", readback)
    assert main(["trace-audit", "--expected", str(tmp_path / "expected.json"),
                 "--readback", str(tmp_path / "readback.json"), "--project-id", "project"]) == 0
    assert '"complete": true' in capsys.readouterr().out
