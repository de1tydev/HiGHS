# Transfer checks and UC-relaxation pilots: negative results

These follow the initial-root IPX pilot. They do not establish substantial or stable acceleration. Normal solver defaults remain unchanged. The same pinned experimental binary contains both default-off patches; all settings below are explicit. These are custom public-source DC unit-commitment models, not a claim of UC.jl formulation parity or production-system validation.

## Initial-root IPX on PEGASE89

Both arms use two threads, parallel search off, outer-gap return/logging enabled, seed 0, and the same twelve initial valid security pairs. Only the initial-root IPX option changes. Every arm starts cold; every new incumbent must pass all 192 source-listed outage checks, or violating pairs are added and the master is solved again. There is no inherited incumbent or basis between arms/rounds. The 600-second cap is **summed solver-child process wall across all rounds**, unlike the internal HiGHS time request in the earlier PEGASE1354 experiment. Whole-loop time includes generation, independent checking and re-separation.

| Public date | Arm | Solver process s | Whole loop s | Rounds | Final numerical gap |
|---|---|---:|---:|---:|---:|
| 2017-02-01 | choose | 28.010 | 29.715 | 1 | 0.9861% |
| 2017-02-01 | initial-root IPX | 39.186 | 40.944 | 1 | 0.9470% |
| 2017-08-01 | choose | 89.384 | 92.826 | 2 | 0.9994% |
| 2017-08-01 | initial-root IPX | 103.959 | 107.397 | 2 | 0.9972% |

The candidate's whole-loop time increased by **37.8%** in February and **15.7%** in August. These are one-seed exploratory observations, not stable regression estimates. Together with the failed larger-date target completions in [INITIAL_ROOT_IPX.md](INITIAL_ROOT_IPX.md), they do not support promoting the root-only option as a general acceleration.

All four final source-primal checks passed all **192 listed** outages. Eighteen of 210 possible line outages are not listed, including two non-islanding lines; this is not an all-single-line or AC-security claim. February has zero shedding/overflow. Both August points have approximately **312.105451 MWh of source-allowed load shedding** over 36 hours and zero overflow. They are valid points of the soft model, not zero-shedding operational schedules. August's two rounds expanded from 12 to 23 security pairs in both arms; all round costs are retained.

This measures transfer conditional on the same pre-existing twelve-pair screen, not cold-screen discovery. Bounds come from the relaxed screened master and are accepted only with a fully checked incumbent; the certificates include conservative printed-bound allowances. The independent checker validates the primal/objective, not the solver's dual proof. Full numeric records, model/solution hashes and the measured driver hash are in [pegase89-root-ipx-transfer.json](recorded_results/pegase89-root-ipx-transfer.json).

## UC relaxation followed by network lift and repair

Scope: February PEGASE1354, 36 hours, **base-network only**, with unchanged source-allowed penalized shedding, overflow and reserve shortfall. The original full model has 381,268 rows and 313,776 columns. Both protocols below retain the original objective and all source semantics. The initial-root IPX option is false; outer-gap return/logging is true; both use two threads, parallel search off, and choose LP engines.

The UC relaxation retains commitment, generation, ramps, reserves, segments, startup costs and shedding, replacing the network with aggregate balance. Every original network-feasible point projects to this UC relaxation, and only nonnegative overflow penalties are dropped. Thus its valid global lower bound remains valid for the original objective. A UC primal is **not** an original upper bound until DC reconstruction and both the frozen source checker and every original MPS row/bound/integrality/objective check pass.

A fixed-commitment network LP fixes **all u/y/z** to an eligible schedule. Its checked primal can improve the upper bound. Its restricted lower bound is **never** used as a global bound. None of these trials transfers a basis into a new full MIP.

### Protocol v1: negative matched pilot

Predeclared allocation: UC up to 120 requested seconds at 0.5% gap, fixed-commitment repair up to 60 seconds, then a fresh full MIP with the checked start and the remaining requested allocation. Requested limits sum to at most 600 seconds; each next call also respects the remaining measured solver-process allowance. Unused requested allocation is not recycled. Both arms freshly generate the original model; all setup, lift, repair and validation work is included in E2E time.

| Arm | Solver process s | E2E s | Checked upper bound | Valid global lower bound | Gap | Target reached |
|---|---:|---:|---:|---:|---:|---|
| Fresh full-MIP control | 523.606 | 549.565 | 19,051,753.242198 | 18,960,413.053060 | 0.4794% | Yes |
| UC/repair/full-MIP pipeline | 560.373 | 604.996 | 19,214,862.094425 | 18,960,413.053060 | 1.3242% | No |

The initial UC stage provided a full-network-feasible point, and the repair did not meaningfully improve it. Starting the full MIP incurred a new cold root LP; the pipeline still missed 1%. The E2E elapsed ratio is **not** a time-to-target speedup ratio because the pipeline did not reach the target. Its E2E time above 600 seconds is retained: the cap applies to solver stages, while setup/checks are additional.

### Protocol v2: longer uninterrupted UC, also negative

A separate predeclared diagnostic allocated UC up to 480 requested seconds at 1%, then at most one fixed-commitment repair up to 120 seconds. It had **no full-MIP fallback**. All distinct complete retained UC incumbents were lifted and checked after UC completion, in chronological order, including validation costs even if an earlier point had met the target. A fresh matched control was conditional on success; that condition failed, so no v2 control ran.

- Actual UC process wall: 481.202459 s; internal reported time: 480.03 s
- Repair request was reduced to 118.797541 s after the UC process overshoot; actual repair process wall: 8.479868 s, reported LP time: 5.76 s
- Sum of requested limits: 598.797541 s; actual solver-process wall: 489.682327 s
- All auxiliary child wall: 37.688968 s; authoritative complete-arm E2E: **530.729400 s**
- Final checked upper: 19,214,862.094425; valid UC-only lower: 18,887,471.913161; gap: **1.7038383%**, missing 1%
- No watchdog kill or aggregate solver-budget breach

The 480-second UC checkpoint file is **byte-identical** to v1's 120-second file: the longer stage found no new incumbent. All three distinct UC lifts and the repair passed both original checks. The final UC output duplicated the third checkpoint exactly and was not rechecked a second time. The best point has zero shedding/overflow; the earlier worse point retains 838.813077 MWh of source-allowed shedding. Repair changed the best objective only at floating-point accumulation scale.

This diagnostic must not be compared with the old v1 control as a formal new paired speedup: the all-incumbent processing policy and execution episode differ, and the diagnostic missed the target anyway. No further UC budget tuning is justified by these observations alone.

## Evidence, accounting and reproducibility scope

The machine-readable [pipeline record](recorded_results/uc-network-pipeline-negative.json) retains exact stage limits, per-child `wait4` resources, checks, points and certificate provenance. Bounds are solver-reported and adjusted conservatively for twelve-significant-digit log rounding; feasibility/objective checking is independent and floating-point, not an exact rational certificate. Killed or invalid-status runs cannot supply a bound. Soft-limit overshoot and missing reported fields are retained rather than hidden.

The source exporter/checker, solver patches and source commit remain the pinned versions already identified in this package. These compact records publish the negative findings and measured specialized driver identities. Portable packaging of the newer orchestration harnesses is not included in this checkpoint; do not mistake these records for a complete executable replay bundle for every protocol. The unchanged original model remains the checker authority for subsequent formulation experiments.

## Joint startup/shutdown capacity cuts: negative paired pilot

A subsequent narrow formulation experiment appended valid inequalities to the
same February full-network model. It changed neither the solver engine nor the
original rows, columns, costs, bounds or slack policies. For a generator with
minimum uptime at least two hours, let a=Pmax−min(startup_limit,Pmax) and
b=Pmax−min(shutdown_limit,Pmax). For t before the last period, and only when both
a and b are positive, the added row is:

    p_t + sum(reserve_t) <= Pmax*u_t - a*y_t - b*z_(t+1)

The original minimum-up row at t+1 forbids simultaneous startup at t and shutdown
at t+1 for integer-feasible schedules. The new inequality therefore equals an
existing capacity inequality in each admitted integer case. It can strengthen
the fractional relaxation. It must not be applied with these coefficients to
one-hour-minimum-up units, and no post-horizon transition is assumed.

There are 170 eligible units and 35 applicable periods, adding exactly 5,950 rows
and 29,750 nonzeros, zero columns. An append audit recovered the entire original
MPS byte stream exactly and checked the source-derived antecedent rows and
binary domains. The solver-free suite passed 28 tests, including 144,342 selected
capacity comparisons over 7,230 valid schedules and an explicit fractional
witness. A separate 16-solve tiny smoke passed all eight original/cuts optimum
comparisons with presolve on/off and all 24 original-primal checks.

The cold seed-0 pair used the same two-thread/parallel-off configuration and
600-second request per arm as above, with fresh generation in both arms:

| Metric | Original | Original plus cuts |
|---|---:|---:|
| Reported solver seconds | 506.96 | 521.31 |
| Solver-process seconds | 509.777 | 524.071 |
| Full E2E seconds | 542.522 | 564.704 |
| Final gap using checked primal | 0.4794% | 0.5427% |
| Checked original upper | 19,051,753.242198 | 19,063,880.505653 |
| Adjusted solver lower | 18,960,413.053060 | 18,960,413.053060 |
| Presolved rows/columns/nonzeros | 242,511 / 158,424 / 929,996 | 248,017 / 158,270 / 958,478 |

Both arms reached 1%, but cuts were **2.80% slower in solver-process wall** and
**4.09% slower E2E** in this fixed-order pilot. The cut transformation/audit cost
8.481 seconds is included. The initial root bound improved only 15.92 objective
units; the final lower bound was identical. All six distinct incumbent checks
passed against the unchanged source and every original MPS row/bound/objective.
Both best points have numerical-zero shedding and zero overflow. No dropped
coefficients, watchdog kill, or solver-wall budget overshoot was observed.
This is a negative acceleration result, not a general slowdown estimate.

One provenance limitation is explicit: the main binary/library and source were
pre-pinned, but the loaded HIPO-off `libhighs_extras.so` stub was hashed only after
the run. Its post-run hash is retained; it is not presented as a historical pin.
Future protocols pin both libraries before execution. See the full
[joint-cut record](recorded_results/joint-capacity-cuts-negative.json), including
per-PID resources, hashes and all timing differences. As with the other newer
specialized protocols, this results checkpoint is not a complete portable
orchestration-code release.

## Sparse-angle substitution: stopped after the presolve gate

A separate application-layer candidate eliminated explicit line-flow variables
by substituting the original `f=w*(theta_source-theta_target)` equations into
nodal balances and normal-rating rows. It retained the original reference,
parallel-line ratings, every overflow variable/cost and all ordinary UC records.
No capacity cuts or other modifications were combined with it.

Eight tiny algebraic fixture groups passed. Three existing vector files, containing
two distinct incumbents, passed projection/reconstruction and the original source
and full-MPS checks; retained values stayed bitwise unchanged and original
linear objectives were unchanged. The maximum reconstructed original-row
residual was 9.87e-8, within the unchanged 1e-5 check tolerance.

A bounded **public presolve-only** inspection then gave:

| Model | Loaded rows/columns/nonzeros | Presolved rows/columns/nonzeros |
|---|---|---|
| Original | 381,268 / 313,776 / 1,232,543 | 242,511 / 158,424 / 929,996 |
| Sparse angles | 309,592 / 242,100 / 1,149,131 | 243,698 / 158,162 / 958,632 |

Despite the smaller raw input, the candidate had 0.49% more presolved rows,
0.17% fewer columns and 3.08% more nonzeros. No conditioning benefit was measured.
It was stopped here: **no full LP/MIP solve and no time-to-1% result**. The 4.935 s
presolve observation is not a fresh timing pair against the historical original;
no presolve speed ratio is claimed. Both libraries were pre-pinned and their
actual load paths verified, with no coefficient-dropping warnings.

The experiment also records a certification limit: serializing aggregated
coefficients changes some equalities by rounding (maximum reader-space
substitution error 1.819e-12, 0.59375 ULP). Successful original-primal checking
does not supply an unconditional original-model lower bound. No such bound or
original-MPS gap claim is made. Details and resource caveats are in the
[presolve-gate record](recorded_results/sparse-angle-presolve-gate.json).
