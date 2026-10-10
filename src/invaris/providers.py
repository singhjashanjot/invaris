"""Model adapters with explicit tool-call normalization and estimated spend limits."""

from __future__ import annotations

import ipaddress
import json
import math
import os
import threading
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlsplit


class ProviderConfigurationError(RuntimeError):
    """Raised when the explicitly configured provider cannot be constructed."""


class ProviderResponseError(RuntimeError):
    """Raised when a model response does not satisfy the provider contract."""


class BudgetLimitError(RuntimeError):
    """Raised before a request when its conservative estimate exceeds authorization."""


class ProviderRequestError(RuntimeError):
    """A sanitized request failure that retains its uncertain spend reservation."""

    def __init__(self, message: str, pending_estimate_usd: float) -> None:
        super().__init__(message)
        self.pending_estimate_usd = pending_estimate_usd


def _value(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _wire_messages(messages: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    converted = []
    for original in messages:
        message = dict(original)
        if message.get("role") == "assistant" and message.get("tool_calls"):
            calls = []
            for original_call in message["tool_calls"]:
                call = dict(original_call)
                if "function" not in call:
                    call = {"id": call["id"], "type": "function", "function": {
                        "name": call["name"],
                        "arguments": json.dumps(call["arguments"], ensure_ascii=False),
                    }}
                calls.append(call)
            message["tool_calls"] = calls
        if message.get("role") == "tool" and isinstance(message.get("content"), Mapping):
            message["content"] = json.dumps(message["content"], ensure_ascii=False)
        converted.append(message)
    return converted


def _decimal(value: Any, name: str, *, allow_zero: bool) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ProviderConfigurationError(f"{name} must be a finite USD amount.") from exc
    if not number.is_finite() or number < 0 or (not allow_zero and number == 0):
        qualifier = "non-negative" if allow_zero else "greater than zero"
        raise ProviderConfigurationError(f"{name} must be {qualifier} and finite.")
    return number


class SpendBudget:
    """One provider-wide estimated USD budget, shared across sequential or parallel calls."""

    def __init__(
        self,
        spend_limit_usd: Any,
        input_usd_per_million: Any,
        output_usd_per_million: Any,
    ) -> None:
        self.limit = _decimal(spend_limit_usd, "spend_limit_usd", allow_zero=False)
        self.input_rate = _decimal(input_usd_per_million, "input_usd_per_million", allow_zero=True)
        self.output_rate = _decimal(output_usd_per_million, "output_usd_per_million", allow_zero=True)
        self._spent = Decimal(0)
        self._pending: dict[int, Decimal] = {}
        self._next_reservation = 1
        self._lock = threading.Lock()

    def _cost(self, input_tokens: int, output_tokens: int) -> Decimal:
        return (
            Decimal(input_tokens) * self.input_rate
            + Decimal(output_tokens) * self.output_rate
        ) / Decimal(1_000_000)

    def reserve(self, input_token_bound: int, max_output_tokens: int) -> tuple[int, Decimal]:
        estimate = self._cost(input_token_bound, max_output_tokens)
        with self._lock:
            committed = self._spent + sum(self._pending.values(), Decimal(0))
            if committed + estimate > self.limit:
                raise BudgetLimitError(
                    "Conservative request estimate exceeds the remaining authorized USD budget."
                )
            reservation_id = self._next_reservation
            self._next_reservation += 1
            self._pending[reservation_id] = estimate
        return reservation_id, estimate

    def settle(
        self, reservation_id: int, input_tokens: Any, output_tokens: Any
    ) -> Decimal | None:
        token_values = (input_tokens, output_tokens)
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0
            for value in token_values
        ):
            return None
        measured = self._cost(input_tokens, output_tokens)
        with self._lock:
            if reservation_id not in self._pending:
                return None
            del self._pending[reservation_id]
            self._spent += measured
        return measured

    def abandon_as_uncertain(self, reservation_id: int) -> Decimal:
        with self._lock:
            return self._pending.get(reservation_id, Decimal(0))

    @property
    def spent_estimate_usd(self) -> Decimal:
        with self._lock:
            return self._spent

    @property
    def pending_estimate_usd(self) -> Decimal:
        with self._lock:
            return sum(self._pending.values(), Decimal(0))

    @property
    def remaining_estimate_usd(self) -> Decimal:
        with self._lock:
            return self.limit - self._spent - sum(self._pending.values(), Decimal(0))


class OpenAICompatibleProvider:
    """OpenAI Chat Completions provider with a conservative per-request spend gate."""

    INPUT_TOKEN_OVERHEAD = 256

    def __init__(
        self,
        model: str | None = None,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
        max_output_tokens: int = 1024,
        spend_limit_usd: float | str | None = None,
        input_usd_per_million: float | str | None = None,
        output_usd_per_million: float | str | None = None,
        client: Any = None,
    ) -> None:
        configured_model = model or os.getenv("INVARIS_MODEL")
        if not configured_model or not configured_model.strip():
            raise ProviderConfigurationError("Set INVARIS_MODEL or pass model explicitly.")
        if not math.isfinite(timeout) or timeout <= 0 or timeout > 120:
            raise ValueError("timeout must be greater than 0 and at most 120 seconds")
        if not isinstance(max_output_tokens, int) or isinstance(max_output_tokens, bool) or not 1 <= max_output_tokens <= 100_000:
            raise ValueError("max_output_tokens must be an integer from 1 through 100000")

        self.model = configured_model.strip()
        self.timeout = timeout
        self.max_output_tokens = max_output_tokens
        self._client = client
        self._base_url = base_url if base_url is not None else os.getenv("OPENAI_BASE_URL")
        if self._base_url:
            _validate_base_url(self._base_url)
        configured_api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY")
        self._api_key = configured_api_key if configured_api_key and configured_api_key.strip() else None
        if self._api_key is None and api_key is None and self._base_url:
            litellm_api_key = os.getenv("LITELLM_API_KEY")
            self._api_key = litellm_api_key if litellm_api_key and litellm_api_key.strip() else None

        limit = (
            spend_limit_usd
            if spend_limit_usd is not None
            else os.getenv("INVARIS_MAX_SPEND_USD")
            or os.getenv("INVARIS_MAX_ESTIMATED_COST_USD")
        )
        input_rate = (
            input_usd_per_million
            if input_usd_per_million is not None
            else os.getenv("INVARIS_INPUT_USD_PER_MILLION")
        )
        output_rate = (
            output_usd_per_million
            if output_usd_per_million is not None
            else os.getenv("INVARIS_OUTPUT_USD_PER_MILLION")
        )
        self._budget_config = (limit, input_rate, output_rate)
        self.cost_budget: SpendBudget | None = None
        self._budget_error: str | None = None
        if any(value is not None and str(value).strip() for value in self._budget_config):
            if any(value is None or not str(value).strip() for value in self._budget_config):
                self._budget_error = (
                    "Live calls require INVARIS_MAX_SPEND_USD and both explicit rate settings."
                )
            else:
                try:
                    self.cost_budget = SpendBudget(*self._budget_config)
                except ProviderConfigurationError as exc:
                    self._budget_error = str(exc)

    def _require_budget(self) -> SpendBudget:
        if self._budget_error:
            raise ProviderConfigurationError(self._budget_error)
        if self.cost_budget is None:
            raise ProviderConfigurationError(
                "Live calls require INVARIS_MAX_SPEND_USD, "
                "INVARIS_INPUT_USD_PER_MILLION, and INVARIS_OUTPUT_USD_PER_MILLION."
            )
        return self.cost_budget

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self._api_key:
            raise ProviderConfigurationError(
                "Set OPENAI_API_KEY before using the live model provider."
            )
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderConfigurationError(
                "The openai package is required for the live model provider."
            ) from exc

        options: dict[str, Any] = {
            "api_key": self._api_key,
            "timeout": self.timeout,
            "max_retries": 0,
        }
        if self._base_url:
            options["base_url"] = self._base_url
        try:
            self._client = OpenAI(**options)
        except Exception:
            raise ProviderConfigurationError(
                "Could not initialize the configured OpenAI-compatible client."
            ) from None
        from .tracing import wrap_model_client

        self._client = wrap_model_client(self._client)
        return self._client

    def next(self, messages: Sequence[Mapping[str, Any]], tools: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        """Request one turn after reserving conservative estimated spend."""
        budget = self._require_budget()
        client = self._get_client()
        wire_messages = _wire_messages(messages)
        request_body = {
            "model": self.model,
            "messages": wire_messages,
            "tools": list(tools) if tools else None,
        }
        input_byte_bound = len(
            json.dumps(request_body, ensure_ascii=False, default=str).encode("utf-8")
        ) + self.INPUT_TOKEN_OVERHEAD
        reservation_id, upper_estimate = budget.reserve(input_byte_bound, self.max_output_tokens)

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=wire_messages,
                tools=list(tools) if tools else None,
                max_completion_tokens=self.max_output_tokens,
                timeout=self.timeout,
            )
        except Exception:
            pending = budget.abandon_as_uncertain(reservation_id)
            raise ProviderRequestError(
                "The configured model request failed; its conservative spend estimate remains reserved.",
                float(pending),
            ) from None

        choices = _value(response, "choices", ())
        if not choices:
            budget.abandon_as_uncertain(reservation_id)
            raise ProviderResponseError("Model response did not contain a choice.")
        message = _value(choices[0], "message")
        if message is None:
            budget.abandon_as_uncertain(reservation_id)
            raise ProviderResponseError("Model response did not contain a message.")

        calls = []
        for call in _value(message, "tool_calls", ()) or ():
            function = _value(call, "function")
            call_id = _value(call, "id")
            name = _value(function, "name")
            raw_arguments = _value(function, "arguments", "{}")
            if not isinstance(call_id, str) or not call_id or not isinstance(name, str) or not name:
                budget.abandon_as_uncertain(reservation_id)
                raise ProviderResponseError("Model returned a tool call without a valid id and name.")
            try:
                arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
            except (TypeError, json.JSONDecodeError) as exc:
                budget.abandon_as_uncertain(reservation_id)
                raise ProviderResponseError("Model returned invalid JSON tool arguments.") from exc
            if not isinstance(arguments, dict):
                budget.abandon_as_uncertain(reservation_id)
                raise ProviderResponseError("Tool arguments must decode to a JSON object.")
            calls.append({"id": call_id, "name": name, "arguments": arguments})

        usage_obj = _value(response, "usage")
        input_tokens = _value(usage_obj, "prompt_tokens")
        output_tokens = _value(usage_obj, "completion_tokens")
        usage: dict[str, Any] = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }
        prompt_details = _value(usage_obj, "prompt_tokens_details")
        cache_tokens = _value(prompt_details, "cached_tokens")
        if (
            isinstance(cache_tokens, int)
            and not isinstance(cache_tokens, bool)
            and isinstance(input_tokens, int)
            and not isinstance(input_tokens, bool)
            and 0 <= cache_tokens <= input_tokens
        ):
            usage["cache_tokens"] = cache_tokens
        total_tokens = _value(usage_obj, "total_tokens")
        if total_tokens is not None:
            usage["total_tokens"] = total_tokens

        estimate = budget.settle(reservation_id, input_tokens, output_tokens)
        cost_metadata = {
            "status": "measured_usage" if estimate is not None else "unverified",
            "currency": "USD",
            "estimated_cost_usd": float(estimate) if estimate is not None else None,
            "pending_upper_bound_usd": float(upper_estimate) if estimate is None else 0.0,
            "cumulative_estimated_usd": float(budget.spent_estimate_usd),
            "remaining_estimated_usd": float(budget.remaining_estimate_usd),
            "rates_source": "explicit_user_configuration",
            "billing_guarantee": False,
        }
        usage["cost_estimate"] = cost_metadata
        if estimate is not None:
            usage["estimated_cost_usd"] = float(estimate)
        return {
            "tool_calls": calls,
            "content": _value(message, "content") or "",
            "usage": usage,
        }


def _validate_base_url(value: str) -> None:
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        if not hostname or parsed.username or parsed.password or parsed.fragment:
            raise ValueError
        if parsed.scheme == "https":
            return
        if parsed.scheme != "http":
            raise ValueError
        if hostname.lower() == "localhost":
            return
        address = ipaddress.ip_address(hostname)
        if address.is_loopback:
            return
    except ValueError as exc:
        raise ProviderConfigurationError(
            "OPENAI_BASE_URL must use HTTPS, or HTTP on localhost/loopback for local testing."
        ) from exc
    raise ProviderConfigurationError(
        "OPENAI_BASE_URL must use HTTPS, or HTTP on localhost/loopback for local testing."
    )


class FakeProvider:
    """Explicit testing-only provider that returns prearranged, zero-cost responses."""

    def __init__(self, responses: Sequence[Mapping[str, Any]]) -> None:
        self._responses = list(responses)
        self.calls = 0

    def next(self, messages: Sequence[Mapping[str, Any]], tools: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        del messages, tools
        if self.calls >= len(self._responses):
            raise ProviderResponseError("Fake provider response queue is exhausted.")
        self.calls += 1
        response = dict(self._responses[self.calls - 1])
        response.setdefault("tool_calls", [])
        response["content"] = response.get("content") or ""
        response.setdefault("usage", {"input_tokens": 0, "output_tokens": 0})
        usage = dict(response["usage"])
        usage["provider"] = "fake"
        usage["mode"] = "testing"
        response["usage"] = usage
        return {key: response[key] for key in ("tool_calls", "content", "usage")}
