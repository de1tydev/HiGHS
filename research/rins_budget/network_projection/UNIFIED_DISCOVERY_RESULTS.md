# Unified discovery checkpoint — 2026-10-05

The June 1, 2017, PEGASE1354 36-hour trial completed with a checked original
upper of **$13,916,348.591578348**, numerical integer lower of
**$13,479,669.490115203**, and gap **3.137885621285791%**. This is a **negative
result** against the 1% target. Witness checks pass; advancement and source
soft-model closure remain false. There is no accepted speed ratio, held-out
result or solver-superiority claim. [Compact evidence](evidence/unified_discovery_v1.json)
projects the retained final result, outer receipt and evidence audit.

## Measured mechanism

This application-layer trial uses unchanged official HiGHS 1.15.1 development
commit [`d547a3ad8af5399651187fb0e133cf0e42615b82`](https://github.com/ERGO-Code/HiGHS/commit/d547a3ad8af5399651187fb0e133cf0e42615b82).
Fresh two-LP seeding is followed by two discovery MIPs with
`mip_max_improving_sols = 1`, then a normal proof MIP with the default
2,147,483,647 limit. Both discovery calls actually stop at SolutionLimit;
call 3 actually runs and stops at TimeLimit. Both discovery bounds are
discarded, and their raw master objectives are not admitted original uppers.
Only call 3 contributes the numerical MIP lower, after the retained
$0.000184796694903 printed-bound allowance.

| Call | Role | Process seconds | Recovered provisional original cost | New distinct / violated supports |
|---|---|---:|---:|---:|
| 1 | Discovery | 17.908129 | 17,045,017.684322760 | 6 / 5 |
| 2 | Discovery | 13.122803 | 15,196,732.376662644 | 2 / 2 |
| 3 | Proof | 422.742276 | 13,916,348.591578256 | No continuation |

Both carries select the best eligible checked point from this invocation and
pass exact current-master containment, binary and native checks; actual logs
admit both starts. Call 2 changes 545 retained columns (550 total) and improves
the same destination-master objective by $2,064,215.3612522315. The two
transition batches contain genuinely new supports under the stated exact
positive-scale identity test; this does not establish general redundancy
detection or identify the first genuine native improvement event. No prior
invocation's optimization state, basis or search tree is supplied.

Discovery points are provisional: call 2 has 848.8796525412347 MWh shedding.
Only the final point receives the independent physical checks and admitted
upper. All **28,080 source-derived binaries**, original matrix and complete
literal rows pass without rounding; the source and direct-DC checks cover all
**1,288 listed outages** and **66,360,168 nonself pair-hours**. The 703 unlisted
outages remain excluded. Final shedding and reserve shortfall are zero;
overflow is **1.2791126664524202e-6 MWh**, below the 1e-5 MWh guard, and direct
post-slack violations are zero. The lower concerns the **literal binary64 LODF
integer model**, not an exact tree proof or an exact physical-DC lower
certificate. The upper is a numerically checked witness.

## Accounting, recovery and limits

The shared 600-second process ledger uses **541.2564292169991 seconds**, leaving
**58.743570783000905** unused. Its six stages include seeding and both carries;
nested helpers are charged once. The authoritative whole invocation is
**1,102.960181973991 seconds of 1,800**, through exact process reap, including
checking, stage persistence, cleanup and recovery pauses. It is not pure
HiGHS time. Return code 2 records the completed negative result; no watchdog,
health error or surviving descendant is recorded.

A post-launch persistence-controller naming guard required a correction from
the old directory-family test to exact approved run-directory equality.
The audit reconstructs the recorded executed-body hash from that exact change;
execution provenance itself is recorded, not replayed. Frozen numerical source
is unchanged, all 839 source pins match, and clocks/deadlines were not reset.
There is no claim that the entire executed controller was byte-frozen before
launch. The initial tiny naming failure remains a failure; corrected limited
tiny testing reached expected support exhaustion without exercising proof
call 3. This full trial now supplies that observation.

All nine stage acknowledgement and cleanup chains pass the retained-evidence
audit. Historical archive/readback checks are receipt-based after cleanup;
the audit reran no solver or physical checker. The ninth stage contains
pre-acknowledgement state: final result and completion were written afterward.
Those finalized files, the outer receipt and audit are preserved in a separate
233-member terminal capsule, SHA-256
`21f86ebea4698c2d20c5dd96e1f231528bda00dc2a290f49354e2237d9a2344d`.
Its sealing/readback was administration after the measured invocation, not a
rescore or extra optimization time.

The earlier [2.625640665% result](EARLY_DISCOVERY_RESULTS.md) and this 3.137885621%
result are distinct retained outcomes, not a matched performance comparison.
A prospective parallel method is being designed separately and has no measured
result here. [Historical failures](RESULTS.md), [correctness advisories](../CORRECTNESS_ADVISORY.md)
and [pristine validation limits](../portable_pristine_reference_replay_v3/VALIDATION.md)
remain unchanged. This addendum publishes compact evidence only; it neither
publishes the full trial harness nor expands the [existing tiny replay](README.md)
validation scope.
