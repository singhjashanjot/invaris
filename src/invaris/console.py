"""Loopback-only operator console for the authorized fixture and saved evidence."""

from __future__ import annotations

import hmac
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import uuid
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from .evidence import redact_secrets, verify_manifest
from .fixture import SCENARIOS

RUN_ID = re.compile(r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$")
ASSETS = Path(__file__).parent / "web"
SCENARIO_DETAILS = {
    "wrong_active_group": ("Classical connection", "Replace a classical-only active configuration and verify fresh hybrid negotiation."),
    "disk_runtime_mismatch": ("Configuration drift", "Resolve the mismatch between configuration on disk and the running service."),
    "one_shot_action_failure": ("Recover from failure", "Encounter a seeded failed action, recover, and independently verify the candidate."),
    "already_compliant": ("Already compliant", "Verify a compatible service without unnecessary mutation."),
    "impossible_client_requirement": ("Conflicting client policy", "Recognize an infeasible client contract and block before mutation."),
    "missing_probe_evidence": ("Missing evidence", "Withhold readiness when a fresh connection cannot be independently verified."),
    "held_out_config": ("Held-out configuration", "Investigate a configuration variant outside the basic seeded setup."),
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _read_json(path: Path) -> dict | list:
    try:
        if path.is_symlink() or path.stat().st_size > 4_000_000:
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, (dict, list)) else {}
    except (OSError, ValueError):
        return {}


class ConsoleState:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        if not (self.root / "compose.yaml").is_file():
            raise ValueError("Console requires the owned fixture repository")
        self.project = "invaris-console"
        self.artifacts = self.root / "artifacts" / "console"
        self.session_token = secrets.token_urlsafe(32)
        self.fixture_ready = False
        self.jobs: list[dict] = []
        self.lock = threading.RLock()
        self.active_thread: threading.Thread | None = None
        self.secret_values = [value for key, value in os.environ.items()
                              if re.search(r"KEY|TOKEN|PASSWORD|SECRET", key, re.I) and len(value) >= 8]
        self.evidence_paths = self._evidence_allowlist()

    def sanitize(self, value: Any) -> Any:
        value = redact_secrets(value)
        if isinstance(value, str):
            for secret in self.secret_values:
                value = value.replace(secret, "[REDACTED]")
            return value[:24000]
        if isinstance(value, dict):
            return {key: self.sanitize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.sanitize(item) for item in value[:1024]]
        return value

    def _evidence_allowlist(self) -> set[str]:
        paths = set()
        for directory in (self.root / "docs" / "evidence", self.root / "business"):
            if directory.is_dir():
                for path in directory.rglob("*"):
                    if path.is_file() and path.suffix in {".json", ".md", ".csv", ".png"}:
                        if path.resolve().is_relative_to(directory.resolve()) and not path.is_symlink():
                            paths.add(path.relative_to(self.root).as_posix())
        for name in ("docs/hackathon-integration-proof.md", "docs/release-validation.md", "docs/trace-audit.md",
                     "docs/neatlogs-tracing.md", "docs/entire-evidence.md", "docs/operations.md"):
            if (self.root / name).is_file():
                paths.add(name)
        return paths

    def _run_directory(self, run_id: str) -> Path | None:
        if not RUN_ID.fullmatch(run_id):
            return None
        for parent in (self.root / "artifacts" / "runs", self.artifacts / "runs"):
            directory = parent / run_id
            if directory.is_dir() and not directory.is_symlink() and directory.resolve().is_relative_to(parent.resolve()):
                return directory
        return None

    def _trace_audits(self) -> dict[str, dict]:
        audits = {}
        for name in ("neatlogs-oct12-coverage.json", "console-validation-oct12.json"):
            coverage = _read_json(self.root / "docs/evidence" / name)
            records = coverage.get("records", []) if isinstance(coverage, dict) else []
            records = records if isinstance(records, list) else []
            audits.update({record["run_id"]: record["audit"] for record in records
                           if isinstance(record, dict) and isinstance(record.get("run_id"), str)
                           and isinstance(record.get("audit"), dict)})
        return audits

    def _summary(self, directory: Path, row: dict, audits: dict) -> dict:
        metadata = row.get("metadata", {})
        metadata = metadata if isinstance(metadata, dict) else {}
        audit = audits.get(directory.name)
        return {
            "id": directory.name, "scenario": row.get("scenario_id", "unknown"),
            "version": row.get("version", "unknown"), "status": row.get("evaluator_status", "UNVERIFIED"),
            "agent_status": row.get("status", "UNVERIFIED"),
            "verified": row.get("verified") is True, "mode": metadata.get("mode", "unknown"),
            "created_at": datetime.fromtimestamp(directory.stat().st_mtime, UTC).isoformat(),
            "cost": row.get("estimated_cost"), "input_tokens": row.get("input_tokens"),
            "output_tokens": row.get("output_tokens"), "duration": row.get("duration_seconds"),
            "trace_id": metadata.get("trace_id"),
            "trace_coverage": "verified" if audit and audit.get("complete") is True else "partial" if audit else "not-checked",
        }

    def runs(self) -> list[dict]:
        directories = []
        for parent in (self.root / "artifacts" / "runs", self.artifacts / "runs"):
            if parent.is_dir():
                directories.extend(directory for directory in parent.iterdir()
                                   if RUN_ID.fullmatch(directory.name) and directory.is_dir() and not directory.is_symlink())
        audits = self._trace_audits()
        result = []
        for directory in sorted(directories, key=lambda path: path.stat().st_mtime, reverse=True)[:300]:
            row = _read_json(directory / "result.json") or _read_json(directory / "invalid-run.json")
            if isinstance(row, dict) and row:
                result.append(self._summary(directory, row, audits))
        return self.sanitize(result)

    def run_detail(self, run_id: str) -> dict | None:
        directory = self._run_directory(run_id)
        if directory is None:
            return None
        row = _read_json(directory / "result.json") or _read_json(directory / "invalid-run.json")
        if not isinstance(row, dict) or not row:
            return None
        bundle = _read_json(directory / "bundle.json")
        bundle = bundle if isinstance(bundle, dict) else {}
        agent = bundle.get("agent", {})
        agent = agent if isinstance(agent, dict) else {}
        manifest = _read_json(directory / "manifest.json")
        audit = self._trace_audits().get(run_id)
        readback = _read_json(self.root / "artifacts/private" / f"trace-readback-{run_id}.json")
        readback = readback if isinstance(readback, dict) else {}
        trace_spans = []
        saved_spans = readback.get("spans", [])
        saved_spans = saved_spans if isinstance(saved_spans, list) else []
        for span in saved_spans[:1024]:
            if isinstance(span, dict):
                metadata = span.get("span_metadata", {})
                metadata = metadata if isinstance(metadata, dict) else {}
                trace_spans.append({"id": span.get("span_id"), "parent": span.get("parent_span_id"),
                                    "name": metadata.get("node_name", span.get("node_name")),
                                    "type": metadata.get("node_type", span.get("node_type")), "status": span.get("status")})
        return self.sanitize({
            "run": self._summary(directory, row, self._trace_audits()),
            "agent": {"status": agent.get("status", row.get("status")),
                      "final_response": agent.get("model_claim"), "reason": agent.get("reason"),
                      "model_calls": row.get("model_calls"), "tool_calls": row.get("tool_calls")},
            "events": bundle.get("events", []),
            "receipts": {key: bundle.get(key, {}) for key in ("independent_verification", "baseline", "final", "contract")},
            "rollback": bundle.get("rollback", {}),
            "artifact_integrity": {"integrity_valid": isinstance(manifest, dict) and verify_manifest(directory, manifest),
                                   "authenticity_verified": False},
            "trace_audit": audit,
            "trace": {"id": self._summary(directory, row, {}).get("trace_id"), "source": "Saved Neatlogs SDK readback",
                      "spans": trace_spans, "complete": audit.get("complete") if audit else None},
        })

    def integrations(self) -> list[dict]:
        index = _read_json(self.root / "docs/evidence/hackathon-proof-index.json")
        entries = index.get("integrations", []) if isinstance(index, dict) else []
        if not isinstance(entries, list) or len(entries) != 3:
            entries = [
            {"id": "neatlogs", "name": "Neatlogs", "status": "verified-scoped", "headline": "Actual application traces verified", "detail": "Every scenario has structural cloud evidence. Two historical traces remain partial; fresh runs are separate. Public CLI OAuth is not claimed.", "evidence_paths": ["docs/evidence/neatlogs-oct12-coverage.json"]},
            {"id": "entire", "name": "Entire", "status": "verified-local", "headline": "Genuine checkpoints and Graph retrieval", "detail": "Local development context is captured and linked to source history. Hosted authentication and automatic hooks are not claimed.", "evidence_paths": ["docs/evidence/entire-oct12-checkpoint.json", "docs/evidence/entire-final-graph.json"]},
            {"id": "cfo", "name": "cfo.ai", "status": "local_reconciliation_only", "headline": "Local inference-cost reconciliation is available; shared business-plan review record is absent.", "detail": "Local inference reconciliation is not an API integration or update to the shared plan.", "evidence_paths": ["business/final-measured-assumptions.json"]},
            ]
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            evidence = entry.get("evidence_paths", [])
            entry["evidence_paths"] = [path for path in evidence if path in self.evidence_paths] if isinstance(evidence, list) else []
            if entry.get("id") == "cfo" and not (self.root / "business/cfo-review.md").is_file():
                entry["status"] = "local_reconciliation_only"
                entry["headline"] = "Local inference-cost reconciliation is available; the shared business-plan review record is absent."
        return self.sanitize(entries)

    def bootstrap(self) -> dict:
        summary = _read_json(self.root / "docs/evidence/final-study-summary.json")
        ledger = _read_json(self.root / "artifacts/private/model-spend.json")
        summary = summary if isinstance(summary, dict) else {}
        ledger = ledger if isinstance(ledger, dict) else {}
        with self.lock:
            jobs = self.sanitize(self.jobs)
        return {
            "session_token": self.session_token,
            "product": {"name": "Invaris", "tagline": "Verified cryptographic change."},
            "scenarios": [{"id": name, "name": SCENARIO_DETAILS[name][0], "description": SCENARIO_DETAILS[name][1]} for name in SCENARIOS],
            "summary": {"latest_study": {"id": summary.get("study_id"), "summaries": summary.get("summaries", {})}},
            "integrations": self.integrations(), "runs": self.runs(), "jobs": jobs,
            "business": {"review_available": (self.root / "business/cfo-review.md").is_file(),
                         "shared_plan_url": "https://cfo.ai/s/aMAZiEnSXtphYplP",
                         "estimated_inference_per_verified_migration": summary.get("summaries", {}).get("V2", {}).get("cost_per_verified_migration"),
                         "forecast_is_hypothesis": True},
            "budget": {key: ledger.get(key) for key in ("authorized_total_usd", "committed_estimate_usd", "billing_guarantee")},
            "fixture": {"project": self.project, "ready": self.fixture_ready},
        }

    def launch(self, request: dict) -> dict:
        if not isinstance(request, dict) or set(request) - {"action", "scenario", "mode", "approved", "acknowledge_spend"}:
            raise ValueError("Invalid action payload")
        action, mode = request.get("action"), request.get("mode", "offline")
        scenario = request.get("scenario", SCENARIOS[0])
        if (not isinstance(action, str) or not isinstance(mode, str) or not isinstance(scenario, str)
                or action not in {"setup", "run"} or mode not in {"offline", "live"} or scenario not in SCENARIOS):
            raise ValueError("Choose a supported action, mode, and scenario")
        if request.get("approved") is not True:
            raise PermissionError("Explicit owned-sandbox approval is required")
        if action == "run" and mode == "live" and request.get("acknowledge_spend") is not True:
            raise PermissionError("Live mode requires explicit paid-model authorization")
        with self.lock:
            if any(job["status"] in {"queued", "running"} for job in self.jobs):
                raise RuntimeError("An owned fixture action is already active")
            if action == "run" and not self.fixture_ready:
                raise RuntimeError("Prepare the owned sandbox before running the agent")
            job = {"id": str(uuid.uuid4()), "action": action, "scenario": scenario, "mode": mode,
                   "status": "queued", "created_at": _now(), "finished_at": None,
                   "message": "Queued for the owned sandbox", "run_id": None, "events": []}
            self.jobs = (self.jobs + [job])[-30:]
            self.active_thread = threading.Thread(target=self._execute, args=(job,), daemon=False)
            self.active_thread.start()
            return dict(job)

    def _execute(self, job: dict) -> None:
        self.artifacts.mkdir(parents=True, exist_ok=True)
        runs_directory = self.artifacts / "runs"
        before = set(runs_directory.iterdir()) if runs_directory.is_dir() else set()
        command = [sys.executable, "-m", "invaris", "--root", str(self.root), "--project", self.project]
        if job["action"] == "setup":
            command.append("setup")
        else:
            command += ["run", "--approve-sandbox", "--version", "V2", "--scenario", job["scenario"],
                        "--artifacts", str(self.artifacts)]
            if job["mode"] == "offline":
                command.append("--offline")
        with self.lock:
            job.update(status="running", message="Preparing the fixture" if job["action"] == "setup" else "Agent executing with bounded tools")
        try:
            with subprocess.Popen(command, cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, encoding="utf-8", errors="replace", bufsize=1,
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)) as process:
                for line in process.stdout:
                    if len(line) > 8192:
                        continue
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(event, dict) and "tool" in event:
                        event = self.sanitize({key: event.get(key) for key in ("tool", "ok", "group", "error")})
                        with self.lock:
                            job["events"] = (job["events"] + [event])[-100:]
                returncode = process.wait()
            if job["action"] == "setup" and returncode == 0:
                self.fixture_ready = True
            if runs_directory.is_dir():
                candidates = [path for path in runs_directory.iterdir() if path not in before and RUN_ID.fullmatch(path.name)]
                if candidates:
                    job["run_id"] = max(candidates, key=lambda path: path.stat().st_mtime).name
            with self.lock:
                job.update(status="succeeded" if returncode == 0 else "failed", finished_at=_now(),
                           message="Action completed; inspect the independent outcome" if returncode == 0 else "Action failed; no readiness claim is implied")
        except Exception as error:
            with self.lock:
                job.update(status="failed", finished_at=_now(), message=f"Action failed: {type(error).__name__}")

    def wait_active(self) -> None:
        if self.active_thread is not None:
            self.active_thread.join()


class ConsoleServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, state: ConsoleState, port: int) -> None:
        self.state = state
        super().__init__(("127.0.0.1", port), ConsoleHandler)


class ConsoleHandler(BaseHTTPRequestHandler):
    server: ConsoleServer

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _valid_host(self) -> bool:
        port = self.server.server_address[1]
        return self.headers.get("Host") in {f"127.0.0.1:{port}", f"localhost:{port}"}

    def _send(self, status: int, content: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(content)

    def _json(self, status: int, value: Any) -> None:
        content = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self._send(status, content, "application/json; charset=utf-8")

    def do_GET(self) -> None:
        if not self._valid_host() or self.headers.get("Sec-Fetch-Site") == "cross-site":
            self._json(403, {"error": "Loopback same-site access only"})
            return
        path = unquote(urlsplit(self.path).path)
        state = self.server.state
        if path == "/api/bootstrap":
            self._json(200, state.bootstrap())
        elif path == "/api/jobs":
            with state.lock:
                self._json(200, {"jobs": state.sanitize(state.jobs)})
        elif path.startswith("/api/runs/"):
            detail = state.run_detail(path.removeprefix("/api/runs/"))
            self._json(200 if detail else 404, detail or {"error": "Run not found"})
        elif path.startswith("/api/evidence/"):
            name = path.removeprefix("/api/evidence/")
            candidate = state.root / name
            if (name not in state.evidence_paths or not candidate.resolve().is_relative_to(state.root)
                    or candidate.is_symlink() or not candidate.is_file()):
                self._json(404, {"error": "Evidence not allowlisted"})
            elif candidate.suffix == ".png":
                self._send(200, candidate.read_bytes(), "image/png")
            elif candidate.suffix == ".json":
                self._json(200, state.sanitize(_read_json(candidate)))
            else:
                text = state.sanitize(candidate.read_text(encoding="utf-8"))
                self._send(200, text.encode("utf-8"), "text/plain; charset=utf-8")
        elif path in {"/app.js", "/scene.js", "/styles.css", "/design.css"}:
            candidate = ASSETS / path.lstrip("/")
            if candidate.is_file():
                content_type = "application/javascript" if candidate.suffix == ".js" else "text/css"
                self._send(200, candidate.read_bytes(), content_type + "; charset=utf-8")
            else:
                self._json(503, {"error": "Console assets are unavailable"})
        elif path == "/" or path == "/app" or path.startswith("/app/"):
            candidate = ASSETS / "index.html"
            if candidate.is_file():
                self._send(200, candidate.read_bytes(), "text/html; charset=utf-8")
            else:
                self._json(503, {"error": "Console assets are unavailable"})
        else:
            self._json(404, {"error": "Not found"})

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json(400, {"error": "Invalid content length"})
            return
        if not 0 < length <= 4096 or self.headers.get("Transfer-Encoding"):
            self._json(413, {"error": "Action payload must be at most 4096 bytes"})
            return
        raw_payload = self.rfile.read(length)
        origin = "http://" + self.headers.get("Host", "")
        provided_token = self.headers.get("X-Invaris-Session", "")
        if (not self._valid_host() or self.headers.get("Origin") != origin
                or self.headers.get("Sec-Fetch-Site") == "cross-site"
                or not hmac.compare_digest(provided_token.encode("utf-8"), self.server.state.session_token.encode("utf-8"))):
            self._json(403, {"error": "Same-origin session authorization required"})
            return
        if urlsplit(self.path).path != "/api/jobs":
            self._json(404, {"error": "Not found"})
            return
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            self._json(415, {"error": "JSON content type required"})
            return
        try:
            request = json.loads(raw_payload)
            job = self.server.state.launch(request)
        except (ValueError, UnicodeError, TypeError):
            self._json(400, {"error": "Invalid action payload"})
        except PermissionError as error:
            self._json(403, {"error": str(error)})
        except RuntimeError as error:
            self._json(409, {"error": str(error)})
        else:
            self._json(202, self.server.state.sanitize(job))


def serve_console(root: Path, port: int = 8766) -> None:
    if not 1024 <= port <= 65535:
        raise ValueError("Console port must be between 1024 and 65535")
    state = ConsoleState(root)
    server = ConsoleServer(state, port)
    print(f"Invaris console: http://127.0.0.1:{port} (local operator access only)", flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        state.wait_active()
