import json
from pathlib import Path


def test_dependency_inventory_matches_locked_versions():
    root = Path(__file__).resolve().parents[1]
    locked = {}
    for line in (root / "requirements.lock").read_text(encoding="utf-8").splitlines():
        if "==" in line and not line.startswith("#"):
            name, version = line.split("==", 1)
            locked[name.lower().replace("_", "-")] = version
    inventory = json.loads((root / "docs" / "dependency-inventory.json").read_text(encoding="utf-8"))
    recorded = {row["name"].lower().replace("_", "-"): row["version"] for row in inventory["packages"]}
    assert recorded == locked
    assert inventory["legal_clearance"] is False
    assert all(row["declared_license"] or row["review_required"] for row in inventory["packages"])
