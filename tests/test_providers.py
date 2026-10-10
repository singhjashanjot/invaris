import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from invaris.contracts import ModelReply
from invaris.providers import (
    BudgetLimitError,
    FakeProvider,
    OpenAICompatibleProvider,
    ProviderConfigurationError,
    ProviderRequestError,
    ProviderResponseError,
)


class StubCompletions:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.kwargs = None
        self.call_count = 0

    def create(self, **kwargs):
        self.kwargs = kwargs
        self.call_count += 1
        if self.error:
            raise self.error
        return self.response


class StubClient:
    def __init__(self, completions):
        self.chat = type("Chat", (), {"completions": completions})()


class ProviderTests(unittest.TestCase):
    def test_internal_tool_history_is_serialized_without_mutation(self):
        messages = [
            {"role": "assistant", "content": "Inspecting", "tool_calls": [
                {"id": "inspect-1", "name": "inspect_service", "arguments": {"target": "fixture"}}
            ]},
            {"role": "tool", "tool_call_id": "inspect-1", "content": {"ok": True}},
        ]
        completions = StubCompletions({
            "choices": [{"message": {"content": "UNVERIFIED: inspection only"}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 5},
        })
        self._provider(StubClient(completions)).next(messages, [])
        wire = completions.kwargs["messages"]
        self.assertEqual(wire[0]["tool_calls"][0], {
            "id": "inspect-1", "type": "function", "function": {
                "name": "inspect_service", "arguments": '{"target": "fixture"}'
            }
        })
        self.assertEqual(wire[1]["content"], '{"ok": true}')
        self.assertEqual(messages[0]["tool_calls"][0]["name"], "inspect_service")
        self.assertEqual(messages[1]["content"], {"ok": True})

    def _provider(self, client, **kwargs):
        return OpenAICompatibleProvider(
            "explicit-model",
            client=client,
            spend_limit_usd="2",
            input_usd_per_million="1",
            output_usd_per_million="2",
            **kwargs,
        )

    def test_provider_normalizes_calls_usage_and_estimated_cost(self):
        completions = StubCompletions(
            {
                "choices": [{"message": {
                    "content": "Checking the fixture.",
                    "tool_calls": [{
                        "id": "call-1",
                        "function": {"name": "inspect", "arguments": '{"target":"tls"}'},
                    }],
                }}],
                "usage": {"prompt_tokens": 14, "completion_tokens": 6, "total_tokens": 20},
            }
        )
        provider = self._provider(StubClient(completions))
        result = provider.next([{"role": "user", "content": "inspect"}], [{"type": "function"}])
        self.assertEqual(result["tool_calls"], [{"id": "call-1", "name": "inspect", "arguments": {"target": "tls"}}])
        self.assertEqual(set(result), {"tool_calls", "content", "usage"})
        validated = ModelReply.model_validate(result)
        self.assertEqual(validated.content, "Checking the fixture.")
        self.assertEqual(result["usage"]["input_tokens"], 14)
        self.assertEqual(result["usage"]["output_tokens"], 6)
        self.assertEqual(result["usage"]["total_tokens"], 20)
        self.assertAlmostEqual(result["usage"]["estimated_cost_usd"], 0.000026)
        self.assertEqual(result["usage"]["cost_estimate"]["status"], "measured_usage")
        self.assertFalse(result["usage"]["cost_estimate"]["billing_guarantee"])
        self.assertEqual(completions.kwargs["model"], "explicit-model")
        self.assertEqual(completions.kwargs["max_completion_tokens"], 1024)

    def test_tool_turn_with_null_content_validates_as_model_reply(self):
        response = {
            "choices": [{"message": {"content": None, "tool_calls": [{
                "id": "call-1", "function": {"name": "inspect", "arguments": "{}"}
            }]}}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 3},
        }
        result = self._provider(StubClient(StubCompletions(response))).next([], [])
        self.assertEqual(set(result), {"tool_calls", "content", "usage"})
        self.assertEqual(result["content"], "")
        ModelReply.model_validate(result)

    def test_cached_prompt_tokens_are_normalized_without_changing_billing(self):
        response = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {
                "prompt_tokens": 14,
                "completion_tokens": 6,
                "prompt_tokens_details": {"cached_tokens": 5},
            },
        }
        result = self._provider(StubClient(StubCompletions(response))).next([], [])
        self.assertEqual(result["usage"]["cache_tokens"], 5)
        self.assertAlmostEqual(result["usage"]["estimated_cost_usd"], 0.000026)
        ModelReply.model_validate(result)

    def test_missing_or_invalid_cached_prompt_tokens_are_omitted(self):
        details = [None, {}, {"cached_tokens": "3"}, {"cached_tokens": True},
                   {"cached_tokens": -1}, {"cached_tokens": 15}]
        for prompt_details in details:
            with self.subTest(prompt_details=prompt_details):
                response = {
                    "choices": [{"message": {"content": "ok"}}],
                    "usage": {"prompt_tokens": 14, "completion_tokens": 6},
                }
                if prompt_details is not None:
                    response["usage"]["prompt_tokens_details"] = prompt_details
                result = self._provider(StubClient(StubCompletions(response))).next([], [])
                self.assertNotIn("cache_tokens", result["usage"])
                ModelReply.model_validate(result)

    def test_live_call_without_cap_or_rates_does_not_request(self):
        completions = StubCompletions(response={})
        with patch.dict("os.environ", {}, clear=True):
            provider = OpenAICompatibleProvider("explicit-model", client=StubClient(completions))
        with self.assertRaisesRegex(ProviderConfigurationError, "USD_PER_MILLION"):
            provider.next([], [])
        self.assertEqual(completions.call_count, 0)

    def test_canonical_budget_env_precedes_legacy_alias(self):
        with patch.dict(
            "os.environ",
            {
                "INVARIS_MAX_SPEND_USD": "3",
                "INVARIS_MAX_ESTIMATED_COST_USD": "4",
                "INVARIS_INPUT_USD_PER_MILLION": "1",
                "INVARIS_OUTPUT_USD_PER_MILLION": "2",
            },
            clear=True,
        ):
            provider = OpenAICompatibleProvider("explicit-model", client=StubClient(StubCompletions()))
        self.assertEqual(provider.cost_budget.limit, 3)

    def test_legacy_budget_env_remains_supported(self):
        with patch.dict(
            "os.environ",
            {
                "INVARIS_MAX_ESTIMATED_COST_USD": "4",
                "INVARIS_INPUT_USD_PER_MILLION": "1",
                "INVARIS_OUTPUT_USD_PER_MILLION": "2",
            },
            clear=True,
        ):
            provider = OpenAICompatibleProvider("explicit-model", client=StubClient(StubCompletions()))
        self.assertEqual(provider.cost_budget.limit, 4)

    def test_call_is_rejected_before_request_when_upper_bound_exceeds_budget(self):
        completions = StubCompletions(response={})
        provider = OpenAICompatibleProvider(
            "explicit-model",
            client=StubClient(completions),
            spend_limit_usd="0.00001",
            input_usd_per_million="1",
            output_usd_per_million="1",
        )
        with self.assertRaises(BudgetLimitError):
            provider.next([], [])
        self.assertEqual(completions.call_count, 0)

    def test_uncertain_request_failure_keeps_reservation_and_hides_error(self):
        completions = StubCompletions(error=RuntimeError("private-token-value"))
        provider = OpenAICompatibleProvider(
            "explicit-model",
            client=StubClient(completions),
            spend_limit_usd="0.0024",
            input_usd_per_million="1",
            output_usd_per_million="2",
        )
        with self.assertRaises(ProviderRequestError) as caught:
            provider.next([{"role": "user", "content": "hello"}], [])
        self.assertNotIn("private-token", str(caught.exception))
        self.assertGreater(caught.exception.pending_estimate_usd, 0)
        self.assertGreater(provider.cost_budget.pending_estimate_usd, 0)
        with self.assertRaises(BudgetLimitError):
            provider.next([{"role": "user", "content": "hello"}], [])
        self.assertEqual(completions.call_count, 1)

    def test_base_url_requires_https_or_loopback_http(self):
        with self.assertRaises(ProviderConfigurationError):
            OpenAICompatibleProvider("m", base_url="http://api.example.test")
        with self.assertRaises(ProviderConfigurationError):
            OpenAICompatibleProvider("m", base_url="https://user:secret@example.test")
        for url in ("https://api.example.test/v1?api_key=secret", "https://api.example.test/v1?"):
            with self.subTest(url=url), self.assertRaises(ProviderConfigurationError):
                OpenAICompatibleProvider("m", base_url=url)
        provider = OpenAICompatibleProvider("m", base_url="http://127.0.0.1:8000/v1")
        self.assertEqual(provider._base_url, "http://127.0.0.1:8000/v1")
        provider = OpenAICompatibleProvider("m", base_url="https://api.example.test/v1")
        self.assertEqual(provider._base_url, "https://api.example.test/v1")

    def test_base_url_reads_openai_base_url(self):
        with patch.dict("os.environ", {"OPENAI_BASE_URL": "https://api.example.test/v1"}, clear=True):
            provider = OpenAICompatibleProvider("m")
        self.assertEqual(provider._base_url, "https://api.example.test/v1")

    def test_litellm_key_falls_back_for_custom_base_url(self):
        for openai_key in (None, "", "   "):
            environment = {
                "OPENAI_BASE_URL": "https://gateway.example.test/v1",
                "LITELLM_API_KEY": "litellm-secret",
            }
            if openai_key is not None:
                environment["OPENAI_API_KEY"] = openai_key
            with self.subTest(openai_key=openai_key), patch.dict("os.environ", environment, clear=True):
                provider = OpenAICompatibleProvider("m")
            self.assertEqual(provider._api_key, "litellm-secret")

    def test_litellm_key_is_not_used_for_default_openai(self):
        with patch.dict("os.environ", {"LITELLM_API_KEY": "litellm-secret"}, clear=True):
            provider = OpenAICompatibleProvider("m")
        self.assertIsNone(provider._api_key)

    def test_openai_key_takes_precedence_over_litellm_key(self):
        with patch.dict(
            "os.environ",
            {
                "OPENAI_BASE_URL": "https://gateway.example.test/v1",
                "OPENAI_API_KEY": "openai-secret",
                "LITELLM_API_KEY": "litellm-secret",
            },
            clear=True,
        ):
            provider = OpenAICompatibleProvider("m")
        self.assertEqual(provider._api_key, "openai-secret")

    def test_model_is_required_and_timeout_and_output_are_bounded(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ProviderConfigurationError, "INVARIS_MODEL"):
                OpenAICompatibleProvider()
        with self.assertRaises(ValueError):
            OpenAICompatibleProvider("explicit-model", timeout=121)
        with self.assertRaises(ValueError):
            OpenAICompatibleProvider("explicit-model", max_output_tokens=0)

    def test_credentials_are_required_for_sdk_client_creation(self):
        provider = OpenAICompatibleProvider(
            "explicit-model",
            api_key="",
            spend_limit_usd="1",
            input_usd_per_million="1",
            output_usd_per_million="1",
        )
        with self.assertRaisesRegex(ProviderConfigurationError, "OPENAI_API_KEY"):
            provider.next([], [])

    def test_non_object_tool_arguments_are_rejected(self):
        response = {"choices": [{"message": {"tool_calls": [{
            "id": "call-1", "function": {"name": "inspect", "arguments": "[]"}
        }]}}]}
        provider = self._provider(StubClient(StubCompletions(response)))
        with self.assertRaisesRegex(ProviderResponseError, "JSON object"):
            provider.next([], [])

    def test_fake_provider_marks_testing_mode(self):
        provider = FakeProvider([{"content": "fixture", "usage": {"input_tokens": 1}}])
        result = provider.next([], [])
        self.assertEqual(set(result), {"tool_calls", "content", "usage"})
        self.assertEqual(result["usage"]["provider"], "fake")
        self.assertEqual(result["usage"]["mode"], "testing")
        self.assertEqual(result["tool_calls"], [])
        self.assertEqual(result["usage"], {"input_tokens": 1, "provider": "fake", "mode": "testing"})
