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
