# Release validation

## October 12 operator frontend validation

The implemented release now includes a loopback-only landing page and interactive operator console, in addition to the CLI and owned TLS fixture. Workflow approvals, scenario selection, run receipts, independent verdicts, saved SDK trace trees, integration evidence, the matched-study comparison, and the business-plan link are connected to real local artifacts and bounded CLI jobs. No action runs automatically on page load. This is not a remotely hosted or multiuser production service.

Fresh local validation passes 232 unit tests and 11 subtests, with one Windows symlink test skipped, plus all eight real Docker/TLS integration tests. Ruff, dependency consistency, JavaScript syntax, wheel creation, and inclusion of all three frontend assets pass. Browser checks cover desktop and narrow mobile layouts, evidence-file retrieval, separate setup/run consent, paid consent, and actual workflow execution.

A fresh `pip-audit` lookup across the locked Python requirements reports no known vulnerabilities. The lock is pinned rather than fully hashed; this does not cover native image dependencies or establish security certification.

Fresh GitHub CI run `38171504827` passes on operator-console source `29f7b9d`: 233 unit tests on Linux and all eight real Docker/TLS integration tests. Linux can run the symlink test skipped locally on Windows. Normal push CI `38171503906` also passes. See `evidence/console-ci-oct12.json`; later frontend identifier-only cleanup does not change agent migration semantics.

Three separate console runs verify a scripted no-op, scripted recovery, and a live Claude Haiku recovery. The live run `960415d5-92fd-4e64-90e9-7840d91d86fd` independently verifies the hybrid connection and rollback; its cloud trace `4b0e7a97d43c5bc477f1d55d6b389589` passes structural audit with 20 spans: eight LLM, nine agent tools, one rollback tool, and two workflows. The failed restart is an actual ERROR span followed by successful recovery. Duration is 52.781 seconds and estimated inference is $0.0726209. These runs do not replace the original matched study or imply general reliability. The unchanged project ledger now records $5.7884838 against the $10 authorization; estimates are not invoices. See `evidence/console-validation-oct12.json`.

The partner roles and judge-facing proof checklist are consolidated in `hackathon-integration-proof.md`. Neatlogs SDK application verification, Entire local checkpoint/Graph evidence, and the reviewed cfo.ai business artifact are available. The official Neatlogs dashboard permalink or screenshot still requires human dashboard sign-in. Optional hosted authentication, public posts, recording, and submission are not claimed complete.

## October 12 follow-up

The cloud application verification gap is now substantially closed: all seven original V1 traces and five original V2 traces pass structural coverage. Two original V2 traces remain partial; separate fresh V2 migration/no-op traces pass and are not substituted into the matched study. Every seeded scenario now has complete V2 application trace evidence, including failed-action recovery and matched V1/V2 infeasibility behavior. The new `trace-audit` command fails closed on partial or malformed readbacks. See `trace-audit.md` and `evidence/neatlogs-oct12-coverage.json`.

Latest tooling source is `429769a`; migration semantics remain the evaluated `aa5777b` source. Unit validation now passes 207 tests plus 11 subtests, Ruff, and `pip check`. Fresh CI run `38166297502` also passes 207 unit tests and all 8 real Docker/TLS integration tests on this source. A new genuine Entire checkpoint is linked to the audit-development source commit. Gateway-reported total spend is $3.0659827, conservative local ledger $5.7158629, below the $10 authorization.

This closes current reproducible sandbox tracing evidence, not every historical trace or an enterprise deployment assessment. The October 11 sections below are retained as dated evidence; their initial pending/failure observations are superseded by this follow-up where explicitly stated. Hosted optional authentication remains unverified. Submission/publication is still deferred.

## Historical release decision — October 11

Invaris 0.1.0 is a validated, authorized TLS migration sandbox, not a production deployment platform. The agent, controller, independent verification, recovery, rollback, reports, budget ledger, and regression checks work in the owned fixture. Complete cloud tracing remains an open release gate. Do not represent every external integration as complete or deploy this agent to customer infrastructure.

Final semantic source: `aa5777b1647bdc712fc7a444e17a3679adb3021d`. Evidence/documentation commits follow with genuine timestamps; no public history was backdated.

## Verification performed

- 185 unit tests and 11 subtests pass; 8 integration tests are excluded from this unit command.
- All 8 real Docker/TLS integration tests pass locally and in fresh CI run `38092951097` on the final source. Normal push checks `38092951036` also pass.
- Ruff and `pip check` pass. The earlier audit of locked Python dependencies reported no known advisories. This is not a native-image audit, penetration test, or security certification.
- The final evaluation bundle and all 21 run bundles pass hash-integrity checks. Hashes do not prove provenance or authenticity.
- Actual fixture runtime is OpenSSL 3.5.9. Fresh probes check negotiated TLS group, certificate/hostname, client policy, and application response. TLS certificate signatures remain classical.

## Final matched live evaluation

Study: `ebeea671-7e12-4493-9531-04456a74efeb`. Seven scenarios, one repetition, three arms, 21 retained attempts; seven matched V1/V2 pairs with no control mismatches or unmatched attempts. The model is Claude Haiku through the configured gateway. Source hashes and common budgets are saved in `evidence/final-study-summary.json`.

| Metric | V1 | V2 | Fixture-specific fixed script |
|---|---:|---:|---:|
| Correct classifications | 6/7 | 7/7 | 7/7 |
| False-readiness claims | 1 | 0 | 0 |
| Verified non-no-op migrations | 4 | 4 | 4 |
| Seeded recoveries | 2/2 | 2/2 | 2/2 |
| Correct no-op / blocker | 1 / 1 | 1 / 1 | 1 / 1 |
| Estimated inference USD | 0.3968316 | 0.3992516 | 0 |
| Input / output tokens | 164248 / 6452 | 165538 / 6376 | 0 / 0 |
| Observed elapsed seconds | 252.547 | 237.546 | 138.218 |
| Model / tool calls | 45 / 52 | 44 / 50 | 0 / 38 |

V2 improves safety classification in this small test, not overall cost: its estimated inference is slightly higher. The script matches V2, costs no inference, and is faster; its fixture knowledge is disclosed. One repetition cannot establish statistical superiority, universal accuracy, or commercial advantage over deterministic automation.

V2 correctly returns VERIFIED for four migration cases and the already-compliant case, BLOCKED for an impossible client policy without mutation, and UNVERIFIED for missing probe evidence. The disk/runtime mismatch is fixed by restart without rewriting configuration. Rollback is independently verified for all five V2 VERIFIED outcomes; it is not claimed for the blocked or missing-evidence outcomes.

The V2 infeasibility circuit breaker uses a trusted capability receipt and cancels remaining actions before another tool/model request. The final blocked study attempt uses one model call and two read-only tools, with zero changed files. Earlier model-prose-only stopping was unreliable; this gate is enforced outside model discretion.

Historical studies are retained, not rewritten or pooled: 63 attempts in `090330` and 21 in `a6d844`. The larger early study does not establish final-source accuracy.

## Partner evidence and unresolved gate

### Neatlogs

SDK 1.4.26 is installed and the synthetic Doctor probe passes. Real application traces persist for some runs, but final V2 readback is incomplete: two partial HTTP 200 records, three HTTP 404 records, and two HTTP 409 records with `dlq` finalization. The successful migration trace has three remote LLM spans against seven local model calls; the recovery trace fails finalization. Graceful shutdown reports zero SDK drops, export failures, truncations, or overflow. These counters do not prove backend completeness.

See `evidence/final-study-trace-readback.json` for IDs, parents, counts, and diagnostics. Exact root cause is not established; do not blame a specific backend/SDK bug without proof. Local TLS verification remains separate from telemetry persistence. Optional public CLI readback is waiting on human OAuth or a scoped service-account token; the SDK key is not a CLI credential. No detections, alerts, or platform evals were configured.

### Entire

Genuine isolated-session checkpoints and official Graph queries are verified locally, including final-source graph retrieval in `evidence/entire-final-graph.json`. Automatic Codex hooks await approval; hosted GitHub App/checkpoint links remain unverified. A reused old checkpoint trailer does not prove new capture of later changes. See `entire-evidence.md`.

### cfo.ai

The user-generated six-page shared Main Scenario was reviewed across 39 months. Browser review is not an API/export integration. Local measured-cost reconciliation is in `../business/measured-assumptions.json`; the shared model still has its placeholder and pending measured field. No shared plan update, validated revenue, customers, downside scenario, or financing is claimed. See `../business/cfo-review.md`.

## Spending and security boundaries

At the saved check, gateway-reported key spend is $3.0092106 and the conservative local ledger is $5.6113937, below the authorized $10. The gateway figure is key-account spend, not a per-study invoice. The remote cap remains $20; the local ledger is not a guaranteed billing limit. No additional paid workload is necessary for this release; never reset the ledger.

Changes are limited to the approved disposable fixture. CA signing material is removed after leaf issuance; the probe mounts only public trust, not signing/leaf private keys. Probe evidence is structurally checked, not cryptographically signed attestation. Reports are static and sanitized; provider credentials and private artifacts are not publishable. Keys previously pasted in conversation should be rotated before deployment.

Dependency locks are version-pinned, not hash-locked. OS/native package security and license review remain separate; no project license has been selected. Enterprise deployment would require independent security review, customer authorization and isolation, signing/attestation, operational monitoring, billing controls, and validated PKI/client scope.

Submission, social posting, and demo publication remain deferred as requested. Source and sanitized evidence are pushed to the authorized repository.
