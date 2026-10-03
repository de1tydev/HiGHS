# Pristine-reference PG89 revalidation — 2026-10-03

The fixed nine-pair study passed its prespecified criteria on pristine official
HiGHS commit [`d547a3ad`](https://github.com/ERGO-Code/HiGHS/commit/d547a3ad8af5399651187fb0e133cf0e42615b82).
Early integer cut discovery reduced median solver-process time by **63.85%**
and median full-arm time by **54.03%**. All 18 arms reached independently
primal-checked, solver-bound-based 1% numerical endpoints; every pair improved
both timing measures, and each date passed the fixed 30% median requirement.

This is a **new official development-reference lineage**, with no private solver
patches. The earlier common outer-gap option is absent from both arms. These
results do not repair or overwrite archived evidence or establish whether an
old SCUC run triggered an upstream defect. The [correctness advisory](../CORRECTNESS_ADVISORY.md)
remains applicable to those histories. No timing ratio mixes old and new runtimes.

## Method and fixed scope

The control starts with an empty security cache and solves cold integer masters
to the 1% target, separating violated original security rows between solves.
The candidate starts equally empty, allows one discovery solve to stop at its
first improving integer solution, checks the specified outages, adds violated
original rows, and starts a fresh cold proof solve at the unchanged 1% target.
Discovery requests at most 300 seconds within the shared 600-second solver budget.
No incumbent, objective bound, basis or internal solver state carries from
discovery into proof. Ordinary internal solver heuristics remain enabled.

The control required **26 proof solves**. The candidate used **nine discovery
solves and nine proof solves**. This measures application-level scheduling and
cut discovery; it does not establish a faster LP kernel, general MILP speedup,
or superiority over the earlier LP-screening bundle.

The custom preventive DC-SCUC model has 36 hours, 89 buses, 12 units and 210
lines, including 77 finite-rated lines. Every final point is checked against
all **192 outages specified in the public source**, covering 14,721 eligible
line/outage pairs and 529,956 pair-hours. The source omits 18 of 210 line outages;
this is not every possible single-line outage or an AC security certificate.

May, June and September 2017 and seeds 211–213 were fixed before these outcomes.
Arm order alternated across the nine pairs, beginning control then candidate.
These inputs were already exposed in earlier studies. All nine declared pairs
ran once; there were no retries, replacements, censored arms or unrun slots.
The rule retained clean incomplete outcomes and stopped only on fatal integrity,
resource, cancellation or cleanup failure; no performance-dependent stopping
or retuning was permitted.

## Every paired timing

Seconds, shown as control / early discovery. Reductions are medians of paired
fractions, not ratios of separately aggregated times.

| Date | Seed | Solver seconds A / early | Full-arm seconds A / early | Reduction solver / arm |
|---|---:|---:|---:|---:|
| 2017-05-01 | 211 | 77.39 / 20.83 | 105.75 / 40.82 | 73.08% / 61.40% |
| 2017-05-01 | 212 | 72.66 / 25.00 | 100.75 / 44.84 | 65.60% / 55.49% |
| 2017-05-01 | 213 | 89.47 / 23.81 | 118.88 / 43.83 | 73.39% / 63.14% |
| 2017-06-01 | 211 | 66.43 / 24.01 | 94.47 / 43.43 | 63.85% / 54.03% |
| 2017-06-01 | 212 | 68.78 / 29.26 | 97.22 / 49.46 | 57.45% / 49.12% |
| 2017-06-01 | 213 | 79.85 / 28.34 | 110.16 / 49.14 | 64.51% / 55.39% |
| 2017-09-01 | 211 | 85.87 / 56.38 | 106.80 / 76.56 | 34.34% / 28.32% |
| 2017-09-01 | 212 | 102.93 / 53.51 | 131.85 / 73.25 | 48.02% / 44.45% |
| 2017-09-01 | 213 | 89.04 / 39.52 | 120.28 / 60.43 | 55.61% / 49.76% |

May, June and September median reductions were **73.08%, 63.85%, 48.02%** in
solver time and **61.40%, 54.03%, 44.45%** in full-arm time. The worst individual
pair improved **34.34% / 28.32%**; the best improved **73.39% / 63.14%**.
The 30% criterion applies to each date's median, so the individual 28.32%
observation remains visible. Three seeds per date on one topology do not
establish a distributional tail guarantee or performance on untouched cases.

## Primal quality and numerical bounds

All terminal shedding, shared overflow and reserve shortfall values are
**exactly zero**: 57,672, 49,896 and 648 entries respectively across the 18 arms.
All 648 reserve requirements passed. The maximum final source/matrix residual
is 1.504e-9; the largest raw outage overload is 2.911e-11 MW, below the unchanged
1e-5 checking tolerance. Every certificate upper point was also the last proof
point, and all same-case lower/upper intervals were consistent.

Final numerical gaps range from **0.8601% to 0.9994%**. The incumbent feasibility
and objective are independently checked; global lower bounds come from HiGHS
with the retained conservative printed-bound allowance. They are not exact
independent dual proofs or a universal solver-correctness guarantee.

The 1% stopping rule permits different incumbent costs. For June seed 212,
the candidate found a **1,469.01 lower source cost (0.0546%)**; the other paired
source costs agree up to numerical rounding. Every separate objective and gap
is retained in [the compact records](result.json). Signed source/linear
objective discrepancies range from -2.79e-9 to +1.40e-8; no slack or discrepancy
was clipped away.

## Runtime, validation and clocks

Both arms use the same pristine 1006-file official source, CLI, main library
and extras library. The pin contains the official #3179, #3181, #3270 and #3318
repairs and later upstream changes; it is a development commit, not a released
version. The exact #3270 LP now returns Unbounded with presolve on and off.
The official #3179 regression and independent original-MPS objective check pass.
The #3181 public compatibility points pass with their scaling warnings retained;
actual retry-path coverage remains unestablished.

The configured test outcome is **168/169 CTest entries and 399/400 unit cases**.
`AffinityReducedCoreCount` remains unmet in this cloud environment: unavailable
CPU topology files trigger the upstream fallback. Explicit thread settings
bypass automatic selection for this study. The failure and the initial verbose
CTest log-cap stop are preserved; the remaining 163 tests passed separately.
No full-suite-pass or production-readiness claim is made. The independent tiny
replay passed model/API, source/outage, runtime and cleanup checks before timing.

The build uses GCC 14.2, CMake 4.4.3, Ninja, Release/shared main and extras,
HIPO off, int32 and two-job LTO. Python is 3.12.14 with NumPy 2.3.5 and SciPy
1.17.0. Both arms explicitly use two solver threads, parallel search off,
presolve on, seed-specific randomness, relative gap 0.01, and the official
absolute-gap default 1e-6. The common native profile options are log_dev_level=1
and highs_analysis_level=128. The cloud exposes nine logical CPUs and about
9.7 GiB memory, without a guaranteed dedicated quota.

The per-arm limit is 600 seconds of actual solver-process wall time, including
load and output, and 1800 seconds of containing arm-process time. All model
generation, API readback, repeated solves, source/outage checking and durable arm
output occur inside the arm endpoint. Common package/runtime provisioning,
controller-only checks and research reporting are outside it; no total campaign
cost claim is made. The shared outer physical monitor and lightweight read-only
artifact audits were active. Every overshoot field is retained and is zero in
this study. No larger-case acceleration is established by this PG89 result.

The measured package remains pinned at `f48ac4f8…`. A separately packaged public
copy has documentation-only changes, with every executable and payload byte
preserved. Its runnable validation is reported separately from these timings.
Full source/runtime digests, stage counts, allowances, quality records and audit
identities are in [result.json](result.json). Historical tables and replay
packages remain unchanged.
