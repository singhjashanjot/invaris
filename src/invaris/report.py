"""Responsive, self-contained HTML evaluation and comparison reports."""

from __future__ import annotations

import html
from typing import Any, Mapping, Sequence

_METRICS = (
    ("Attempts", "attempts"),
    ("Correct outcomes", "correct_outcomes"),
    ("Evaluated runs", "outcome_denominator"),
    ("Verified migrations", "verified_migrations"),
    ("Migration-feasible runs", "migration_feasible_runs"),
    ("False readiness", "false_readiness"),
    ("Invalid runs", "infrastructure_invalid_runs"),
    ("Correct no-ops", "correct_noops"),
    ("Already-compliant runs", "already_compliant_runs"),
    ("Correct blockers", "correct_blockers"),
    ("Infeasible policy runs", "infeasible_policy_runs"),
    ("Successful recoveries", "successful_recoveries"),
    ("Recovery attempts", "recovery_attempts"),
    ("Estimated cost", "estimated_cost"),
    ("Billed cost", "billed_cost"),
    ("Cost / verified migration", "cost_per_verified_migration"),
    ("Wall time (s)", "wall_time_seconds"),
    ("Input tokens", "input_tokens"),
    ("Output tokens", "output_tokens"),
    ("Cache tokens", "cache_tokens"),
    ("Model calls", "model_calls"),
    ("Tool calls", "tool_calls"),
)


def _e(value: Any) -> str:
    return html.escape("Not reported" if value is None else str(value), quote=True)


def _document(title: str, mode: str, content: str) -> str:
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark"><title>""" + _e(title) + """</title>
<style>
:root{color-scheme:dark;--bg:#0b1220;--panel:#111d2e;--panel2:#16243a;--line:#2b3c55;--text:#eef4fb;--muted:#b5c3d4;--accent:#70d6c4;--warn:#ffd27a;--bad:#ff9a9a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1240px;margin:auto;padding:clamp(1rem,4vw,3rem)}h1,h2,h3{line-height:1.2;margin:0}h1{font-size:clamp(1.8rem,4vw,2.7rem);letter-spacing:-.025em}h2{font-size:1.2rem;margin:2rem 0 1rem}p{color:var(--muted)}.top{display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;flex-wrap:wrap;margin-bottom:1.4rem}
.mode{border:1px solid var(--line);background:var(--panel);border-radius:999px;padding:.35rem .75rem;color:var(--accent);font-size:.88rem;font-weight:650}.sub{margin:.55rem 0 0;color:var(--muted)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,190px),1fr));gap:.8rem}.card,.panel{background:var(--panel);border:1px solid var(--line);border-radius:14px}.card{padding:1rem;min-height:96px}.label{display:block;color:var(--muted);font-size:.83rem;margin-bottom:.45rem}.value{font-size:1.35rem;font-weight:720;overflow-wrap:anywhere;font-variant-numeric:tabular-nums}
.table-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:var(--panel)}table{border-collapse:collapse;width:100%;min-width:680px}th,td{padding:.75rem .85rem;text-align:left;border-bottom:1px solid var(--line);vertical-align:top;overflow-wrap:anywhere}th{color:#d7e4f2;font-size:.85rem;background:var(--panel2)}tr:last-child td{border-bottom:0}.good{color:var(--accent);font-weight:650}.bad{color:var(--bad);font-weight:650}.unknown{color:var(--warn);font-weight:650}
.compare{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,330px),1fr));gap:1rem}.version{padding:1rem}.version h3{margin-bottom:1rem;font-size:1.08rem}.compact{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:.5rem 1rem;margin:0}.compact dt{color:var(--muted)}.compact dd{margin:0;text-align:right;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}.note{color:var(--muted);font-size:.9rem;margin-top:1rem}
@media(max-width:520px){main{padding:1rem}.card{min-height:80px}.value{font-size:1.15rem}th,td{padding:.6rem}}
</style></head><body><main><header class="top"><div><h1>""" + _e(title) + """</h1><p class="sub">Invaris Migration Engineer &middot; evaluation evidence</p></div><span class="mode">Run mode: """ + _e(mode) + """</span></header>""" + content + """</main></body></html>"""


def _cards(summary: Mapping[str, Any]) -> str:
    cards = []
    for label, key in _METRICS:
        if key in summary:
            cards.append('<article class="card"><span class="label">' + _e(label) + '</span><div class="value">' + _e(summary.get(key)) + '</div></article>')
    return '<div class="cards">' + "".join(cards) + "</div>"


def _scenario_table(rows: Sequence[Mapping[str, Any]], columns: Sequence[tuple[str, str]]) -> str:
    head = "".join("<th scope=\"col\">" + _e(label) + "</th>" for label, _ in columns)
    body = []
    for row in rows:
        cells = []
        for _, key in columns:
            value = row.get(key)
            if key == "outcome_correct":
                rendered = "Pass" if value is True else "Fail" if value is False else "Unscored"
                css = "good" if value is True else "bad" if value is False else "unknown"
                cells.append('<td class="' + css + '">' + rendered + "</td>")
            else:
                cells.append("<td>" + _e(value) + "</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return '<div class="table-wrap"><table><thead><tr>' + head + "</tr></thead><tbody>" + "".join(body) + "</tbody></table></div>"


def render_report(
    summary: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]] | None = None,
    title: str = "Invaris Evaluation Report",
    mode: str = "offline",
) -> str:
    """Render one evaluation summary and its run verdicts as self-contained HTML."""
    details = list(rows if rows is not None else summary.get("rows", []))
    content = "<h2>Evaluation metrics</h2>" + _cards(summary)
    content += "<h2>Scenario verdicts</h2>"
    columns = (("Scenario", "scenario_id"), ("Version", "version"), ("Agent status", "status"), ("Readiness claim", "claims_readiness"),
               ("Evaluator status", "evaluator_status"), ("Verified", "verified"), ("Verdict", "outcome_correct"))
    content += _scenario_table(details, columns) if details else '<p class="note">No scenario runs were supplied.</p>'
    content += '<p class="note">Outcome scoring uses the independent evaluator fields; agent status text alone does not establish a pass.</p>'
    return _document(title, mode, content)


def render_comparison_report(comparison: Mapping[str, Any]) -> str:
    """Render side-by-side V1/V2/fixed-script metrics and scenario outcomes."""
    mode = str(comparison.get("mode", "offline"))
    summaries = comparison.get("summaries", {})
    labels = [str(label) for label in comparison.get("labels", summaries.keys())]
    versions = []
    for label in labels:
        summary = summaries.get(label, {})
        metric_rows = []
        for metric, key in _METRICS:
            if key in summary:
                metric_rows.append("<dt>" + _e(metric) + "</dt><dd>" + _e(summary.get(key)) + "</dd>")
        versions.append('<section class="panel version"><h3>' + _e(label) + '</h3><dl class="compact">' + "".join(metric_rows) + "</dl></section>")
    content = "<h2>Version comparison</h2><div class=\"compare\">" + "".join(versions) + "</div>"
    content += "<h2>Scenario verdicts</h2>"
    scenario_rows = []
    for label in labels:
        summary = summaries.get(label, {})
        for row in summary.get("rows", []):
            scenario_rows.append({"scenario_id": row.get("scenario_id"), "version": label,
                                  "status": row.get("status"), "evaluator_status": row.get("evaluator_status"),
                                  "claims_readiness": row.get("claims_readiness"),
                                  "verified": row.get("verified"), "outcome_correct": row.get("outcome_correct")})
    columns = (("Scenario", "scenario_id"), ("Run set", "version"), ("Agent status", "status"), ("Readiness claim", "claims_readiness"),
               ("Evaluator status", "evaluator_status"), ("Verified", "verified"), ("Verdict", "outcome_correct"))
    content += _scenario_table(scenario_rows, columns) if scenario_rows else '<p class="note">No scenario runs were supplied.</p>'
    mismatches = comparison.get("matched_control_mismatches")
    content += '<p class="note">Matched control mismatches: ' + _e(mismatches) + '. Scenario rows include every supplied attempt; no outcomes are inferred from labels alone.</p>'
    content += '<p class="note">Unmatched attempts: ' + _e(len(comparison.get("unmatched_attempts", []))) + '. These attempts remain in the totals but are not matched evidence of improvement.</p>'
    return _document("Invaris V1 / V2 Evaluation", mode, content)
