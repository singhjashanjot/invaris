import shutil
import subprocess
from pathlib import Path

import pytest


def test_frontend_smoke():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the frontend smoke test")

    script = Path(__file__).with_name("frontend_smoke.cjs")
    result = subprocess.run([node, str(script)], capture_output=True, text=True, check=False, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
