# Neatlogs tracing evidence

## Integration

Invaris is one Python CLI agent service using the OpenAI client directly, without an agent framework. The C TLS fixture does not call a model and is not instrumented. The model-capable CLI entry points are `run` and `evaluate`. Neatlogs SDK `1.4.26` wraps the client; workflow and tool spans capture sanitized inputs, outputs, errors, and trace IDs. Each CLI process initializes once and flushes/shuts down in `finally`.

The SDK project is `2dfd398b-9874-4878-9a9a-d9fe62e6cdbe`; its ingest host is `ingest.neatlogs.com`. The ignored local `.env` provides SDK configuration. Never publish it, its contents, credentials, or personalized endpoints. SDK readback and the public API CLI are separate paths.

## Verified application readback

The installed SDK trace-read endpoint was used to retrieve actual application traces. These are not synthetic Doctor traces and not public CLI OAuth readbacks:

- Trace `40733e2a561180a013f0a3bad929e3a0` returned 9 spans, including 5 LLM spans. Its trace status was `error`; this verifies trace persistence/readback, not a successful migration or agent outcome.
- Trace `4b821a1ab8e2fe622c7abd31cbd11f50` returned 18 spans, including 7 LLM spans. Actual LLM tool use was independently verified, but the agent exhausted its 24k token budget, so its status remains `UNVERIFIED`.

The live batch `090330` is still running and has no final results. Some interrupted batch attempts remain `processing` (HTTP 202) or failed (HTTP 409). The evidence record includes pending/error attempts and will be extended as new records are collected. Do not summarize the batch as fully verified or treat these two standalone runs as a matched evaluation or final scores. See `docs/evidence/neatlogs-application-readback.json`.

These readbacks establish persisted tracing only. The independent fixture verifier remains the source of TLS/application contract evidence. Trace volume is not a quality metric, and no token-saving or improvement claim is made from these traces.

## Operator paths

The currently configured matched live evaluation runs at `artifacts/evaluations/090330bb-2602-4397-9b7e-c6bc13e29d0d`. Resume it with `python -m invaris evaluate --resume-evaluation <directory>` as documented in `docs/operations.md`; do not reset project spend or start a replacement and call it matched. Collect exact trace IDs and completed SDK readbacks for all relevant attempts before reporting aggregate tracing coverage.

The SDK Doctor remote synthetic probe was separately verified earlier. Its result verifies the SDK telemetry path, not application instrumentation. No public Neatlogs CLI authentication/readback is claimed here.
