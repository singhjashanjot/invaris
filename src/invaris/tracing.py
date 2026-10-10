"""Neatlogs lifecycle and span adapter; no local trace substitute is used."""

from __future__ import annotations

import importlib
import json
import logging
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TracingStatus:
    state: str
    reason: str | None = None


@dataclass
class SpanRecorder:
    """Safe, explicit recorder for attributes on the SDK's active OpenTelemetry span."""

    span: Any = None
    trace_id: str | None = None

    def set_output(self, output: Any) -> None:
        if self.span is not None:
            self.span.set_attribute("output.value", _serialized(output))

    def set_error(self, error: BaseException | str) -> None:
        if self.span is None:
            return
        message = str(error)
        from .evidence import redact_secrets

        self.span.set_attribute("error.type", type(error).__name__ if isinstance(error, BaseException) else "Error")
        self.span.set_attribute("error.message", _serialized(redact_secrets(message)))
        try:
            from opentelemetry.trace import Status, StatusCode

            self.span.set_status(Status(StatusCode.ERROR, description="Operation failed"))
        except ImportError:
            pass


def _serialized(value: Any) -> str:
    from .evidence import redact_secrets

    sanitized = redact_secrets(value)
    encoded = json.dumps(sanitized, ensure_ascii=False, default=str)
    if len(encoded) > 16384:
        encoded = json.dumps(
            {"truncated": True, "preview": encoded[:16000]}, ensure_ascii=False
        )
    return encoded


_neatlogs: Any = None
_status = TracingStatus("uninitialized")


def configure_tracing(
    *, api_key: str | None = None, workflow_name: str = "invaris-migration"
) -> TracingStatus:
    """Initialize the documented Neatlogs SDK, or clearly report degraded tracing."""
    global _neatlogs, _status
    key = api_key if api_key is not None else os.getenv("NEATLOGS_API_KEY")
    if not key or not key.strip():
        _neatlogs = None
        _status = TracingStatus("degraded", "NEATLOGS_API_KEY is not configured")
        logger.warning("Neatlogs tracing degraded: %s", _status.reason)
        return _status

    try:
        sdk = importlib.import_module("neatlogs")
        for name in ("init", "wrap", "trace", "flush", "shutdown"):
            if not callable(getattr(sdk, name, None)):
                raise TypeError(f"Installed Neatlogs SDK lacks {name}().")
        sdk.init(api_key=key.strip(), endpoint="https://ingest.neatlogs.com", workflow_name=workflow_name)
    except Exception as exc:
        _neatlogs = None
        _status = TracingStatus("degraded", f"Neatlogs initialization failed: {type(exc).__name__}")
        logger.error("Neatlogs tracing degraded: %s", _status.reason)
        return _status

    _neatlogs = sdk
    _status = TracingStatus("configured")
    return _status


def tracing_status() -> TracingStatus:
    return _status


def wrap_model_client(client: Any) -> Any:
    """Apply Neatlogs' official client wrapper when tracing is configured."""
    if _neatlogs is None:
        return client
    try:
        return _neatlogs.wrap(client)
    except Exception as exc:
        _status_set_degraded(f"Neatlogs client wrapping failed: {type(exc).__name__}")
        return client


def _status_set_degraded(reason: str) -> None:
    global _neatlogs, _status
    _neatlogs = None
    _status = TracingStatus("degraded", reason)
    logger.error("Neatlogs tracing degraded: %s", reason)


@contextmanager
def traced_operation(name: str, kind: str = "WORKFLOW", inputs: Any = None) -> Iterator[SpanRecorder]:
    """Record sanitized input, output, error state, and SDK trace identity."""
    if _neatlogs is None:
        if _status.state == "uninitialized":
            logger.warning("Neatlogs tracing degraded: configure_tracing() was not called")
        yield SpanRecorder()
        return
    try:
        span_context = _neatlogs.trace(name, kind)
        span = span_context.__enter__()
    except Exception as exc:
        _status_set_degraded(f"Neatlogs span failed: {type(exc).__name__}")
        raise
    try:
        span.set_attribute("input.value", _serialized(inputs))
        span_context_value = span.get_span_context()
        raw_trace_id = getattr(span_context_value, "trace_id", 0)
        trace_id = f"{raw_trace_id:032x}" if raw_trace_id else None
    except Exception as exc:
        try:
            span_context.__exit__(*sys.exc_info())
        finally:
            _status_set_degraded(f"Neatlogs span recording failed: {type(exc).__name__}")
        raise
    recorder = SpanRecorder(span=span, trace_id=trace_id)
    try:
        yield recorder
    except BaseException as exc:
        recorder.set_error(exc)
        try:
            suppressed = span_context.__exit__(*sys.exc_info())
        except Exception as exc:
            _status_set_degraded(f"Neatlogs span failed: {type(exc).__name__}")
        raise
        if not suppressed:
            raise
    else:
        try:
            span_context.__exit__(None, None, None)
        except Exception as exc:
            _status_set_degraded(f"Neatlogs span failed: {type(exc).__name__}")
            raise


trace_span = traced_operation


def flush_tracing(timeout_millis: int = 30000) -> bool:
    if _neatlogs is None:
        return False
    try:
        return bool(_neatlogs.flush(timeout_millis=timeout_millis))
    except Exception as exc:
        _status_set_degraded(f"Neatlogs flush failed: {type(exc).__name__}")
        return False


def shutdown_tracing(timeout_millis: int = 30000) -> bool:
    global _neatlogs
    if _neatlogs is None:
        return False
    sdk = _neatlogs
    _neatlogs = None
    try:
        return bool(sdk.shutdown(timeout_millis=timeout_millis))
    except Exception as exc:
        _status_set_degraded(f"Neatlogs shutdown failed: {type(exc).__name__}")
        return False
