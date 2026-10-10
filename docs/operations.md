# Invaris operator guide

## Current verified status

This is a sandbox release for the owned disposable TLS fixture. It does not migrate arbitrary production services, change certificate authentication to post-quantum signatures, or establish whole-system quantum safety. Fresh authenticated TLS 1.3 key exchange and the supported application response are checked against the fixture contract.

The final semantic source is commit `aa5777b1647bdc712fc7a444e17a3679adb3021d`. Validation passes 185 unit tests plus 11 subtests, Ruff, and `pip check`. Full fresh CI run `38092951097` passed normal checks and all 8 real Docker/TLS integration tests on this source. A prior locked-dependency vulnerability audit found no known advisories; none of these checks certifies native or whole-system security. The current image confirms OpenSSL 3.5.9.

The final-source study `ebeea671-7e12-4493-9531-04456a74efeb` is complete: 21 attempts, 7 matched V1/V2 pairs, no control mismatches or unmatched attempts. Correct classifications: V1 6/7, V2 7/7, fixed script 7/7. V1 has one false-readiness claim; V2 and the script have zero. Each arm recovers in 2/2 seeded recovery cases. Estimated model costs are $0.3968316 (V1), $0.3992516 (V2), and $0 (script). One repetition cannot establish statistical superiority; the deterministic script knows this small fixture and is cheaper and faster.

Historical studies remain unchanged: `090330` has 63 attempts (V1 16/21 correct, V2 17/21, script 21/21); `a6d844` has 21 attempts (V1 5/7, V2 6/7, script 7/7). They use earlier agent versions and are not pooled into the final study. See `docs/release-validation.md`.

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
.venv\Scripts\python.exe -m invaris verify-bundle --directory artifacts/evaluations/ebeea671-7e12-4493-9531-04456a74efeb
```

Offline mode is a scripted smoke model, not evidence of live agent improvement. The evaluation has V1, V2, and a deterministic fixed-script arm; the latter invokes no model. All recorded studies are complete. Use `--resume-evaluation <directory>` only for a genuinely interrupted study with unchanged controls and source; never portray a new run as a continuation of changed-source evidence. Resume requires the integrity manifest and binds semantic source hashes, effective model, rates, budget, and scenarios. It does not reset project spend. The total configured limits for both versions are 64k tokens, 16 steps, 24 tool calls, and 600 seconds.

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

- Neatlogs SDK readback verified real application trace `40733e2a561180a013f0a3bad929e3a0` with 9 spans, including 5 LLM spans; its trace status was `error`. Trace `4b821a1ab8e2fe622c7abd31cbd11f50` read back with 18 spans, including 7 LLM spans, and independently verified actual LLM tool use; the agent outcome is `UNVERIFIED` because its 24k token budget was exhausted. These are SDK readback-path results, not public CLI results. Matched-study readback has HTTP 409, HTTP 404, and partial HTTP 200 outcomes; full coverage is not confirmed. SDK graceful shutdown was observed and the Doctor probe passes, but neither proves application trace delivery. See `docs/evidence/final-study-trace-readback.json` for the complete final study's seven V2 readback attempts; missing/partial/failed telemetry remains unresolved.
- Entire's seven Codex hooks await approval. Multiple genuine isolated-session checkpoints and final-source Graph retrieval are verified locally; see `docs/entire-evidence.md`. Hosted GitHub App/checkpoint links and automatic capture remain unverified.
- The shared cfo.ai artifact was reviewed across all six pages and 39 Main Scenario months. The actual shared artifact is the source; no official export was needed. Measured inference reconciliation is recorded in `business/measured-assumptions.json`: the 21-attempt V2 live arm cost $1.2196459 estimated, or $0.1108769 per 11 verified migrations. Costs retain all attempts. The shared artifact's $6 inference placeholder remains unchanged; it is local planning content, not a cfo.ai export or a measured cost.

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

The CA signing key is generated during root initialization and deleted after leaf issuance. The fixture retains its leaf key; the probe receives only a read-only trust volume containing the public CA certificate. TLS certificate signatures remain classical; the hybrid key-exchange group does not make certificate authentication post-quantum. The final-source release study is complete and reviewed. Still open: obtain full matched-study trace readback coverage; complete the desired hosted Entire integration; and conduct independent security/cryptographic review before any production expansion. Public submission, social posts, and demo publication are explicitly deferred. This is not an enterprise production release or a complete quantum-safe solution.
