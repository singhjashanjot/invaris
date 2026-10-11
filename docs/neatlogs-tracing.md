# Neatlogs tracing evidence

## Integration

Invaris is one Python CLI agent service using the OpenAI client directly, without an agent framework. The C TLS fixture does not call a model and is not instrumented. The model-capable CLI entry points are `run` and `evaluate`. Neatlogs SDK `1.4.26` wraps the client; workflow and tool spans capture sanitized inputs, outputs, errors, and trace IDs. Each CLI process initializes once and flushes/shuts down in `finally`.

The SDK project is `2dfd398b-9874-4878-9a9a-d9fe62e6cdbe`; its ingest host is `ingest.neatlogs.com`. The ignored local `.env` provides SDK configuration. Never publish it, its contents, credentials, or personalized endpoints. SDK readback and the public API CLI are separate paths.

## Verified application readback

The installed SDK trace-read endpoint was used to retrieve actual application traces. These are not synthetic Doctor traces and not public CLI OAuth readbacks:

- Trace `40733e2a561180a013f0a3bad929e3a0` returned 9 spans, including 5 LLM spans. Its trace status was `error`; this verifies trace persistence/readback, not a successful migration or agent outcome.
- Trace `4b821a1ab8e2fe622c7abd31cbd11f50` returned 18 spans, including 7 LLM spans. Actual LLM tool use was independently verified, but the agent exhausted its 24k token budget, so its status remains `UNVERIFIED`.

The new matched-study readback in `docs/evidence/matched-study-trace-readback.json` contains HTTP 409, HTTP 404, and partial HTTP 200 outcomes. None establishes full trace coverage for the study. SDK graceful shutdown was observed and the SDK Doctor probe passes again; neither establishes application trace delivery or complete readback. The `090330` pre-parser/security study has 63 recorded attempts, but its tracing evidence is incomplete. Do not infer full coverage or final results from partial readbacks. See `docs/evidence/matched-study-trace-readback.json` for the current matched-study readback and `docs/evidence/neatlogs-application-readback.json` for the standalone traces above.

These readbacks establish persisted tracing only. The independent fixture verifier remains the source of TLS/application contract evidence. Trace volume is not a quality metric, and no token-saving or improvement claim is made from these traces.

## October 12 application coverage verification

Refreshed SDK readback now structurally verifies all seven original V1 traces and five original V2 traces, including actual failed-action recovery with the failed tool span present. Two historical V2 traces remain partial. Separate fresh V2 migration and no-op executions now have complete model/tool/workflow/rollback counts, so all seven scenarios have real verified V2 cloud application evidence. Fresh executions are not substituted into the original matched study.

The pure offline `trace-audit` gate compares identities, graph structure, and actual span counts against local run receipts; HTTP 200 alone cannot pass it. See `docs/trace-audit.md` and `docs/evidence/neatlogs-oct12-coverage.json`. Earlier observations below remain dated historical evidence, not the current overall application coverage status. Exact historical missing-span cause is unresolved.

## Operator paths

The final-source study `ebeea671-7e12-4493-9531-04456a74efeb` completed and gracefully shut down the SDK. All SDK queue-drop, export-failure, truncation, and overflow counters were zero. Readback after shutdown still reports two partial HTTP 200 traces, three HTTP 404 traces, and two HTTP 409 traces marked `dlq` across the seven V2 attempts. The successful synthetic Doctor probe is separate. See `docs/evidence/final-study-trace-readback.json` and `docs/evidence/neatlogs-doctor.json`; no full application coverage is claimed. The exact SDK/backend persistence or readback cause is unresolved, and this remains a release gate for complete partner evidence.

The SDK Doctor remote synthetic probe was separately verified earlier. Its result verifies the SDK telemetry path, not application instrumentation. No public Neatlogs CLI authentication/readback is claimed here.
