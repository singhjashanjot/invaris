# Invaris operator guide

## Current verified status

This is a sandbox release for the owned disposable TLS fixture. It does not migrate arbitrary production services, change certificate authentication to post-quantum signatures, or establish whole-system quantum safety. Fresh authenticated TLS 1.3 key exchange and the supported application response are checked against the fixture contract.

Migration semantics remain evaluated commit `aa5777b1647bdc712fc7a444e17a3679adb3021d`; latest trace-audit tooling is `429769a`. Current test status is 227 unit tests plus 11 subtests, with one Windows symlink test skipped; eight Docker integration tests are pending a fresh run. A prior locked-dependency audit found no known advisories; none of these checks certifies native or whole-system security. The current image confirms OpenSSL 3.5.9.

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
.venv\Scripts\python.exe -m invaris serve --port 8766
```

The frontend binds to loopback at `http://127.0.0.1:8766/`. The landing page links to `/app`, the local operator console. Its sections cover workflows, runs, traces, integrations, evidence, and business information. The console owns the Invaris Docker Compose project and exposes only its scoped operations; this frontend is not a remote production service and has no multiuser authentication.

Setup and run are separate actions, each requiring its own explicit approval in the console. Merely loading or navigating the page does not start either action. Offline mode executes the real scripted TLS workflow without an LLM; it is a smoke path, not live-agent evidence. Live paid runs require the explicit paid-run acknowledgement and are bounded by the existing $10 local estimate authorization and spend ledger described below. Do not cancel an active setup or run process: rollback may still be in progress.

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

- October 12 SDK readback structurally verifies all seven original V1 traces and five original V2 traces. Two historical V2 records remain partial, but separate fresh V2 migration/no-op runs now pass, giving actual cloud evidence for every scenario. The `trace-audit` gate rejects partial counts and broken topology. See `docs/trace-audit.md` and `docs/evidence/neatlogs-oct12-coverage.json`; fresh traces are not substituted into the original matched study. Dashboard login is still needed to obtain the official permalink and screenshot; public CLI OAuth remains optional and unverified.
- Entire's seven Codex hooks await approval. Multiple genuine isolated-session checkpoints and final-source Graph retrieval are verified locally; see `docs/entire-evidence.md`. Hosted GitHub App/checkpoint links and automatic capture remain unverified.
- The shared cfo.ai artifact was reviewed across all six pages and 39 Main Scenario months. This is a reviewed artifact, not an API integration or official export. Final matched-study V2 estimated inference is $0.3992516 across seven attempts: $0.05703594 per attempt and $0.0998129 per verified non-no-op migration across four migrations, as recorded in `business/final-measured-assumptions.json`. The older `business/measured-assumptions.json` retains a separate historical study and must not be pooled with the final study. The shared model still has a $6 placeholder and PENDING measured field; the local reconciliation does not update its formulas.

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

The CA signing key is generated during root initialization and deleted after leaf issuance. The fixture retains its leaf key; the probe receives only a read-only trust volume containing the public CA certificate. TLS certificate signatures remain classical; the hybrid key-exchange group does not make certificate authentication post-quantum. The final-source release study is complete and reviewed. Current application cloud evidence exists for every scenario. Still open: recover the two historical partial V2 traces; complete optional hosted Entire authentication if desired; and conduct independent security/cryptographic review before any production expansion. Public submission, social posts, and demo publication are explicitly deferred. This is not an enterprise production release or a complete quantum-safe solution.
