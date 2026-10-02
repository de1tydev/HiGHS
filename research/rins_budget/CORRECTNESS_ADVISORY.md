# Correctness advisory — 2026-10-02

Historical 1% gap and time-to-1% acceleration claims in this research directory
are **provisional pending revalidation on a corrected reference**. Do not use
the current research packages for production dispatch or planning decisions.
Original result tables, timings, source identities and archived packages are
preserved; this advisory does not silently replace their evidence.

## Confirmed failure on an official regression model

The pinned HiGHS source, `73cac48c5340d775a477087198611862559be250`, lacks the
upstream path-mixing-cut correction in [PR #3179](https://github.com/ERGO-Code/HiGHS/pull/3179),
for [issue #3171](https://github.com/ERGO-Code/HiGHS/issues/3171). The official
[fix commit](https://github.com/ERGO-Code/HiGHS/commit/28339ce4b57bf8858036cbb36f4fc66d97fedd06)
keeps bound substitutions consistent while combining rows into a cut.

We reproduced the defect on the official
[85-row, 99-column regression model](https://github.com/ERGO-Code/HiGHS/blob/28339ce4b57bf8858036cbb36f4fc66d97fedd06/check/instances/issue-3171.mps).
The unchanged recovered binary reported `Optimal` with primal and lower bounds
of `42332.2356068`. An isolated backport reported `Optimal` at
`42215.5250005`, matching the upstream regression oracle.

A separate parser checked the original MPS and both complete saved solution
vectors using 80-digit Decimal arithmetic, without a solver or its model API.
Both vectors satisfy all 85 rows, 99 column bounds and 49 binary constraints.
Their recomputed objectives are exactly `42332.235606780` and
`42215.525000540`. The second feasible point is `116.710606240` cheaper, which
disproves the old binary's optimality and lower-bound claim on this fixture.
This check does not independently prove the corrected result's global optimum.

The isolated correction passed the official focused regression and all 168
configured CTest tests: 353 unit cases and 1,259,994 assertions. Its reference
preserves the three earlier default-off research patches; all three switches
were off in this reproduction. It is a corrected custom reference, not a
pristine build of the entire upstream development branch. Compact identities
and results are in [the reproduction record](correctness_advisory/reproduction.json).

## Effect on the SCUC reports

The SCUC models contain variable and bound types that can enter the affected
code. We have **not established that any historical SCUC run triggered this
defect**. A cross-check of comparable published lower bounds against the best
independently checked feasible upper bounds found no contradiction, but cannot
exclude the defect. Some result groups have no retained full-scope feasible
upper bound for that comparison, and the old raw runtime artifacts are no
longer locally available.

The independent SCUC checks support the reported primal feasibility and
objective checks, including the specified outage coverage. They do not verify
that every solver-generated cut is valid or that its global lower bound is
sound. Consequently they cannot by themselves establish the claimed 1% gap.
Historical wall times remain recorded measurements; their interpretation as
time to a valid 1% solution, and the associated acceleration claims, require
revalidation. No fixture-specific objective difference has been applied to
SCUC results, and no historical timing has been adjusted.

## Current status

New performance runs are paused. The separate original-space incumbent-repair
correction in [PR #3181](https://github.com/ERGO-Code/HiGHS/pull/3181) is also
being assessed before selecting the reference for resumed work. Passing the
#3179 regression does not make the reference universally bug-free or provide
an independent dual certificate.

After the reference and its correctness tests are fixed, the first performance
priority is a fresh matched revalidation of the already reported PG89 method,
with the same full-source checks and all outcomes retained. Neither a corrected
PG89 speedup nor general solver acceleration has yet been established by this
advisory.
