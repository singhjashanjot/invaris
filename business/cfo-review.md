# CFO model review

## Scope and evidence status

Source: user-shared [cfo.ai model](https://cfo.ai/s/aMAZiEnSXtphYplP). The reviewer inspected all six visible model pages and each of the 39 rendered Main Scenario months from October 2026 through December 2029. This is a browser-observed review, **not** an official API or XLSX export. Values below are transcribed from the visible model as supplied in the review brief; no claim is made that a source export or underlying formula audit was performed.

The business is a sandbox prototype with no validated customers or revenue. The forecast is a planning construct, not evidence of traction, customer demand, realized margin, or available financing. The roster is a 14-role placeholder plan and does not assert that these people are employed. Local live inference estimates are now available in the reconciliation below; the shared model itself remains unchanged.

## Model inputs observed

| Input | Enterprise | Midmarket |
|---|---:|---:|
| Initial opportunities per month | 1 | 2 |
| Pilot price, three months | $60,000 | $25,000 |
| Pilot conversion | 25% | 35% |
| Pilot-to-contract conversion | 45% | 50% |
| Annual recurring contract value (ACV) | $240,000 | $90,000 |
| Monthly churn | 0.8% | 1.5% |

Pilots are paid and last three months; recurring revenue is modeled as ACV divided by 12. These are assumptions, not observed conversion or retention results.

| Cost or financing input | Observed value / treatment |
|---|---|
| Inference/migration | $6 placeholder; measured field is $0 and says “PENDING - using placeholder” |
| Verification | $1.50 |
| Platform | $3,000/month |
| Payroll burden | 22% |
| Software | $600/employee/month |
| Fixed G&A | $12,000/month |
| Security/compliance | $5,000/month |
| Sales commission | 10% |
| Engineering COGS | 10% |
| Opening cash | $1.5 million, hypothetical |

The $6 input is not validated and must not be described as measured inference cost or as a complete COGS estimate. The 14-role placeholder roster includes a founder CEO and CTO at $120,000 annual salary each, with engineering, security, sales, and customer-success hiring through 2028. It is a staffing assumption, not a personnel claim.

## Main Scenario checkpoints

| Month | Revenue/month | COGS | Opex | Profit/(burn) | Ending cash | Runway shown |
|---|---:|---:|---:|---:|---:|---:|
| Oct 2026 | $11,483 | $4,363 | $53,040 | ($45,920) | $1,454,080 | 31.7 months |
| Minimum cash, Sep 2028 | — | — | — | — | $96,355 | — |
| First operating breakeven, Oct 2028 | — | — | — | — | — | — |
| Dec 2029 | $884,854 | $117,172 | $346,788 | $420,894 profit | $2,931,051 | — |

The displayed runway is cash divided by the current month's burn. It is a point-in-time ratio, not a complete forward financing or solvency analysis. The cash forecast assumes monthly on-time collection, no capex, and no new financing. The model's ending cash remains positive in Main, but its $96,355 September 2028 trough leaves little room for delays, misses, or unmodeled needs relative to the hypothetical opening balance.

## Checks, discrepancies, and limits

- Across all 39 rendered months, gross profit equals revenue minus COGS, and operating income equals gross profit minus opex, within $1 of displayed rounding.
- Overview, assumptions, and roster date labels show January 2026–December 2027, while the forecast spans October 2026–December 2029. Resolve this discrepancy before using the plan operationally.
- Overview text refers to Downside and Upside, but the visible scenario selector exposes Main only. Downside and Upside are not verified model outputs in this review.
- Costs, hiring, opportunities, conversions, ACV, churn, and opening cash are assumptions. The available review did not validate their source, formulas beyond the stated identity checks, collection timing, or financing completeness.
- No actual customer, revenue, employee, measured inference cost, or committed financing is established by this model.

## Local revenue sensitivity (not a cfo.ai scenario)

This is an independently computed local sensitivity using the rounded cfo.ai Main values, **not** a cfo.ai-generated Downside scenario. For each month, set local revenue to 90% of the displayed Main revenue and hold displayed costs and financing assumptions unchanged. Recompute monthly profit as `local revenue - displayed COGS - displayed opex`, and roll cash forward by adding that monthly profit to prior-month cash. Starting cash is the hypothetical $1.5 million. This simple case assumes the same COGS despite lower revenue and does not reforecast hiring, commissions, working capital, or any other variable input; it is directional, not a full integrated downside case.

Under that calculation, cash first turns negative in May 2028 at approximately **($4,530)**; the minimum is approximately **($281,490)** in November 2028; December 2029 ending cash is approximately **$1,714,239**. Rounded displayed source values create rounding uncertainty. The case illustrates sensitivity to revenue delivery and reinforces the need for a cash buffer and hiring gates; it should not be represented as a model output or forecast.

## Final-source inference update (October 11, 2026)

The final-source study retained seven V2 live attempts: estimated inference $0.3992516, or $0.05703594 per attempt. Four independently verified non-no-op migrations give $0.0998129 per verified migration, retaining every V2 attempt in the cost numerator. These single-repetition estimates are a local inference reference only, not billed cost, full delivery COGS, a cfo.ai export, or statistical proof. The zero-inference fixture-specific script also passed all seven cases; no economic superiority over that script is claimed. See `business/final-measured-assumptions.json` and `docs/evidence/final-study-summary.json`. The historical reconciliation below remains unchanged.

## Practical decision implications

### Measured inference reconciliation (October 11, 2026)

The completed pre-repair matched study retained 21 live V2 attempts across seven seeded scenarios, with three repetitions each. Their conservative estimated inference total was **$1.2196459**, or **$0.0580784 per attempted run**. Eleven attempts were counted as independently verified non-no-op migrations, making inference **$0.1108769 per verified migration** when all V2 attempt costs remain in the numerator, including blocked, failed, missing-evidence, and no-op attempts. Per-run billed costs and separate recovery-only costs are unavailable, not zero.

See `business/measured-assumptions.json` and `docs/evidence/matched-study-summary.json` for denominators, model, controls, and limits. These are local measurements and reconciliation, **not a cfo.ai export or an update to the shared read-only model**. The shared model still displays its $6 placeholder and PENDING measured field. The measured inference reference does not validate the separate $1.50 verification allowance or engineering, support, security, onboarding, infrastructure, and other delivery costs. This study predates the final status-parser/security repairs; subsequent release validation is documented separately rather than silently replacing these results.

1. Protect liquidity: stage discretionary hiring against signed pilots, collections, and measured delivery capacity; monitor the cash trough and build a buffer for slower conversion or payment.
2. Sell a scoped, paid three-month pilot with explicit success criteria and delivery boundaries. Do not sell the forecast as validated enterprise demand or promise a broad enterprise deployment on these assumptions.
3. Do not present forecast revenue, conversion, margins, or runway as traction. Clearly label the plan as hypothetical until supported by customer and operating evidence.
4. Replace the $6 placeholder when live-cost results are available, documenting the measured workload and window. Keep inference distinct from migration, verification, engineering, support, and other COGS so a single inference measurement is not mistaken for all-in delivery cost.
5. Correct the date labels and make any downside/upside cases visible, formula-linked, and documented before using them for decisions.
