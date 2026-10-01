# Recorded research results (2026-10-01)

## Decision

Keep the normal HiGHS defaults. Nested-RINS-off is an experimental ablation, not a demonstrated general improvement. Its result on one custom public SCUC model is mixed. The patch is supplied for reproduction and further investigation.

## One custom 1%-gap SCUC case

Public input: PEGASE89, 2017-02-01, 36 hours. Custom preventive DC formulation; 89 buses, 210 lines, 1,296 binary variables in the screened master. Verification covers the 192 line outages explicitly listed by the input. It does not claim all 210 line outages, AC feasibility, or generator-contingency security. Two unlisted lines are non-islanding; the missing list is not simply the bridges.

Each arm starts with the same twelve valid security pairs, no inherited primal incumbent, one solver thread and parallel search off. The 300-second global budget includes model generation, solve, source-data checking and any re-separation. The input/generator/checker/driver hashes are recorded in the machine-readable summary. All six arms finished in one round, so there was no new separation work in these particular measurements. This compares a shared initial screen, not cold security screening.

| Seed | Default end-to-end s | Nested-RINS-off s | Observed time change | Full-model gap |
|---|---:|---:|---:|---:|
| 0 | 35.212 | 30.627 | -13.0% | 0.9861% |
| 1 | 35.402 | 37.186 | +5.0% | 0.9881% |
| 2 | 34.802 | 33.578 | -3.5% | 0.9872% |

All six final primal vectors passed the independent source-data checker, including direct refactorization of every listed outage topology. No load shed, reserve shortfall in the checked solutions, line-overflow slack, or dropped-coefficient warning was observed. The common incumbent cost is approximately 3,534,678.762427. The numerical certificates use a valid relaxed-master lower bound and the fully checked incumbent; printed lower bounds are adjusted conservatively for log rounding. These are tolerance-based numerical certificates, not exact rational proofs.

One run per treatment/seed is a small exploratory screen. The +5.0% observation is retained; cloud-host noise and seed-specific paths matter. There is no holdout-case evaluation or evidence for a general SCUC speedup. Do not report the 45-second static-model timeout versus the screened solve as a speedup ratio.

## Regression evidence

- Official source baseline: all 166 CTest entries passed; Catch reports 328 cases and 1,259,125 assertions
- Additive RINS diagnostics build: all 166 CTest entries passed with logging enabled
- Nested-only-RINS-off build: all 166 CTest entries passed
- Source base: 73cac48c5340d775a477087198611862559be250, source version 1.15.1
- Release -O3 -DNDEBUG with automatic LTO, GCC 14.2.0, CMake 4.4.3, Ninja 1.13.2
- Shared cloud runtime exposed nine logical CPUs and approximately 9.7 GiB RAM. The reported CPU model was AMD EPYC 9V74; this is not an allocation of 80 cores or a guaranteed host quota

## Earlier zero-gap fixture screen

Ten bundled small MILPs, seeds 0/1/2, two repetitions per treatment: 120 runs. Default versus the existing global RINS-off option. All optimal statuses, expected objective comparisons and independent final-primal checks passed. Dcmulti and bell5 provided leads, but other cases were mixed and most solves were sub-second. The machine-readable per-fixture medians are retained without a broad-performance claim.

Crucially, those fixture runs used zero relative/absolute gap, whereas the SCUC target is 1%. Dcmulti's expensive top-level RINS calls started at gaps already below 1%, so those fixture savings cannot be transferred to the user's SCUC goal. The public API checker was subsequently hardened to snapshot the original LP and reject non-finite accumulators; it validates final primal feasibility, not the dual certificate or every intermediate incumbent.

## What the diagnostics establish

Separate scope instrumentation observed recursive RINS through depth 3 on dcmulti. Seed 0 had a top-level incumbent-field improvement; seeds 1/2 had no immediate incumbent-field improvement. Local subproblem improvements, accounting-weighted LP counters and synchronous lower-bound fields are not interchangeable with original-problem benefit. Unchanged immediate fields can still precede later propagation/conflict effects. Nested wall-clock intervals must be merged before summing. Diagnostic timings are not pooled with uninstrumented performance results.

## Publication-time replay guards

The published screening driver requires a new output directory and refuses to certify an original-model bound when HiGHS reports ignored/dropped matrix coefficients. These guards were added after the recorded six-arm experiment. All recorded arms already used fresh directories and had no such warnings, so the observations are unaffected. `SOURCE_MANIFEST.json` at the research-package root retains both the historical measured driver hash and the current published driver hash. Solver-free guard tests are in `scuc/test_driver_hygiene.py`.

## Larger cold-LP experiment: negative end-to-end result

A separate one-seed experiment used public PEGASE1354 (2017-02-01, 36 hours), a custom **base-network UC model, not N-1**: 381,268 rows, 313,776 columns, 28,080 binary variables and 1,232,543 nonzeros. The source allows penalized shedding/overflow; neither penalties nor feasibility semantics changed between arms. These runs have a requested **600-second solver budget**; setup/read/check costs are separate, unlike the earlier 300-second end-to-end PEGASE89 protocol.

| Cold LP engine | Reported solve s | Status | Final gap using checked incumbent | First visible <1% report s | Peak RSS GiB |
|---|---:|---|---:|---:|---:|
| default/choose | 600.42 | Time limit reached | 0.4794% | 600.4 | 1.84 |
| IPX | 637.02 | Time limit reached | 0.4644% | 637.0 | 1.71 |

Neither arm reported the target strictly within 600 seconds. A sub-1% final certificate does not change the returned time-limit status or erase the overshoot. Both final points passed the independent source-data base-network primal/objective check; the dual bounds are reported by HiGHS and are not independently verified dual certificates. Both had shedding at numerical zero (raw sum −1e−13 MWh) and zero overflow. This is not an N-1/AC certificate.

IPX reduced the first cold LP stage from roughly 210 seconds to roughly 150 seconds, and produced a better early incumbent. That did **not** improve total solving: later sub-MIP time increased from about 68 to 191 seconds. The experiment is rejected as an end-to-end speedup, and defaults remain unchanged. IPM work is not counted in the simplex LP-iteration total, so a lower iteration count is not evidence of less work. The public option applies to every no-basis LP, including nested subproblems; it is not an isolated root-only switch.

The matched configurations are `options/cold-lp-default.options` and `options/cold-lp-ipx.options`. Use the same pinned executable, model bytes, seed 0, requested `--time_limit 600`, unique `--solution_file` paths, and an identical per-run `mip_improving_solution_file` setting pointing at a unique checkpoint destination. The recorded protocol used a 7 GiB virtual-address cap and a 660-second emergency process watchdog, which did not fire in either arm. All observed solver overshoot is retained. Independent checking follows the solve and is not charged to its 600-second request. See `recorded_results/pg1354-cold-lp-600.json` for hashes, source checks, CPU time and exact measurements.

The subsequently measured outer-gap-aware heuristic return is reported below. Matched thread-budget and additional LP-engine experiments remain separate research questions.

## Default-off outer-gap return experiment

A later same-binary, seed-0 observation/enabled pair on the 600-second PEGASE1354
base-network model measured 602.55 versus 585.58 solver seconds (2.8%). Both
returned the same independently checked primal and 0.4794% gap using the solver
dual bound. The direct-child candidate-to-parent delay fell from 19.21 to 0.12
seconds. This verifies a mechanism, not substantial or stable acceleration;
see [OUTER_GAP.md](OUTER_GAP.md) for scope, tests, overshoot, and replay.

## Matched two-thread HiPO screen

A later same-build choose/HiPO pair with outer-gap enabled in both was negative:
choose reached the target at 542.36 s; HiPO stopped at 604.15 s with 1.716% gap.
Both final primals passed. See [HIPO_RESULTS.md](HIPO_RESULTS.md), including the
actual OpenBLAS configuration and corrected resource-accounting limitation.

## Initial-main-root-only IPX pilot

The same-binary February seed-0 pilot took 564.48 s control versus 465.27 s
initial-root-only IPX, a preliminary 17.6% reduction. Both final primals pass
and both meet the requested 1% gap. The control had a brief low-CPU monitor
overlap; repeatability is unestablished. Frozen-policy held-out-date validation
has completed: both August and November fail to reach 1% in either arm, so no
stable acceleration is established. See [INITIAL_ROOT_IPX.md](INITIAL_ROOT_IPX.md).

## Transfer and application-layer negative results

Initial-root IPX also regressed on the PEGASE89 February/August seed-0 transfer
checks (+37.8% and +15.7% whole-loop time), with all 192 listed outages checked.
The August soft-model points include 312.105451 MWh of load shedding. A separate
UC-relaxation/network-repair pipeline missed the 1% target, and extending UC to
480 seconds produced no new incumbent. See [NEGATIVE_TRANSFER.md](NEGATIVE_TRANSFER.md)
for complete scopes, unchanged objectives, stage budgets and retained failures.

A later 5,950-row joint startup/shutdown capacity strengthening was also negative:
both arms met 1%, but the candidate added 2.80% solver wall and 4.09% E2E time.
Its final bound was unchanged. The proof, tests, original-model checks and
post-run extras-library provenance caveat are retained in NEGATIVE_TRANSFER.md.

Sparse-angle flow elimination was stopped at its presolve-only gate: it produced
3.08% more presolved nonzeros and no demonstrated conditioning benefit. No full
solve or original-model lower-bound transfer was claimed.

## Input serialization validation

A tiny correctness smoke exposed ambiguous fixed-binary bounds in the frozen
SCUC writer. The additive [canonical v2 exporter](scuc/canonical_v2/README.md)
fixes that serialization and checks every loaded model field through the actual
HiGHS API. A retrospective audit found exact identity for eight historical
matrices, including all PEGASE1354 and screened PEGASE89 inputs; the ninth was
the already-disclosed full-static smoke with tiny dropped coefficients and no
incumbent. See [LOADER_FIDELITY.md](scuc/LOADER_FIDELITY.md). This is a correctness
repair and input-validation result, with no new performance claim.
