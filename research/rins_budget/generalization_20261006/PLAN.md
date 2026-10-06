# Frozen prospective generalization and CPU retrieval campaign

Registered before downloading or solving test instances on 2026-10-06.
Algorithm baseline: 6b2fee0d4c3f5a2b2d595ed6526c3f9e6e9e0eec, unchanged current_scuc package.
Native: official d547a3ad8af5399651187fb0e133cf0e42615b82, rebuilt locally.

## First round

Fixed order: case1354pegase 2017-01-15, 2017-04-15, 2017-07-15;
36 hours; seed 1 once each. Dates selected by calendar, without inspecting
loads, solutions or performance. Repository text search found no prior results
for these dates. This is repository-relative unexposed status, not a guarantee
about private historical exposure. Missing/unsupported data stays a failure;
no replacement date, seed retry or outcome-based parameter change.

Restore pinned Python 3.12 / numpy 2.3.5 / scipy 1.17.0 / threadpoolctl 3.6.0;
run pure tests then one seed-1 transition tiny. Large runs require these gates.
Build: two jobs, maximum 20 minutes, 4 GiB planned build disk. Serial numerical
runs; original 7 GiB AS / 6 GiB RSS / 512 MiB file / zero core policies;
2 GiB free memory/disk floor, original stricter launch storage admissions.
Stop on failed native qualification, tiny failure, cancellation, resource gate,
source drift or cleanup failure. Ordinary scientific NONPASS is retained and
permits the next fixed date. Each large invocation outer bound is 2460 seconds;
preparation 600, candidate 1800, cumulative seed-LP/MIP/carry process wall 600.
These nested clocks are NOT additive. Record preparation/model building,
solver ledger, checker phase measurements and complete start-through-reap wall;
report unseparated timing where no individual timer exists, never infer it.

Accept only unchanged original binary/matrix/source N-1 and independent DC
checks with true original cost and slack accounting. Preserve every failure.
Bound labels remain exact literal-model hard-zero LP or numerical hard-zero
MIP; no certified physical-DC or original soft-problem lower bound claim.

## Subsequent acceleration route

Only after frozen evaluation, develop CPU historical-day feature retrieval and
confidence-ranked commitment suggestions. Training/selection sources restricted
to historical exposed dates 2017-06-01, 2017-10-01, 2017-12-01; no test solutions
or test-outcome-driven hyperparameter selection. Compare last historical
schedule and nearest-load-profile retrieval with confidence partial starts or
bounded neighborhood repair. Historical labels require newly checked schedules
or verified retained artifacts. No fabricated labels. Reversible fixes only;
reserve budget for unrestricted full-problem fallback. Restricted repair bounds
are never global lower bounds. Count feature/prediction/repair overhead and all
solver process wall. Freeze any follow-on evaluation before running it; use a
new calendar test panel if results informed implementation choices.

## Additional user-directed tracks (before scientific runs)

Annual rolling experiments must use past-only labels available before each
forecast horizon, with a 36-hour embargo to avoid overlapping labels. The
three exposed 2017 dates above are potential implementation-development data,
NOT permitted future labels for January/April/July 2017. A separate prospective
chronological learning panel is required; do not reuse the frozen-generalization
panel to claim annual learned speedups. Report cross-season/load/renewable
strata, label solves, training, feature generation, repair, fallback, checking
and total cumulative runtime over all attempted horizons. No random splitting.

Kernel track remains independent of formulation/learning. Next experiment:
profile the pristine official binary on a retained SCUC master after successful
frozen validation and on bundled general-MILP models (egout, flugpl, p0033),
seed 1, two threads, parallel off, 60 seconds each, serially. Record presolve,
root/node LP, separation and heuristic timings using native analysis support
in a separate diagnostic invocation, not a retiming of the frozen panel.
Before proposing a default-off core patch, require a measured hotspot and
read prior NEGATIVE_TRANSFER.md, INITIAL_ROOT_IPX.md, ROOT_CHILD_CREDIT.md and
RINS records. No repeated RINS toggles or unsupported root-LP switches.
A kernel patch must preserve numeric/global-bound semantics, have an explicit
switch, and use paired original/patch runs on the entire fixed panel; retain
all slower/failing/timed-out cases. Profiling/parameter changes are not kernel
code acceleration. Lack of a justified patch is reported as such.

Kernel input inventory before profiling: p0033 is absent from the official
checkout and will be recorded missing, not replaced. Add a separate diagnostic
panel of bundled dcmulti and gesa2 (chosen by known model identity, before any
run), seeds 1 and 2, 60 native seconds each, with profiling off/on in alternating
order. Retain the original egout/flugpl seed-1 diagnostics. Compare outcomes and
instrumentation overhead only; this is not a core optimization claim. Use 75
seconds outer per call, 7 GiB AS, one serial process and bounded logs.
