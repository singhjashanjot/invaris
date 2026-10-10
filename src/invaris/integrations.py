"""Read-only checks for configured integrations and local partner evidence."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class IntegrationCheck:
    name: str
    state: str
    reason: str
    details: dict[str, Any] = field(default_factory=dict)


def check_model_configuration(
    *, env: dict[str, str] | None = None
) -> IntegrationCheck:
    values = os.environ if env is None else env
    model = values.get("INVARIS_MODEL", "").strip()
    missing_settings = []
    if not model:
        missing_settings.append("INVARIS_MODEL")
    base_url = values.get("OPENAI_BASE_URL", "").strip() or None
    has_openai_key = bool(values.get("OPENAI_API_KEY", "").strip())
    has_litellm_key = bool(values.get("LITELLM_API_KEY", "").strip())
    if not has_openai_key and not (has_litellm_key and base_url):
        missing_settings.append("OPENAI_API_KEY or LITELLM_API_KEY with OPENAI_BASE_URL")
    spend_limit = values.get("INVARIS_MAX_SPEND_USD", "").strip() or values.get(
        "INVARIS_MAX_ESTIMATED_COST_USD", ""
    ).strip()
    spend_limit_source = (
        "INVARIS_MAX_SPEND_USD"
        if values.get("INVARIS_MAX_SPEND_USD", "").strip()
        else "INVARIS_MAX_ESTIMATED_COST_USD"
    )
    required_rates = (
        "INVARIS_INPUT_USD_PER_MILLION",
        "INVARIS_OUTPUT_USD_PER_MILLION",
    )
    missing_budget = []
    if not spend_limit:
        missing_budget.append("INVARIS_MAX_SPEND_USD")
    missing_budget.extend(name for name in required_rates if not values.get(name, "").strip())
    missing_settings.extend(missing_budget)
    if missing_settings:
        return IntegrationCheck(
            "model", "available", "Live model calls need the model, credential, authorized USD cap, and both explicit rates.",
            {
                "model": model or None,
                "base_url": base_url,
                "missing_settings": missing_settings,
                "missing_budget_settings": missing_budget,
            },
        )
    try:
        cap = Decimal(spend_limit)
        rates = [Decimal(values[name]) for name in required_rates]
        valid_budget = cap.is_finite() and cap > 0 and all(
            rate.is_finite() and rate >= 0 for rate in rates
        )
    except (InvalidOperation, ValueError):
        valid_budget = False
    if not valid_budget:
        return IntegrationCheck(
            "model", "unverified", "Spend cap or configured token rate is not a valid finite USD amount.",
            {"model": model, "base_url": base_url, "spend_cap_source": spend_limit_source, "budget": "invalid"},
        )
    return IntegrationCheck(
        "model", "configured", "Provider settings are present; connectivity is unverified.",
        {
            "model": model,
            "base_url": base_url,
            "connectivity": "unverified",
            "spend_cap_source": spend_limit_source,
            "rates_configured": True,
        },
    )


def _doctor_schema(payload: Any) -> tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, "Doctor output must be a JSON object."
    if payload.get("format_version") != "neatlogs.doctor/v2":
        return False, "Doctor format_version is not neatlogs.doctor/v2."
    runtime = payload.get("runtime")
    if not isinstance(runtime, dict) or runtime.get("schema_version") != "2":
        return False, "Doctor runtime.schema_version is not 2."
    if runtime.get("language") != "python":
        return False, "Doctor runtime.language is not python."
    try:
        installed_version = importlib.metadata.version("neatlogs")
    except importlib.metadata.PackageNotFoundError:
        return False, "Neatlogs package is not installed in this interpreter."
    if runtime.get("sdk_version") != installed_version:
        return False, "Doctor SDK version does not match the installed package."
    checks = payload.get("checks")
    if not isinstance(checks, list) or not checks or any(
        not isinstance(item, dict) or item.get("status") != "pass" for item in checks
    ):
        return False, "Doctor checks are missing or include a non-pass result."
    if payload.get("status") != "pass" or payload.get("first_failure") is not None:
        return False, "Doctor reports an unsuccessful check."
    return True, ""


def check_neatlogs(
    *, probe: bool = False, timeout: float = 30.0, env: dict[str, str] | None = None
) -> IntegrationCheck:
    """Run the official SDK Doctor and validate its v2 JSON result."""
    values = os.environ.copy() if env is None else dict(env)
    if probe and not values.get("NEATLOGS_API_KEY", "").strip():
        return IntegrationCheck(
            "neatlogs", "available", "Doctor probe requires NEATLOGS_API_KEY; no probe was run."
        )
    mode = "--probe" if probe else "--local"
    try:
        result = subprocess.run(
            [sys.executable, "-m", "neatlogs", "doctor", mode, "--endpoint", "https://ingest.neatlogs.com", "--json"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=values,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return IntegrationCheck(
            "neatlogs", "unverified", f"Doctor could not complete: {type(exc).__name__}."
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return IntegrationCheck(
            "neatlogs", "unverified", "Doctor did not emit valid JSON.",
            {"returncode": result.returncode},
        )
    valid, reason = _doctor_schema(payload)
    if result.returncode != 0 or not valid:
        return IntegrationCheck(
            "neatlogs", "unverified", reason or "Doctor returned a failure status.",
            {"returncode": result.returncode},
        )
    return IntegrationCheck(
        "neatlogs",
        "configured" if probe else "available",
        "Doctor probe passed." if probe else "Local Doctor passed; backend delivery is unverified.",
        {"sdk_version": payload["runtime"]["sdk_version"], "schema_version": "2"},
    )


def inspect_partner_evidence(
    partner: str, paths: Sequence[str | Path]
) -> IntegrationCheck:
    """Inventory caller-designated local evidence without asserting provenance or validity."""
    if partner not in {"entire", "cfo.ai"}:
        raise ValueError("partner must be 'entire' or 'cfo.ai'")
    artifacts = []
    for supplied_path in paths:
        path = Path(supplied_path)
        if not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        artifacts.append({"path": str(path.resolve()), "sha256": digest})
    if not artifacts:
        return IntegrationCheck(
            partner, "unavailable", "No local evidence artifacts were found.", {"artifacts": []}
        )
    return IntegrationCheck(
        partner,
        "unverified",
        "Local artifacts exist; partner provenance and semantic validity are unverified.",
        {"artifacts": artifacts},
    )


def check_integrations(
    *,
    evidence: dict[str, Sequence[str | Path]] | None = None,
    neatlogs_probe: bool = False,
) -> list[IntegrationCheck]:
    evidence = evidence or {}
    return [
        check_model_configuration(),
        check_neatlogs(probe=neatlogs_probe),
        inspect_partner_evidence("entire", evidence.get("entire", ())),
        inspect_partner_evidence("cfo.ai", evidence.get("cfo.ai", ())),
    ]
