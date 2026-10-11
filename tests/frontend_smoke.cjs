const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const appSource = fs.readFileSync(path.join(__dirname, "../src/invaris/web/app.js"), "utf8");
const bootstrap = {
  session_token: "test-session",
  product: { name: "Invaris", tagline: "Verified cryptographic change." },
  scenarios: [
    { id: "already_compliant", name: "Already compliant", description: "A bounded test scenario." },
    { id: "one_shot_action_failure", name: "Action failure", description: "A seeded failure." },
  ],
  summary: { latest_study: null },
  integrations: [],
  runs: [
    { id: "11111111-1111-4111-8111-111111111111", scenario: "already_compliant", version: "V2",
      status: "VERIFIED", mode: "live-model", verified: true },
    { id: "22222222-2222-4222-8222-222222222222", scenario: "one_shot_action_failure", version: "V2",
      status: "BLOCKED", mode: "offline-smoke-not-LLM", verified: false },
  ],
  jobs: [],
  business: {},
  budget: {},
  fixture: { project: "invaris-console", ready: false },
};

class FakeElement {
  constructor(tagName) {
    this.tagName = tagName;
    this.children = [];
    this.dataset = {};
    this.attributes = {};
    this.listeners = {};
    this.disabled = false;
    this.value = "";
    this.checked = false;
    this.className = "";
    this.hidden = false;
    this.focused = false;
  }

  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  focus() { this.focused = true; }
  matches(selector) {
    if (/^\.[\w-]+$/.test(selector)) return this.className.split(/\s+/).includes(selector.slice(1));
    const tag = selector.match(/^[a-z]+/);
    assert.ok(tag && /^(?:[a-z]+)(?:\[[\w-]+="[^"]*"\])*$/.test(selector), "Unsupported selector: " + selector);
    if (this.tagName !== tag[0]) return false;
    return [...selector.matchAll(/\[([\w-]+)="([^"]*)"\]/g)].every(([, name, value]) => {
      const actual = name.startsWith("data-")
        ? this.dataset[name.slice(5).replace(/-([a-z])/g, (_match, letter) => letter.toUpperCase())]
        : this[name] ?? this.attributes[name];
      return String(actual) === value;
    });
  }
  querySelectorAll(selector) { return allElements(this).slice(1).filter(node => node.matches(selector)); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  get textContent() { return this.children.map(child => typeof child === "string" ? child : child.textContent).join(""); }
  set textContent(value) { this.children = [String(value)]; }
}

function allElements(node) {
  return [node, ...node.children.flatMap(child => child instanceof FakeElement ? allElements(child) : [])];
}

function change(root, selector, value) {
  const input = root.querySelector(selector);
  assert.ok(input, "Missing change target: " + selector);
  if (input.type === "checkbox") input.checked = value;
  else input.value = value;
  root.listeners.change({ target: input });
}

function search(root, value) {
  const input = root.querySelector('input[type="search"]');
  assert.ok(input, "Missing search input");
  input.value = value;
  input.listeners.input({ target: input });
}

function assertReadOnlyRequests(requests) {
  for (const url of ["/api/bootstrap", "/api/jobs"]) {
    assert.ok(requests.some(request => request.url === url), "Missing GET " + url);
  }
  assert.ok(requests.every(request => request.method === "GET"), "Page interactions must not submit jobs");
  assert.ok(requests.every(request => ["/api/bootstrap", "/api/jobs"].includes(request.url)), "Unexpected endpoint");
}

async function renderRoute(route) {
  const root = new FakeElement("div");
  const body = new FakeElement("body");
  const requests = [];
  const document = {
    body,
    createElement: tag => new FakeElement(tag),
    createElementNS: (_namespace, tag) => new FakeElement(tag),
    getElementById: id => id === "app" ? root : allElements(root).find(node => node.id === id) || null,
  };
  const window = {
    InvarisVisuals: { mount() {}, transition(callback) { callback(); } },
    addEventListener() {},
    scrollTo() {},
  };
  const context = {
    document,
    window,
    location: { pathname: route },
    history: { pushState() {} },
    fetch: async (url, options = {}) => {
      requests.push({ url, method: options.method || "GET" });
      const payload = url === "/api/bootstrap" ? bootstrap : { jobs: [] };
      return {
        ok: true,
        status: 200,
        headers: { get: name => name.toLowerCase() === "content-type" ? "application/json" : null },
        json: async () => payload,
        text: async () => JSON.stringify(payload),
      };
    },
    Intl,
    Date,
    URL,
    encodeURIComponent,
    decodeURI,
    setTimeout,
    clearTimeout,
    console,
  };
  vm.runInNewContext(appSource, context, { filename: "app.js" });
  await new Promise(resolve => setImmediate(resolve));
  await new Promise(resolve => setImmediate(resolve));
  return { root, body, requests };
}

async function main() {
  const workflows = await renderRoute("/app/workflows");
  assert.equal(workflows.body.dataset.screen, "workflows");
  assert.match(workflows.root.textContent, /Choose a bounded workflow/);
  assert.match(workflows.root.textContent, /Needs setup/);
  const actionButtons = allElements(workflows.root).filter(node => node.tagName === "button" && node.dataset.action);
  assert.equal(actionButtons.find(node => node.dataset.action === "setup").disabled, true);
  assert.equal(actionButtons.find(node => node.dataset.action === "run").disabled, true);
  assertReadOnlyRequests(workflows.requests);

  const scenarioCards = workflows.root.querySelectorAll(".scenario-card");
  assert.equal(scenarioCards.length, 2);
  search(workflows.root, "ALREADY COMPLIANT");
  assert.deepEqual(scenarioCards.map(card => card.hidden), [false, true]);
  search(workflows.root, "no matching scenario");
  assert.ok(scenarioCards.every(card => card.hidden));
  search(workflows.root, "");
  assert.ok(scenarioCards.every(card => !card.hidden));

  change(workflows.root, 'input[data-state="runApproved"]', true);
  assert.equal(workflows.root.querySelector('input[data-state="runApproved"]').focused, true);
  change(workflows.root, 'input[name="mode"][value="live"]', "live");
  const paidConsent = workflows.root.querySelector('input[data-state="liveAcknowledged"]');
  const runConsent = workflows.root.querySelector('input[data-state="runApproved"]');
  assert.ok(paidConsent, "Paid mode must render a separate spending approval");
  assert.notEqual(paidConsent, runConsent);
  assert.equal(paidConsent.type, "checkbox");
  assert.equal(paidConsent.checked, false);
  assert.equal(runConsent.checked, false);
  assert.equal(workflows.root.querySelector('input[name="mode"][value="live"]').focused, true);
  assert.equal(workflows.root.querySelector('button[data-action="run"]').disabled, true);
  assertReadOnlyRequests(workflows.requests);

  const runs = await renderRoute("/app/runs");
  const list = runs.root.querySelector(".run-list");
  assert.ok(list);
  assert.equal(list.querySelectorAll(".run-row").length, 2);
  change(runs.root, 'select[data-filter="runOutcome"]', "BLOCKED");
  assert.equal(list.querySelectorAll(".run-row").length, 1);
  assert.match(list.textContent, /one_shot_action_failure/);
  assert.doesNotMatch(list.textContent, /already_compliant/);
  change(runs.root, 'select[data-filter="runMode"]', "live-model");
  assert.equal(list.querySelectorAll(".run-row").length, 0);
  assert.match(list.textContent, /No runs match this search/);
  change(runs.root, 'select[data-filter="runOutcome"]', "all");
  assert.equal(list.querySelectorAll(".run-row").length, 1);
  assert.match(list.textContent, /already_compliant/);
  change(runs.root, 'select[data-filter="runMode"]', "all");
  search(runs.root, "ONE_SHOT_ACTION_FAILURE");
  assert.equal(list.querySelectorAll(".run-row").length, 1);
  assert.match(list.textContent, /one_shot_action_failure/);
  assert.doesNotMatch(list.textContent, /already_compliant/);
  search(runs.root, "no matching run");
  assert.equal(list.querySelectorAll(".run-row").length, 0);
  assert.match(list.textContent, /No runs match this search/);
  search(runs.root, "");
  assert.equal(list.querySelectorAll(".run-row").length, 2);
  assertReadOnlyRequests(runs.requests);

  for (const route of ["/app", "/app/runs", "/app/integrations", "/app/evidence", "/app/business"]) {
    const page = await renderRoute(route);
    assert.ok(page.root.textContent.length > 0, `${route} should render content`);
    assertReadOnlyRequests(page.requests);
  }
  console.log("Frontend smoke tests passed.");
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
