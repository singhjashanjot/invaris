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
