# Corrected-reference PG89 revalidation — 2026-10-02

**Additional correctness advisory — 2026-10-03:** The two-fix reference used
for this revalidation also reproduces the official #3270 continuous-LP presolve
failure. Its SCUC trigger is unknown. The primal checks and recorded timings
remain evidence, but the 1% endpoint and time-to-1% interpretation are provisional
pending a new reference and revalidation. [Read the new evidence and limits](../CORRECTNESS_ADVISORY.md#additional-presolve-counterexample--2026-10-03).

The fixed nine-pair revalidation passed on a reference containing the two
official correctness fixes. Early integer cut discovery reduced median solver
process time by **66.05%** and median arm end-to-end time by **56.19%**. All nine
pairs improved both endpoints, all 18 arms completed within budget, and every
date passed the prespecified 30% median reduction requirement on both endpoints.

These are fresh matched measurements on the same corrected runtime. They do
not replace the historical numbers or establish whether the old SCUC runs
triggered the defect described in the [correctness advisory](../CORRECTNESS_ADVISORY.md).
This is revalidation on previously exposed dates and seeds, not an untouched
holdout or evidence of general MILP acceleration.

The published arm order was verified. The old raw stop predicate was unavailable
after workspace loss, so a new full-panel continuation rule was frozen before
these outcomes: retain clean complete or incomplete pairs, stopping dependent
execution only on fatal integrity, resource, cancellation or cleanup failures.

## Method and comparator

The control is the cold integer security-screening loop. Both arms begin with
an empty security cache. The candidate allows one discovery solve to stop at
its first improving integer solution, checks all specified outages, adds only
violated original security rows, then solves a cold proof master at the
unchanged 1% target. Discovery primal values and bounds are discarded; no
incumbent, basis, start or internal solver state is carried.

Across this panel the control used 27 proof solves. The candidate used nine
short discovery solves and nine proof solves. The measured method saves work
spent solving incomplete security masters to 1%; it is application-level
scheduling and cut discovery, not a faster LP kernel. The comparison does not
establish superiority over the earlier LP-screening bundle.

The source is the public PG89 36-hour custom preventive DC-SCUC model on
2017-05-01, 2017-06-01 and 2017-09-01. Seeds 211–213 and alternating arm order
were fixed before execution. Each point is checked against all **192 outages
specified by the source**, covering 14,721 eligible line/outage pairs and
529,956 pair-hours. This is not every possible single-line outage or an AC
security certificate; the source contingency list omits 18 of 210 lines.

## All paired timings

Times are seconds. Each cell shows control / early discovery. Reductions are
paired fractions, not ratios of separately aggregated times.

| Date | Seed | Solver seconds A / early | Arm seconds A / early | Reduction solver / arm |
|---|---:|---:|---:|---:|
| 2017-05-01 | 211 | 127.61 / 32.39 | 155.05 / 51.66 | 74.62% / 66.68% |
| 2017-05-01 | 212 | 101.75 / 33.93 | 130.01 / 53.73 | 66.66% / 58.67% |
| 2017-05-01 | 213 | 121.76 / 27.91 | 149.79 / 46.71 | 77.08% / 68.82% |
| 2017-06-01 | 211 | 89.43 / 24.95 | 117.81 / 44.21 | 72.10% / 62.47% |
| 2017-06-01 | 212 | 72.82 / 25.60 | 100.66 / 44.10 | 64.84% / 56.19% |
| 2017-06-01 | 213 | 75.25 / 25.55 | 103.15 / 45.33 | 66.05% / 56.05% |
| 2017-09-01 | 211 | 113.38 / 54.80 | 142.48 / 75.93 | 51.67% / 46.71% |
| 2017-09-01 | 212 | 116.47 / 51.16 | 144.79 / 71.94 | 56.07% / 50.32% |
| 2017-09-01 | 213 | 102.66 / 41.42 | 131.81 / 61.23 | 59.65% / 53.55% |

May, June and September median reductions were respectively **74.62%, 66.05%,
56.07%** in solver time and **66.68%, 56.19%, 50.32%** in arm time. The worst
individual pair improved **51.67% / 46.71%**; the best improved **77.08% / 68.82%**.
All nine declared pairs are included. There were no failed, censored, retried,
replaced or unrun arms.

## Feasibility, objective quality and bounds

All final source and matrix checks passed. Every saved load-shedding,
shared-overflow and reserve-shortfall variable is exactly zero: respectively
57,672, 49,896 and 648 entries across the 18 final points. All 648 reserve
requirements passed. The maximum original matrix residual was 9.124e-10;
maximum base-network and outage residuals were 9.116e-10 and 4.229e-10 MW.
The largest raw outage overload was 2.569e-11 MW, within the unchanged 1e-5
checking tolerance.

Final numerical gaps range from **0.8930% to 0.9987%**. Primal feasibility and
objectives are independently checked; global lower bounds come from HiGHS,
with the original conservative printed-bound allowance. They are not exact
independent dual proofs. All comparable final lower/upper intervals are
consistent across arms and seeds.

The endpoint is a checked 1% gap, so paired incumbents need not have identical
cost. The candidate's true source cost was up to **0.2735% higher** (September,
seed 211) and up to **0.5258% lower** (May, seed 213). All nine differences are
retained in [the compact result](result.json), together with source/linear/matrix
objectives, signed arithmetic overpayment, slack counts, residuals, proof-point
identities and bound allowances. Maximum absolute objective overpayment was
1.304e-8. The certificate-upper point was the last proof point in every arm.

## Runtime, limits and validation

The same executable and loaded main/extras libraries serve both arms. The
source is pinned official commit `73cac48c5340d775a477087198611862559be250`,
the three preserved opt-in research patches, and isolated official fixes
[#3179](https://github.com/ERGO-Code/HiGHS/commit/28339ce4b57bf8858036cbb36f4fc66d97fedd06)
and [#3181](https://github.com/ERGO-Code/HiGHS/commit/ae53450f395cf0a278858868b64813ea99bb4767).
It is a corrected custom reference, not pristine upstream defaults or a whole
development-branch update. Root-only IPX and root-child credit are off; the
same outer-gap option is on in both arms. Full options and source/runtime
digests are in the JSON record.

The combined reference passed 168/168 CTest tests, 353 unit cases and
1,259,994 assertions, including the official #3179 regression. Four #3180
attachment comparisons checked compatibility, but all reported zero repair
LPs, so they did not dynamically exercise the #3181 repair branch. The corrected
replay passed its separate tiny run and offline verification. Terminal review
checked all 45 solver stages, model API fidelity, actual library identities,
saved solution artifacts, original-source checks and process cleanup.

Each arm retained a 600-second aggregate actual solver-process budget and
1,800-second containing-process limit, with a 600-second helper cap and 7 GiB
process memory limit. All stage and arm overruns were zero. Solver-process
times include launch, nested solver work and output through exact reap. Arm
times also include generation, model/API readback, checking and durable arm
output. Redundant controller-only integrity checks and final archival/reporting
remain outside this explicitly defined endpoint; no total-campaign cost claim
is made. The timed-arm payload, policy and primary clocks stayed unchanged;
operator observation/checkpoint wrappers were added outside those endpoints
after pair 2. No historical runtime or timing is pooled with this campaign.

The environment exposed nine logical CPUs and about 9.7 GiB RAM; exclusive
quota was not guaranteed. Build settings were GCC 14.2, CMake 4.4.3, Ninja,
Release/shared, HiPO off and 32-bit HiGHS indices. Solver options use two
threads with parallel search off. There was one numerical workload at a time.

Use the [additive corrected replay kit](../portable_early_integer_corrected_replay_v1/README.md)
to reconstruct the exact tested source and package. Historical packages remain
unchanged. This panel supports a substantial scoped PG89 improvement; three
seeds per date and one network do not establish broad tail reliability or
larger-case gains. Previously negative larger transfers are not overturned.
