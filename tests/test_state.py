import json

from invaris.state import load_checkpoint, save_checkpoint


def test_checkpoint_is_atomic_json_and_filters_secrets(tmp_path):
    path = tmp_path / "run" / "state.json"
    save_checkpoint(path, {"run_id": "r1", "api_token": "do-not-store", "nested": {"password": "hidden", "ok": 1}})
    assert load_checkpoint(path) == {"run_id": "r1", "nested": {"ok": 1}}
    assert "do-not-store" not in path.read_text()
    assert json.loads(path.read_text())["run_id"] == "r1"
