# Hackathon integration proof

**Evidence snapshot: October 12, 2026.** This is a judge-facing account of the work and its current evidence. Current challenge requirements and judging weights were verified on October 12 from the Neatlogs hackathon page's main requirements section and submission FAQ DOM using the T3 collaborative browser. The FAQ answer was read from `#neathack-faq-answer-panel` after opening the “What do I need to submit?” question. These requirements are current page evidence, not a guarantee of eligibility or judge acceptance. No deadline or eligibility determination is claimed.

## Claim and result

Invaris is a Python CLI agent that assesses and migrates an owned disposable TLS fixture under a strict hybrid key-exchange policy. It inspects the fixture, proposes a bounded configuration change, applies it only through guarded tools, restarts and probes the service, checks the application contract, and records an independent evaluator result. The deliverable combines agent workflow evidence and runtime traces (Neatlogs), local development-session checkpoints and code retrieval (Entire), and a reviewed business plan with locally measured inference assumptions (cfo.ai).

The implemented loopback frontend is a vanilla JavaScript/CSS interface served by Python. It launches the same bounded CLI through a serial job runner, never arbitrary shell commands. Open `/app/workflows` for separately approved fixture setup and live or scripted runs; `/app/runs` for independent verdicts, actual tool receipts, rollback and saved SDK span trees; `/app/evidence` for the unchanged matched study; `/app/integrations` for partner artifacts; and `/app/business` for measured costs and the actual cfo.ai share. It is not a remotely hosted or multiuser service. No job runs on page load.

The separate frontend live-recovery run `960415d5-92fd-4e64-90e9-7840d91d86fd` verifies the real hybrid connection and rollback. Its Neatlogs trace `4b0e7a97d43c5bc477f1d55d6b389589` passes structural audit with 20 spans, including a failed restart, subsequent recovery, eight LLM calls, nine agent tools and one rollback tool. The run cost estimate is $0.0726209; it does not replace any matched-study attempt. See `evidence/console-validation-oct12.json`.

The evaluated final-source study retained one repetition across seven matched scenarios. V1 classified 6/7 outcomes correctly and made one false-readiness claim; V2 classified 7/7 correctly with no false-readiness claims; a fixture-specific fixed script also classified 7/7 correctly with zero inference spend. Both V1 and V2 recovered in 2/2 seeded recovery cases. These results are small-sample fixture evidence, not statistical proof, production accuracy, or proof that an agent is economically superior to the known-fixture script. The final study is tied to migration source `aa5777b`; current audit tooling is `429769a`; subsequent documentation/evidence commit is `0e46a63`. Git records the initial public commit `166c1b9` at `2026-10-11 02:26:35 +05:30`, audit tooling commit `429769a` at `2026-10-12 00:31:37 +05:30`, and latest evidence/docs commit `0e46a63` at `2026-10-12 00:36:59 +05:30`; no dates were backdated.

## Integration evidence matrix

The statuses below describe what the artifacts prove. They do not imply hosted account authorization, public publication, or third-party certification.

| Integration | Status | Verified evidence | Pending evidence |
|---|---|---|---|
| Neatlogs | Application instrumentation and structural cloud readback verified with limits | All 7 original V1 traces and 5 original V2 traces pass the offline structure/count audit; two original V2 traces remain partial. Two separate fresh V2 runs have complete cloud traces and are not substituted into the matched study. | A dashboard permalink and screenshot for judge review are not included. Public Neatlogs CLI OAuth is unverified. |
| Entire | Genuine local checkpoints and final-source Graph retrieval verified | Checkpoint `01M4P5F42NEWP4TDWNFHWZVR2R` is locally verified and linked to audit tooling commit `429769a`; local final-source Graph retrieval finds the infeasibility gate. | Hosted GitHub App authorization, hosted checkpoint link, and automatic hook capture are unverified. |
| cfo.ai | User-shared plan reviewed in browser; measured inputs reconciled locally | Shared six-page model and 39 Main Scenario months reviewed; measured inference reference retained in local evidence. | No API/XLSX export, no shared-model update, and no verified customers or realized revenue. |

### Neatlogs — architecture, implementation, runtime, reasoning, result

- **Architecture:** The model-capable `run` and `evaluate` CLI flows use the OpenAI client directly, without an agent framework. Neatlogs SDK `1.4.26` wraps the client; workflow, model, and tool spans are emitted from the Python process. The independent C TLS fixture is not instrumented. Each CLI process initializes tracing once and flushes/shuts down in `finally`.
- **Implementation:** The project ID is `2dfd398b-9874-4878-9a9a-d9fe62e6cdbe`. Span metadata records workflow ancestry, model/tool node names, status, and sanitized inputs/outputs/errors. Cloud snapshots are checked offline against local run receipts by `trace-audit`; the gate checks identity, span uniqueness/counts, workflow structure, parent links, cycles/disconnection, model/tool totals, and expected rollback evidence. It makes no network, model, Docker, or mutation calls.
- **Runtime:** The final study produced seven original V1 and seven original V2 application traces. SDK readback structurally verifies all seven V1 and five V2 original traces; two original V2 records are still partial. Separate fresh V2 runs for `already_compliant` and `wrong_active_group` are verified complete. Fresh runs remain separate evidence and do not repair or replace historical matched attempts. The SDK Doctor synthetic probe is not presented as an application trace.
- **Reasoning:** One trace demonstrates why a successful HTTP response is not enough: V1's `impossible_client_requirement` trace is structurally complete (17 spans, 7 model calls, 8 tool calls), while the agent said `VERIFIED` and the independent evaluator said `BLOCKED`. V2's corresponding original trace is structurally complete (5 spans, 1 model call, 2 tool calls) and both agent and evaluator said `BLOCKED`. In the `one_shot_action_failure` V2 trace, the `restart_service` tool first has an actual `ERROR` span, a later `restart_service` span succeeds, and `rollback_and_reverify` is recorded.
- **Result:** The failed-action recovery trace ends with agent and evaluator statuses both `VERIFIED`. Across the final matched study the aggregate outcomes are V1 6/7, V2 7/7, fixed script 7/7, one repetition. No statistical superiority claim follows.
- **Judge evidence links:** Trace IDs and sanitized trace-audit snapshots are linked by evidence paths below. The trace IDs are actual Neatlogs application IDs, but a dashboard permalink and screenshot have not been captured into this proof package. Do not represent the local JSON snapshots as dashboard screenshots or authenticated public links.

The official current evidence accordion also calls for an improved before/after run (for example, two Neatlogs traces plus compared numbers), Neatlogs project-trace links or screenshots, Entire checkpoints or Entire Graph output, a CFO plan covering pricing/costs/revenue/runway, a failed action showing the next step, public posts using `#neatHack`, and a public repository with event-dated commits. The matched V1/V2 study supplies before/after traces and compared outcome numbers; the recovery trace documents the failed action and subsequent step; the local Entire and CFO artifacts cover their respective items. SDK trace verification is complete for the stated scoped records, but the Neatlogs project-trace link/screenshot requirement remains **pending**: checked-in JSON snapshots do not fulfill that format requirement. T3's `app.neatlogs.com` destination redirected to sign-in, and no authenticated dashboard was available. A human with dashboard access must provide a project-trace permalink or screenshot, or an official share link, before this item can be marked complete.

### Entire — architecture, implementation, runtime, reasoning, result

- **Architecture:** Entire was used as a development-time coding-agent history/checkpoint and local code-retrieval tool, separate from the Invaris runtime agent and its TLS fixture.
- **Implementation:** A genuine isolated Codex session was attached and locally recorded. The October 12 checkpoint record contains checkpoint metadata, session/agent identity, timestamp, and commit mapping. The Entire Graph plugin's local doctor/query evidence records retrieval against the final migration source.
- **Runtime:** Checkpoint `01M4P5F42NEWP4TDWNFHWZVR2R` maps to tooling commit `429769a206ce6b9618f1c1ea411aa3f2429be809`. The final-source graph record is tied to migration commit `aa5777b1647bdc712fc7a444e17a3679adb3021d` and retrieves the `infeasibility_gate` implementation. These are local checkpoint/graph artifacts, not hosted links.
- **Reasoning:** The checkpoint supports a bounded claim that one isolated worker session contributed trace-audit development; it does not capture the main conversation or every refinement. Graph retrieval demonstrates that a relevant source symbol can be found in the recorded repository snapshot; it does not quantify token savings or agent performance.
- **Result:** The local checkpoint and graph artifacts provide reviewable evidence for this limited development-tool role. Hosted Entire GitHub App authentication, public checkpoint sharing, raw transcript upload, and automatic hook capture are not claimed.
- **Reproduction:** With the locally installed Entire CLI and repository checkout, inspect current checkpoint metadata using `entire checkpoint explain HEAD --json`. Compare the returned checkpoint and commit fields with the saved record. This command inspects local metadata; it does not authorize or prove hosted sharing.

### cfo.ai — architecture, implementation, runtime, reasoning, result

- **Architecture:** cfo.ai is the business-planning artifact, not a runtime component. The shared user-generated model was reviewed in browser; local Python evidence reconciles measured inference assumptions for decision-making. There is no asserted API integration or automated writeback.
- **Implementation:** The reviewer inspected all six visible pages and each of 39 rendered Main Scenario months (October 2026–December 2029). The shared model displays a $6 inference/migration placeholder and a measured field shown as $0/PENDING. The final-source local V2 study records 7 attempts, estimated inference of `$0.3992516` total, `$0.05703594` per attempt and `$0.0998129` per independently verified non-no-op migration (4 migrations); all attempt costs remain in the numerator. These are configured estimates, not invoices, and are not all-in delivery cost. The shared plan was not changed.
- **Runtime:** Visible Main assumptions include paid three-month pilot prices of `$60,000` enterprise and `$25,000` midmarket; annual contract values of `$240,000` and `$90,000`; 25%/35% pilot conversion; and 45%/50% pilot-to-contract conversion. These are model assumptions, not observed pricing acceptance, customers, or conversions. The model shows `$11,483` monthly revenue in October 2026, a `$96,355` minimum cash balance in September 2028, first operating breakeven in October 2028, and `$884,854` monthly revenue / `$2,931,051` ending cash in December 2029. Its opening cash is hypothetical `$1.5 million`; displayed starting runway is 31.7 months.
- **Reasoning:** Reconciliation keeps measured inference separate from verification, engineering, support, onboarding, infrastructure, and other COGS. A local sensitivity that reduces each displayed Main revenue by 10% while holding displayed costs fixed turns cash negative in May 2028 (about `-$4,530`) and bottoms near `-$281,490` in November 2028. That is an independently computed sensitivity, not a cfo.ai Downside scenario.
- **Result:** The forecast, conversion assumptions, staffing plan, and opening financing remain planning assumptions, not validated traction, actual margin, or committed funding. The shared model has date-label inconsistencies; only Main was visible, despite text mentioning Downside/Upside.
- **Judge evidence link:** The user-shared model is [cfo.ai Main Scenario](https://cfo.ai/s/aMAZiEnSXtphYplP). The review record is `business/cfo-review.md`; this is browser-observed review, not an official export or formula audit.

## Offline reproduction and metadata checks

These commands do not access the model provider or Neatlogs. Trace auditing uses an already saved local run receipt and a sanitized private cloud readback. The example paths are machine-local artifacts; they are not part of the public evidence bundle, so a clone needs its own real receipt and readback. The checked-in evidence files retain trace IDs and audit summaries for review.

```powershell
.venv\Scripts\python.exe -m invaris trace-audit `
  --expected artifacts/runs/7f94ea34-a622-4533-9a9a-6ac7f2ae135d/result.json `
  --readback artifacts/private/trace-readback-7f94ea34-a622-4533-9a9a-6ac7f2ae135d.json `
  --project-id 2dfd398b-9874-4878-9a9a-d9fe62e6cdbe
```

The command above is provided as a reproduction pattern; when copying it, use the exact local run/readback paths available on the machine. A passing audit means the supplied snapshot satisfies structural checks, not cryptographic authenticity. It does not expose model content or credentials. To inspect local Entire checkpoint metadata, run `entire checkpoint explain HEAD --json` from the repository root and compare it with `docs/evidence/entire-oct12-checkpoint.json`.

The standalone business evidence is reviewable in `business/cfo-review.md`, `business/final-measured-assumptions.json`, and `docs/evidence/final-study-summary.json`; no live model call is needed to review these saved records.

## Build and validation record

The October 12 CI record identifies source `429769a`, CI run `38166297502`, 207 unit tests, 8 Docker/TLS integration tests, Ruff passing, plus local 11 subtests and `pip check`. These checks validate the disposable fixture and software in that environment; they are not production certification, a native security audit, or proof of post-quantum certificate authentication. The migration changes the fixture's TLS key-exchange configuration; certificate signatures remain classical. No claim of production deployment, broad system quantum safety, or production-grade PQC is made.

## Publication and criteria checklist

The current requirements below were read from the official challenge main section and submission FAQ DOM on October 12, 2026.

| Judging category | Weight |
|---|---:|
| Agent | 30% |
| Partner integrations | 25% |
| Demo | 20% |
| Building in public | 15% |
| Usefulness and originality | 10% |

The submission FAQ requires a public repository and a demo video of no more than three minutes. The video must explicitly cover **architecture, implementation, runtime, reasoning, and result for each of Neatlogs, Entire, and CFO**. The corresponding five-part narratives are organized under each integration above; the repository commits provide dated implementation evidence within the event window. Supporting evidence belongs in the repository. These requirements are reported from the page DOM as read, not as a prediction of judging outcome.

| Item | Evidence/status |
|---|---|
| Use Neatlogs and Entire to build or improve an agent | Local implementation/traces and Entire checkpoint/graph evidence are documented above; current eligibility interpretation requires organizer confirmation. |
| Include a cfo.ai business plan | Shared user model reviewed and local inference costs reconciled; no export or shared-model writeback. |
| Provide actual before/after traces with numbers | Matched V1/V2 study and specific corresponding infeasibility traces included; one repetition and two partial historical V2 traces are disclosed. |
| Neatlogs project-trace links or screenshots | Pending. SDK trace verification is complete for scoped records, but local JSON evidence is not the required dashboard link/screenshot. `app.neatlogs.com` redirected to sign-in; human dashboard access or an official share link is needed. |
| Show Entire checkpoints or graph output | Local checkpoint metadata and graph output are included; hosted authentication/link is not verified. |
| Explain cfo.ai pricing, cost, revenue, and runway | Planning inputs, measured inference estimate, forecast checkpoints, and limitations are stated above. |
| Show failed action and next step | Actual error span followed by the successful next restart action and rollback/reverify evidence is included. |
| Public repository and event-dated commits | Public repository history uses actual dates; initial, implementation, and current evidence commit dates are stated above. |
| Public posts using `#neatHack` | Deferred by user; no posts are claimed. |
| Demo video, maximum three minutes | Deferred by user; no video is claimed. When created, it must explicitly cover architecture, implementation, runtime, reasoning, and result for each of Neatlogs, Entire, and CFO. |
| Public submission | Deferred by user; no submission is claimed. |

Official references: [Neatlogs hackathon challenge and FAQ](https://neatlogs.com/hackathon#challenge) and [Entire Neathacks 2026](https://hack.entire.io/neathacks-2026). Neatlogs current challenge and submission FAQ requirements were verified in the page DOM as described above. Separate eligibility decisions and judge acceptance are not established here.
