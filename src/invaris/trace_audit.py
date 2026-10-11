"""Offline structural audit of a Neatlogs trace readback."""

from __future__ import annotations

from typing import Any

SCHEMA = "invaris.trace_audit.v1"
LIMITATIONS = [
    "This offline audit can only assess the supplied readback and local expected row.",
    "Complete means structural count coverage and does not prove cryptographic authenticity.",
    "HTTP success and SDK counters alone do not prove that a trace is complete.",
    "The audit does not inspect or return model inputs, outputs, or credentials.",
]
_NODE_TYPES = {"llm", "tool_call", "workflow"}


def audit_trace_readback(expected: dict, payload: dict, *, project_id: str) -> dict:
    """Check whether a supplied readback structurally covers a local trace row."""
    issues: list[str] = []
    expected_counts: dict[str, int | None] = {"model_calls": None, "tool_calls": None}
    observed_counts: dict[str, int | None] = {
        "spans": None,
        "model_calls": None,
        "tool_calls": None,
        "rollback_and_reverify_tools": None,
        "reported_model_calls": None,
        "reported_tool_calls": None,
    }

    expected_row = expected if isinstance(expected, dict) else {}
    payload_row = payload if isinstance(payload, dict) else {}
    if not isinstance(expected, dict):
        issues.append("expected_row_invalid")
    if not isinstance(payload, dict):
        issues.append("payload_invalid")
    metadata = expected_row.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
        issues.append("expected_metadata_invalid")

    for field in ("model_calls", "tool_calls"):
        value = expected_row.get(field)
        if not _valid_count(value):
            issues.append(f"expected_{field}_invalid")
        else:
            expected_counts[field] = value

    version = expected_row.get("version")
    if not isinstance(version, str) or version not in {"V1", "V2"}:
        issues.append("expected_version_invalid")
        version = None
    trace_id = metadata.get("trace_id")
    if not isinstance(trace_id, str) or not trace_id:
        issues.append("expected_trace_id_invalid")
        trace_id = None
    rollback_verified = metadata.get("rollback_verified")
    if rollback_verified is not None and not isinstance(rollback_verified, bool):
        issues.append("expected_rollback_verified_invalid")
        rollback_verified = None

    supplied_project_id = payload_row.get("projectId")
    if not isinstance(project_id, str) or not project_id or supplied_project_id != project_id:
        issues.append("project_id_mismatch")
    if trace_id is not None and payload_row.get("_id") != trace_id:
        issues.append("trace_id_mismatch")

    spans = payload_row.get("spans")
    if not isinstance(spans, list):
        issues.append("spans_invalid")
        spans = []
    else:
        observed_counts["spans"] = len(spans)
    if len(spans) > 1024:
        issues.append("span_limit_exceeded")
        spans = []

    reported_total = payload_row.get("spanCount")
    if not _valid_count(reported_total):
        issues.append("reported_span_count_invalid")
    elif isinstance(payload_row.get("spans"), list) and reported_total != len(spans):
        issues.append("reported_span_count_mismatch")

    for source, output in (("llmCalls", "reported_model_calls"), ("toolCalls", "reported_tool_calls")):
        if source not in payload_row:
            continue
        value = payload_row[source]
        if not _valid_count(value):
            issues.append(f"{output}_invalid")
        else:
            observed_counts[output] = value

    records: list[dict[str, Any]] = []
    span_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    for span in spans:
        if not isinstance(span, dict):
            issues.append("span_invalid")
            continue
        span_id = span.get("span_id")
        parent_id = span.get("parent_span_id")
        if not isinstance(span_id, str) or not span_id:
            issues.append("span_id_invalid")
            span_id = None
        elif span_id in span_ids:
            duplicate_ids.add(span_id)
        else:
            span_ids.add(span_id)
        if parent_id is not None and (not isinstance(parent_id, str) or not parent_id):
            issues.append("parent_span_id_invalid")
            parent_id = None

        span_metadata = span.get("span_metadata")
        if span_metadata is not None and not isinstance(span_metadata, dict):
            issues.append("span_metadata_invalid")
            span_metadata = {}
        if not isinstance(span_metadata, dict):
            span_metadata = {}
        node_name = span_metadata.get("node_name", span.get("node_name"))
        node_type = span_metadata.get("node_type", span.get("node_type"))
        if not isinstance(node_name, str) or not node_name:
            issues.append("node_name_invalid")
            node_name = None
        if not isinstance(node_type, str) or node_type.lower() not in _NODE_TYPES:
            issues.append("node_type_invalid")
            node_type = None
        else:
            node_type = node_type.lower()
        records.append({"id": span_id, "parent": parent_id, "name": node_name, "type": node_type})

    if duplicate_ids:
        issues.append("span_id_duplicate")
    valid_ids = {record["id"] for record in records if record["id"] is not None}
    for record in records:
        parent_id = record["parent"]
        if parent_id is not None and parent_id not in valid_ids:
            issues.append("span_parent_unresolved")

    roots = [record for record in records if record["parent"] is None]
    if len(roots) != 1:
        issues.append("root_count_invalid")
    elif roots[0]["name"] != "invaris.run":
        issues.append("root_name_invalid")
    elif roots[0]["type"] != "workflow":
        issues.append("root_type_invalid")

    by_id = {record["id"]: record for record in records if record["id"] is not None}
    cycle_found = False
    for record in records:
        visited: set[str] = set()
        current = record
        while current["id"] is not None and current["parent"] is not None:
            current_id = current["id"]
            if current_id in visited:
                cycle_found = True
                break
            visited.add(current_id)
            parent = by_id.get(current["parent"])
            if parent is None:
                break
            current = parent
    if cycle_found:
        issues.append("span_cycle_detected")
    if len(roots) == 1 and not cycle_found:
        for record in records:
            current = record
            visited: set[str] = set()
            while current["parent"] is not None and current["id"] not in visited:
                if current["id"] is not None:
                    visited.add(current["id"])
                parent = by_id.get(current["parent"])
                if parent is None:
                    break
                current = parent
            if current["id"] != roots[0]["id"]:
                issues.append("span_disconnected")
                break

    target_workflow = f"invaris.migration.{version}" if version is not None else None
    if len(roots) == 1 and target_workflow is not None:
        workflow_found = any(
            record["name"] == target_workflow and record["type"] == "workflow"
            and record["parent"] == roots[0]["id"]
            for record in records
        )
        if not workflow_found:
            issues.append("migration_workflow_missing")

    model_calls = sum(record["type"] == "llm" for record in records)
    tool_calls = sum(record["type"] == "tool_call" for record in records)
    rollback_tools = sum(
        record["type"] == "tool_call"
        and record["name"] in {"rollback_and_reverify", "invaris.rollback_and_reverify"}
        for record in records
    )
    observed_counts.update(
        model_calls=model_calls,
        tool_calls=tool_calls,
        rollback_and_reverify_tools=rollback_tools,
    )

    for count_name, observed in (("model_calls", model_calls), ("tool_calls", tool_calls)):
        expected_count = expected_counts[count_name]
        if count_name == "tool_calls" and expected_count is not None and rollback_verified is True:
            expected_count += 1
            expected_counts[count_name] = expected_count
        if expected_count is not None and observed < expected_count:
            issues.append(f"{count_name}_underreported")
        reported_key = f"reported_{count_name}"
        reported = observed_counts[reported_key]
        if reported is not None and reported != observed:
            issues.append(f"{reported_key}_mismatch")
    if rollback_verified is True and rollback_tools < 1:
        issues.append("rollback_tool_missing")

    return {
        "schema": SCHEMA,
        "complete": not issues,
        "issues": issues,
        "observed_counts": observed_counts,
        "expected_counts": expected_counts,
        "limitations": LIMITATIONS.copy(),
    }


def _valid_count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0
