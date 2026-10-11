(() => {
  "use strict";

  const root = document.getElementById("app");
  const state = { bootstrap: null, jobs: [], loading: false, error: "", route: null, query: "", runOutcome: "all", runMode: "all", run: null, selectedScenario: "", mode: "offline", setupApproved: false, runApproved: false, liveAcknowledged: false, notice: "", evidence: null, evidencePath: "", pollTimer: null, jobSignature: "", submitting: false };
  const iconPaths = {
    mark: "M12 2.8 20 7v10l-8 4.2L4 17V7z M8 9.1l4 2.1 4-2.1 M12 11.2v4.6", grid: "M4 4h6v6H4z M14 4h6v6h-6z M4 14h6v6H4z M14 14h6v6h-6z", workflow: "M6 4v5a3 3 0 0 0 3 3h6a3 3 0 0 1 3 3v5 M18 4v2 M6 18v2", runs: "M5 4h14v16H5z M8 8h8 M8 12h8 M8 16h5", links: "M9 15l6-6 M7 17H5a3 3 0 0 1 0-6h4 M17 7h2a3 3 0 0 1 0 6h-4", evidence: "M12 3v12 M7 10l5 5 5-5 M4 19h16", chart: "M4 19V5 M4 19h16 M7 15l4-5 3 2 5-7", search: "M10.8 17.5a6.7 6.7 0 1 1 0-13.4 6.7 6.7 0 0 1 0 13.4z M16 16l4 4", arrow: "M5 12h14 M13 6l6 6-6 6", external: "M13 5h6v6 M19 5l-9 9 M17 13v6H5V7h6", check: "M5 12l4 4L19 6", shield: "M12 3 19 6v5c0 5-3 8-7 10-4-2-7-5-7-10V6z M9 12l2 2 4-4", pulse: "M3 12h4l3-7 4 14 3-7h4", layers: "m12 3 9 5-9 5-9-5 9-5z M3 12l9 5 9-5 M3 16l9 5 9-5"
  };
  const nav = [{ path: "/app", label: "Overview", icon: "grid" }, { path: "/app/replay", label: "Guided replay", icon: "pulse" }, { path: "/app/workflows", label: "Workflows", icon: "workflow" }, { path: "/app/runs", label: "Runs", icon: "runs" }, { path: "/app/integrations", label: "Integrations", icon: "links" }, { path: "/app/evidence", label: "Evidence", icon: "evidence" }, { path: "/app/business", label: "Business case", icon: "chart" }];

  function el(tag, className, content) { const node = document.createElement(tag); if (className) node.className = className; if (content !== undefined && content !== null) node.textContent = String(content); return node; }
  function icon(name, className = "icon") { const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg"); svg.setAttribute("viewBox", "0 0 24 24"); svg.setAttribute("class", className); svg.setAttribute("fill", "none"); svg.setAttribute("stroke", "currentColor"); svg.setAttribute("stroke-width", "1.7"); svg.setAttribute("stroke-linecap", "round"); svg.setAttribute("stroke-linejoin", "round"); svg.setAttribute("aria-hidden", "true"); const path = document.createElementNS("http://www.w3.org/2000/svg", "path"); path.setAttribute("d", iconPaths[name] || iconPaths.mark); svg.append(path); return svg; }
  function button(label, action, className = "button") { const node = el("button", className, label); node.type = "button"; node.dataset.action = action; return node; }
  function link(label, href, className = "") { const node = el("a", className, label); node.href = href; return node; }
  function sectionTitle(kicker, title, description) { const head = el("div", "section-heading"); head.append(el("p", "eyebrow", kicker), el("h1", "page-title", title)); if (description) head.append(el("p", "page-description", description)); return head; }
  function invariantScene(compact = false) {
    const scene = el("div", "core-scene" + (compact ? " compact-scene" : ""));
    const canvas = document.createElement("canvas");
    canvas.className = "core-canvas";
    canvas.dataset.invariantScene = "true";
    canvas.setAttribute("aria-hidden", "true");
    scene.append(canvas);
    if (!compact) {
      const label = el("div", "core-topline");
      label.append(el("span", "core-coordinate", "FIG. 01 / INVARIANT CORE"), el("span", "core-illustration", "ILLUSTRATION"));
      scene.append(label, el("span", "core-label core-label-top", "01 / APPROVED CONTRACT"),
        el("span", "core-label core-label-left", "CLASSICAL"), el("span", "core-label core-label-right", "POST-QUANTUM"),
        el("span", "core-label core-label-bottom", "02 / CONNECTION EVIDENCE"));
      const footer = el("div", "core-bottomline");
      footer.append(el("span", "", "Different paths. One invariant."), button("Pause motion", "toggle-motion", "motion-toggle"));
      scene.append(footer);
    }
    return scene;
  }

  function overviewSignal() {
    const panel = el("section", "workspace-signal");
    const copy = el("div", "signal-copy");
    copy.append(el("p", "eyebrow", "CONTROL PLANE / APPROVAL-FIRST"), el("h2", "", "No proof. No readiness."),
      el("p", "signal-description", "The model proposes. The contract decides. Start a bounded workflow or inspect the last recorded live run."));
    const actions = el("div", "signal-actions");
    actions.append(linkWithIcon("Open workflows", "/app/workflows"));
    const latest = (state.bootstrap?.runs || []).find(run => run.mode === "live-model");
    if (latest) actions.append(linkWithIcon("Inspect last live run", "/app/runs/" + encodeURIComponent(latest.id)));
    copy.append(actions);
    const graphic = invariantScene(true);
    graphic.append(el("span", "compact-caption", "ILLUSTRATION / NOT A RUN"));
    panel.append(copy, graphic);
    return panel;
  }
  function commandPalette() {
    const pages = nav.map(item => ({ label: item.label, detail: "Workspace page", path: item.path }));
    const runs = (state.bootstrap?.runs || []).map(run => ({ label: pretty(run.scenario),
      detail: run.id + " · " + run.status, path: "/app/runs/" + encodeURIComponent(run.id) }));
    window.InvarisVisuals?.openCommandPalette([{ label: "Landing page", detail: "The Invaris method", path: "/" }, ...pages, ...runs], go);
  }

  function proofSummary(data) {
    const rail = el("section", "proof-rail");
    rail.setAttribute("aria-label", "Independent proof summary");
    const checks = data.receipts?.independent_verification?.checks || {};
    const stages = [
      { name: "Connection", label: checks.target_group === true ? "Target group observed" : "Target group not proved", passed: checks.target_group === true, glyph: "pulse" },
      { name: "Contract", label: data.run?.verified === true ? "Independent checks passed" : "Not independently verified", passed: data.run?.verified === true, glyph: "shield" },
      { name: "Artifacts", label: data.artifact_integrity?.integrity_valid === true ? "Hashes checked · not attested" : "Integrity not proved", passed: data.artifact_integrity?.integrity_valid === true, glyph: "evidence" },
      { name: "Rollback", label: data.rollback?.verified === true ? "Baseline restored" : "Restoration not proved", passed: data.rollback?.verified === true, glyph: "workflow" }
    ];
    stages.forEach((stage, index) => {
      const card = el("article", "proof-stage" + (stage.passed ? " proof-passed" : ""));
      card.append(el("span", "proof-stage-number", String(index + 1).padStart(2, "0")), icon(stage.glyph),
        el("strong", "", stage.name), el("span", "", stage.label));
      rail.append(card);
    });
    return rail;
  }

  function runFilters() {
    const toolbar = el("div", "run-toolbar");
    const groups = [
      { key: "runOutcome", label: "Outcome", selected: state.runOutcome,
        options: [["all", "All outcomes"], ["VERIFIED", "Verified"], ["BLOCKED", "Blocked"], ["UNVERIFIED", "Unverified"]] },
      { key: "runMode", label: "Execution mode", selected: state.runMode,
        options: [["all", "All modes"], ["live-model", "Live agent"], ["offline-smoke-not-LLM", "Offline script"], ["fixed-script-baseline-not-LLM", "Fixed baseline"]] }
    ];
    groups.forEach(group => {
      const label = el("label", "run-filter");
      label.append(el("span", "", group.label));
      const select = document.createElement("select");
      select.dataset.filter = group.key;
      group.options.forEach(([value, text]) => {
        const option = el("option", "", text);
        option.value = value;
        option.selected = value === group.selected;
        select.append(option);
      });
      label.append(select);
      toolbar.append(label);
    });
    return toolbar;
  }
  function notice(text, kind = "info") { const box = el("div", `notice notice-${kind}`, text); box.setAttribute("role", kind === "error" ? "alert" : "status"); return box; }
  function fmt(value, style = "number") { if (value === null || value === undefined || value === "") return "—"; if (style === "money") { const numericValue = Number(value); return Number.isFinite(numericValue) ? new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 3 }).format(numericValue) : String(value); } if (style === "date") { const parsedDate = new Date(value); return Number.isNaN(parsedDate.getTime()) ? String(value) : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(parsedDate); } if (style === "duration") { const numericValue = Number(value); return Number.isFinite(numericValue) ? `${numericValue.toFixed(1)}s` : String(value); } const numericValue = Number(value); return Number.isFinite(numericValue) ? new Intl.NumberFormat().format(numericValue) : String(value); }
  function slug(value) { return String(value || "unknown").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""); }
  function pretty(value) { return String(value ?? "—").replace(/[_-]+/g, " ").replace(/\b\w/g, character => character.toUpperCase()); }
  function modeLabel(value) { const labels = { live: "Live model", "live-model": "Live model", offline: "Offline smoke · not LLM", "offline-smoke-not-LLM": "Offline smoke · not LLM", "fixed-script-baseline-not-LLM": "Fixed script baseline · not LLM" }; return labels[value] || pretty(value); }
  function pathRoute() { const path = decodeURI(location.pathname); if (path === "/") return { page: "landing" }; if (path === "/app") return { page: "overview" }; if (path === "/app/replay") return { page: "replay" }; if (path === "/app/workflows") return { page: "workflows" }; if (path === "/app/runs") return { page: "runs" }; if (path.startsWith("/app/runs/")) return { page: "run", id: path.slice("/app/runs/".length) }; if (path === "/app/integrations") return { page: "integrations" }; if (path === "/app/evidence") return { page: "evidence" }; if (path === "/app/business") return { page: "business" }; return { page: "notfound" }; }
  function go(path) { stopReplay(); replay.index = 0; state.run = null; state.runRequest = (state.runRequest || 0) + 1; if (location.pathname !== path) history.pushState({}, "", path); state.query = ""; state.notice = ""; state.evidence = null; state.evidencePath = ""; state.route = pathRoute(); const update = () => { render(); window.scrollTo({ top: 0, behavior: "instant" }); document.getElementById("main-content")?.focus({ preventScroll: true }); if (state.route.page === "run") loadRun(state.route.id); if (state.route.page === "replay") loadRecordedReplay(); }; if (window.InvarisVisuals) window.InvarisVisuals.transition(update); else update(); }
  async function api(path, options = {}) { const headers = { Accept: "application/json", ...(options.headers || {}) }; if (options.body) headers["Content-Type"] = "application/json"; const response = await fetch(path, { ...options, headers }); const type = response.headers.get("content-type") || ""; const data = type.includes("json") ? await response.json() : await response.text(); if (!response.ok) throw new Error(typeof data === "object" && data ? (data.detail || data.error || data.message || `Request failed (${response.status})`) : `Request failed (${response.status})`); return data; }
  async function loadRun(id) { if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(id)) { state.run = { error: "That run ID is not a valid UUID." }; render(); return; } const requestId = state.runRequest = (state.runRequest || 0) + 1; state.run = null; render(); let result; try { result = await api(`/api/runs/${encodeURIComponent(id)}`); } catch (error) { result = { error: error.message }; } if (state.runRequest !== requestId || state.route?.page !== "run" || state.route.id !== id) return; state.run = result; render(); }
  async function refreshData() { try { const [boot, jobs] = await Promise.all([api("/api/bootstrap"), api("/api/jobs")]); state.bootstrap = boot; state.jobs = Array.isArray(jobs.jobs) ? jobs.jobs : []; state.error = ""; state.loading = false; if (!state.selectedScenario && boot.scenarios?.length) state.selectedScenario = boot.scenarios[0].id; if (state.fixtureNeedsSetup && boot.fixture?.ready) { state.fixtureNeedsSetup = false; state.notice = "Fixture setup finished. Review the job below before launching a run."; } render(); } catch (error) { state.error = error.message || "Could not load Invaris."; state.loading = false; render(); } }
  function jobSignature(jobs) { return JSON.stringify((jobs || []).map(job => [job.id, job.status, job.run_id])); }
  async function pollJobs() { try { const data = await api("/api/jobs"); const jobs = Array.isArray(data.jobs) ? data.jobs : []; const signature = jobSignature(jobs); if (signature !== state.jobSignature) { const hadPrevious = Boolean(state.jobSignature); state.jobSignature = signature; state.jobs = jobs; await refreshData(); if (hadPrevious && state.route.page === "run") loadRun(state.route.id); } const active = jobs.some(job => ["queued", "running", "pending"].includes(String(job.status).toLowerCase())); if (state.pollTimer) clearTimeout(state.pollTimer); state.pollTimer = active ? setTimeout(pollJobs, 1600) : null; } catch { if (state.pollTimer) clearTimeout(state.pollTimer); state.pollTimer = setTimeout(pollJobs, 5000); } }
  function startPolling() { if (state.pollTimer) clearTimeout(state.pollTimer); state.jobSignature = jobSignature(state.jobs); pollJobs(); }
  async function launch(action) { if (!state.bootstrap?.session_token) { state.notice = "Session is not ready. Reload and try again."; render(); return; } if (!(action === "setup" ? state.setupApproved : state.runApproved)) { state.notice = action === "setup" ? "Confirm the fixture setup authorization first." : "Confirm the run authorization first."; render(); return; } if (action === "run" && !state.bootstrap.fixture?.ready) { state.notice = "Complete fixture setup before starting a run."; render(); return; } if (action === "run" && state.mode === "live" && !state.liveAcknowledged) { state.notice = "Acknowledge possible model charges before choosing live mode."; render(); return; } const scenario = state.selectedScenario || state.bootstrap.scenarios?.[0]?.id; if (!scenario) { state.notice = "No scenarios are available from the server."; render(); return; } state.submitting = true; state.notice = "Submitting request…"; render(); const payload = { action, scenario, mode: action === "setup" ? "offline" : state.mode, approved: true }; if (action === "run" && state.mode === "live") payload.acknowledge_spend = true; try { const job = await api("/api/jobs", { method: "POST", headers: { "X-Invaris-Session": state.bootstrap.session_token }, body: JSON.stringify(payload) }); state.jobs = [job, ...state.jobs.filter(existing => existing.id !== job.id)]; state.setupApproved = false; state.runApproved = false; state.liveAcknowledged = false; state.notice = `Request accepted. Job ${job.id || ""} is ${job.status || "being prepared"}.`; state.submitting = false; render(); startPolling(); } catch (error) { state.submitting = false; state.notice = `Request failed: ${error.message}`; render(); } }
  function topbar() { const bar = el("header", "topbar"); const searchWrap = el("label", "searchbox"); searchWrap.append(icon("search")); const input = document.createElement("input"); input.type = "search"; input.placeholder = "Search runs and scenarios…"; input.setAttribute("aria-label", "Search runs and scenarios"); input.value = state.query; input.addEventListener("input", () => { state.query = input.value; updateSearchResults(); }); searchWrap.append(input); bar.append(searchWrap); const jump = button("Quick jump", "command-palette", "quick-jump"); jump.append(el("kbd", "", "Ctrl K")); bar.append(jump); const status = el("div", "system-status"); status.append(el("span", "status-dot"), el("span", "status-label", state.error ? "Connection issue" : "Console connected")); bar.append(status); return bar; }
  function sidebar(active) { const aside = el("aside", "sidebar"); const brand = link("", "/app", "brand"); const symbol = el("span", "brand-symbol"); symbol.append(icon("mark", "icon brand-icon")); brand.append(symbol, el("span", "brand-name", "invaris")); aside.append(brand); const group = el("div", "nav-group"); group.append(el("p", "nav-label", "Workspace")); nav.forEach(item => { const anchor = link("", item.path, `nav-link${active === item.path ? " active" : ""}`); if (active === item.path) anchor.setAttribute("aria-current", "page"); anchor.append(icon(item.icon, "icon nav-icon"), el("span", "", item.label)); group.append(anchor); }); aside.append(group); const footer = el("div", "sidebar-footer"); const secured = el("div", "secure-note"); secured.append(icon("shield", "icon"), el("span", "", "Verified change")); footer.append(secured, el("span", "build-label", "INVARIS · CONTROL PLANE")); aside.append(footer); return aside; }
  function shell(page) { const active = page === "overview" ? "/app" : page === "run" ? "/app/runs" : `/app/${page}`; const frame = el("div", "app-frame"); frame.append(sidebar(active)); const area = el("div", "app-area"); area.append(topbar()); const main = el("main", "app-main"); main.id = "main-content"; main.tabIndex = -1; area.append(main); frame.append(area); root.replaceChildren(frame); return main; }
  function metric(label, value, foot, iconName) { const card = el("article", "metric-card"); const top = el("div", "metric-top"); top.append(el("span", "metric-label", label), icon(iconName || "pulse", "icon metric-icon")); card.append(top, el("p", "metric-value", value), el("p", "metric-foot", foot)); return card; }
  function row(label, value, mono = false) { const item = el("div", "data-row"); item.append(el("span", "data-label", label), el("span", mono ? "data-value mono" : "data-value", value)); return item; }
  function statusPill(value) { return el("span", `pill pill-${slug(value)}`, pretty(value)); }
  function empty(title, detail) { const box = el("div", "empty-state"); box.append(icon("layers", "icon empty-icon"), el("h3", "", title), el("p", "", detail)); return box; }
  function matches(value) { return !state.query || String(value || "").toLowerCase().includes(state.query.toLowerCase()); }
  function updateSearchResults() {
    const list = root.querySelector(".run-list");
    if (list) {
      list.replaceChildren();
      recentRuns(list, state.bootstrap?.runs || [], state.route.page === "runs" ? Infinity : 4);
    }
    const scenarios = [...root.querySelectorAll(".scenario-card")];
    scenarios.forEach(card => {
      card.hidden = !matches(card.textContent);
    });
    const grid = root.querySelector(".scenario-grid");
    if (grid) {
      let message = grid.querySelector(".scenario-search-empty");
      if (!message) {
        message = el("p", "scenario-search-empty", "No scenarios match this search. Clear it to see all workflows.");
        message.setAttribute("role", "status");
        grid.append(message);
      }
      message.hidden = scenarios.some(card => !card.hidden);
    }
  }
  function runCard(run) { const card = el("article", "run-row"); const main = el("div", "run-row-main"); main.append(link(run.scenario || "Scenario", `/app/runs/${encodeURIComponent(run.id)}`, "run-title"), el("span", "run-id mono", run.id || "—")); card.append(main); const meta = el("div", "run-row-meta"); meta.append(el("span", "verdict-label", "Independent"), statusPill(run.status), el("span", "muted", modeLabel(run.mode)), el("span", "muted", fmt(run.created_at, "date"))); card.append(meta); const end = el("div", "run-row-end"); end.append(el("span", "run-cost", fmt(run.cost, "money")), el("span", `verify-mark ${run.verified ? "is-verified" : ""}`, run.verified ? "Verified" : "Not verified")); card.append(end); return card; }
  function recentRuns(container, runs, count = 5) { const filtered = (runs || []).filter(run => matches(`${run.id} ${run.scenario} ${run.version} ${run.status} ${run.mode}`) && (state.route?.page !== "runs" || ((state.runOutcome === "all" || run.status === state.runOutcome) && (state.runMode === "all" || run.mode === state.runMode)))); if (!filtered.length) { container.append(empty("No runs match this search.", "Runs will appear here after an authorized workflow completes.")); return; } filtered.slice(0, count).forEach(run => container.append(runCard(run))); }
  function sectionCard(title, subtitle) { const card = el("section", "panel"); const head = el("div", "panel-head"); head.append(el("h2", "panel-title", title)); if (subtitle) head.append(el("p", "panel-subtitle", subtitle)); card.append(head); return card; }
  function linkWithIcon(label, href) { const anchor = link("", href, "text-link"); anchor.append(el("span", "", label), icon("arrow", "icon")); return anchor; }
  function renderOverview(main) { const boot = state.bootstrap || {}; const runs = boot.runs || []; const study = boot.summary?.latest_study; const verified = runs.filter(run => run.verified).length; main.append(sectionTitle("WORKSPACE / OVERVIEW", "Change with a chain of proof.", "A bounded migration workflow with independent verification, recorded from first action to final receipt.")); if (state.error) main.append(notice(`Could not load live workspace data: ${state.error}`, "error")); main.append(onboardingPanel(), overviewSignal()); const metrics = el("div", "metric-grid"); metrics.append(metric("Recorded runs", fmt(runs.length), "From the connected workspace", "runs"), metric("Verified runs", fmt(verified), "Verification recorded by the server", "shield"), metric("Committed estimate", fmt(boot.budget?.committed_estimate_usd, "money"), "Current authorized work", "chart"), metric("Fixture", boot.fixture?.ready ? "Ready" : "Not set up", boot.fixture?.project || "Awaiting project details", "workflow")); main.append(metrics); const split = el("div", "content-grid"); const recent = sectionCard("Recent runs", "Open a run to inspect its trace and receipts."); const list = el("div", "run-list"); recentRuns(list, runs, 4); recent.append(list); const side = el("aside", "panel insight-panel"); side.append(el("p", "eyebrow", "LATEST STUDY"), el("h2", "panel-title", study?.id || "No study loaded"), el("p", "panel-subtitle", "Study outcomes come from the connected evaluation record.")); if (study?.summaries) Object.entries(study.summaries).forEach(([name, value]) => { const line = el("div", "study-line"); line.append(el("span", "", name), el("strong", "", `${fmt(value.correct_outcomes)}/${fmt(value.attempts)}`)); side.append(line); }); else side.append(el("p", "muted", "No evaluation summary is available.")); side.append(linkWithIcon("Review evidence", "/app/evidence")); split.append(recent, side); main.append(split); const jobsPanel = sectionCard("Workflow activity", "Requests and setup jobs reported by the service."); renderJobs(jobsPanel, state.jobs.slice(0, 4)); main.append(jobsPanel); }
  function check(label, key, checked, description) { const wrap = el("label", "check-control"); const input = document.createElement("input"); input.type = "checkbox"; input.checked = checked; input.dataset.state = key; const copy = el("span", "check-copy"); copy.append(el("strong", "", label), el("small", "", description)); wrap.append(input, copy); return wrap; }
  function renderJobs(panel, jobs) { if (!jobs?.length) { panel.append(empty("No workflow activity yet.", "Choose a scenario to explicitly set up the fixture or request a run.")); return; } const list = el("div", "jobs-list"); jobs.forEach(job => { const item = el("article", "job-row"); const heading = el("div", "job-heading"); heading.append(el("strong", "", pretty(job.action)), statusPill(job.status)); item.append(heading, el("p", "job-description", job.message || `${job.scenario || "Scenario"} · ${modeLabel(job.mode)}`), el("span", "job-time", fmt(job.created_at, "date"))); if (job.run_id) item.append(link("Open resulting run →", `/app/runs/${encodeURIComponent(job.run_id)}`, "small-link")); if (Array.isArray(job.events) && job.events.length) { const events = el("div", "job-events"); job.events.forEach((event, index) => events.append(eventCard(event, index))); item.append(events); } list.append(item); }); panel.append(list); }
  function renderWorkflows(main) { const boot = state.bootstrap || {}; const scenarios = boot.scenarios || []; main.append(sectionTitle("WORKSPACE / WORKFLOWS", "Choose a bounded workflow.", "Fixture setup and migration runs are explicit requests. Nothing runs automatically when you open this page.")); if (state.notice) main.append(notice(state.notice, state.notice.startsWith("Request failed") ? "error" : "info")); if (!scenarios.length) { main.append(notice(state.error ? `Scenarios unavailable: ${state.error}` : "No scenarios are currently exposed by the service.", state.error ? "error" : "info")); return; } main.append(onboardingPanel()); const grid = el("div", "scenario-grid"); scenarios.forEach(scenario => { const card = el("button", `scenario-card${state.selectedScenario === scenario.id ? " selected" : ""}`); card.type = "button"; card.dataset.scenario = scenario.id; card.setAttribute("aria-pressed", String(state.selectedScenario === scenario.id)); card.append(el("span", "scenario-topline", `SCENARIO · ${scenario.id}`), el("strong", "scenario-name", scenario.name), el("span", "scenario-description", scenario.description || "No description provided."), icon(state.selectedScenario === scenario.id ? "check" : "arrow", "icon scenario-mark")); grid.append(card); }); main.append(grid); const setup = sectionCard("Fixture setup", "Setup creates the local invaris-console project and requires your approval."); setup.append(row("Project", boot.fixture?.project || "invaris-console"), row("Current state", boot.fixture?.ready ? "Ready" : "Needs setup")); if (!boot.fixture?.ready) { setup.append(check("I authorize fixture setup", "setupApproved", state.setupApproved, "This submits one setup job to the local service.")); const actionButton = button(state.submitting ? "Submitting…" : "Set up fixture", "setup", "button button-secondary"); actionButton.disabled = state.submitting || !state.setupApproved; setup.append(actionButton); } else setup.append(notice("Fixture is ready. Setup is not needed.", "success")); main.append(setup); const launchCard = sectionCard("Run workflow", boot.fixture?.ready ? "Choose a mode, then authorize the request." : "Fixture setup must finish before any workflow can run."); const modes = el("div", "mode-options"); [["offline", "Offline smoke · not LLM", "Local verification only. No model inference or fee."], ["live", "Live model run", "May incur model charges under the configured budget."]].forEach(([value, label, detail]) => { const option = el("label", `mode-option${state.mode === value ? " chosen" : ""}`); const radio = document.createElement("input"); radio.type = "radio"; radio.name = "mode"; radio.value = value; radio.checked = state.mode === value; const copy = el("span", "mode-copy"); copy.append(el("strong", "", label), el("small", "", detail)); option.append(radio, copy); modes.append(option); }); launchCard.append(modes); if (state.mode === "live") launchCard.append(check("I acknowledge the paid model run", "liveAcknowledged", state.liveAcknowledged, `This run may incur model charges. Budget guarantee: ${boot.budget?.billing_guarantee === false ? "estimates only, not an invoice ceiling" : "not independently guaranteed"}.`)); launchCard.append(check("I authorize this workflow run", "runApproved", state.runApproved, "This submits a job now. The service reports actual status and evidence.")); const launchButton = button(state.submitting ? "Submitting…" : "Authorize and launch", "run", "button button-primary"); launchButton.disabled = state.submitting || !boot.fixture?.ready || !state.runApproved || (state.mode === "live" && !state.liveAcknowledged); launchCard.append(launchButton); main.append(launchCard); const jobsPanel = sectionCard("Recent requests", "Live status from the jobs endpoint."); renderJobs(jobsPanel, state.jobs.slice(0, 6)); main.append(jobsPanel); }
  async function loadRecordedReplay() { const requestId = state.runRequest = (state.runRequest || 0) + 1; state.run = null; render(); let result; try { result = await api("/api/evidence/docs%2Fevidence%2Ffeatured-run-replay.json"); } catch (error) { result = { error: error.message }; } if (state.runRequest !== requestId || state.route?.page !== "replay") return; state.run = result; render(); }
  const replay = { index: 0, timer: null, speed: 1 };
  function stopReplay() { if (replay.timer) clearTimeout(replay.timer); replay.timer = null; }
  function replayEvents(data) {
    const events = Array.isArray(data.events) ? data.events.slice() : [];
    if (data.receipts?.independent_verification) events.push({ name: "independent_verification", receipt: data.receipts.independent_verification });
    if (data.rollback) events.push({ name: "rollback_verification", receipt: data.rollback });
    return events;
  }
  function advanceReplay() {
    stopReplay();
    if (!["run", "replay"].includes(state.route?.page) || !state.run || document.hidden) return;
    const events = replayEvents(state.run);
    if (replay.index >= events.length - 1) return;
    const duration = Number(events[replay.index]?.duration_seconds);
    replay.timer = setTimeout(() => { replay.index++; advanceReplay(); render(); }, Math.max(500, Math.min(2200, Number.isFinite(duration) ? duration * 1000 : 1300)) / replay.speed);
  }
  function replayPanel(data) {
    const events = replayEvents(data);
    const panel = el("section", "replay-workspace");
    panel.setAttribute("aria-label", "Recorded execution replay");
    const head = el("div", "replay-topbar");
    const title = el("div", "");
    title.append(el("p", "eyebrow", "RECORDED EXECUTION / ZERO MODEL SPEND"), el("h2", "", "Follow the decision. Inspect the proof."));
    head.append(title, el("span", "replay-clock", "Original run " + Number(data.run?.duration || 0).toFixed(3) + "s"));
    panel.append(head, el("p", "panel-subtitle", "Real saved tool receipts. Playback compresses waiting; it is not live execution or measured span timing. Certificate signatures remain classical RSA."));
    if (!events.length) { panel.append(empty("No replay events available.", "Inspect the saved trace below instead.")); return panel; }
    replay.index = Math.max(0, Math.min(replay.index, events.length - 1));
    const controls = el("div", "replay-controls");
    controls.append(button(replay.timer ? "Pause replay" : "Play replay", "replay-play", "button button-primary"), button("Step", "replay-step", "button button-secondary"), button("Reset", "replay-reset", "button button-secondary"));
    const speed = button(replay.speed + "× presentation speed", "replay-speed", "button button-secondary");
    controls.append(speed, el("span", "muted", (replay.index + 1) + " / " + events.length + " recorded operations"));
    panel.append(controls);
    const grid = el("div", "replay-grid");
    const track = el("div", "replay-track");
    events.forEach((event, index) => {
      const failed = event.receipt?.ok === false || event.ok === false;
      const step = button("", "replay-select", "replay-step" + (index === replay.index ? " active" : index < replay.index ? " completed" : "") + (failed ? " failed" : ""));
      step.dataset.index = String(index);
      step.setAttribute("aria-current", index === replay.index ? "step" : "false");
      step.append(el("span", "replay-step-number", String(index + 1).padStart(2, "0")), el("strong", "", pretty(event.name || "Recorded event")), el("span", "", failed ? "FAILED / RECOVERABLE" : index <= replay.index ? "RECEIPT RECORDED" : "INSPECT STEP"));
      track.append(step);
    });
    const event = events[replay.index];
    const inspector = el("div", "replay-inspector");
    inspector.append(el("p", "eyebrow", "EVIDENCE INSPECTOR"), el("h3", "", pretty(event.name || "Event")));
    if (event.duration_seconds != null) inspector.append(row("Measured tool duration", Number(event.duration_seconds).toFixed(3) + "s"));
    if (event.receipt?.ok === false) inspector.append(notice("The action failed. The agent must inspect this result before retrying; a plausible final answer is not proof.", "error"));
    if (event.name === "restart_service" && replay.index > 0 && events[replay.index - 1]?.receipt?.ok === false) inspector.append(notice("Recovery: a bounded retry after the failed restart.", "success"));
    if (event.name === "rollback_verification" && event.receipt?.candidate_reverified) inspector.append(notice("Baseline restoration was tested. The approved candidate was then reapplied and independently reverified; this is not a claim that the final service remains at baseline.", "info"));
    inspector.append(el("pre", "json-block", JSON.stringify(event.receipt || event, null, 2)));
    grid.append(track, inspector); panel.append(grid);
    return panel;
  }
  function onboardingPanel() {
    const panel = el("section", "onboarding-steps");
    panel.append(el("p", "eyebrow", "START HERE / OPERATOR GUIDE"), el("h2", "", "Explore first. Authorize only when ready."));
    [["01", "Explore a recorded agent", "Inspect a genuine run, failure, recovery and receipts. No credentials or model spend needed."], ["02", "Choose an owned sandbox", "Select a seeded scenario. Fixture setup is a separate explicit approval, never a production target."], ["03", "Approve execution", "Offline smoke is not an LLM agent. Live mode needs configured credentials and separate paid-model consent."], ["04", "Verify and restore", "Inspect the independent verdict and negotiated group. Test baseline restoration, then reapply and independently reverify the approved candidate."]].forEach(([number, title, detail]) => {
      const step = el("article", "onboarding-step"); step.append(el("span", "", number), el("strong", "", title), el("p", "", detail)); panel.append(step);
    });
    panel.append(linkWithIcon("Explore recorded workflow →", "/app/replay"));
    panel.append(linkWithIcon("Configure an authorized run →", "/app/workflows"));
    return panel;
  }
  document.addEventListener?.("visibilitychange", () => { if (document.hidden) stopReplay(); });
  function renderRuns(main) { main.append(sectionTitle("WORKSPACE / RUNS", "Run ledger.", "Every row is sourced from the service. Open a run for actual tool events, receipts, and integrity checks.")); if (state.error) main.append(notice(state.error, "error")); const panel = sectionCard("All runs", `${(state.bootstrap?.runs || []).length} run records`); panel.append(runFilters()); const list = el("div", "run-list"); recentRuns(list, state.bootstrap?.runs || [], Infinity); panel.append(list); main.append(panel); }
  function appendObjectRows(target, object) { if (!object || typeof object !== "object" || !Object.keys(object).length) { target.append(el("p", "muted", "No data reported.")); return; } Object.entries(object).forEach(([key, value]) => target.append(row(pretty(key), typeof value === "object" && value !== null ? JSON.stringify(value) : value === null ? "null" : String(value)))); }
  function eventCard(event, index) { const card = el("article", "event-card"); const receipt = event.receipt && typeof event.receipt === "object" ? event.receipt : null; const ok = event.ok ?? receipt?.ok; const group = event.group || receipt?.observed_group; const head = el("div", "event-heading"); head.append(el("span", "event-index", String(index + 1).padStart(2, "0")), el("strong", "event-tool", event.tool || event.name || "Tool event"), statusPill(ok === false ? "failed" : ok === true ? "ok" : event.status || "recorded")); card.append(head); if (group) card.append(el("p", "event-group", `Observed group: ${group}`)); const error = event.error || receipt?.error; if (error) card.append(el("pre", "event-error", typeof error === "string" ? error : JSON.stringify(error, null, 2))); const data = { ...event }; ["error", "tool", "name", "group", "ok"].forEach(key => delete data[key]); if (Object.keys(data).length) { const details = document.createElement("details"); const summary = document.createElement("summary"); summary.textContent = "Event details"; details.append(summary, el("pre", "json-block", JSON.stringify(data, null, 2))); card.append(details); } return card; }
  function tracePanel(trace) { const spans = Array.isArray(trace.spans) ? trace.spans : []; const panel = sectionCard("Saved SDK trace", "Saved Neatlogs SDK readback · actual spans returned for this run."); panel.append(row("Trace ID", trace.id ?? "Not reported", true), row("Source", trace.source || "Saved Neatlogs SDK readback"), row("Completeness", trace.complete === true ? "Complete" : trace.complete === false ? "Incomplete" : "Not reported")); if (!spans.length) { panel.append(empty("No saved spans returned.", "The trace response contains no spans; none are inferred or synthesized.")); return panel; }
    const byId = new Map(); spans.forEach((span, index) => { const key = span.id == null ? `__span_${index}` : String(span.id); if (!byId.has(key)) byId.set(key, { span, key, children: [] }); }); const roots = []; byId.forEach(node => { const parentId = node.span.parent == null ? "" : String(node.span.parent); const parent = byId.get(parentId); if (parent && parent !== node) parent.children.push(node); else roots.push(node); });
    const tree = el("ul", "trace-tree"); const added = new Set(); const appendNode = (parent, node) => { if (added.has(node.key)) return; added.add(node.key); const item = el("li", "trace-node"); const line = el("div", "trace-line"); line.append(el("span", "trace-name", node.span.name || "Unnamed span"), statusPill(node.span.status ?? "status not reported")); const meta = el("span", "trace-meta", [node.span.type, node.span.id != null ? `id ${node.span.id}` : "", node.span.parent != null ? `parent ${node.span.parent}` : ""].filter(Boolean).join(" · ")); item.append(line, meta); parent.append(item); if (node.children.length) { const children = el("ul", "trace-children"); item.append(children); node.children.forEach(child => appendNode(children, child)); } }; roots.forEach(node => appendNode(tree, node)); byId.forEach(node => { if (!added.has(node.key)) appendNode(tree, node); }); panel.append(tree); return panel; }
  function renderRun(main) { main.append(link("← All runs", "/app/runs", "back-link")); const id = state.route.id || state.run?.run?.id || "Featured recorded run"; if (!state.run) { main.append(sectionTitle("RUN DETAIL", "Loading run record…", id)); return; } if (state.run.error) { main.append(sectionTitle("RUN DETAIL", "Run unavailable", id), notice(state.run.error, "error")); return; } const data = state.run; const run = data.run || {}; main.append(sectionTitle("RUN DETAIL", state.bootstrap?.scenarios?.find(item => item.id === run.scenario)?.name || pretty(run.scenario || "Migration run"), run.id || id)); const summary = el("div", "run-summary"); const status = el("div", "run-summary-status"); status.append(el("span", "verdict-label", "Independent verdict"), statusPill(run.status), el("span", `verify-mark ${run.verified ? "is-verified" : ""}`, run.verified ? "Independent verification passed" : "Not independently verified")); summary.append(status, row("Agent verdict", run.agent_status ?? data.agent?.status ?? "Not reported"), row("Mode", modeLabel(run.mode)), row("Created", fmt(run.created_at, "date")), row("Cost", fmt(run.cost, "money")), row("Input tokens", fmt(run.input_tokens)), row("Output tokens", fmt(run.output_tokens)), row("Duration", fmt(run.duration ?? (run.duration_seconds != null ? run.duration_seconds : null), "duration")), row("Trace ID", run.trace_id || "—", true), row("Trace coverage", run.trace_coverage ?? "—")); main.append(replayPanel(data), proofSummary(data), summary); const agent = sectionCard("Agent outcome", "The agent’s status is its own claim; the independent verdict above is authoritative."); if (data.agent?.status !== undefined) agent.append(row("Agent verdict", data.agent.status)); const agentDetails = { ...(data.agent || {}) }; delete agentDetails.status; delete agentDetails.final_response; appendObjectRows(agent, agentDetails); if (data.agent?.final_response) { const explanation = document.createElement("details"); const label = document.createElement("summary"); label.textContent = "Read the agent’s final claim"; explanation.append(label, el("pre", "json-block", data.agent.final_response)); agent.append(explanation); } main.append(agent); if (data.trace) main.append(tracePanel(data.trace)); const safety = sectionCard("Safety and integrity", "Independent checks and rollback details reported for this run."); const checks = el("div", "integrity-grid"); [["Artifact integrity", data.artifact_integrity], ["Independent verification", data.receipts?.independent_verification], ["Baseline", data.receipts?.baseline], ["Final receipt", data.receipts?.final], ["Contract", data.receipts?.contract], ["Rollback", data.rollback], ["Trace audit", data.trace_audit]].forEach(([label, object]) => { const card = el("article", "integrity-card"); card.append(el("h3", "", label)); appendObjectRows(card, object); checks.append(card); }); safety.append(checks); main.append(safety); const events = sectionCard("Tool events", `${Array.isArray(data.events) ? data.events.length : 0} sanitized events from this run.`); if (!data.events?.length) events.append(empty("No tool events reported.", "The service did not attach any sanitized events to this run.")); else { const list = el("div", "event-list"); data.events.forEach((event, index) => list.append(eventCard(event, index))); events.append(list); } main.append(events); }
  function renderIntegrations(main) { main.append(sectionTitle("WORKSPACE / INTEGRATIONS", "Evidence follows the system that produced it.", "Integration status reflects the connected service’s report. Local traces and shared artifacts have different verification boundaries.")); const integrations = state.bootstrap?.integrations || []; if (!integrations.length) { main.append(state.error ? notice(state.error, "error") : empty("No integrations reported.", "Integration records will appear when the service returns them.")); return; } const grid = el("div", "integration-grid"); integrations.forEach(item => { const card = el("article", "integration-card"); const head = el("div", "integration-heading"); head.append(el("div", "integration-mark", item.name?.slice(0, 1) || "I")); const title = el("div", "integration-title-wrap"); title.append(el("h2", "", item.name || "Integration"), statusPill(({ neatlogs: item.status?.includes("dashboard_verified") ? "SDK + dashboard verified" : "SDK verified · dashboard pending", entire: "Local proof verified", cfo: "Plan reviewed" })[item.id] || item.status)); head.append(title); card.append(head, el("p", "integration-headline", item.headline || ""), el("p", "integration-detail", item.detail || "")); if (Array.isArray(item.evidence_paths) && item.evidence_paths.length) { const links = el("div", "evidence-paths"); item.evidence_paths.forEach(path => { const actionButton = button(String(path), "evidence-open", "path-button"); actionButton.dataset.path = String(path); links.append(actionButton); }); card.append(links); } grid.append(card); }); main.append(grid); const dashboardVerified = (state.bootstrap?.integrations || []).some(item => item.id === "neatlogs" && item.status?.includes("dashboard_verified")); const proofNote = sectionCard("Neatlogs organizer proof", "Authenticated dashboard evidence is distinct from SDK readback."); proofNote.append(row("Organizer format", "Neatlogs dashboard link or screenshot"), row("Submission evidence", dashboardVerified ? "Authenticated dashboard trace captured" : "Pending human login"), row("SDK readback", "Inspect saved SDK spans per run and the separately captured dashboard evidence.")); main.append(proofNote); const note = sectionCard("How to read these connections", "Integration labels do not imply a shared trust boundary."); note.append(row("Neatlogs SDK", "Trace evidence is trace-level saved readback, not a dashboard screenshot."), row("Entire", "A local checkpoint can be inspected; hosted history is unverified."), row("CFO", "A reviewed, shared artifact is evidence of that artifact—not an API integration.")); main.append(note); if (state.evidencePath) { const viewer = sectionCard("Evidence file", state.evidencePath); viewer.append(button("Close viewer", "evidence-close", "button button-quiet")); if (state.evidence === null) viewer.append(notice("Loading allowlisted evidence…")); else if (state.evidence.error) viewer.append(notice(state.evidence.error, "error")); else viewer.append(el("pre", "json-block evidence-viewer", typeof state.evidence === "string" ? state.evidence : JSON.stringify(state.evidence, null, 2))); main.append(viewer); } }
  function renderEvidence(main) { const study = state.bootstrap?.summary?.latest_study; main.append(sectionTitle("WORKSPACE / EVIDENCE", "Small study. Visible limits.", "Evaluation outcomes come from the latest study returned by the service. Counts are not a guarantee of future performance.")); if (!study) { main.append(state.error ? notice(state.error, "error") : empty("No study summary available.", "The service did not return a latest study.")); return; } main.append(el("div", "study-id", `STUDY · ${study.id || "UNSPECIFIED"}`)); const summaries = study.summaries || {}; const names = ["V1", "V2", "Fixed script"]; const compare = el("section", "study-comparison"); const heading = el("div", "comparison-heading"); heading.append(el("span", "", "Approach"), el("span", "", "Correct outcomes / attempts"), el("span", "", "False readiness"), el("span", "", "Estimated cost")); compare.append(heading); names.forEach(name => { const item = summaries[name]; const line = el("div", "comparison-row"); line.append(el("strong", "", name), el("span", "comparison-result", item ? `${fmt(item.correct_outcomes)} / ${fmt(item.attempts)}` : "Not reported"), el("span", "", item ? fmt(item.false_readiness) : "—"), el("span", "", item ? fmt(item.estimated_cost, "money") : "—")); compare.append(line); }); main.append(compare); main.append(notice("Sample sizes are small. A perfect result in this study does not establish general reliability; offline smoke runs are not LLM evidence.", "caution")); const panel = sectionCard("Study evidence", "Counts and costs are copied from the returned study summary."); if (!Object.keys(summaries).length) panel.append(empty("Study has no approach summaries.", "No outcomes are available to compare.")); else { const cards = el("div", "study-cards"); names.forEach(name => { const item = summaries[name]; const card = el("article", "study-card"); card.append(el("p", "eyebrow", name), el("strong", "study-score", item ? `${fmt(item.correct_outcomes)} / ${fmt(item.attempts)}` : "—"), el("span", "muted", "correct outcomes")); if (item) card.append(row("False readiness", fmt(item.false_readiness)), row("Estimated cost", fmt(item.estimated_cost, "money"))); cards.append(card); }); panel.append(cards); } main.append(panel); const paths = [...new Set((state.bootstrap?.integrations || []).flatMap(item => Array.isArray(item.evidence_paths) ? item.evidence_paths : []))]; const evidencePanel = sectionCard("Available evidence paths", "Only paths explicitly supplied by the server are requested."); if (!paths.length) evidencePanel.append(el("p", "muted", "No allowlisted evidence paths were returned.")); else { const list = el("div", "evidence-path-list"); paths.forEach(path => { const actionButton = button(String(path), "evidence-open", "path-button"); actionButton.dataset.path = String(path); list.append(actionButton); }); evidencePanel.append(list); } main.append(evidencePanel); if (state.evidencePath) { const viewer = sectionCard("Evidence file", state.evidencePath); viewer.append(button("Close viewer", "evidence-close", "button button-quiet")); if (state.evidence === null) viewer.append(notice("Loading allowlisted evidence…")); else if (state.evidence.error) viewer.append(notice(state.evidence.error, "error")); else viewer.append(el("pre", "json-block evidence-viewer", typeof state.evidence === "string" ? state.evidence : JSON.stringify(state.evidence, null, 2))); main.append(viewer); } }
  function renderBusiness(main) { const business = state.bootstrap?.business || {}; const budget = state.bootstrap?.budget || {}; main.append(sectionTitle("WORKSPACE / BUSINESS CASE", "A forecast is a hypothesis.", "Keep projected value separate from measured run evidence. Share the reviewed artifact when it is available.")); const hero = el("section", "business-hero"); hero.append(el("p", "eyebrow", "COST MODEL"), el("h2", "", "Estimate first. Verify each migration."), el("p", "", "Per-migration inference estimates are planning inputs. Actual spending and verification outcomes should be read from completed run records."), el("strong", "business-amount", fmt(business.estimated_inference_per_verified_migration, "money")), el("span", "business-caption", "estimated inference per verified non-no-op migration")); main.append(hero); const panels = el("div", "content-grid"); const budgetPanel = sectionCard("Authorized budget", "Values reported by the service."); budgetPanel.append(row("Authorized total", fmt(budget.authorized_total_usd, "money")), row("Committed estimate", fmt(budget.committed_estimate_usd, "money")), row("Billing guarantee", budget.billing_guarantee === false ? "No · estimates, not invoices" : budget.billing_guarantee === true ? "Reported by service" : "Not reported")); panels.append(budgetPanel); const sharePanel = sectionCard("Reviewed business plan", "A shared artifact is not an API integration."); sharePanel.append(el("p", "panel-subtitle", business.review_available ? "A reviewed shared plan is available." : "The service has not confirmed that a reviewed plan is available.")); const shareUrl = business.shared_plan_url || "https://cfo.ai/s/aMAZiEnSXtphYplP"; if (business.review_available || business.shared_plan_url) { const anchor = link("", shareUrl, "button button-primary share-link"); anchor.target = "_blank"; anchor.rel = "noopener noreferrer"; anchor.append(el("span", "", "Open shared plan"), icon("external", "icon")); sharePanel.append(anchor); } else sharePanel.append(el("p", "muted", "No share link reported.")); panels.append(sharePanel); main.append(panels); main.append(notice(business.forecast_is_hypothesis === false ? "The service does not label this forecast as a hypothesis." : "Forecasts are hypotheses, not measured savings or guarantees.", "caution")); main.append(linkWithIcon("Inspect actual runs", "/app/runs")); }
  function renderLanding() {
    root.replaceChildren();
    const header = el("header", "landing-header");
    const brand = link("", "/", "brand landing-brand");
    const symbol = el("span", "brand-symbol");
    symbol.append(icon("mark", "icon brand-icon"));
    brand.append(symbol, el("span", "brand-name", "invaris"));
    const navigation = el("nav", "landing-nav");
    navigation.setAttribute("aria-label", "Main navigation");
    [["The method", "#method"], ["Measured evidence", "#evidence"], ["The stack", "#integrations"]]
      .forEach(([label, href]) => navigation.append(link(label, href)));
    header.append(brand, navigation, linkWithIcon("Open console", "/app"));
    root.append(header);

    const page = el("main", "landing-main");
    const hero = el("section", "landing-hero");
    const intro = el("div", "hero-intro");
    const tag = el("div", "hero-tag");
    tag.append(el("span", "status-dot"), el("span", "", "VERIFIED CRYPTOGRAPHIC CHANGE"));
    const title = el("h1", "hero-title");
    title.append(el("span", "", "The config says yes."), el("span", "hero-question", "Does the connection?"));
    const actions = el("div", "hero-actions");
    actions.append(linkWithIcon("Open agent console", "/app"), link("Explore the method ↘", "#method", "text-link secondary-link"));
    const chips = el("div", "protocol-chips");
    ["TLS 1.3", "X25519 + ML-KEM", "INDEPENDENT VERIFICATION"].forEach(text => chips.append(el("span", "", text)));
    intro.append(tag, title, el("p", "hero-copy", "A migration can look complete and still be wrong. Invaris investigates what runs, makes a bounded change, and checks the connection that actually happened."),
      actions, chips, el("p", "hero-boundary", "Owned sandbox. Explicit approval. Classical certificate signatures."));
    hero.append(intro, invariantScene());
    page.append(hero);

    const study = state.bootstrap?.summary?.latest_study;
    const before = study?.summaries?.V1;
    const after = study?.summaries?.V2;
    const ribbon = el("section", "evidence-ribbon");
    ribbon.id = "evidence";
    const context = el("div", "ribbon-context");
    context.append(el("p", "eyebrow", "MEASURED, NOT PROMISED"), el("strong", "", "One study. Visible improvement."),
      el("small", "", "7 scenarios · 1 repetition per arm"));
    const outcome = el("div", "ribbon-metric");
    outcome.append(el("span", "", "Correct classifications / V1 → V2"),
      el("strong", "", before && after ? before.correct_outcomes + "/" + before.attempts + " → " + after.correct_outcomes + "/" + after.attempts : "— → —"));
    const readiness = el("div", "ribbon-metric");
    readiness.append(el("span", "", "False-readiness claims / V1 → V2"),
      el("strong", "", before && after ? before.false_readiness + " → " + after.false_readiness : "— → —"));
    ribbon.append(context, outcome, readiness, linkWithIcon("Inspect the study", "/app/evidence"));
    page.append(ribbon, el("p", "study-boundary", "Small-sample fixture evidence, not a reliability guarantee. The fixture-specific fixed script also scored 7/7, faster and without inference."));

    const method = el("section", "method-section");
    method.id = "method";
    const methodHeading = el("div", "section-intro");
    methodHeading.append(el("p", "eyebrow", "A CLOSED LOOP, NOT A CONFIDENT ANSWER"),
      el("h2", "landing-section-title", "The agent acts.\nThe evidence decides."),
      el("p", "section-description", "A model proposes the next step. Guarded tools execute it. A separate verifier decides whether the result meets the contract."));
    const loop = el("div", "execution-map");
    const steps = [["Inspect", "Find disk/runtime drift", "layers"], ["Act", "Change only what is approved", "workflow"],
      ["Verify", "Probe a fresh connection", "pulse"], ["Recover", "Retry, rollback, or stop", "shield"]];
    steps.forEach(([name, detail, glyph], index) => {
      const step = el("article", "execution-step");
      step.append(el("span", "step-no", String(index + 1).padStart(2, "0")), icon(glyph), el("h3", "", name), el("p", "", detail));
      loop.append(step);
    });
    const recovery = el("div", "recovery-line");
    recovery.append(el("span", "", "↳"), el("span", "", "A failed action is a decision point—not a hidden error."), el("span", "mono", "SCHEMATIC / NOT A RUN"));
    method.append(methodHeading, loop, recovery);
    page.append(method);

    const capabilities = el("section", "capability-section");
    const capabilityHeading = el("div", "section-intro");
    capabilityHeading.append(el("p", "eyebrow", "BUILT FOR THE MOMENT THINGS DISAGREE"), el("h2", "landing-section-title", "Trust is an outcome.\nNot an interface treatment."));
    capabilities.append(capabilityHeading);
    const capabilitiesGrid = el("div", "capability-grid");
    [["01", "Runtime over configuration", "A fresh handshake can expose a process that never loaded the configuration on disk.", "DISK ≠ RUNTIME", "layers"],
      ["02", "Recovery with a record", "Failed tool calls remain visible. The next action responds to the result, not a polished success story.", "FAILURE → RECOVERY", "workflow"],
      ["03", "Readiness has a gate", "The model’s claim and the independent verdict are separate. Missing evidence cannot become a green light.", "NO PROOF → NO READINESS", "shield"],
      ["04", "Inspect the whole path", "Read tool receipts, actual SDK spans, artifact hashes, and independently checked rollback results.", "REVIEWABLE EVIDENCE", "evidence"]]
      .forEach(([number, name, description, caption, glyph]) => {
        const card = el("article", "capability-card");
        const head = el("div", "capability-head");
        head.append(el("span", "proof-index", number), icon(glyph));
        card.append(head, el("h3", "", name), el("p", "", description), el("span", "capability-caption", caption));
        capabilitiesGrid.append(card);
      });
    capabilities.append(capabilitiesGrid);
    page.append(capabilities);

    const integrations = el("section", "landing-integrations");
    integrations.id = "integrations";
    const integrationHeading = el("div", "section-intro");
    integrationHeading.append(el("p", "eyebrow", "THE WORK BEHIND THE WORK"), el("h2", "landing-section-title", "Three tools.\nThree different kinds of proof."));
    const integrationGrid = el("div", "partner-grid");
    [["Neatlogs", "RUNTIME OBSERVABILITY", "Model calls, tool results, failure and recovery—with saved application trace readback.", "Trace evidence"],
      ["Entire", "DEVELOPMENT CONTEXT", "Genuine local checkpoints and Graph retrieval. Hosted and automatic capture are not claimed.", "Local evidence"],
      ["cfo.ai", "BUSINESS PLANNING", "The actual shared plan, reviewed alongside measured inference estimates. Not a fabricated API connection.", "Reviewed artifact"]]
      .forEach(([name, role, detail, boundary]) => {
        const card = el("article", "partner-card");
        card.append(el("span", "partner-role", role), el("h3", "", name), el("p", "", detail), el("span", "partner-boundary", boundary));
        integrationGrid.append(card);
      });
    integrations.append(integrationHeading, integrationGrid, linkWithIcon("Review integration proof", "/app/integrations"));
    page.append(integrations);

    const closing = el("section", "landing-cta");
    const closingCopy = el("div", "");
    closingCopy.append(el("p", "eyebrow", "OPEN THE CONTROL PLANE"), el("h2", "", "Make the change.\nKeep the proof."),
      el("p", "", "Explore the scenarios. Authorize the work. Inspect what actually happened."));
    closing.append(closingCopy, linkWithIcon("Explore Invaris", "/app"));
    page.append(closing);
    root.append(page);
    const footer = el("footer", "landing-footer");
    footer.append(el("span", "", "INVARIS / VERIFIED CRYPTOGRAPHIC CHANGE"), el("span", "", "AUTHORIZED SANDBOX · NOT A PRODUCTION DEPLOYMENT"), link("Open console ↗", "/app"));
    root.append(footer);
  }
  function render() { state.route = pathRoute(); document.body.dataset.screen = state.route.page; if (state.route.page === "landing") { renderLanding(); window.InvarisVisuals?.mount(root); return; } const main = shell(state.route.page); if (state.loading && !state.bootstrap) { main.append(notice("Loading live workspace data…")); return; } switch (state.route.page) { case "overview": renderOverview(main); break; case "workflows": renderWorkflows(main); break; case "runs": renderRuns(main); break; case "run": case "replay": renderRun(main); break; case "integrations": renderIntegrations(main); break; case "evidence": renderEvidence(main); break; case "business": renderBusiness(main); break; default: main.append(sectionTitle("NOT FOUND", "This page does not exist.", "Use the console navigation to continue."), link("Go to overview", "/app", "button button-primary")); } window.InvarisVisuals?.mount(root); }
  async function openEvidence(path) { const allowed = (state.bootstrap?.integrations || []).some(item => (item.evidence_paths || []).includes(path)); if (!allowed || !path || path.includes("..")) { state.evidencePath = path; state.evidence = { error: "This path was not allowlisted by the service." }; render(); return; } state.evidencePath = path; state.evidence = null; render(); try { state.evidence = await api(`/api/evidence/${encodeURIComponent(path)}`); } catch (error) { state.evidence = { error: error.message }; } render(); }
  root.addEventListener("click", event => { const target = event.target.closest("a,button"); if (!target) return; if (target.matches("a")) { const href = target.getAttribute("href"); if (href?.startsWith("/app") || href === "/") { event.preventDefault(); go(href); } return; } const action = target.dataset.action; if (action?.startsWith("replay-")) { if (action === "replay-play") { if (replay.timer) stopReplay(); else { if (replay.index >= replayEvents(state.run).length - 1) replay.index = 0; advanceReplay(); } } else { stopReplay(); if (action === "replay-step") replay.index = Math.min(replay.index + 1, replayEvents(state.run).length - 1); if (action === "replay-reset") replay.index = 0; if (action === "replay-select") replay.index = Number(target.dataset.index) || 0; if (action === "replay-speed") replay.speed = replay.speed === 1 ? 2 : replay.speed === 2 ? 4 : 1; } render(); return; } if (action === "toggle-motion") { window.InvarisVisuals?.toggleMotion(); return; } if (action === "command-palette") { commandPalette(); return; } if (target.dataset.scenario) { state.selectedScenario = target.dataset.scenario; state.runApproved = false; state.liveAcknowledged = false; render(); } else if (action === "setup" || action === "run") launch(action); else if (action === "evidence-open") openEvidence(target.dataset.path || ""); else if (action === "evidence-close") { state.evidencePath = ""; state.evidence = null; render(); } });
  root.addEventListener("change", event => { const input = event.target; const key = input.dataset.state; if (["runOutcome", "runMode"].includes(input.dataset.filter)) { state[input.dataset.filter] = input.value; updateSearchResults(); return; } if (["setupApproved", "runApproved", "liveAcknowledged"].includes(key)) { state[key] = input.checked; render(); root.querySelector(`input[data-state="${key}"]`)?.focus(); } else if (input.name === "mode") { state.mode = input.value; state.runApproved = false; state.liveAcknowledged = false; render(); root.querySelector(`input[name="mode"][value="${state.mode}"]`)?.focus(); } });
  window.addEventListener("keydown", event => { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); commandPalette(); } });
  window.addEventListener("popstate", () => { stopReplay(); replay.index = 0; state.runRequest = (state.runRequest || 0) + 1; state.route = pathRoute(); state.run = null; render(); if (state.route.page === "run") loadRun(state.route.id); if (state.route.page === "replay") loadRecordedReplay(); });
  state.route = pathRoute(); if (state.route.page !== "landing") { state.loading = true; render(); refreshData().then(() => { if (state.route.page === "run") loadRun(state.route.id); if (state.route.page === "replay") loadRecordedReplay(); startPolling(); }); } else { render(); refreshData(); }
})();
