# Patched-reference qualification: bounded correctness evidence

Recorded **2026-10-07**. Official HiGHS d547 plus the isolated #3357/#3367
minimal patch completed the bounded qualification described below, with the
**AffinityReducedCoreCount exception retained**. This adds assertions-enabled
regression evidence and two full-source SCUC checks to the
[earlier Release checkpoint](../correctness_3357_3367_20261007/README.md).
It does not promote a global reference or restore historical speed claims.
[RESULTS.json](RESULTS.json) contains exact identities and compact observations;
[REPLAY_INDEX.md](REPLAY_INDEX.md) maps the public sources and replay limits.

## Native correctness gate

Matched assertions-enabled builds used `-O1 -g1`, without `NDEBUG`; all 285
compile commands per arm were checked. Pristine d547 reproduces the #3357
symmetry-on branch-marker/stabilizer failures, the #3364 rule-only LP presolve
assertion, and the #3359 ordered-MPS assertion. The candidate passes each;
symmetry-off controls and bounds remain correct. Each arm also passes the
same 118 focused native cases (117 assertion-bearing plus one existing empty
case), totaling 904 Catch assertions, including actual symmetry/orbital-fixing
coverage. No historical SCUC trigger is established.

The preserved #3359 fixture independently has integer and LP-relaxation optimum
25: an exact feasible witness and equality-row multipliers verify all 69 rows
and 88 columns, with `lambda A >= c` and `lambda b = 25`. Exhaustive enumeration
finds 630 paths, eight optimal; 13 rejection/metamorphic checks pass. This
certifies that fixture's expected answer, not the solver in general.

All **169 configured Release CTest entries executed: 168 passed, one failed**.
The failing `unit_tests_all` entry reports 399/400 cases and
1,260,048/1,260,049 assertions passing. `AffinityReducedCoreCount` expects one
core and sees five. The identical executable fails identically with pristine
and candidate DSOs: missing CPU-topology files trigger the unchanged upstream
fallback. No timeout or skipped entry is counted as a pass.

A **separate fresh-process aggregate**, excluding exactly that affinity case,
passes 399 cases and 1,260,048 assertions. This removes the failed case's
skipped-cleanup contamination from evidence for those included cases. Native
per-test thread settings remain unchanged; no global thread pin is claimed
for this aggregate. The original 168/169 result and unresolved exception remain.
The qualified Release CLI/DSO also pass the dedicated fixtures and known LP.
Later SCUC work uses explicit thread counts; automatic-thread and affinity
correctness are outside this qualification.

## Full-source tiny SCUC

One cold solve of the already exposed three-bus/two-hour triangle used
threads=1, parallel=off and seed=1. All original constraints and both eligible
monitored-line/outage pairs were installed. Exact API model comparison passes
at 48 columns, 78 rows, 192 nonzeros and 12 binaries. The objective is **660**,
matching an independent exact physical-source lower bound and feasible witness.
All matrix, bound, integrality and physical residuals are zero; all four
pair-hours and 12 original shedding/overflow values pass with zero slack.
This input has no reserve product.

The original option audit covered **114 user-settable records**. A separate
post-run, no-model audit of the same pinned library and immutable options file
covers **161 records**, including 47 advanced records, with required settings
and no undeclared nondefaults. It is current configuration evidence, **not
retroactive proof of every option in the historical solver process**. Original
smoke evidence is unchanged and no solve was repeated.

Presolve reduced the tiny model to empty: zero nodes and zero root LP
iterations. It covers parsing, formulation, presolve/postsolve and independent
checking, but supplies no SCUC root, branching or cut-generation coverage.

## One exposed PG89 cold-control arm

Exactly one May 1, 2017 PG89 arm A, seed 211, ran on the patched Release runtime
with threads=2, parallel=off and presolve=on. The pre-run no-model option audit
covered all 161 records; exact per-solve CLI overrides and loaded DSOs were
also checked. No discovery/acceleration arm or comparator ran.

Three prescribed fresh cold integer-proof solves installed original security
pairs **0 → 11 → 12**; newly violated pairs were **11 → 1 → 0**. Only those
original rows persisted. No incumbent, basis, solver state or historical advice
carried between calls. All 16 API fidelity fields pass for each export.
Each stage checks all **192 listed outages, 14,721 eligible pairs and 529,956
pair-hours** over 36 hours, 89 buses, 12 units and 210 lines (77 finite-rated).
The source omits 18 possible line-outage scenarios. Scope is listed-source
preventive DC-SCUC, not all possible N-1 outages or AC security.

The independently checked feasible upper objective is **2,678,903.091965961**.
The HiGHS numerical lower bound after the unchanged printed-bound allowance is
**2,652,648.747188473**, giving **0.9800408554%**, within the fixed 1% endpoint.
This lower bound is solver-based; it is **not an independent exact dual proof**
or an exact optimum. Native “Optimal” uses the configured 1% tolerance.

All 3,204 shedding, 2,772 shared-overflow and 36 reserve-shortfall values are
exactly zero, using raw signed values without clipping. All 36 recomputed
reserve deficits are zero. Raw final outage overload is 6.821e-13 MW and the
maximum source residual is 7.751e-10, below the unchanged 1e-5 tolerance.
Source-linear minus true-source cost is +8.382e-9. These supplementary quality
checks are diagnostic-only and do not redefine the original acceptance policy.

Each solve processed **one top-level node**, with 26,832 / 25,817 / 23,546 LP
iterations and maximum internal sub-MIP depths 8 / 12 / 6. Logs establish
substantial nonempty root separation and internal MIP work, but do not qualify
an extended top-level search tree.

Actual solver-process debit was **109.737106087 seconds** of 600; the original
contained-arm endpoint was **150.133613374 seconds** of 1,800. An additional
outer safety monitor observed **151.852677099 seconds**. These are distinct
scopes, not quantities to sum. The per-MIP 60-second watchdog grace charges
actual elapsed time; it does not extend the 600-second budget. The arm includes
model generation/export/readback, solving and original checks; common setup,
offline terminal review and archival transfer are outside that endpoint.
There were no numerical retries, timeouts, interruptions, cleanup failures or
remaining experiment processes. **Times are unpaired observations, with no
speedup claim or comparison to historical runtime cohorts.**

## Publication and limits

This is a source/result report and replay index. It contains no solver binary,
complete raw run bundle or portable patched-runtime adapter. The existing
pristine recipe rejects this patched source identity; see the explicit guard
caveat in [REPLAY_INDEX.md](REPLAY_INDEX.md). Publication preparation performed
no build or optimization and leaves earlier reports unchanged.

The results support bounded experimental work on this exposed pathway with
explicit thread counts and the retained exception. They do not establish
universal correctness, production readiness, other-date/seed/network transfer,
a 1354-bus result, or an acceleration outcome.
