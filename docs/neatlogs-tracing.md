# Neatlogs tracing setup

## Scope

Invaris is one Python CLI agent service using the OpenAI client directly, without an agent framework. The C TLS fixture does not call a model and is not instrumented. The independent model-capable CLI entry points are `run` and `evaluate`.

- Project: `2dfd398b-9874-4878-9a9a-d9fe62e6cdbe`.
- SDK: Neatlogs `1.4.26`, the latest version returned by pip on October 11, 2026.
- Ingest endpoint: `https://ingest.neatlogs.com`.
- `run` workflow: `tls-migration`.
- `evaluate` workflow: `migration-comparison`; each scenario invocation has its own root trace.
- OpenAI calls have one capture owner: `neatlogs.wrap(client)`. Existing workflow/tool spans group calls and record sanitized inputs, outputs, errors, and trace IDs.
- Each CLI process initializes once, then flushes and shuts down in `finally`, including on failure.

The supplied SDK key is stored in the ignored root `.env`. The CLI loads that file before initialization. Never publish `.env`, copy its contents into artifacts, or use this SDK key as public API CLI authentication. No detections, alerts, or eval configuration was added by this tracing setup.

## Verification performed

The official SDK commands were executed with `.env` loaded in the child environment, not with a key on the command line:

```powershell
.venv\Scripts\python.exe -m neatlogs doctor --local --endpoint https://ingest.neatlogs.com --json
.venv\Scripts\python.exe -m neatlogs doctor --probe --endpoint https://ingest.neatlogs.com --json
```

Both returned exit code zero and Doctor v2 `status: pass`. The remote synthetic trace `6430bd586a384976086173583ea2db89` was visible and finalized, with four spans, one root, valid hierarchy and input/output, numeric token totals, and zero duplicate spans.

This verifies the SDK telemetry pipeline, not the application. No Invaris command or live model request was run during this setup.

## Application verification: waiting on the user

The source and fixture image have changed since the previous sandbox run. Refresh the owned sandbox and run an instrumented entry point yourself:

```powershell
.venv\Scripts\python.exe -m invaris setup
.venv\Scripts\python.exe -m invaris run --offline --approve-sandbox --scenario wrong_active_group
```

Offline mode exercises workflow/tool spans without model spending; it is not evidence of LLM capture or model improvement. Return the result, especially `metadata.trace_id`, to verify the actual application trace. Live-mode verification additionally requires the existing model credential, model selection, explicit rates, and authorized spend cap.

## Optional public API CLI readback: waiting on a human

SDK Doctor readback succeeded without CLI login. Separate CLI readback has not been performed: it requires human device approval or a securely provided service-account token. Use dashboard host `https://app.neatlogs.com` explicitly on every CLI command, inspect profiles first, and use profile `setup-https---app-neatlogs-com` only if unused or bound to that exact origin. Exclude SDK credentials from CLI child processes. Do not pass project context to project discovery.
