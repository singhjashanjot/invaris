import json
import threading
import urllib.error
import urllib.request

import pytest

from invaris.console import ConsoleServer, ConsoleState, serve_console
from invaris.evidence import build_manifest

RUN = "11111111-1111-1111-1111-111111111111"


@pytest.fixture
def state(tmp_path, monkeypatch):
    (tmp_path / "compose.yaml").write_text("services: {}", encoding="utf-8")
    monkeypatch.setenv("NEATLOGS_API_KEY", "configured-sensitive-key-123")
    (tmp_path / ".env").write_text("private-value-never-serve", encoding="utf-8")
    evidence = tmp_path / "docs" / "evidence"
    evidence.mkdir(parents=True)
    (evidence / "proof.json").write_text(json.dumps({"checked": True}), encoding="utf-8")
    return ConsoleState(tmp_path)


@pytest.fixture
def console(state):
    server = ConsoleServer(state, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    yield server, base
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)


def request(base, path, *, method="GET", body=None, headers=None):
    payload = json.dumps(body).encode() if body is not None else None
    values = {"Content-Type": "application/json", **(headers or {})}
    operation = urllib.request.Request(base + path, data=payload, headers=values, method=method)
    try:
        response = urllib.request.urlopen(operation, timeout=3)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        content = response.read()
        return response.status, response.headers, json.loads(content)


def make_run(state):
    directory = state.root / "artifacts" / "runs" / RUN
    directory.mkdir(parents=True)
    row = {"run_id": RUN, "scenario_id": "one_shot_action_failure", "version": "V2",
           "status": "VERIFIED", "evaluator_status": "VERIFIED", "verified": True, "model_calls": 3, "tool_calls": 4,
           "metadata": {"mode": "live-model", "trace_id": "a" * 32,
                        "artifact_directory": "never-expose-private-directory"}}
    bundle = {"agent": {"status": "VERIFIED", "reason": "checked", "model_claim": "configured-sensitive-key-123"},
              "events": [{"name": "restart_service", "receipt": {"ok": False, "error": "seeded"}}],
              "rollback": {"attempted": True, "verified": True},
              "independent_verification": {"verified": True}}
    for name, value in (("result.json", row), ("bundle.json", bundle)):
        (directory / name).write_text(json.dumps(value), encoding="utf-8")
    (directory / "manifest.json").write_text(json.dumps(build_manifest(directory, ("result.json", "bundle.json"))), encoding="utf-8")
    return directory


def test_bootstrap_uses_actual_runs_and_redacts_private_metadata(state, console):
    make_run(state)
    _, base = console
    status, headers, payload = request(base, "/api/bootstrap")
    assert status == 200
    assert payload["runs"][0]["id"] == RUN
    assert payload["runs"][0]["trace_coverage"] == "not-checked"
    assert payload["fixture"] == {"project": "invaris-console", "ready": False}
    assert headers["Cache-Control"] == "no-store"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert "never-expose-private-directory" not in json.dumps(payload)
    assert "configured-sensitive-key-123" not in json.dumps(payload)


def test_detail_preserves_failure_and_rollback_without_credentials(state, console):
    make_run(state)
    _, base = console
    status, _, detail = request(base, "/api/runs/" + RUN)
    assert status == 200
    assert detail["events"][0]["receipt"]["ok"] is False
    assert detail["rollback"]["verified"] is True
    assert detail["artifact_integrity"] == {"integrity_valid": True, "authenticity_verified": False}
    assert detail["agent"]["final_response"] == "[REDACTED]"


@pytest.mark.parametrize("path", ["/.env", "/api/evidence/.env", "/api/evidence/docs/evidence/../../.env", "/api/runs/../../.env"])
def test_private_paths_are_never_served(console, path):
    _, base = console
    status, _, payload = request(base, path)
    assert status == 404
    assert "private-value-never-serve" not in json.dumps(payload)


def test_public_evidence_is_allowlisted(console):
    _, base = console
    assert request(base, "/api/evidence/docs/evidence/proof.json")[2] == {"checked": True}


def test_integrations_without_markdown_have_no_dangling_evidence_or_review_claim(state):
    index_path = state.root / "docs/evidence/hackathon-proof-index.json"
    index_path.write_text(json.dumps({"integrations": [
        {"id": "neatlogs", "evidence_paths": ["docs/evidence/proof.json", "docs/trace-audit.md"]},
        {"id": "entire", "evidence_paths": ["docs/evidence/proof.json"]},
        {"id": "cfo", "status": "shared_plan_reviewed_local_reconciliation",
         "headline": "Reviewed plan", "evidence_paths": ["business/cfo-review.md", "docs/evidence/proof.json"]},
    ]}), encoding="utf-8")
    integrations = state.integrations()
    assert all(path in state.evidence_paths for item in integrations for path in item["evidence_paths"])
    cfo = next(item for item in integrations if item["id"] == "cfo")
    assert cfo["status"] == "local_reconciliation_only"
    assert "review record is absent" in cfo["headline"]


def cfo_review_record():
    return {
        "schema": "invaris.cfo-browser-review/v1",
        "review_status": "reviewed",
        "source": "shared_browser",
        "share_url": "https://cfo.ai/s/aMAZiEnSXtphYplP",
        "reviewed_at": "2026-10-12T04:38:00+05:30",
        "pages": ["Costs & Unit Economics", "Team & Payroll", "P&L Burn Runway", "Assumptions",
                  "Revenue & Customers", "Invaris Plan Overview"],
        "scenario": "Main Scenario",
        "scenario_months": 39,
        "scope": "Visible browser review only; no API/export/formula audit or shared-model update.",
    }


def test_browser_review_record_enables_cfo_status_without_markdown(state):
    path = state.root / "business/cfo-browser-review-oct12.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(cfo_review_record()), encoding="utf-8")
    state.evidence_paths = state._evidence_allowlist()

    cfo = next(item for item in state.integrations() if item["id"] == "cfo")
    assert state._cfo_review_available() is True
    assert cfo["status"] == "shared_plan_reviewed_local_reconciliation"
    assert "business/cfo-browser-review-oct12.json" in cfo["evidence_paths"]
    assert "business/cfo-review.md" not in cfo["evidence_paths"]


@pytest.mark.parametrize("change", [
    {"schema": "unrecognized/v9"}, {"share_url": "https://cfo.ai/s/other"},
    {"review_status": "pending"}, {"pages": ["Costs & Unit Economics"]},
    {"scenario_months": 0}, {"scenario_months": True}, {"scope": "API audit and model update"},
    {"reviewed_at": "not-a-date"}, {"reviewed_at": "2026-10-12T04:38:00"},
])
def test_invalid_browser_review_record_downgrades_cfo(state, change):
    path = state.root / "business/cfo-browser-review-oct12.json"
    path.parent.mkdir(parents=True)
    record = cfo_review_record()
    record.update(change)
    path.write_text(json.dumps(record), encoding="utf-8")

    cfo = next(item for item in state.integrations() if item["id"] == "cfo")
    assert state._cfo_review_available() is False
    assert cfo["status"] == "local_reconciliation_only"
    assert "business/cfo-browser-review-oct12.json" not in cfo["evidence_paths"]


def test_bootstrap_reports_browser_review_without_markdown(state):
    path = state.root / "business/cfo-browser-review-oct12.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(cfo_review_record()), encoding="utf-8")
    assert state.bootstrap()["business"]["review_available"] is True


def test_local_markdown_evidence_remains_available(state):
    review = state.root / "business/cfo-review.md"
    review.parent.mkdir(parents=True)
    review.write_text("Reviewed locally", encoding="utf-8")
    state.evidence_paths = state._evidence_allowlist()
    assert "business/cfo-review.md" in state.evidence_paths


def test_rebinding_host_and_cross_site_bootstrap_are_rejected(console):
    _, base = console
    assert request(base, "/api/bootstrap", headers={"Host": "attacker.example"})[0] == 403
    assert request(base, "/api/bootstrap", headers={"Sec-Fetch-Site": "cross-site"})[0] == 403


@pytest.mark.parametrize("changes", [{}, {"Origin": "https://attacker.example"}, {"X-Invaris-Session": "wrong"}])
def test_action_requires_same_origin_session(console, state, changes):
    _, base = console
    headers = {"Origin": base, "X-Invaris-Session": state.session_token}
    if not changes:
        headers = {}
    else:
        headers.update(changes)
    assert request(base, "/api/jobs", method="POST", body={"action": "setup", "approved": True}, headers=headers)[0] == 403
    assert state.jobs == []


def test_action_requires_explicit_approval(console, state):
    _, base = console
    headers = {"Origin": base, "X-Invaris-Session": state.session_token}
    assert request(base, "/api/jobs", method="POST", body={"action": "setup"}, headers=headers)[0] == 403
    assert state.jobs == []


def test_live_requires_separate_spending_approval(state):
    state.fixture_ready = True
    with pytest.raises(PermissionError, match="paid-model"):
        state.launch({"action": "run", "approved": True, "mode": "live"})
    assert state.jobs == []


@pytest.mark.parametrize("body", [{"action": []}, {"action": "run", "scenario": "shell;delete"}, {"action": "setup", "command": "arbitrary"}, ["setup"]])
def test_payload_cannot_inject_commands(state, body):
    with pytest.raises(ValueError):
        state.launch(body)


def test_run_requires_fixture_setup_and_rejects_concurrency(state):
    with pytest.raises(RuntimeError, match="Prepare"):
        state.launch({"action": "run", "approved": True})
    state.fixture_ready = True
    state.jobs.append({"status": "running"})
    with pytest.raises(RuntimeError, match="already active"):
        state.launch({"action": "run", "approved": True})


def test_valid_job_is_scoped_and_explicit(state, monkeypatch):
    observed = []
    monkeypatch.setattr(state, "_execute", lambda job: observed.append(dict(job)))
    state.fixture_ready = True
    job = state.launch({"action": "run", "scenario": "already_compliant", "mode": "offline", "approved": True})
    state.wait_active()
    assert observed[0]["scenario"] == "already_compliant"
    assert observed[0]["mode"] == "offline"
    assert job["status"] == "queued"


def test_port_validation_prevents_non_operator_bindings(tmp_path):
    with pytest.raises(ValueError, match="port"):
        serve_console(tmp_path, 80)


def test_symlinked_json_is_not_read(state, tmp_path):
    from invaris.console import _read_json
    target = tmp_path / "target.json"
    target.write_text('{"secret":"value"}', encoding="utf-8")
    link = tmp_path / "link.json"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("Symlink creation is unavailable")
    assert _read_json(link) == {}


def test_malformed_trace_metadata_does_not_break_detail(state):
    directory = make_run(state)
    row = json.loads((directory / "result.json").read_text(encoding="utf-8"))
    row["metadata"] = None
    (directory / "result.json").write_text(json.dumps(row), encoding="utf-8")
    private = state.root / "artifacts" / "private"
    private.mkdir(parents=True)
    (private / f"trace-readback-{RUN}.json").write_text(json.dumps({"spans": None}), encoding="utf-8")
    (state.root / "docs/evidence/neatlogs-oct12-coverage.json").write_text(
        json.dumps({"records": [{"run_id": RUN, "audit": None}]}), encoding="utf-8")
    detail = state.run_detail(RUN)
    assert detail["trace"]["id"] is None
    assert detail["trace"]["spans"] == []
    assert detail["trace_audit"] is None
    assert detail["artifact_integrity"]["integrity_valid"] is False


def test_trace_view_uses_only_structural_saved_readback(state):
    make_run(state)
    private = state.root / "artifacts" / "private"
    private.mkdir(parents=True)
    (private / f"trace-readback-{RUN}.json").write_text(json.dumps({"spans": [
        {"span_id": "span-1", "parent_span_id": "root", "status": "ERROR",
         "span_metadata": {"node_name": "restart_service", "node_type": "TOOL"},
         "input": "private-model-prompt", "output": "private-model-response"}]}), encoding="utf-8")
    detail = state.run_detail(RUN)
    assert detail["trace"]["spans"][0]["status"] == "ERROR"
    assert detail["trace"]["spans"][0]["name"] == "restart_service"
    assert "private-model" not in json.dumps(detail)


def test_fixture_setup_does_not_require_paid_model_consent(state, monkeypatch):
    monkeypatch.setattr(state, "_execute", lambda job: None)
    job = state.launch({"action": "setup", "mode": "live", "approved": True})
    state.wait_active()
    assert job["action"] == "setup"


def test_frontend_routes_and_assets_are_served_without_starting_jobs(console, state):
    _, base = console
    for path, content_type in (("/", "text/html"), ("/app/workflows", "text/html"),
                               ("/app.js", "application/javascript"), ("/scene.js", "application/javascript"),
                               ("/styles.css", "text/css"), ("/design.css", "text/css")):
        with urllib.request.urlopen(base + path, timeout=3) as response:
            assert response.status == 200
            assert response.headers["Content-Type"].startswith(content_type)
            assert response.read()
    assert state.jobs == []


def test_execution_invokes_only_the_owned_bounded_cli(state, monkeypatch):
    import io

    from invaris import console as console_module

    observed = []

    class FakeProcess:
        stdout = io.StringIO(
            '{"tool":"restart_service","ok":false,"error":"seeded"}\nprivate raw output\n')

        def __init__(self, command, **kwargs):
            observed.append((command, kwargs))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def wait(self):
            return 0

    monkeypatch.setattr(console_module.subprocess, "Popen", FakeProcess)
    state.fixture_ready = True
    state.launch({"action": "run", "scenario": "one_shot_action_failure",
                  "mode": "live", "approved": True, "acknowledge_spend": True})
    state.wait_active()
    command, options = observed[0]
    assert command[1:3] == ["-m", "invaris"]
    assert command[command.index("--project") + 1] == "invaris-console"
    assert "--approve-sandbox" in command
    assert "--offline" not in command
    assert "--reset-spend" not in command
    assert options.get("shell", False) is False
    assert state.jobs[0]["status"] == "succeeded"
    assert state.jobs[0]["events"] == [{"tool": "restart_service", "ok": False, "group": None, "error": "seeded"}]
    assert "private raw output" not in json.dumps(state.jobs)
