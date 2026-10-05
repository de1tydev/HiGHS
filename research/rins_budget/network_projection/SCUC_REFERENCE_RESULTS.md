# June1354 conventional completion comparison

Recorded 2026-10-05 on the exposed 36-hour PEGASE1354 June 1, 2017 case,
with random seed 0. The [projected candidate](SCUC_TARGET_RESULTS.md) passed
the 1% integer target. A fresh conventional workflow using uninterrupted
ordinary proof did not produce a full-target feasible upper within its
600-second contained-process budget. This is a completion contrast for one
development sample, with no speed ratio, timeout-derived speedup, repeatability
or general acceleration claim.

Independent terminal audit passed for the conventional run's evidence and
classification; the run itself did not reach the target. Its final capsule
was archived and its actual bytes verified by readback.

| Quantity | Projected candidate | Conventional ordinary proof |
| --- | ---: | ---: |
| Full-target checked upper | 13,779,019.591303479 | None admitted |
| Conservative numerical MIP lower | 13,741,689.973312583 | 13,603,099.016513968 |
| Same-run exact projected-LP lower | 13,736,286.327225514 | No LP seed |
| Target interval against checked upper | 0.270916% numerical; 0.310133% exact-LP | Unavailable |
| Charged contained-process ledger | 143.402847636 / 600 s | 597.608062564 / 600 s |
| Whole invocation including checks and stage archives | 555.937916431 / 1,800 s | 695.883742347 / 1,800 s |
| Complete literal scan | Passed | Failed at two newly found pairs |
| Final independent source and direct-DC checks | Passed | Not run; no eligible target point |

## Why the conventional arm did not complete

The conventional arm retained original DC angles and flows, all 28,080
source binaries and original costs. It started with an empty security-pair
cache after exact removal of 144 historical rows, and used ordinary HiGHS
proof with a 595-second native limit inside a 600-second process allocation.
It used no LP seed, first-start rows, projected cuts, incumbent input, basis,
tree or carry state. Its policy permits at most three cold proof calls, with
a further call requiring newly witnessed original security rows.

The one launched solve returned cleanly at its native time limit, reporting
595.35 native seconds, a master incumbent cost of 13,790,007.905913303 and a
1.36% master gap. Current-master row, bound and binary checks passed, as did
the hard-zero and positive-slack guards. The subsequent complete literal
scan covered all 66,360,168 monitored pair-hours and found two new violated
pairs, with a maximum conservative violation of 272.1136523157682 MW.
Consequently, that incumbent cost is not a target upper, and the 1.36%
solver report is not a full-target interval.

All 144 original security rows for the two discovered pairs were appended
over every finite hour and both signs. Only 2.391937436 process seconds
remained, below the required 5-second launch margin, so no changed-master
proof was launched. No eligible full-target point reached the final physical
checker. The run completed its records and all three stage acknowledgements,
with no watchdog kill or surviving process. Its raw outcome is
`actual_or_whole_time_censoring`; here the binding limit was the remaining
contained-process budget, not the 1,800-second whole-invocation cap.

The raw native log retains an `Inconsistent max bound violation` diagnostic
of 7.171e-7 and the expected time-limit warning. The unchanged independent
current-master checks measured a maximum row residual of 7.16945119e-7,
below the inherited 1e-5 primal tolerance. Terminal audit verified admission
under the frozen diagnostic rules and source pins; no warning-free execution
or relaxed tolerance is claimed.

## Common target and distinct methods

Both arms used the same pinned source data, serialized original MPS, current
runtime and unmodified official HiGHS commit
`d547a3ad8af5399651187fb0e133cf0e42615b82`, with seed 0, two configured
threads, parallel mode off and presolve on. The common hard-zero target changes
only the 22,356 originally positive shedding upper bounds to zero; the other
26,388 shedding bounds and all 36 reserve-shortfall bounds were already zero.
The positive-sum guard remains 1e-5 MWh for each slack category.

The candidate combines a complete 5,148-row source-valid first-start family,
adaptive per-line network-value cuts, two fresh seed LPs, one first-discovery
MIP and one permitted same-master discovery-to-proof transition using a
verified current-run start. Its charged ledger includes seed, discovery,
start preparation and proof. The conventional arm gives its first ordinary
proof the full remaining allocation and separates new original rows afterward.
This comparison therefore covers an application/formulation and allocation
policy bundle; it does not isolate a HiGHS internal patch or a single mechanism.

The candidate's final upper passed original-source feasibility and cost,
unrounded binary, literal-network and independent direct-DC checks for all
1,288 source-listed outages. Shedding and reserve shortfall were zero; positive
shared overflow was 9.48365595832e-7 MWh. Its fresh exact LP lower belongs to
the actual one-installed-batch seed matrix. The later numerical MIP lower is
a separately admitted solver report. Both apply to the hard-zero integer
subset of the stored literal binary64 LODF model, not the old soft optimum or
larger negligible-shedding domain. Physical upper feasibility is numerical at
the inherited tolerances; no exact physical-DC lower bound is certified.

## Clock boundary and retained history

Both clocks start from pinned serialized original MPS and source data.
Earlier acquisition/export, environment recovery and build are outside both
clocks. Fresh run-specific transformation, factor preparation, export/readback,
checks, raw stage archival and cleanup are inside each whole-invocation clock.
The contained ledgers are measured process time, not native solver time.
Later independent audit and consolidated publication are separate research
administration. Neither arm imports historical points, lower bounds or search
state; the candidate also begins with an empty support bank.

The earlier `conventional-zero-01` attempt remains separately recorded as
infrastructure-censored: after a clean native time-limit return with no
solution (298.490106340 process seconds; 296.39 native log seconds), archival
acknowledgement missed its original 120-second deadline. It is not rescored,
combined with this run or used for a performance
inference. The earlier target report and all other published checkpoints
remain historical records; this addendum supplies the completed conventional
attempt that the target report still described as pending.

[Compact evidence](evidence/scuc_reference_v1.json) binds the raw results,
point checks, clocks, diagnostics, review and terminal archives by SHA-256.
These are commitments to retained evidence, not public retrieval links.
Full matrices, vectors and current runners are not bundled. The current method
still has no published, validated portable entrypoint; the existing public
source and fixed tiny replay exercise the earlier aggregate formulation.
Fresh confirmation cases and further matched experiments remain necessary
before a stable acceleration claim.
