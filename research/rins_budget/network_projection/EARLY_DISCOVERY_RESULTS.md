# Early discovery with checked incumbent carry — 2026-10-05

The completed June 1, 2017, PEGASE1354 36-hour trial is a **negative result**:
checked original upper **$13,843,098.438742805**, numerical integer lower
**$13,479,628.416815203**, relative gap **2.625640665%**, above the 1% target.
The final witness and local evidence audit pass; advancement and source
soft-model closure remain false. There is no accepted speed ratio or held-out
result. [Compact evidence](evidence/early_discovery_v2.json) preserves every
master, the final checks, accounting, earlier failures and provenance hashes.

## What was measured

This is an application-layer experiment using unchanged official HiGHS commit
[`d547a3ad8af5399651187fb0e133cf0e42615b82`](https://github.com/ERGO-Code/HiGHS/commit/d547a3ad8af5399651187fb0e133cf0e42615b82),
not a C++ solver change. Fresh two-LP seeding supplies the projected network
cuts. Only the first top-level MIP sets the standard option
`mip_max_improving_sols = 1`; heuristic child MIPs inherit that option with
their own counters. Calls 2 and 3 retain the default unlimited improving-solution
limit, 2147483647. Each is a fresh proof solve with a checked, complete canonical
start from an earlier point in this invocation. No historical optimization
state, basis or search tree is supplied.

Both carried starts preserve retained point bits and original binary domains,
use upward-rounded full-network eta values, pass exact current-master and
native feasibility checks, and are admitted as feasible in the actual solver
logs. Carry preparation makes no optimizer call, new factorization or full
network scan. Option getter reports use a separate probe handle; execution is
supported by the pinned option files, native identities and actual solve logs.

| Call | Role / stop | Process seconds | Projected objective | Recovered original provisional cost | Shared overflow MWh | Provisional gap |
|---|---|---:|---:|---:|---:|---:|
| 1 | Discovery / solution limit | 13.633291 | 14,033,147.062303314 | 17,045,017.684322760 | 602.374124404 | 20.945268146% |
| 2 | Proof / time limit | 121.196829 | 13,952,454.440342850 | 14,140,755.779285235 | 37.660267788 | 4.695901747% |
| 3 | Proof / time limit | 326.918963 | 13,843,098.432787996 | 13,843,098.438742750 | 0.000001190951 | 2.625640665% |

All three lifts pass the original matrix, binary and complete literal-network
checks; shedding and reserve shortfall are zero for each. Only call 3 receives
the final independent physical checks and admitted original upper. The first
call's raw objective and bound are diagnostic only: its provisional interval
uses the fresh exact LP lower, $13,474,893.024853207. Calls 2 and 3 supply eligible
numerical MIP lowers of $13,476,719.781615233 and $13,479,628.416815203 after the
conservative printed-bound allowance. The method uses two seed cut batches and
two between-master batches.

At the final point, projected objective and admitted original upper differ by
only **$0.005954809**. The remaining **$363,470.021927602** interval is an open
integer proof/incumbent gap; material network underpricing at that point does
not explain it. This observation does not establish a faster algorithm or
predict the outcome of another call schedule.

## Final witness and scope

All **28,080** source-derived binary values pass without rounding, with zero
integrality residual. Original literal rows, the independent source checker
and the direct-DC checker pass. Coverage includes all **1,288 source-listed
outages**, **66,360,168 nonself pair-hours**, **103,104 signed normal rows** and
**132,720,336 signed security rows**. The 703 unlisted outages remain excluded.

Load shedding and reserve shortfall are zero. Shared overflow is
**1.1909507975360614e-6 MWh**, maximum **9.814220902626404e-8 MW**, costing
**$0.005954753987680307**. Each positive slack total is below the declared
1e-5 MWh guard. Final direct-DC post-slack violation is zero; original matrix
row and bound residuals are 4.297078248782782e-10 and 2.154e-10.

The upper is a numerically checked physical witness. The lower is a numerical
HiGHS bound for the **literal binary64 LODF integer model**, not an exact tree
proof or an exact physical-DC lower certificate. Physical primal checks do not
change that lower-bound domain. The tiny protective overflow is not exactly
zero and does not turn the missed 1% target into a success.

## Accounting and evidence limits

The 600-second charged process ledger totals **541.142117302 seconds**: fresh
LP seed 59.805153385; discovery 13.633291377; carry 9.479009931; proof
121.196829131; carry 10.108870859; proof 326.918962619. Nested carry helpers are
charged once. All allocations pass; the 58.857882698 seconds remaining did not
fund another solve. Final physical checking is within the whole clock.

The authoritative whole invocation is **1,040.611957914 seconds of 1,800**,
from immediately before launch through exact process reap, including campaign
preparation, checking, serialization, archival and cleanup. It is not pure
HiGHS time. The runner returns 2 for the completed negative outcome; there is
no watchdog, health error or surviving descendant. Sampled peak tree RSS is
2,611,490,816 bytes; minimum sampled free disk is 11,805,196,288 bytes.

This trial uses a **512 MiB Python / 64 MiB native per-file policy** and removes
duplicate compressed/readback stage copies only after verified archival
acknowledgement. That retention policy differs from earlier trials, so their
whole times are not a controlled speed comparison. All nine stage
acknowledgement, manifest and cleanup chains agree. The independent local audit
passed 1,103 checks over 910 unique local files, including all 742 source pins.
It authenticated historical archive/readback receipts without downloading the
nine archives again; it ran no solver or new physical check. The finalized
result and outer receipt are preserved in the separate complete terminal
archive identified in the compact evidence. Large archives are not bundled
with this public summary.

## Earlier failures remain failures

- Carry v1 saved a 2.995223448% gap, already above target, but was killed by the
  disk-headroom gate during final archive sealing after 979.338654249 whole
  seconds. Its 541.166070247-second ledger and checked saved witness do not
  repair the missing final result and terminal acknowledgement
- Early-discovery attempt 01 stopped on storage admission after 205.301551460
  whole seconds and 73.295573185 charged seconds. It never reached the first
  carry into call 2 or the final physical check, and admitted no final upper

Neither failed invocation is rescored or used as a speed-ratio denominator.
The [earlier checkpoint](RESULTS.md) retains the other rejected outcomes and
correctness advisories. The published [core and fixed tiny recipe](README.md)
keep their existing validation scope: this result does not publish or validate
a portable full 36-hour entrypoint.
