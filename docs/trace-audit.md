# Cloud trace audit

The `trace-audit` CLI compares a saved Neatlogs SDK readback with a local run's `result.json`. It makes no network, model, mutation, or Docker calls. Exit 0 means the supplied snapshot passes structural coverage; exit 1 means incomplete/invalid coverage. Invalid file/JSON input returns the normal CLI error.

The audit checks trace/project identity, unique span IDs, reported counts, one named workflow root, the migration child workflow, parent resolution, cycles/disconnection, model/tool counts, and a rollback span where the local row says rollback was verified. Rollback is additional to the agent tool count. Null rollback metadata is not a positive rollback claim. Input is bounded to 1024 spans; credentials and model messages are not returned. This is not authenticated attestation and cannot establish continuous availability or prove that a forged input file is genuine.

## Local example

The following actual October 12 application run and sanitized private readback are already available on the development machine:

```powershell
.venv\Scripts\python.exe -m invaris trace-audit `
  --expected artifacts/runs/7f94ea34-a622-4533-9a6c-6ac7f2ae135d/result.json `
  --readback artifacts/private/trace-readback-7f94ea34-a622-4533-9a6c-6ac7f2ae135d.json `
  --project-id 2dfd398b-9874-4878-9a9a-d9fe62e6cdbe
```

On this machine the reproduction interpreter is `.tools/repro-venv/Scripts/python.exe`. A new clone must collect its own real run and cloud readback; private artifacts are not committed.

The readback format is the SDK Doctor response shape: `_id`, `projectId`, `spanCount`, optional `llmCalls`/`toolCalls`, and a `spans` array with `span_id`, `parent_span_id`, and `span_metadata.node_name`/`node_type`. Only semantic identities/counts are needed; do not save or publish raw model content unnecessarily. The public API CLI has a different response shape and authentication; do not pass its output as this shape without an explicit reviewed conversion. Never use an SDK project key as a public CLI token.

## October 12 verification

All seven original V1 cloud traces pass. Five original V2 traces now pass after delayed processing, including the failed-action/recovery trace. Two original V2 traces still fail and are retained unchanged. Separate fresh V2 migration and no-op runs pass with all expected model/tool/workflow/rollback spans. Thus every seeded scenario has a verified V2 application trace, but the original matched study still has two partial V2 cloud records. Fresh runs are not substituted into that study or called matched repetitions.

See `evidence/neatlogs-oct12-coverage.json`; detailed sanitized recovery and policy-before/after snapshots are also retained there. The historical gate now automatically catches the two partial records instead of relying on HTTP 200 or zero SDK errors. The exact cause of their missing spans is not established.
