# Invaris operator guide

## Boundary and current status

This release operates only on the owned disposable TLS fixture. It does not migrate arbitrary production services, change certificate authentication to post-quantum signatures, or prove whole-stack quantum safety. The target is a fresh authenticated TLS 1.3 connection using `X25519MLKEM768`, with the supported application response and approved client expectations intact.

The source implementation is present. Local tests provide component evidence; they do not prove live-model improvement, external partner completion, or production readiness. A fresh Python 3.12 virtual environment installed the lock and editable package successfully, passed dependency consistency checks, and passed 134 unit tests plus six subtests on October 11, 2026. Ruff passed. Seven integration tests were deliberately deselected. The fixture image rebuilt successfully, including compilation with warnings treated as errors. After the tracing setup request, the application and integration suite have not been run again; the existing running sandbox can still use an older image. Run `setup` yourself before verifying the latest application. Independent clean-machine and current-image runtime validation remain release gates.

## Prerequisites and installation

- Python 3.12 or newer, with a virtual environment.
- Docker Engine with Compose and Linux containers, directly or through WSL on Windows. The Windows adapter uses the default WSL distribution if native Docker is unavailable.
- Network access to download the pinned image, verified OpenSSL source, and Python packages.
- Optional live mode: model credential, model selection, explicit token prices, and an authorized total USD estimate cap.

From the repository root, in PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.lock
.venv\Scripts\python.exe -m pip install --no-deps -e .
```

On Linux use `python3.12` and `.venv/bin/python` instead. The lock pins versions but does not contain wheel hashes or constitute a supply-chain attestation. Fresh-machine setup is not yet independently validated.

The ignored `.env` contains local credentials. Preserve the existing file; do not overwrite it with `.env.example`. The CLI loads `.env` before tracing and provider initialization. Never put secrets in command arguments, public bundles, screenshots, or commits.

## Commands the operator runs

Review the README scope before authorizing changes. `setup` builds the fixture and initializes its ephemeral CA and owned volumes:

```powershell
.venv\Scripts\python.exe -m invaris setup
.venv\Scripts\python.exe -m invaris run --offline --approve-sandbox --scenario wrong_active_group
.venv\Scripts\python.exe -m invaris evaluate --offline --approve-sandbox --include-held-out
```

`--offline` is an explicitly scripted smoke model. Its comparison is NOT live agent-improvement evidence.

Every evaluation also runs a separate `Fixed script` arm using deterministic supported remediation under the same scoped tools and independent verifier. That arm never invokes a language model, records zero model tokens/inference cost, and is labeled `fixed-script-baseline-not-LLM`. V1/V2 offline smoke arms are still scripts, not live agents. The report exposes all three arms, denominators, readiness claims versus gated agent status, control mismatches, and unmatched attempts.

Live mode omits `--offline` and requires these settings in `.env`:

```text
INVARIS_MODEL=<approved model identifier>
OPENAI_API_KEY=<local credential>
OPENAI_BASE_URL=<optional HTTPS compatible provider endpoint>
INVARIS_MAX_SPEND_USD=<explicitly authorized total estimate cap>
INVARIS_INPUT_USD_PER_MILLION=<explicit input token price>
INVARIS_OUTPUT_USD_PER_MILLION=<explicit output token price>
```

No model identifier, price, or spending authorization is inferred. The project ledger in `artifacts/private/model-spend.json` reserves estimated spend before network calls and retains uncertain reservations. Do not reset it to silently extend authorization. Estimates are not provider invoices or a guaranteed billing ceiling. A project file lock prevents parallel paid runs.

Each scenario resets the named fixture; never run two workflows against the same fixture project concurrently. Use separate `invaris-*` project names if isolation is required. Agent mutations recheck the approved instance and candidate digest inside the fixture control lock before changing state. Corrupted configurations are rejected before stopping the running server. TLS transport failure is not treated as proof that the strict classical client was rejected. Neither the TLS endpoint nor the private fixture network is exposed publicly. The Docker build context is allowlisted to fixture sources, excluding `.env` and private artifacts.

## Results and review

Run artifacts are under `artifacts/runs/<run-id>`. They include the approved contract, baseline, sanitized implementation snapshot and original source hashes, agent/tool history, independent verification, rollback/reapplication evidence, result, HTML report, checkpoint, and integrity manifest. The snapshot excludes `.env` and local credentials; original hashes are not signed provenance, and redacted source text can differ from the hashed bytes. Evaluation artifacts are under `artifacts/evaluations/<comparison-id>`, including all per-run rows, JSON comparison, CSV, report, and manifest. Generated run/evaluation artifacts are ignored by version control.

```powershell
.venv\Scripts\python.exe -m invaris verify-bundle --directory artifacts/runs/<run-id>
```

The manifest checks the listed public artifact bytes, not their authenticity or completeness. It intentionally excludes private checkpoints. A malicious party who replaces both artifacts and manifest can recompute the hashes. Human review must also inspect receipt identity, fresh connection evidence, statuses, failed actions, rollback results, and limitations. `VERIFIED` means the declared fixture contract passed, not production deployment approval.

Core checkpoint save/resume behavior is tested at the library level. There is no operator CLI resume command yet; do not edit checkpoint JSON or replay interrupted mutations manually. Missing evidence must remain `UNVERIFIED`, and incompatible required client policy must remain `BLOCKED`.

## Partner evidence

- Neatlogs: SDK Doctor local and remote synthetic probe passed. Follow `neatlogs-tracing.md` to verify a real application trace; model capture needs a live run.
- Entire: the verified local CLI binary is available under `.tools/entire`, but capture is not enabled. The workspace is not a Git repository; initialization, commits and publication need explicit authorization. Do not fabricate development checkpoints.
- cfo.ai: the browser is still on its sign-in page. `business` prepares measured assumptions only, not a cfo.ai-generated plan. Pricing, costs, revenue and runway must come from a real approved planning session/export.

```powershell
.venv\Scripts\python.exe -m invaris business --results artifacts/evaluations/<comparison-id>/runs.json
```

The remaining external prerequisites were requested together: authorized model settings/spending, cfo.ai sign-in, Git/commit/publication permission, and public-post/video approval. Actual source eligibility and partner sharing must be confirmed before submission.

## Validation and cleanup

```powershell
.venv\Scripts\python.exe -m pytest -m "not integration"
.venv\Scripts\python.exe -m ruff check src tests
.venv\Scripts\python.exe -m pip check
$env:INVARIS_RUN_INTEGRATION="1"
.venv\Scripts\python.exe -m pytest -m integration
```

Integration tests launch their own named disposable fixture projects. They are opt-in and do not call a live model. CI is configured but has not been executed on a hosted repository.

```powershell
.venv\Scripts\python.exe -m invaris cleanup
.venv\Scripts\python.exe -m invaris cleanup --delete-volumes
```

The first command preserves owned state; the second explicitly deletes the selected owned volumes, including the ephemeral CA and fixture state. Neither command is a global Docker prune.

## Release gates still open

1. Start the rebuilt fixture, verify its current-image runtime behavior, and reproduce setup on an independent clean machine.
2. Real live-model baseline and improved matched evaluation, retaining all attempts.
3. Actual application traces with failed-action recovery and trace-informed change.
4. Entire development evidence and genuine cfo.ai export.
5. Authorized public repository, sanitized public progress, and under-three-minute demo.
6. Independent security/cryptographic review before any expansion beyond the sandbox.
