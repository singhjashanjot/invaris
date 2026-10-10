import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from invaris import integrations


class IntegrationTests(unittest.TestCase):
    def test_model_configuration_distinguishes_available_and_configured(self):
        missing = integrations.check_model_configuration(env={})
        self.assertEqual(missing.state, "available")
        self.assertEqual(
            set(missing.details["missing_settings"]),
            {
                "INVARIS_MODEL",
                "OPENAI_API_KEY or LITELLM_API_KEY with OPENAI_BASE_URL",
                "INVARIS_MAX_SPEND_USD",
                "INVARIS_INPUT_USD_PER_MILLION",
                "INVARIS_OUTPUT_USD_PER_MILLION",
            },
        )
        result = integrations.check_model_configuration(
            env={
                "INVARIS_MODEL": "declared-model",
                "OPENAI_API_KEY": "set",
                "INVARIS_MAX_ESTIMATED_COST_USD": "2",
                "INVARIS_INPUT_USD_PER_MILLION": "1",
                "INVARIS_OUTPUT_USD_PER_MILLION": "3",
            }
        )
        self.assertEqual(result.state, "configured")
        self.assertEqual(result.details["connectivity"], "unverified")

    def test_provider_is_unavailable_until_cap_and_rates_are_set(self):
        result = integrations.check_model_configuration(
            env={"INVARIS_MODEL": "m", "OPENAI_API_KEY": "present"}
        )
        self.assertEqual(result.state, "available")
        self.assertEqual(len(result.details["missing_budget_settings"]), 3)

    def test_litellm_key_requires_a_nonblank_base_url(self):
        base = {
            "INVARIS_MODEL": "m",
            "LITELLM_API_KEY": "present",
            "INVARIS_MAX_SPEND_USD": "1",
            "INVARIS_INPUT_USD_PER_MILLION": "1",
            "INVARIS_OUTPUT_USD_PER_MILLION": "1",
        }
        for base_url in (None, "", "  "):
            env = dict(base)
            if base_url is not None:
                env["OPENAI_BASE_URL"] = base_url
            result = integrations.check_model_configuration(env=env)
            self.assertEqual(result.state, "available")
            self.assertIn("OPENAI_BASE_URL", result.details["missing_settings"][0])

        result = integrations.check_model_configuration(
            env={**base, "OPENAI_BASE_URL": "https://provider.example/v1"}
        )
        self.assertEqual(result.state, "configured")
        self.assertEqual(result.details["base_url"], "https://provider.example/v1")

    def test_openai_key_takes_precedence_over_litellm_key(self):
        result = integrations.check_model_configuration(
            env={
                "INVARIS_MODEL": "m",
                "OPENAI_API_KEY": "openai",
                "LITELLM_API_KEY": "litellm",
                "INVARIS_MAX_SPEND_USD": "1",
                "INVARIS_INPUT_USD_PER_MILLION": "1",
                "INVARIS_OUTPUT_USD_PER_MILLION": "1",
            }
        )
        self.assertEqual(result.state, "configured")

    def test_canonical_budget_and_rates_make_provider_configured(self):
        result = integrations.check_model_configuration(
            env={
                "INVARIS_MODEL": "m",
                "OPENAI_API_KEY": "present",
                "INVARIS_MAX_SPEND_USD": "1.25",
                "INVARIS_INPUT_USD_PER_MILLION": "0.5",
                "INVARIS_OUTPUT_USD_PER_MILLION": "2.0",
            }
        )
        self.assertEqual(result.state, "configured")

    def test_invalid_budget_rates_are_not_reported_configured(self):
        result = integrations.check_model_configuration(
            env={
                "INVARIS_MODEL": "m",
                "OPENAI_API_KEY": "present",
                "INVARIS_MAX_SPEND_USD": "not-money",
                "INVARIS_INPUT_USD_PER_MILLION": "1",
                "INVARIS_OUTPUT_USD_PER_MILLION": "2",
            }
        )
        self.assertEqual(result.state, "unverified")

    def test_neatlogs_probe_requires_key_without_running_command(self):
        with patch.object(integrations.subprocess, "run") as run:
            result = integrations.check_neatlogs(probe=True, env={})
        run.assert_not_called()
        self.assertEqual(result.state, "available")
        self.assertIn("no probe was run", result.reason)

    def test_neatlogs_validates_doctor_v2_payload(self):
        payload = {
            "format_version": "neatlogs.doctor/v2",
            "status": "pass",
            "first_failure": None,
            "runtime": {"language": "python", "schema_version": "2", "sdk_version": "1.4.26"},
            "checks": [{"name": "local", "status": "pass"}],
        }
        with patch.object(integrations.importlib.metadata, "version", return_value="1.4.26"), patch.object(
            integrations.subprocess,
            "run",
            return_value=SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr=""),
        ):
            result = integrations.check_neatlogs(env={})
        self.assertEqual(result.state, "available")
        self.assertEqual(result.details["schema_version"], "2")

    def test_doctor_rejects_wrong_schema(self):
        payload = {"format_version": "neatlogs.doctor/v1"}
        with patch.object(
            integrations.subprocess,
            "run",
            return_value=SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr=""),
        ):
            result = integrations.check_neatlogs(env={})
        self.assertEqual(result.state, "unverified")
        self.assertIn("format_version", result.reason)

    def test_partner_evidence_is_inventoried_but_unverified(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "checkpoint.json"
            artifact.write_text('{"checkpoint":"local"}', encoding="utf-8")
            result = integrations.inspect_partner_evidence("entire", [artifact])
        self.assertEqual(result.state, "unverified")
        self.assertTrue(result.details["artifacts"][0]["sha256"])
        self.assertEqual(integrations.inspect_partner_evidence("cfo.ai", []).state, "unavailable")
