# Historical commitment advice: failed repair and a cheap abstention check

The fixed May-to-June history repair failed. HiGHS reported the restricted model infeasible after one 0.475-second native call; the complete qualification took 19.500 seconds. An independent exact row sum then explained why: the historical commitment lacked 319.271 MW and 811.662 MW of capacity for current load plus hard spinning reserve at hours 35 and 36.

The added module is an advisory necessary-condition check. It does not optimize, change HiGHS, establish dispatch/network feasibility, or implement a trained predictor. The existing [current SCUC pipeline](../current_scuc/README.md) and its [successful exposed May result](../may_current_scuc_20261006/README.md) are unchanged.

## What was tested

One independently checked May 1, 2017 seed-0 commitment was mapped to the exposed June 1 seed-1, 36-hour target. The temporal mask retained all 260 unit trajectories, or 9,360 commitment values. Only their current u bounds were fixed; all 28,080 original integer declarations, current source costs, rows and other bounds were preserved. The target was the existing hard-zero-shedding/shortfall model, with the original negligible-overflow quality endpoint.

The declared limits were 25 seconds requested native solve time, 30 seconds actual repair-process time, and 300 seconds actual whole qualification. Complete current native readbacks passed before and after fixing, with only u lower/upper bounds changed. Normal presolve left 4,577 rows and 6,987 continuous columns; the first root LP took 1,075 iterations and returned Infeasible. The process took 5.680 seconds, including loading, mapping and readbacks. No point was returned, so no subsequent original/source/direct-DC or 1,288-outage upper check ran. No U or global lower bound was admitted; all subproblem bounds were discarded. There was no fallback, alternate date, or second repair.

This is a failed restricted historical plan, not infeasibility of the unfixed June problem. It is also not a fresh full-solve speed comparison: historical label/seed construction was outside the qualification. A preceding preparation-only API-identity failure is preserved with zero native calls. The final preparation used authenticated same-case saved bundles with their historical authority explicitly retained, and freshly read back the actual integer target.

## Independent explanation

| Hour, one-based | Current online capacity MW | Current load MW | Hard reserve MW | Capacity deficit MW |
|---|---:|---:|---:|---:|
| 35 | 46,697.472846376 | 46,108.09358 | 908.65 | 319.270733624 |
| 36 | 46,697.472846376 | 46,590.96489 | 918.17 | 811.662043624 |

For each hour, sum the 260 current rows `p + reserve <= Pmax*u`, subtract the aggregate balance equality and the reserve lower row, and substitute the fixed columns. Every unfixed coefficient cancels. The exact calculation retains the two fixed-one balance auxiliaries, hard-zero shedding and shortfall, and binary64 coefficients as rational numbers. Both resulting inequalities are contradictory. The proof does not depend on an objective, network support or solver dual. Its matrix/request hashes and exact deficits are in `EVIDENCE.json`.

Independent readback verified all 36 combinations, 9,432 selected rows and 9,360 fixes. A relaxed per-unit ramp screen and singleton-bus normal/emergency capacity screen detected no additional contradiction; their passes do not establish dispatch or network feasibility. The aggregate deficit already suffices.

Across the three previously exposed chronological links, the descriptive source-only rule also rejects June-to-October at hour 20, even treating its five temporally released units as fully available: capacity is short by about 2,075.665 MW. October-to-December passes this necessary condition only. That did not trigger another repair. Only May-to-June has the exact current-matrix contradiction certificate here.

## Advisory guard and limits

`capacity_abstention.py` implements exact arithmetic on supplied finite values and an explicit nonnegative aggregate feasibility allowance. A released/unfixed unit contributes its current allowed maximum capacity. Unsupported soft-slack, incomplete or malformed inputs are distinguished from a proved capacity deficit. A pass means only that this necessary condition did not reject the advice. It never accepts a point, certifies a global bound, or claims network feasibility.

All supply, including any imports or storage, must be covered by the declared capacity envelope. Reserve products must share the stated capacity and have simultaneous additive requirements; overlapping or alternative products cannot be double-counted. The module checks data shapes and declarations, not the truth of the caller's model assertions.

The model contract is essential: each unit obeys `p + sum(reserve) <= Pmax*u`, balance has the supplied current load, and shedding and reserve shortfall are hard zero. A caller accepting numerical residuals must supply a conservative aggregate allowance covering that contract; a small rounding discrepancy must not become a false infeasibility claim. The module is standalone and is not wired into the production CLI.

Run the pure tests with `python -B -m unittest -v test_capacity_abstention.py` from this directory. They include feasible dispatch/reserve witnesses, released capacity, exact boundaries and allowance, plus unsupported/invalid inputs. The recorded run passed 10 pure test methods, including 1,936 enumerated feasible witness/hint/bound combinations. No solver, native API or network service is required.

A minimal exact-boundary example:

```python
from capacity_abstention import SUPPORTED_SCOPE, UnitBounds, assess_adequacy

result = assess_adequacy(
    horizon=1, units=[UnitBounds("g", [10], [1], [None])],
    load=[8], hard_reserve=[2], scope=SUPPORTED_SCOPE,
    complete_scope=True, hard_zero_load_shedding=True,
    hard_zero_reserve_shortfall=True,
)
assert result.status == "retain_unknown"
assert result.network_feasibility == "unknown"
```

The next history step is source-aware abstention, not another fully fixed plan selected after these outcomes. Four sparse, already exposed dates are functional fixtures, not a learned generalization dataset. See [the remaining data requirements](DATA_REQUIREMENTS.md). No new optimization campaign is released by this checkpoint.
