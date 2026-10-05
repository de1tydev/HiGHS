# Four-thread first-discovery checkpoint — 2026-10-05

The completed June 1, 2017, PEGASE1354 36-hour trial is a **negative result**:
checked original upper **$14,140,755.779285314**, numerical integer lower
**$13,493,992.67771506**, relative gap **4.573752009%**, above the 1% target.
The selected witness passes full soft-model numerical checks but has material
network overflow. Neither the secure benchmark target nor advancement passed;
there is no held-out result or accepted speed ratio.
[Compact evidence](evidence/parallel_mip_v1.json) records the measured calls,
checks, accounting and provenance hashes.

## Method and activation

This uses the pristine official HiGHS development commit
[`d547a3ad8af5399651187fb0e133cf0e42615b82`](https://github.com/ERGO-Code/HiGHS/commit/d547a3ad8af5399651187fb0e133cf0e42615b82).
The application-layer method is the same
[first-discovery-only schedule with checked incumbent carry](EARLY_DISCOVERY_RESULTS.md):
two fresh LP seeds, one discovery MIP with `mip_max_improving_sols = 1`, then
two fresh proof MIPs with the default unlimited improving-solution count.
The only production algorithm option changes are `parallel: off → on` and
`threads: 2 → 4`; concurrency simulation remains false. No historical
optimization state, basis or search tree is supplied. The original coordinator
was unchanged, with no amendment during this trial.

The preceding tiny off/2 and on/4 checks both matched the $1540.5 reference and
passed full source/physical checks. Official `bell5` finished Optimal in both
arms at **8,966,406.49152**, with all **58 ordinary integer variables** checked.
Its main-MIP simplex scheduler IDs were **0** versus **0, 1, 2, 3**, supported
by nonsimulated dispatch inspection. This subsecond fixture establishes
activation, without measured temporal overlap or a speed claim.

In the June trial, call 3 performed main-MIP simplex work on all four IDs,
with **115 nodes** and **298,754 LP iterations**. Calls 1 and 2 reported zero
nodes and main-MIP simplex work only on ID 0; their extra thread activity was
analytic-center work. Nested profile times are not additive wall-clock costs.

## Selected witness and failure

Call 3 reduced the projected objective to **$13,910,534.633444283**, but its
fully priced original provisional cost rose to **$14,793,922.395080075**.
This substantial underpricing prevents treating the projected objective as an
original upper. The minimum-original-cost rule selected **call 2**, followed
by independent source and direct-DC checks of that point.

All **28,080 original binaries**, original matrix rows, full literal-network
rows and direct checks of **1,288 source-listed outages** passed after shared
slack. Coverage was **66,360,168 nonself pair-hours**; 703 unlisted outages
remain excluded. No binaries were rounded. Shedding and reserve shortfall
were zero, but shared overflow was **37.66026778847732 MWh**, maximum
**21.94818813973075 MW**, costing **$188,301.3389423866**. The negligible-slack
guard therefore failed. The raw `quality_failed: false` flag denotes numerical
QA only; it does not qualify a secure endpoint.

The lower subtracts the frozen printed-bound allowance from call 3's native
bound. It concerns the **literal binary64 LODF integer model**, not an exact
MIP proof or exact physical-DC lower certificate. The final TimeLimit/
`HighsStatus::Warning` and **2.276e-11** inconsistent-bound diagnostic were
admitted under the unchanged policy with passing raw-master primal QA.
Warnings, including scaling advice, remain recorded; no threshold was relaxed.

## Accounting and evidence

The charged seed/carry/MIP process ledger was **542.2152179180121 / 600 seconds**,
leaving **57.78478208198794 seconds** unused. Whole invocation time through exact
reap was **1055.9335038169957 / 1800 seconds**, including checking, serialization,
archival and cleanup. Exit 2 intentionally records failed advancement; cleanup
completed with no surviving descendants. Outer sampled tree RSS was
**3,362,156,544 bytes**; the separate stage sampler observed **3,362,230,272 bytes**.
These samples occur at different instants, can double-count shared pages and
do not establish an absolute memory peak.

The read-only terminal audit matched 793 source pins, 303 loaded-runtime
hashes, all nine archive/cleanup chains and 137 stable terminal artifacts.
Rejected packaging V1 pinned an empty freeze log; its preserved V2 correction
changed packaging metadata before numerical execution. The finalized raw
capsule has **232 members**, **81,922,582 bytes**, SHA-256
`cbb1c08adb32704ce3919bc7696f083e3acef53aca1bd1ccc4588d22086333d8`.
This public summary adds no solver code, benchmark rerun, CI result or portable
36-hour replay claim. Earlier reports and the [existing tiny recipe](README.md)
retain their historical scope.
