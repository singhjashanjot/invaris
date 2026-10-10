"""Validation and targeted secret redaction for local evidence bundles."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

DEFAULT_REQUIRED_RECEIPTS = ("candidate", "probe", "application", "rollback")
_SECRET_PATTERNS = (
    (re.compile(r"(?i)(\b(?:authorization\s*:\s*bearer|bearer)\s+)[A-Za-z0-9._~+/=-]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)\b\s*[:=]\s*['\"]?)[^\s,'\";]+"), r"\1[REDACTED]"),
    (re.compile(r"(?s)-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), "[REDACTED PRIVATE KEY]"),
)


def redact_secrets(value: Any) -> Any:
    """Redact common credential forms while preserving ordinary evidence text."""
    if isinstance(value, str):
        for pattern, replacement in _SECRET_PATTERNS:
            value = pattern.sub(replacement, value)
        return value
    if isinstance(value, Mapping):
        return {key: ("[REDACTED]" if re.search(r"(?i)(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret|private[_-]?key)", str(key)) else redact_secrets(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(item) for item in value)
    return value


def content_sha256(content: bytes | str) -> str:
    """Return a content digest for change detection; this is not provenance proof."""
    payload = content.encode("utf-8") if isinstance(content, str) else content
    return hashlib.sha256(payload).hexdigest()


def validate_evidence(bundle: Mapping[str, Any], required_receipts: tuple[str, ...] = DEFAULT_REQUIRED_RECEIPTS) -> dict[str, Any]:
    """Check receipt presence and revision consistency without asserting integrations."""
    receipts = bundle.get("receipts", [])
    if isinstance(receipts, Mapping):
        receipt_map = dict(receipts)
    else:
        receipt_map = {str(item.get("kind")): item for item in receipts if isinstance(item, Mapping) and item.get("kind")}
    issues: list[dict[str, str]] = []
    missing = [kind for kind in required_receipts if kind not in receipt_map]
    for kind in missing:
        issues.append({"code": "missing_receipt", "item": kind, "message": f"Required {kind} receipt is missing."})

    revisions = bundle.get("revisions", {})
    candidate_revision = revisions.get("candidate") if isinstance(revisions, Mapping) else None
    for kind in ("probe", "application", "rollback"):
        receipt = receipt_map.get(kind)
        if not isinstance(receipt, Mapping):
            continue
        actual = receipt.get("candidate_revision", receipt.get("revision"))
        expected = candidate_revision if kind != "rollback" else (revisions.get("baseline") if isinstance(revisions, Mapping) else None)
        if expected is not None and actual != expected:
            issues.append({"code": "revision_mismatch", "item": kind, "message": f"{kind} receipt revision does not match the declared revision."})
        if kind == "probe" and receipt.get("fresh") is not True:
            issues.append({"code": "probe_not_fresh", "item": kind, "message": "Probe receipt is not explicitly marked fresh."})

    for kind in required_receipts:
        receipt = receipt_map.get(kind)
        if not isinstance(receipt, Mapping) or not receipt:
            issues.append({"code": "receipt_incomplete", "item": kind, "message": f"Required {kind} receipt lacks evidence fields."})
            continue
        revision = receipt.get("candidate_revision", receipt.get("revision"))
        has_revision = isinstance(revision, str) and bool(revision.strip())
        if kind == "candidate":
            meaningful = has_revision
        elif kind == "probe":
            meaningful = has_revision and type(receipt.get("fresh")) is bool
        elif kind in {"application", "rollback"}:
            outcome = any(type(receipt.get(field)) is bool for field in ("ok", "valid", "verified", "app_valid"))
            meaningful = has_revision and outcome
        else:
            meaningful = bool(receipt)
        if not meaningful:
            issues.append({"code": "receipt_incomplete", "item": kind, "message": f"Required {kind} receipt lacks revision or outcome evidence."})

    integration_results = []
    integrations = bundle.get("integrations", [])
    values = integrations.items() if isinstance(integrations, Mapping) else ((str(item.get("name", "unknown")), item) for item in integrations if isinstance(item, Mapping))
    for name, raw in values:
        entry = raw if isinstance(raw, Mapping) else {"status": str(raw)}
        evidence_refs = entry.get("evidence", [])
        status = str(entry.get("status", "unavailable")).lower()
        supported_status = status if evidence_refs or status in {"unavailable", "not_attempted", "not_integrated"} else "unverified"
        integration_results.append({"name": str(name), "status": supported_status,
                                    "evidence": list(evidence_refs) if isinstance(evidence_refs, (list, tuple)) else [evidence_refs] if evidence_refs else []})
        if status in {"integrated", "complete", "verified"} and not evidence_refs:
            issues.append({"code": "integration_unsubstantiated", "item": str(name), "message": "Integration claim has no supporting evidence reference."})

    ready = not issues and not missing
    return {"valid": ready, "status": "valid" if ready else "incomplete", "missing_receipts": missing,
            "issues": issues, "integrations": integration_results,
            "limitations": ["Content hashes detect changes; they do not establish provenance or authenticity."]}


def sanitized_bundle(bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Return a recursively redacted copy suitable for local report preparation."""
    return redact_secrets(bundle)


def implementation_snapshot(root: Path) -> dict[str, Any]:
    files = {}
    sources = sorted((Path(__file__).parent).glob("*.py"))
    sources.extend(root / name for name in (".dockerignore", "compose.yaml", "pyproject.toml", "requirements.lock", "fixture/Dockerfile", "fixture/server.c", "fixture/probe.c", "fixture/control.py"))
    for source in sources:
        if source.is_symlink() or not source.is_file():
            raise ValueError("implementation snapshot requires regular source and fixture files")
        name = "src/invaris/" + source.name if source.parent == Path(__file__).parent else source.relative_to(root).as_posix()
        content = source.read_bytes()
        files[name] = {"sha256_original": hashlib.sha256(content).hexdigest(), "sanitized_text": redact_secrets(content.decode("utf-8"))}
    return {"schema": "invaris.implementation/v1", "files": files, "limitations": ["Local source snapshot, not signed build provenance. Redacted text may differ from original hashed bytes."]}


def build_manifest(directory: Path, filenames: tuple[str, ...]) -> dict[str, Any]:
    entries = {}
    for filename in filenames:
        if not filename or Path(filename).name != filename or "/" in filename or "\\" in filename:
            raise ValueError("manifest entries must be direct artifact filenames")
        target = directory / filename
        if target.is_symlink() or not target.is_file():
            raise ValueError("manifest entry must be a regular, non-symlink artifact")
        content = target.read_bytes()
        entries[filename] = {"sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
    return {
        "schema": "invaris.evidence-manifest/v1",
        "files": entries,
        "limitations": ["Hashes detect artifact changes; they do not establish provenance or authenticity."],
    }


def verify_manifest(directory: Path, manifest: Mapping[str, Any]) -> bool:
    if manifest.get("schema") != "invaris.evidence-manifest/v1":
        return False
    entries = manifest.get("files")
    if not isinstance(entries, dict) or not entries or not all(isinstance(name, str) for name in entries):
        return False
    try:
        actual = build_manifest(directory, tuple(entries))
    except (OSError, ValueError):
        return False
    return actual["files"] == entries


def write_sanitized_json(bundle: Mapping[str, Any], path: str) -> None:
    """Write a redacted JSON artifact to an explicitly supplied local path."""
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(sanitized_bundle(bundle), stream, indent=2, ensure_ascii=False, default=str)
        stream.write("\n")
