# Correctness advisory — 2026-10-02

Historical 1% gap and time-to-1% acceleration claims in this research directory
are **provisional pending revalidation on a corrected reference**. Do not use
the current research packages for production dispatch or planning decisions.
Original result tables, timings, source identities and archived packages are
preserved; this advisory does not silently replace their evidence.

## Additional presolve counterexample — 2026-10-03

The custom reference containing both official #3179 and #3181 backports also
reproduces the continuous-LP failure fixed in [PR #3270](https://github.com/ERGO-Code/HiGHS/pull/3270),
[commit 4e53e2bc](https://github.com/ERGO-Code/HiGHS/commit/4e53e2bcae3fafb3492b231545ade6a59b4ca488).
The exact `dual-bound-relaxation-unbounded` regression is in the official
[TestPresolve.cpp](https://github.com/ERGO-Code/HiGHS/blob/4e53e2bcae3fafb3492b231545ade6a59b4ca488/check/TestPresolve.cpp).
No experimental signed-clique modification was involved.

The model minimizes `-5*x1`, with `x0,x1 >= 0`, `0 <= x2 <= 1`, and rows
`x0-x1-x2 <= 0` and `-x0+x1+x2 <= 1`. Every point `(t,t,0)`, for `t >= 0`,
is feasible and has objective `-5*t`. This is an exact unbounded ray, so the
model cannot be infeasible.

Two fresh processes loaded the same pinned library and exact model through the
public C API. The integer ABI, dimensions, costs, bounds, matrix, objective sense
and offset were checked through model readback before either solve. The only
solver-option difference was presolve on/off. Both API calls returned Ok and
exited cleanly within their limits:

| Presolve | Observed status | Mathematical assessment |
|---|---|---|
| On | Infeasible | Incorrect; the explicit ray proves feasibility and unboundedness |
| Off | Unbounded | Consistent with the exact ray |

The independent audit verified the source and library hashes, literal official
data, model readback, logs, statuses and cleanup. A compact record with the model
and exact identities is [available here](correctness_advisory/presolve_3270.json).
This establishes a baseline counterexample on this continuous LP. It does not
establish a MIP-path trigger or show that any reported SCUC instance triggered
it. The internal stale-cache transition was examined in source, not traced by
these two runs.

Performance experiments are paused while a coherent official reference and its
correctness validation are selected. The PG89 tables remain historical measured
outcomes. Their independent source/primal/objective/outage checks remain useful,
but those checks do not independently prove HiGHS's lower bounds. Therefore the
reported 1% endpoints and time-to-1% acceleration interpretation on the two-fix
reference are **again provisional pending revalidation**. This is not a blanket
claim that those SCUC objectives or schedules are wrong. No result table,
timing, old package, model or saved point has been replaced.

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

## Earlier revalidation update (superseded by the 2026-10-03 caution)

**Update after corrected revalidation — 2026-10-02:** The isolated official
#3179 and [#3181](https://github.com/ERGO-Code/HiGHS/commit/ae53450f395cf0a278858868b64813ea99bb4767)
backports passed the combined reference's 168 configured tests. Fresh matched
PG89 runs passed all nine fixed pairs and their independent terminal audit:
median reductions were 66.05% in solver-process time and 56.19% in arm time.
All 18 arms reached the unchanged 1% numerical endpoint with independently
checked primals and zero shedding, shared overflow and reserve shortfall.
The [corrected report](corrected_pg89_results/RESULTS.md) and
[additive replay kit](portable_early_integer_corrected_replay_v1/README.md)
retain the complete outcome, quality and scope disclosures.

This supports a new result on the corrected custom reference. It does not
establish which old runs, if any, triggered the defect, repair historical
lower-bound evidence, or provide an exact independent dual proof. The #3181
attachment checks established compatibility but did not execute its repair
branch. Larger-case acceleration and production readiness remain unproven.

### Status when this advisory was first published

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
