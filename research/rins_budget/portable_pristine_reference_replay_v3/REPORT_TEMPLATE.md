# Fixed PG89 report template

[REPORT_TEMPLATE.json](REPORT_TEMPLATE.json) is an unfilled template, **not an outcome record**. Every measurement, status, comparison and conclusion is null. Copy it outside the kit before filling it; keep its nine rows even when a row cannot run. No current panel status or performance statistic is implied by the template.

The template retains the measured `f48ac4…` package identity and separately identifies the documentation-only public package. Keep each run's actual package identity when reporting results; executable equivalence does not rewrite old binding records. A new consumer run uses the public package identity recorded by its preparation.

## Required report content

1. Identify the official commit/tree, exact package manifest, runtime binding, actual main/extras libraries, compiler/tool versions and machine environment. State that dates and seeds were already exposed and are not a new untouched holdout. Link the [validation limits](VALIDATION.md).
2. Retain the fixed order: May 211 A/early, May 212 early/A, May 213 A/early; June 211 early/A, June 212 A/early, June 213 early/A; September 211 A/early, September 212 early/A, September 213 A/early. Do not replace, retune or retry a pair in this panel.
3. For all 18 arms, retain terminal status, failure/censoring reason, proof-only checked upper/numerical lower/gap, both timing endpoints, complete original-source and 192-outage checks, actual process debit and cleanup evidence. Use null for unavailable quantities; zero is a measured value.
4. Include true source and linear cost, matrix objective, signed overpayment, shedding, shared overflow, reserve shortfall, raw outage overloads and their worst-witness identities. Preserve units, exact field definitions and links to the supporting artifact hashes. Do not infer missing quality fields from a summary status.
5. Link each row to its compact result, offline-verifier output and independent audit. Source files such as `RESULT.json`, each arm's `summary.json`, final proof check artifacts and outer cleanup receipts should be identified by verified hashes. Avoid machine-specific absolute paths in the published report. Compact public evidence records may omit bulky models/logs while retaining their hashes and the scope of checks performed.
6. Declare eligible/declared counts, and report per-date and overall median paired reduction plus worst/best tails for each endpoint. A ratio is eligible only if both same-runtime arms cleanly complete valid original-source 1% numerical certificates. Show all ineligible outcomes without a ratio; do not substitute a timeout as a measured completion time.

The fixed descriptive criterion is all nine pairs eligible and strictly faster on both endpoints, with each date's median paired reduction at least 30% on each endpoint. This criterion is a summary rule, never a performance-dependent stopping rule. Continue after clean complete, censored or incomplete outcomes; stop dependent execution for integrity/resource/cancellation/cleanup failure and retain all declared unrun rows. A report must state any such stop.

## Timing definitions

- Solver-process wall time: each whole solver process from launch/import through optimization, output and exact reap, with nested work counted once. The requested solver timer is not the debit.
- Complete-process end-to-end time: each containing arm from process launch through exact reap, including startup, runtime verification, model generation/readback, every solve, complete independent checks and durable arm output.
- Excluded controller work: redundant prelaunch integrity/health checks, supervision setup before the arm clock, inter-arm archival/statistical writes and final campaign reporting. These intervals were not separately measured, so do not label the arm endpoint as total campaign elapsed time or total compute cost.

Compute paired reduction as `100 * (A - early) / A` separately for each endpoint, using positive measured A values only. Keep negative reductions when early is slower. Use the same runtime/package within a pair. Do not calculate cross-runtime percentages or combine historical timings. Numerical solver bounds remain solver-derived, not exact independent dual certificates.

## Completing the narrative

Lead with the number of declared/eligible pairs, completion and quality outcomes, then report timing results with the full denominators. State whether the fixed descriptive criterion was met and which endpoint or date missed it. Keep failure/censoring and worst-case tails visible. End with the scoped conclusion supported by this exposed PG89 panel and the outstanding platform/coverage limits; do not extend it to larger cases, general solver acceleration or production operation.

The completed report and its compact evidence should be new files beside this kit, with their own release hashes. Do not rewrite the frozen replay, replace historical tables or fill this distributed template in place.
