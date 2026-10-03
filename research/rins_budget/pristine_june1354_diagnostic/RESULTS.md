# June1354: one pristine first-master diagnostic

**Terminal result: late diagnostic, no full-SCUC certificate.** One retained original empty-pair master reached the time limit with a numerical master gap of **1.4273%**. Its point passed the original-matrix primal check, but failed the full-source security check: **3 violating pairs, 24 line-hours, maximum overload 272.47338756793556 MW**. This is neither an on-time result nor a speed comparison.

## Scope and method

The historical input is `case1354pegase/2017-06-01`, using 36 hours. The native process started on **October 3, 2026, at 21:40:57.861316 UTC**. The data date does not describe the runtime. HiGHS was built from pristine [official development commit d547a3ad8af5399651187fb0e133cf0e42615b82](https://github.com/ERGO-Code/HiGHS/tree/d547a3ad8af5399651187fb0e133cf0e42615b82), with no private patch.

The run reused only the retained original integer model, containing **313,776 columns, 381,268 rows and 1,232,507 nonzeros**, with zero active contingency pairs. Fresh API readback matched all 16 fields before one native solve. Standard recorded options used two threads, parallel off, presolve on, seed 0, a 1% relative MIP gap target and a 600-second time limit; the full option projection is in [result.json](result.json). No primal, basis, cuts or heuristic state were inherited. The resulting point was checked against the original matrix and every specified source outage. This first-master observation excludes model construction and subsequent security-constraint rounds, so it is not a cold full-SCUC-loop benchmark.

## Checked outcome

| Quantity | Retained measurement |
| --- | ---: |
| Native child-process time | 604.3308834820054 s |
| Excess over 600-second on-time ceiling | 4.330883482005447 s |
| Native printed solve time | 601.55 s |
| Whole observation, including checks | 795.2188502909994 s |
| Source security coverage | 1,288 outages; 66,360,168 eligible pair-hours |
| Independently recomputed matrix objective | 13,800,283.938632872 |
| True source cost | 13,800,283.938632818 |
| Maximum original-matrix row residual | 5.997897289944376e-09 |
| Raw shedding | 2e-13 MWh |
| Shared overflow / reserve shortfall | 0.0 / 0.0 MW-hours |

The fixed primal tolerance was 1e-5. Raw shedding is tiny **but is not zero**. Both recorded source-security checks agree on the violating counts; the maximum residual after shared overflow is also 272.47338756793556 MW. A checked full-source feasible upper bound is unavailable. The solver-reported master lower token `13603318.4557` becomes **13,603,318.455513967** after the fixed display-rounding allowance; its numerical relative gap is **0.014272567433740583**. This bound is not an independently verified dual or rational proof.

## What the profile supports

The printed top-level **175.84-second Sub-MIP envelope** was productive: the subsequent incumbent improved by approximately **8.81%**. Late root separation showed diminishing displayed bound gains: between the 392.3- and 425.5-second progress rows, the bound increased by only **8.48008**. These are qualified observations: milestones are rounded, phase and thread clocks overlap, nested child times are already inside the Sub-MIP envelope, and the elapsed separation interval includes related root work and synchronization. They are not isolated removable costs or evidence that a shorter separation phase would preserve the same point or bound. The run stopped with **zero processed branch-and-bound nodes**; the end-of-root milestone does not establish completed root optimality or a completed search.

## Validation and limits

The terminal evidence audit verified 3,856 frozen files and 25 run artifacts, checked provenance and clean process teardown, and independently reproduced the original-matrix primal residuals and objective. It audited the recorded source/topology checks without rerunning them or the solver. The developer warning about a 5.998e-09 bound-violation discrepancy agrees with the recomputed residual and is below tolerance; the TimeLimit warning return is expected. This does not establish general solver correctness.

The current reference admission remains **168/169 CTest entries and 399/400 unit cases**, not a full pass. `AffinityReducedCoreCount` saw 5 cores rather than 1; missing CPU topology triggers an affinity-ignoring fallback, and the test does not check whether its affinity call succeeded. Explicit two-thread selection bypasses that automatic lookup. All other CTest entries passed across the initial and resumed runs; there was no successful complete CTest invocation.

Exact source, runtime, input, model, point, summary and terminal-audit hashes are in [result.json](result.json); [SHA256SUMS](SHA256SUMS) binds these two checkpoint files. The separate [pristine PG89 report](https://github.com/de1tydev/HiGHS/blob/fc0e7087d05f3b521eb44ebc77714b7596e6debd/research/rins_budget/pristine_pg89_results/RESULTS.md) and [public replay kit](https://github.com/de1tydev/HiGHS/blob/4dfbe79059174156572a918562403b3365d14aeb/research/rins_budget/portable_pristine_reference_replay_v3/README.md) provide reference context; their results are not pooled with this observation. No old-runtime ratio, policy benefit or full-SCUC certificate is claimed.
