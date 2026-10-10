import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from invaris import tracing


class StubSpan:
    def __init__(self):
        self.attributes = {}
        self.status = None

    def set_attribute(self, name, value):
        self.attributes[name] = value

    def get_span_context(self):
        return SimpleNamespace(trace_id=123)

    def set_status(self, status):
        self.status = status


class StubSDK:
    def __init__(self):
        self.initialized = None
        self.wrapped = None
        self.span_args = None
        self.span = StubSpan()

    def init(self, **kwargs):
        self.initialized = kwargs

    def wrap(self, client):
        self.wrapped = client
        return ("wrapped", client)

    @contextmanager
    def trace(self, name, kind):
        self.span_args = (name, kind)
        yield self.span

    def flush(self, **kwargs):
        return True

    def shutdown(self, **kwargs):
        return True


class TracingTests(unittest.TestCase):
    def tearDown(self):
        tracing._neatlogs = None
        tracing._status = tracing.TracingStatus("uninitialized")

    def test_missing_key_is_visibly_degraded(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertLogs("invaris.tracing", level="WARNING") as logs:
                status = tracing.configure_tracing()
        self.assertEqual(status.state, "degraded")
        self.assertIn("NEATLOGS_API_KEY", status.reason)
        self.assertIn("degraded", logs.output[0])
        client = object()
        self.assertIs(tracing.wrap_model_client(client), client)

    def test_initializes_wraps_records_inputs_output_and_trace_id(self):
        sdk = StubSDK()
        with patch.object(tracing.importlib, "import_module", lambda name: sdk):
            status = tracing.configure_tracing(api_key="test-key", workflow_name="run")
        client = object()
        wrapped = tracing.wrap_model_client(client)
        with tracing.traced_operation(
            "agent.run", "WORKFLOW", {"api_key": "hidden", "task": "inspect"}
        ) as recorder:
            recorder.set_output({"result": "ok", "access_token": "private"})
        self.assertEqual(status.state, "configured")
        self.assertEqual(sdk.initialized, {"api_key": "test-key", "endpoint": "https://ingest.neatlogs.com", "workflow_name": "run"})
        self.assertEqual(wrapped, ("wrapped", client))
        self.assertEqual(sdk.span_args, ("agent.run", "WORKFLOW"))
        self.assertEqual(recorder.trace_id, f"{123:032x}")
        self.assertIn("[REDACTED]", sdk.span.attributes["input.value"])
        self.assertIn("[REDACTED]", sdk.span.attributes["output.value"])
        self.assertTrue(tracing.flush_tracing())
        self.assertTrue(tracing.shutdown_tracing())

    def test_initialization_failure_is_degraded_without_key_echo(self):
        class BrokenSDK(StubSDK):
            def init(self, **kwargs):
                raise RuntimeError("private key detail")

        with patch.object(tracing.importlib, "import_module", lambda name: BrokenSDK()):
            with self.assertLogs("invaris.tracing", level="ERROR") as logs:
                status = tracing.configure_tracing(api_key="secret", workflow_name="run")
        self.assertEqual(status.state, "degraded")
        self.assertNotIn("private key detail", " ".join(logs.output))

    def test_application_exception_is_recorded_without_degrading_sdk(self):
        sdk = StubSDK()
        with patch.object(tracing.importlib, "import_module", lambda name: sdk):
            tracing.configure_tracing(api_key="test-key")
        with self.assertRaisesRegex(RuntimeError, "tool failed"):
            with tracing.trace_span("tool.inspect", "TOOL"):
                raise RuntimeError("tool failed")
        self.assertEqual(tracing.tracing_status().state, "configured")
        self.assertEqual(sdk.span.attributes["error.type"], "RuntimeError")
        self.assertIn("tool failed", sdk.span.attributes["error.message"])
