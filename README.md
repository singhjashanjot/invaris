# Invaris

## Verified cryptographic change.

**Invaris Migration Engineer is a sandbox TLS migration agent with independently checked post-quantum key exchange.** It inspects an authorized service fixture, plans and applies a bounded change, checks actual connection and application behavior, recovers from failed candidates, and produces a reviewable evidence bundle.

**Status: validated sandbox release (October 11, 2026), with an open Neatlogs cloud trace-completeness issue.** Final-source validation passes 185 unit tests plus 11 subtests, Ruff, and dependency consistency checks; fresh CI also passes all 8 real Docker/TLS integration tests. The completed matched live study has 7 scenarios and 3 arms: V1 correctly classifies 6/7 with one false-readiness claim; V2 correctly classifies 7/7 with zero false-readiness claims; the fixture-specific fixed script also classifies 7/7 without inference cost. This is one repetition, not statistical proof. Entire checkpoints and Graph retrieval are verified locally; hosted linking is not verified. The cfo.ai six-page model is reviewed with a separate local measured-cost reconciliation. SDK Doctor passes, but final application cloud readbacks are missing, partial, or failed; complete tracing is not claimed. This is not enterprise production software or a complete quantum-safe migration. Submission and public demo work are deferred. See [release validation](docs/release-validation.md) for exact results, costs, security boundaries, and outstanding gates. Invaris trademark/domain availability has not been checked.

## Current operator quickstart

With the project virtual environment and Docker Compose ready, the implemented commands are:

```powershell
.venv\Scripts\python.exe -m invaris setup
.venv\Scripts\python.exe -m invaris run --offline --approve-sandbox --scenario wrong_active_group
.venv\Scripts\python.exe -m invaris evaluate --offline --approve-sandbox --include-held-out
```

The offline mode is a scripted smoke path, not live-agent evidence. The final live evaluation is complete at `artifacts/evaluations/ebeea671-7e12-4493-9531-04456a74efeb`; its local report is `report.html`. Sanitized results are in [final study evidence](docs/evidence/final-study-summary.json). Historical studies remain unchanged. Do not resume a completed older study against changed source or reset the project spend ledger. See [docs/operations.md](docs/operations.md) before running live work.

The numbered product, architecture, evaluation, and submission sections below retain the original design scope and intended future work. They describe the plan where a capability has not been verified; they are not a claim that every planned gate is complete.

**Name and positioning:** Invaris draws from invariant: a property that must remain true while a system changes. The product changes cryptography while checking the service properties required by the approved contract. Brand: Invaris. Product: Invaris Migration Engineer. Positioning: verified cryptographic change.

## 1. The decision in plain language

Build one small but complete migration agent, not a cryptography platform or a general trace-analysis product.

A developer gives it a controlled service environment and an approved target policy. The agent investigates what actually runs, changes only allowed files, restarts the fixture, tests fresh connections and application responses, and either produces a verified candidate or explains the blocker. If an action or test fails, that result guides the next permitted action.

There are two mandatory loops:

1. **Task loop:** inspect -> plan -> act -> verify -> recover or stop -> evidence.
2. **Improvement loop:** evaluate agent V1 -> investigate Neatlogs traces -> change the agent -> evaluate V2 on matched cases -> publish the comparison.

Ordinary regression tests are core. Automatic regression generation is not in the initial build. The transcript's lesson is applied through independent verification and trace-informed improvement, not a second product.

## 2. The story we tell

### The problem

The configuration can look correct while the running service uses a different configuration, an unrestarted process, or a different endpoint. An agent can confidently announce success without checking the actual effect.

For this project, the effect is a real TLS connection that meets a declared key-exchange policy while the supported application still works.

### Our narrative

"The configuration says the migration worked. Does the connection agree? Invaris checks, fixes what it is authorized to fix, and shows its evidence."

### One-sentence pitch

"Invaris migrates a supported service to a declared hybrid post-quantum TLS policy, verifies real connection behavior, and recovers when a candidate fails."

### What makes it compelling

The differentiator we must demonstrate is the whole execution loop: runtime-aware changes, fresh verification, no false readiness, adaptive recovery, rollback and measurable improvement. A scanner, report or one-flag change alone is not this product. No world-first or guaranteed-win claim is made.

## 3. User, input and deliverable

Initial user hypothesis: a platform/security developer responsible for a service's TLS configuration and dependency/runtime behavior. Whether that developer will pay remains unvalidated.

**Input:** authorized fixture repository/environment, current revision, target endpoint, approved TLS policy, supported client profiles, application expectations, writable paths, action permissions and budgets.

**Output:** proposed/applied sandbox patch, verified or blocked result, actual connection receipts, client/application results, failed-attempt history, rollback result and explicit limitations. A human reviews the change before any use outside the disposable fixture.

This is not a production deployment assistant in the first release. It does not scan arbitrary public hosts or apply changes to external customer infrastructure.

## 4. Exact initial scope and non-goals

### We will build

- One Python agent using a simple bounded tool-calling loop.
- One Docker Compose project containing the controlled service and runner/client components.
- One small HTTPS fixture backed by pinned compatible OpenSSL libraries.
- Several state/configuration variants of that fixture, not several service frameworks.
- Typed tools for inspection, scoped configuration changes, restart, real probes, application checks and rollback.
- A deterministic verifier outside the agent's writable scope.
- Human-authored regression/evaluation cases and matched V1/V2 runs.
- Neatlogs instrumentation from the first agent run.
- Genuine Entire development context and an actual cfo.ai business plan.
- A terminal-first demo and static local evidence report; no hosted dashboard requirement.

### We will not build initially

FastAPI, React, PostgreSQL, LangGraph, Kubernetes, remote worker fleets, multi-tenant SaaS, a universal crypto inventory, enterprise PKI, certificate-signature migration, a general replay engine, autonomous test generation or a large team of agents.

No new cryptographic primitive, quantum attack or universal quantum-safety assurance. Using a standard algorithm does not confer certification. Classical certificate authentication remains explicitly separate from the scoped key-exchange migration.

## 5. Cryptographic scope and the first feasibility gate

The proposed target is TLS 1.3 hybrid key exchange using X25519MLKEM768 in a controlled compatible stack. OpenSSL 3.5 documentation describes this hybrid group. Select a maintained, tested 3.5.x patch release at implementation time, pin it and its image/build inputs, and record runtime/build identity. Do not assume the host Python or system OpenSSL has this capability. [S2]

A capable binary, a group list and a configuration entry are capability evidence, not proof of negotiation. Cipher-suite names alone do not identify the negotiated key-exchange group.

**First gate before agent implementation:** prove fresh controlled connections can expose the actual negotiated group, validate the fixture certificate/hostname, and exchange the expected application response. Prove a deliberately classical-only case differs. If this gate fails, fix the fixture/probe or explicitly reconsider feasibility; do not substitute configuration text for the missing evidence.

### Fixture implementation choice

Keep orchestration in Python. Build a tiny OpenSSL-backed HTTPS fixture and JSON-emitting client probe in C only where direct library access is needed. This avoids assuming Python's ssl binding exposes group configuration/inspection. The server accepts a bounded external configuration and serves a health response with the loaded configuration digest. The probe reports the negotiated group after a successful handshake using a documented OpenSSL accessor. No custom cryptographic implementation. [S3]

OpenSSL s_server/s_client can be used for capability experiments. The actual application fixture and probe remain tested artifacts, not a diagnostic command passed off as a customer deployment. If a vetted CLI parser is used instead of a helper, freeze/test its supported version and keep raw output; unknown output yields UNVERIFIED, never guessed success.

## 6. Success contract: define it before the agent acts

A small validated JSON/YAML contract contains:

| Field | Meaning |
|---|---|
| scope | Authorized repository, base revision, fixture instance and endpoint |
| policy | Required protocol, group and explicit fallback/client behavior |
| app_checks | Approved health response and configuration-identity expectations |
| permissions | Writable file paths and allowed restart/rollback operations |
| limits | Maximum tool/model steps, retries, duration, tokens and estimated cost |
| approval | Candidate-bound permission for scoped sandbox changes |
| evidence | Required fresh probes, receipts, revisions and rollback check |

The first default policy is strict: the supported client must negotiate the required group. A classical-only client is expected to be rejected, and that break in connectivity is disclosed. A policy that requires classical-only connectivity and forbids classical negotiation is contradictory; report it as blocked, not silently relaxed.

The agent cannot modify policy, probe code, approved client expectations, app tests or evaluator labels to obtain a pass. A revised policy requires an explicit new approval and a new evaluation identity.

Statuses:

- VERIFIED: required fresh connection/client/application evidence passes for the current candidate.
- BLOCKED: a supported diagnosis shows constraints cannot be met within scope/permissions.
- UNVERIFIED: evidence is missing, stale, unparsable or inconclusive.
- FAILED: a candidate/action does not satisfy the contract and has not been successfully recovered.

A correctly explained BLOCKED case can be a successful task outcome in evaluation, but is not counted as a completed migration. Report those counts separately.

## 7. Architecture and minimal technology

~~~text
Approved contract + fixture snapshot
                 |
     Python agent loop + deterministic controller
                 |
   typed tools / receipts / local durable run state
                 |
        Docker Compose service fixture
                 |
      independent client/application verifier
                 |
   result + patch + evidence bundle + local report

Neatlogs: observes model/tool/recovery/evaluation runs
Entire: captures development context behind code changes
cfo.ai: produces the product's business plan
~~~

| Component | Choice and reason |
|---|---|
| Agent | Python 3.12, one supported model/tool-calling client; pin after trace smoke test |
| Contracts | Pydantic for inputs, receipts and final results |
| Orchestration | Plain loop with finite states and hard tool/step boundaries |
| Environment | Docker Compose on Docker Desktop/WSL2 or Linux; no paid cloud required |
| TLS boundary | Pinned OpenSSL-backed service/probe helpers |
| State | Atomic local JSON checkpoints and append-only JSONL events |
| Tests | pytest plus real controlled connections |
| Presentation | Terminal output and generated static HTML/Markdown report |
| Observability | Official Neatlogs SDK; verified APIs rather than invented method names |
| Development history | Supported Entire integration for the actual coding agent |
| Business artifact | cfo.ai export/share plus sanitized supporting assumptions |

Do not select a model by claiming unsupported pricing or capabilities. Choose an available event-authorized tool-capable model after a smoke test; use the same model/settings/budget in matched V1/V2 comparisons. Record provider/model identity and version metadata when available.

Prefer a directly implemented loop over an existing autonomous runtime in this small scope. If any runtime is reused, confirm organizer eligibility and disclose dependencies versus event-written work. No approval is inferred from a Discord question without its official answer.

## 8. Tools and the agent's actual autonomy

Proposed tool names below are our interfaces, not sponsor API names:

| Tool | Scope and result |
|---|---|
| inspect_service | Read permitted config, running/build identity and loaded-config receipts |
| read_allowed_file | Read bounded repository context; exclude secrets and trusted evaluator paths |
| inspect_capabilities | Return tested runtime/group support with uncertainty |
| stage_config_change | Validate/write only approved configuration keys in the candidate workspace |
| apply_candidate | Activate exact candidate digest after scope/approval checks |
| restart_service | Restart only the owned fixture; return readiness and process identity |
| probe_connection | Fresh authorized endpoint connection, group/protocol/certificate receipts |
| check_application | Check the approved response through the connection, not a separate HTTP bypass |
| restore_snapshot | Restore the approved fixture configuration and restart/reverify |
| collect_evidence | Assemble receipts, diff, verdicts and limitations; cannot create fake measurements |

The model chooses which evidence to inspect and the next permitted action from tool results. It is not given the hidden scenario ID or a scenario-to-fix table. Tools implement safe operations; they do not secretly solve the migration.

Demonstrate at least two different decision paths, such as wrong active configuration versus missing restart. Compare against a fixed remediation script. If the script solves the complete suite equally well, state the limited incremental value and add a legitimate bounded variation, not artificial complexity.

No general shell execution tool. Subprocess arguments are validated arrays with fixed executables, timeouts and output limits. No model-built shell strings, arbitrary package installations, host mounts or public endpoint probes.

## 9. Task execution, state and recovery

State machine: INIT -> BASELINE -> PLAN -> STAGED -> APPLIED -> VERIFY -> RECOVER or REPORT. Permission/budget/missing-evidence conditions can stop any stage.

1. Validate the contract, fixture ownership and base revision; take a restorable snapshot.
2. Record baseline probe/application behavior before changes.
3. Inspect relevant runtime/config context, then summarize a bounded plan.
4. Stage a permitted change and bind approval to its digest.
5. Apply/restart; check action receipts instead of assuming execution.
6. Obtain fresh connection and app receipts matching the current candidate/instance.
7. On failure, investigate relevant traces/receipts, choose an allowed revision, and retry within limits. If policy is infeasible, stop truthfully.
8. Verify rollback to the saved baseline, then reapply/reverify the candidate if the requested final sandbox state is migrated. Record both transitions.
9. Emit final result and evidence dossier. LLM prose cannot elevate a deterministic failed/unverified verdict.

Persist contract/candidate revisions, completed actions, receipts, remaining budget and state transitions. Use atomic state-file replacement within the owned run directory. On resume, reconcile process/loaded-config identity and obtain new probes; do not trust a pre-crash success flag. Never restore a snapshot from another run or a changed base revision.

Recovery evidence must include a failed action and what the agent did next, not only a failed test. Include one disclosed, deterministic one-shot fixture restart failure returning a typed error. The agent should inspect status and safely retry/reconcile rather than claim completion. This tests tool handling, not spontaneous resilience to every outage.

## 10. Independent verification and safety

The trusted runner owns verdict calculation. The agent can read results but cannot change its source, checks or ground truth.

A verification receipt binds endpoint, fixture instance, candidate/loaded-config identity, policy version, client profile, probe/library version, timestamp and raw-output digest. Also record TLS version, negotiated group, certificate/hostname verification, app response and elapsed time.

Use fresh full handshakes rather than session-resumed results; disable reuse/ticket behavior as appropriate and reject reused sessions as evidence for this migration. OpenSSL documents that some resumed sessions can report prior group information. [S2]

Authenticate the fixture with a local generated test CA and matching hostname. Do not disable certificate verification to make the demo work. OpenSSL's diagnostic client may continue after certificate errors unless configured to fail; explicitly enforce verification errors and hostname checks if that route is used. [S4]

Do not publish test CA/private keys, model credentials, session tokens or TLS key logs. No external users or production traffic. Restrict agent writes and fixture egress, run without elevated privileges where possible, drop unnecessary capabilities and bound CPU/memory/time. The trusted local launcher may manage Compose; the agent/fixture does not receive the host Docker socket.

Repository text, tool errors and traces are untrusted data, never authority to widen permissions. One workspace and one user is the initial boundary; no multi-tenant production isolation claim.

Latency is measured, but service performance pass/fail requires a predeclared owner threshold. Do not invent an acceptable slowdown after seeing the result.

## 11. Mandatory V1 -> Neatlogs -> V2 improvement

This is core, not an optional feature.

Build an honestly labeled basic V1 loop, not a hidden theatrical failure switch. Record its implementation/prompt and freeze it for evaluation. It may lack explicit fresh-verification enforcement; this is a baseline limitation, not an acceptable final design. All execution stays in the authorized sandbox.

Run the scenario suite and let the independent evaluator identify mistakes. Read the actual Neatlogs spans to locate the failure boundary. A potential finding is that the agent used the on-disk configuration as completion evidence while the active process remained classical-only. Do not claim that finding until a run demonstrates it.

Improve the actual loop/guard/context based on evidence: require fresh current-instance probe receipts, treat error receipts as failed actions, distinguish unsupported policy/client constraints, and avoid unnecessary edits. Capture the code/prompt change with Entire and link it to the compared runs.

Run V2 on clean copies of the same fixtures under the same model, permissions and declared budgets. Retain all evaluated attempts. Verify that previously correct cases remain correct. If no improvement occurs, report it and continue a bounded diagnosis rather than selecting only favorable screenshots.

V2's deterministic readiness gate is core even if V1 never makes the anticipated false-readiness error. In that case demonstrate an observed improvement, or use the failing regression as a labeled unit/fault-injection example, not a fabricated empirical V1 result.

## 12. Evaluation suite and honest measurements

### Minimum scenarios

| Case | Setup and correct outcome |
|---|---|
| Wrong active group | Capable runtime is classical-only; correct permitted config and verify |
| Disk/runtime mismatch | Desired disk config exists but process loads old config; diagnose/reload and verify |
| One-shot action failure | First fixture restart fails; inspect/reconcile/retry and then verify |
| Already compliant | Verify; do not modify unnecessarily |
| Impossible client requirement | Strict hybrid policy plus mandatory classical-only success; report conflict without downgrade |
| Missing/unknown probe evidence | Withhold readiness; return UNVERIFIED with the reason |

Include at least one held-out configuration/path variation after the initial development cases are frozen. The generator/agent does not receive hidden answer keys. Manual fixture faults are labeled as seeded, not customer discoveries.

Use several repeated runs per scenario within a declared budget where practical. Planned target: three repetitions per version/case, adjusted transparently for available resources. A small sample does not establish production reliability. Infrastructure-invalid runs remain reported, not quietly deleted.

### Comparison controls

Same initial snapshots, policy, client expectations, evaluator version, model/settings and budget. Reset fixture state between runs; never let V2 inherit V1's repaired service. Separate cold/warm/cache behavior and record environment noise. Treat budget exhaustion as an outcome, not missing data.

Compare V1, V2 and a fixed supported remediation script. The script baseline has no model token cost; its limitations and permissions must still be comparable. If versions use different models/budgets, report the confounding rather than attributing gains solely to our code.

### Results table to fill after execution

| Metric | V1 | V2 |
|---|---|---|
| Correct task outcomes / valid evaluated runs | Not measured | Not measured |
| Verified migrations / migration-feasible runs | Not measured | Not measured |
| False-readiness claims / evaluated runs | Not measured | Not measured |
| Correct no-op / already-compliant runs | Not measured | Not measured |
| Correct blocker / infeasible-policy runs | Not measured | Not measured |
| Successful recovery / injected-action-failure runs | Not measured | Not measured |
| Policy violations and unnecessary changes | Not measured | Not measured |
| Tokens: input/output and available cache detail | Not measured | Not measured |
| Model cost: billed or explicitly estimated | Not measured | Not measured |
| End-to-end wall time and tool/model calls | Not measured | Not measured |
| Missing-evidence/infrastructure-invalid runs | Not measured | Not measured |

Correctness can improve while latency or cost rises. Explain the verification trade-off; do not require every metric to improve. Report total attempts and cost per verified migration, including unsuccessful attempts; if none succeed, report an undefined denominator.

Ordinary regressions cover stale receipts, policy immutability, wrong group, parser unknowns, failed action handling, unauthorized paths, changed revision, rollback, successful/no-op controls and correct blocked/unverified distinctions. No automatic test generator is required.

## 13. Neatlogs: execution evidence and measured improvement

Use the official SDK with a supported model/client integration verified by a small trace smoke test before building the loop. Record one root run per agent attempt, with spans for model calls, tool calls, retries, verification and final outcome. Preserve parent/child relationships and attach evaluation/scenario/version IDs without supplying the hidden scenario label to the model. Verify traces actually arrive and can be reviewed; local logging is not completed integration. [S5]

Required evidence:

- A real failed tool action, its typed result and the agent's next decision/action.
- Evidence behind the incorrect/uncertain baseline outcome, where observed.
- A code/prompt change informed by those traces.
- Matched V1/V2 runs and their independently calculated numbers.
- Final verifier evidence and scope-aware result, not merely polished answer text.

Use Neatlogs' own viewer/investigation/evaluation capabilities where supported, rather than rebuild them. Exact account features, SDK calls and share/export permissions must be tested. If account export is unavailable, provide authorized accessible trace evidence plus the independent result CSV/JSON; do not invent API endpoints or imply all evaluations run natively.

Redact credentials, private repository content and sensitive prompts before export/public screenshots. For this demo use synthetic fixture data throughout. Capture observable inputs/outputs, decisions and concise summaries, not private chain-of-thought. Export/share enough sanitized evidence that a reviewer can check the claims without a privileged account.

## 14. Entire: checkable development provenance

Initialize Entire using its documented integration with the coding agent actually used. Verify checkpoint/context capture before substantive code changes. Keep a useful development session covering a real change such as fresh-probe enforcement or failed-action handling. Preserve relevant prompts, changed files, concise development context and supported checkpoint identifiers. [S6]

Submission proof: repository-visible checkpoint/context artifacts, supported graph output where available, and a mapping from the V1/V2 source revisions to the relevant captured changes. Entire is development provenance, not runtime correctness or Invaris's resumable state store.

Validate supported agent/workflow behavior instead of promising any exact command/output. Sanitize sessions before making the repository public. Do not fabricate checkpoints after the fact or run a token session merely to display a logo.

Git commits/branches require the user's authorization during implementation. Event-eligible code must follow the organizers' actual rules; existing libraries, plans and reused assets are attributed, not disguised as newly invented work.

## 15. cfo.ai: a real business plan

Use the product to create the actual financial/business plan, not just mention it in the README. A manual in-product workflow/export is sufficient if automation is unavailable; no fabricated MCP calls. Required business categories come from the official challenge. [S1]

Commercial hypothesis: a developer/security team pays for reviewable supported-stack migrations and repeat verification as dependencies/configurations change. Subscription versus one-time migration services must be validated; no assumed recurring demand.

Model:

- Proposed pricing/packages, included verification allowance and extra usage.
- Customers, migrations/customer, conversion/churn assumptions and revenue.
- Model usage including failed/retried attempts, worker duration and artifact storage.
- Human review, onboarding, adapter upkeep, support and sales/acquisition cost.
- Fixed expense, gross margin, cash burn and runway.
- Base, high-retry/high-support and slower-sales scenarios.

Use measured run costs where available; pricing, adoption and support assumptions stay labeled. Include review overhead rather than presenting inference cost as total cost. Token-derived cost estimates use the verified applicable price/date and are distinguished from actual bills. Do not promise cost savings without a customer baseline.

Store/share the actual plan export plus a short assumptions note and sensitivity results. cfo.ai is not a runtime approval, billing or spend-control system; our local controller owns execution limits.

## 16. Repository and artifacts we will implement

Only this README exists as the consolidated plan. The following structure is proposed, not already runnable:

~~~text
README.md
pyproject.toml
lockfile
compose.yaml
.env.example
src/invaris/
  agent.py
  controller.py
  contracts.py
  tools.py
  verifier.py
  tracing.py
  state.py
  report.py
fixture/
  Dockerfile
  server.c
  probe.c
  profiles/
  build-manifest.json
evaluation/
  runner.py
  scenarios/
  approved-policies/
  compare.py
tests/
artifacts/
  sample-sanitized-bundle/
business/
  assumptions.md
  cfo-plan-export
public-build/
  log.md
  approved-screenshots/
~~~

Trusted evaluator/probe files are read-only to the agent. The writable candidate directory is separate from the implementation repository and trusted fixture code. Generated reports escape untrusted strings; don't render tool output as executable HTML.

A run bundle contains contract, instance/build identity, code/prompt versions, configuration patch, action/probe/application/rollback receipts, sanitized events, trace links/IDs, final verdict, result summary and limitations. The evaluation bundle additionally contains raw per-run rows, inclusion rules, matched comparison and Entire change mapping. Hashes detect later artifact changes but do not prove trusted provenance on their own.

### Developer setup we must deliver

Prerequisites: Docker Desktop with Linux containers/WSL2 or Linux Docker, tested Python/compiler setup, model access, Neatlogs account/key, supported Entire integration and cfo.ai access. No enterprise infrastructure or quantum hardware is required.

Implemented commands to build the pinned image, initialize an ephemeral local CA, run a scenario, evaluate V1/V2, render reports and clean only owned fixture resources are documented in `docs/operations.md`. Fresh-machine reproduction remains a release gate, not a completed claim. The layout above is the original design target; use the actual source tree and operator guide for implemented paths.

Environment configuration includes model credentials, Neatlogs credentials, artifact directory and explicit run limits. Keep secrets in ignored local environment storage, not commits/reports/checkpoints. No private keys or populated .env files in the public repository.

## 17. What we say and show: the demo

Official video limit: three minutes or less. Target about 170 seconds, leaving upload/player tolerance. Our own target stays below the limit. Explicitly cover architecture, implementation, runtime behavior, decision-making and result for each of the three partners. [S1]

| Segment | Say | Show |
|---|---|---|
| 0-15s | "The config says ready. The connection disagrees." | Baseline config beside an actual classical-only connection receipt |
| 15-35s | "One Python agent, safe typed tools, a disposable fixture and an independent verifier." | Compact architecture, relevant source and Entire change context |
| 35-105s | "It checks the running service, handles a failed action and verifies the revised candidate." | One coherent failure/recovery run: plan, failed action, diagnosis, bounded correction, fresh handshake and app result |
| 105-140s | "These traces showed the failure boundary; this change improved the matched cases." | Neatlogs spans, V1/V2 source change and real result table |
| 140-160s | "This is how the supported workflow could be sold and what it costs." | Actual cfo.ai plan: pricing, costs, revenue assumptions and runway |
| 160-170s | "Verified for this stack and policy, not a universal quantum-safe claim." | Patch/evidence bundle, scoped verdict and public reproduction route |

Use concise evidence-grounded decision summaries. Keep cryptographic explanation to one sentence in the main video: the approved hybrid key exchange combines classical and post-quantum components; our scoped check is that the connection actually uses it. Put implementation details in supporting material.

Prepare a compact evidence card per partner: where it fits, how we integrated/used it, its actual execution/session, why that use mattered and the resulting artifact. For Neatlogs show trace instrumentation and investigation leading to the measured change; for Entire show supported capture behind that development change; for cfo.ai show the real plan-generation/revision workflow and assumptions behind its export. Development and business workflows have different roles from the migration runtime; do not pretend all three execute inside every migration.

The principal demo should include a completed feasible migration, not only blocked cases. Use a disclosed seeded failure and accurately labeled recorded footage where needed. Do not claim a prerecorded run is live or hide the unsuccessful attempts in the evaluation totals. Show a rollback receipt in the bundle even if its full execution is too long for the main edit.

### Suggested opening and closing

Opening: "This service has the right-looking config, but its running connection is still outside our target policy. Invaris doesn't accept the claim. It investigates, makes an allowed change, and verifies the actual result."

Closing: "Here is the patch, the fresh connection result, the application check and the rollback evidence. Here is the measured agent improvement. This is one supported migration, with its limits visible."

Replace any sentence that implies an unobserved failure or improvement with the actual measured result. Never script a false empirical claim to fit the narrative.

## 18. Build in public: core submission work

The official rubric allocates 30% to agent execution, 25% to partner use, 20% to the demo, 15% to public progress and 10% to utility/originality. Public engagement also relates to a separate community award. The official page asks for event-period #neatHack posts and checkable evidence; recheck it before submission. [S1]

Make genuine posts during the eligible event period:

1. Problem/pitch and the small stack we chose; distinguish concept from implemented work.
2. The first verified capability result or blocker.
3. A sanitized failed handshake/action and the trace showing why it matters.
4. The actual agent change and V1/V2 results, including trade-offs.
5. Final scoped demo, reproduction path and business assumptions.

Include #neatHack as required, useful screenshots and public repository links when available. Maintain an evidence log with post URLs, actual dates, captured run IDs and what was completed. Ask for technical feedback and record meaningful responses. No bought engagement, false endorsements, backdated posts or secret-bearing screenshots.

This is an evidence checklist, not an event schedule. No contest timeline is planned here.

## 19. Score-oriented evidence checklist

| Area | Checkable proof |
|---|---|
| Agent task | Allowed changes, differing decision paths, failed-action recovery and independent outcome |
| Neatlogs | Visible spans, failed action/response, trace-informed change and matched improvement numbers |
| Entire | Useful captured development context linked to source/test changes |
| cfo.ai | Actual plan/export containing pricing, costs, revenue and runway |
| Demo | Accessible video under the limit, clear architecture/runtime/result and partner use |
| Public work | Genuine dated #neatHack posts and build log |
| Utility | A supported migration, not just advice; explicit limits and reproducibility |

The published submission asks for a public repository and event-dated commits. Follow exact eligibility wording and get organizer clarification on reused components; do not assume these planning files or dependencies count as event-created implementation. [S1]

Submission route: publish the required public quote post of the official submission post on X, including team/name, project, repository and demo. Check the current organizer instructions and confirmed cutoff; opening a draft is not a completed submission. Supporting evidence belongs in the accessible repository. [S1]

No win probability, official endorsement or guaranteed superiority is asserted. Score alignment determines priorities, not fabricated metrics.

## 20. Build gates, not a timeline

**G0: access and rules.** Confirm eligible implementation/dependency reuse, supported Entire workflow, Neatlogs trace sharing and cfo.ai artifact access. Record dependency licenses/attribution.

**G1: cryptographic fixture.** Real target/classical connections distinguished, certificate identity checked, application response verified, runtime pinned and fixture reset reproducible. Do not proceed with a pretend probe.

**G2: safe tools and evaluator.** Typed receipts, write boundaries, approval, rollback, current-instance verification and status semantics tested.

**G3: baseline agent.** V1 actually uses tools, runs the seeded suite and has retrievable traces. Preserve the source/prompt used.

**G4: improved agent.** Evidence-informed V2, mandatory freshness/error handling, multiple decision paths and matched comparison. Correct cases do not regress unnoticed.

**G5: complete partners.** Checkpoint/context mapping, Neatlogs failure/improvement evidence and actual cfo.ai model exported/shared.

**G6: reproducibility and presentation.** Fresh setup, clean repository/secret review, sanitized reports, public-build evidence and under-limit video.

No new framework, dashboard or autonomous regression compiler before these gates. If resources are tight, cut UI polish and extra stacks, not actual probes, safety checks, improvement evidence or partner requirements.

## 21. Definition of done

- A clean setup can reproduce a real supported migration.
- The agent inspects, plans, acts and adapts; it is not merely a scripted scenario router.
- One failed action and safe recovery are visible, with alternative cases/no-op tested.
- The independent verifier observes permitted group/protocol, authenticated endpoint and required app behavior on the current candidate.
- Blocked/unverified cases do not become success claims or silent policy downgrades.
- Rollback is tested and fresh resulting state evidence is saved.
- V1/V2 comparisons are real, matched and include all attempts/denominators.
- Neatlogs, Entire and cfo.ai evidence is accessible and sanitized.
- Public progress and source eligibility are documented honestly.
- The video is below the official limit and supporting artifacts reproduce the claim.

Automatic test generation, a hosted frontend and a production SaaS are not completion conditions.

## 22. Risks, fallback decisions and production boundary

| Risk | Required response |
|---|---|
| No reliable negotiated-group evidence | Stop capability gate; fix helper/parser, never infer success from config |
| Tiny suite behaves like a fixed script | Show a real differing decision path and disclose script comparison |
| V1 already succeeds | Do not fabricate failure; inspect other observed deficiencies and report limits |
| V2 fails to improve | Retain data, diagnose and rerun transparently; no cherry-picking |
| Trace/account sharing fails | Verify authorized export/view options; unresolved partner evidence is a submission blocker |
| Entire workflow unsupported | Use a documented supported setup; don't promise arbitrary runtime capture |
| Costs exceed budget | Stop safely, preserve partial evidence and simplify optional work |
| Secret/public artifact risk | Redact before publishing; rotate exposed credentials if necessary |
| Unknown client/policy behavior | UNVERIFIED/BLOCKED, not extrapolation from a single client |

Production expansion would require expert security/crypto review, more supported stacks and real client matrices, stronger change authority, isolation, audit retention/deletion, backups, operational response and maintained verification adapters. Those are future requirements, not features already implemented. An assistant can help build this system; that does not eliminate the need for independent cryptographic review of deployment claims.

## 23. Optional future scope

Only after the core proves useful: additional supported stacks, CI continuous verification, richer review UI, managed private workers and independently validated trace-to-regression generation. Certificate-signature/PKI migration is separate scope. None is promised in the initial submission or used to inflate the pitch.

## 24. Primary references and research limits

These references support technical/rule context; design choices and product hypotheses above are ours. SDK surfaces, pricing, maintained patches and account capabilities must be rechecked at implementation time. No research benchmark is presented as our result.

- [S1] Official challenge/rubric/submission authority: https://neatlogs.com/hackathon
- [S2] OpenSSL 3.5 TLS group configuration and hybrid-group support: https://docs.openssl.org/3.5/man3/SSL_CTX_set1_curves/
- [S3] OpenSSL negotiated-group accessors and resumption caveats: https://docs.openssl.org/3.5/man3/SSL_get0_group_name/
- [S4] OpenSSL diagnostic client and verification options: https://docs.openssl.org/3.5/man1/openssl-s_client/
- [S5] Neatlogs documentation, integration entry point and evidence surfaces: https://docs.neatlogs.com/docs
- [S6] Entire official CLI/integration documentation: https://github.com/entireio/cli

The supplied trace-reading transcript informs evidence inspection, reviewed rubrics, false-positive/negative awareness and regression protection. It is not evidence that our agent has already improved. No exhaustive literature review, trademark clearance or official runtime-eligibility approval is claimed.

## 25. Final instruction to the implementation agent

Build **Invaris Migration Engineer**, following this README only. Start by proving the real fixture/probe, then safe tools, then the minimal agent and matched evaluation. Instrument from the first run. Ship a complete narrow workflow with checkable partner evidence, not a large unfinished platform.

**One product. One supported stack. Real connections. Honest improvement.**
