import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from invaris.trace_audit import audit_trace_readback


def expected_row(*, model_calls=1, tool_calls=1, rollback_verified=True):
    return {
        "version": "V2",
        "model_calls": model_calls,
        "tool_calls": tool_calls,
        "metadata": {"trace_id": "trace-1", "rollback_verified": rollback_verified},
    }


def span(span_id, parent_span_id, node_name, node_type):
    return {
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "span_metadata": {"node_name": node_name, "node_type": node_type},
    }


def payload(spans=None):
    spans = spans or [
        span("root", None, "invaris.run", "WORKFLOW"),
        span("workflow", "root", "invaris.migration.V2", "workflow"),
        span("llm", "workflow", "model.generate", "LLM"),
        span("action", "workflow", "inspect_service", "tool_call"),
        span("tool", "root", "invaris.rollback_and_reverify", "tool_call"),
    ]
    return {
        "_id": "trace-1",
        "projectId": "project-1",
        "spanCount": len(spans),
        "llmCalls": sum(s.get("span_metadata", {}).get("node_type", "").lower() == "llm" for s in spans),
        "toolCalls": sum(s.get("span_metadata", {}).get("node_type", "").lower() == "tool_call" for s in spans),
        "spans": spans,
    }


class TraceAuditTests(unittest.TestCase):
    def audit(self, expected=None, response=None, project_id="project-1"):
        return audit_trace_readback(expected or expected_row(), response or payload(), project_id=project_id)

    def test_full_success(self):
        result = self.audit()
        self.assertTrue(result["complete"], result["issues"])
        self.assertEqual(result["observed_counts"]["model_calls"], 1)
        self.assertEqual(result["observed_counts"]["tool_calls"], 2)

    def test_partial_counts(self):
        result = self.audit(expected_row(model_calls=2))
        self.assertFalse(result["complete"])
        self.assertIn("model_calls_underreported", result["issues"])

    def test_additional_classified_spans_cover_minimum_counts(self):
        spans = payload()["spans"] + [span("llm-2", "workflow", "model.retry", "llm")]
        response = payload(spans)
        response["llmCalls"] = 2
        result = self.audit(response=response)
        self.assertTrue(result["complete"], result["issues"])

    def test_sdk_counters_must_match_classified_spans_when_present(self):
        response = payload()
        response["llmCalls"] = 2
        result = self.audit(response=response)
        self.assertIn("reported_model_calls_mismatch", result["issues"])

    def test_missing_sdk_counters_are_allowed(self):
        response = payload()
        response.pop("llmCalls")
        response.pop("toolCalls")
        result = self.audit(response=response)
        self.assertTrue(result["complete"], result["issues"])

    def test_remote_boolean_counter_is_invalid(self):
        response = payload()
        response["llmCalls"] = True
        result = self.audit(response=response)
        self.assertIn("reported_model_calls_invalid", result["issues"])

    def test_orphan_parent(self):
        spans = payload()["spans"]
        spans[2]["parent_span_id"] = "missing"
        result = self.audit(response=payload(spans))
        self.assertIn("span_parent_unresolved", result["issues"])
        self.assertIn("span_disconnected", result["issues"])

    def test_cycle(self):
        spans = payload()["spans"]
        spans[0]["parent_span_id"] = "workflow"
        result = self.audit(response=payload(spans))
        self.assertIn("span_cycle_detected", result["issues"])

    def test_duplicate_span_ids(self):
        spans = payload()["spans"]
        spans[2]["span_id"] = "workflow"
        result = self.audit(response=payload(spans))
        self.assertIn("span_id_duplicate", result["issues"])

    def test_wrong_project_and_trace(self):
        response = payload()
        response["projectId"] = "other"
        response["_id"] = "other-trace"
        result = self.audit(response=response)
        self.assertIn("project_id_mismatch", result["issues"])
        self.assertIn("trace_id_mismatch", result["issues"])

    def test_boolean_and_negative_counts_are_invalid(self):
        result = self.audit(expected_row(model_calls=True, tool_calls=-1))
        self.assertIn("expected_model_calls_invalid", result["issues"])
        self.assertIn("expected_tool_calls_invalid", result["issues"])

    def test_version_must_be_explicit_v1_or_v2(self):
        result = self.audit(expected_row() | {"version": "2.4.1"})
        self.assertIn("expected_version_invalid", result["issues"])

    def test_malformed_payload_fails_closed(self):
        result = self.audit(response={"_id": "trace-1", "projectId": "project-1", "spans": "bad"})
        self.assertFalse(result["complete"])
        self.assertIn("spans_invalid", result["issues"])
        self.assertIn("reported_span_count_invalid", result["issues"])

    def test_missing_workflow(self):
        spans = [s for s in payload()["spans"] if s["span_id"] != "workflow"]
        response = payload(spans)
        response["llmCalls"] = 1
        response["toolCalls"] = 1
        result = self.audit(response=response)
        self.assertIn("migration_workflow_missing", result["issues"])

    def test_rollback_tool_required(self):
        spans = [s for s in payload()["spans"] if s["span_id"] != "tool"]
        response = payload(spans)
        response["llmCalls"] = 1
        response["toolCalls"] = 0
        result = self.audit(response=response)
        self.assertIn("rollback_tool_missing", result["issues"])

    def test_rollback_does_not_substitute_for_missing_agent_tool(self):
        spans = [item for item in payload()["spans"] if item["span_id"] != "action"]
        result = self.audit(response=payload(spans))
        self.assertIn("tool_calls_underreported", result["issues"])

    def test_null_rollback_does_not_claim_a_rollback(self):
        spans = [item for item in payload()["spans"] if item["span_id"] != "tool"]
        result = self.audit(expected_row(rollback_verified=None), payload(spans))
        self.assertTrue(result["complete"], result["issues"])

    def test_unhashable_version_fails_closed(self):
        result = self.audit(expected_row() | {"version": []})
        self.assertIn("expected_version_invalid", result["issues"])

    def test_root_must_be_a_workflow(self):
        response = payload()
        response["spans"][0]["span_metadata"]["node_type"] = "tool_call"
        result = self.audit(response=response)
        self.assertIn("root_type_invalid", result["issues"])

    def test_hostile_span_count_is_bounded(self):
        response = payload()
        response["spans"] *= 257
        response["spanCount"] = len(response["spans"])
        result = self.audit(response=response)
        self.assertIn("span_limit_exceeded", result["issues"])


if __name__ == "__main__":
    unittest.main()
