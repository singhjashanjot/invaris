# Invaris operator guide

## Current verified status

This is a sandbox release for the owned disposable TLS fixture. It does not migrate arbitrary production services, change certificate authentication to post-quantum signatures, or establish whole-system quantum safety. Fresh authenticated TLS 1.3 key exchange and the supported application response are checked against the fixture contract.

As of October 11, 2026, the current test baseline passed 150 tests plus 9 subtests, with 7 real integration tests; Ruff and the pip audit passed. Full integration CI run `38087724134` succeeded on commit `08cb143`. The current-image setup ran and confirmed OpenSSL 3.5.9. Fresh-machine setup remains an open gate.

A matched live evaluation with 3 repetitions, 7 scenarios, and 3 arms is running in `artifacts/evaluations/090330bb-2602-4397-9b7e-c6bc13e29d0d`. The earlier 3-repetition run stopped after 26 completed rows and one incomplete row; it is preserved as exploratory evidence and its partial results are not final scores.

## Prerequisites and setup

- Python 3.12 or newer and a virtual environment.
- Docker Engine with Compose and Linux containers, directly or through WSL on Windows.
- Network access for pinned images, verified OpenSSL source, and Python packages.
- Live mode additionally uses the already configured provider and the current authorized local estimate cap. Do not copy credentials or personalized endpoints into docs, reports, or command history.

From the repository root in PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.lock
.venv\Scripts\python.exe -m pip install --no-deps -e .
.venv\Scripts\python.exe -m invaris setup
```

On Linux use `python3.12` and `.venv/bin/python`. The lock has no wheel hashes and is not a supply-chain attestation. Do not overwrite the ignored `.env` with `.env.example` or expose credential values.

## Implemented commands

```powershell
.venv\Scripts\python.exe -m invaris run --offline --approve-sandbox --scenario wrong_active_group
.venv\Scripts\python.exe -m invaris evaluate --offline --approve-sandbox --include-held-out
.venv\Scripts\python.exe -m invaris evaluate --resume-evaluation artifacts/evaluations/090330bb-2602-4397-9b7e-c6bc13e29d0d
```

Offline mode is a scripted smoke model, not evidence of live agent improvement. The evaluation has V1, V2, and a deterministic fixed-script arm; the latter invokes no model. The running matched live evaluation should be resumed with `--resume-evaluation <directory>`; do not restart it as a fresh evaluation. Resume requires the integrity manifest and binds semantic source hashes, effective model, rates, budget, and scenarios. It does not reset project spend. The total configured limits for both versions are 64k tokens, 16 steps, 24 tool calls, and 600 seconds.

## Live model, rates, and ledger

The live gateway is configured for Claude Haiku; its effective Bedrock model is Haiku 4.5. The current authorized local estimate cap is $10. The provider's remote cap of $20 rejects a key update with HTTP 401; do not describe that remote cap as usable authorization or include endpoint/credential details in public documentation.

The local ledger uses conservative configured rates of $2.20 per million input tokens and $5.50 per million output tokens. Gateway metadata reports ordinary input at $1.10 and output at $5.50; the configured input rate uses the higher cache-write rate. These are conservative local estimates, not a provider invoice or guaranteed billing ceiling. `LITELLM_API_KEY` is a fallback only for a custom base URL when `OPENAI_API_KEY` is absent.

The ledger at `artifacts/private/model-spend.json` reserves estimated spend before network calls and retains uncertain reservations. Never reset it to extend authorization. A project file lock prevents parallel paid runs. See the current manifest and ledger before resuming or starting another paid workload.

## Isolation and result review

Each scenario resets the named fixture; do not run concurrent workflows against the same fixture project. Mutations recheck the approved instance and candidate digest under the fixture control lock. Corrupt configurations are rejected before stopping the server. TLS transport failure alone does not prove that a strict classical client was rejected. Neither the TLS endpoint nor private fixture network is exposed publicly; the Docker build context excludes `.env` and private artifacts.

Run artifacts live in `artifacts/runs/<run-id>` and evaluation outputs in `artifacts/evaluations/<comparison-id>`. Review the contract, candidate/source hashes, tool history, independent connection and application receipts, failed actions, rollback/reapplication evidence, statuses, and manifest. The manifest detects changes to listed bytes; it does not establish authenticity or completeness. `VERIFIED` means the declared fixture contract passed, not that production deployment is approved.

To verify a run bundle:

```powershell
.venv\Scripts\python.exe -m invaris verify-bundle --directory artifacts/runs/<run-id>
```

## Partner evidence and business model

- Neatlogs SDK readback verified real application trace `40733e2a561180a013f0a3bad929e3a0` with 9 spans, including 5 LLM spans; its trace status was `error`. Trace `4b821a1ab8e2fe622c7abd31cbd11f50` read back with 18 spans, including 7 LLM spans, and independently verified actual LLM tool use; the agent outcome is `UNVERIFIED` because its 24k token budget was exhausted. These are SDK readback-path results, not public CLI results. Live batch `090330` is still running with no final results; some batch traces remain processing or failed. The evidence JSON records pending/error attempts and will receive subsequent records.
- Entire's seven Codex hooks await approval. One genuine local checkpoint was captured using the supported `entire session attach` recovery command and linked to the initial public commit. No hosted Entire GitHub App authorization or hosted checkpoint link is verified. Automatic hooks and session upload are not claimed.
- The shared cfo.ai artifact was reviewed across all six pages and 39 Main Scenario months. The actual shared artifact is the source; no official export was needed. The $6 inference placeholder is not a measured cost. Cost reconciliation remains pending.

The project directory itself should provide the current business command usage and evaluation inputs:

```powershell
.venv\Scripts\python.exe -m invaris business --results artifacts/evaluations/<comparison-id>/runs.json
```

## Cleanup and release gates

```powershell
.venv\Scripts\python.exe -m invaris cleanup
.venv\Scripts\python.exe -m invaris cleanup --delete-volumes
```

The second command deletes selected owned volumes, including ephemeral CA and fixture state; neither is a global Docker prune.

Still open: finish and review the matched live evaluation; obtain completed readback for pending traces; reproduce setup on a fresh machine; complete the desired hosted Entire integration; reconcile measured inference cost; and conduct independent security/cryptographic review before any production expansion. Public submission, social posts, and demo publication are explicitly deferred. This is not an enterprise production release or a complete quantum-safe solution.
