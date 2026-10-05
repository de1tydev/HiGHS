# October1354 case-exposed validation

Recorded 2026-10-05 for PEGASE1354, October 1, 2017, 36 hours, seed 0.
The fresh projected candidate passed the 1% hard-zero SCUC target with a
checked upper of **11,736,221.140286218**, fresh exact projected-LP lower of
**11,732,175.309109941**, and **0.0344730312%** relative interval.
Its terminal evidence and post-exit archive records passed independent audit.

The conventional run ended without an admitted full-target feasible upper
inside its 600-second contained-process budget. Its independent terminal and
archive evidence audits **passed for evidence integrity; the scientific target
was not met**. This is a completion contrast on one exposed validation case,
with no successful-completion speed ratio or general acceleration claim.

| Quantity | Projected candidate | Conventional ordinary proof |
| --- | ---: | ---: |
| Full-target checked upper | 11,736,221.140286218 | None admitted |
| Fresh exact projected-LP lower | 11,732,175.309109941 | No seed LP |
| Conservative numerical MIP lower | Discovery bound excluded | 11,576,857.067234231 |
| Full-target relative interval | 0.0344730312% | Unavailable |
| Contained solver-process ledger | 97.685884136 / 600 s | 597.846746922 / 600 s |
| Compute, validation and local checkpoint work | 328.407928192 / 1,800 s | 648.999994709 / 1,800 s |
| Post-exit archive administration, separately measured | 136.835918915 s | 138.509979294 s |
| Complete literal scan | Passed | Failed at one newly found pair |
| Final independent source and direct-DC checks | Passed | Not run; no eligible target point |

## What was checked

All 28,080 original u/y/z binaries, including fixed binaries, passed without
rounding; their maximum integrality residual was zero. All 48,780 shedding
and reserve variables were exactly zero. Positive shared overflow was
1.6550779946555852e-7 MWh, below the 1e-5 MWh guard, and its original
0.0008275389973277927 penalty cost remains included in the upper.

The full literal scan covered 103,104 signed normal rows and 132,720,336
signed security rows. Both independent direct-DC reports covered all 1,288
source-listed outages and 66,360,168 eligible monitored pair-hours, with no
post-slack violation. Original-source feasibility and cost checks passed.
The audit verified 2,177 assertions, the frozen source, current point/model
bindings, five local checkpoint bundles, final result and clean process exit.
A separate addendum verified archive content bindings to upload/readback
records. That audit did not rerun optimization or physical evaluation.

The lower is an exact weak-duality certificate for the stored binary64
literal LODF **hard-zero shedding/reserve subset**. The physical upper is a
numerically checked witness. This is not an exact physical-DC certificate or
a bound for the original soft-shedding optimum or larger negligible-shedding
domain. Only the 22,356 originally positive shedding bounds were tightened;
26,388 other shedding bounds and all 36 reserve bounds were already zero.

## Methods and solver identity

The candidate combines network projection, source-valid complete first-start
prefix cuts, two fresh seed LPs, current-run network-value cuts and a cold
first-discovery MIP. There are 5,616 logical first-start prefixes: 5,580 rows
are installed for 155 positive-cost units, while 36 zero-cost prefixes for
one additional eligible unit are certified redundant by original bounds.
The omission rule was amended before optimization and does not select rows
from a solution. The first-start rows add no columns.

The seed process took 84.424618198 seconds and the sole cold MIP process took
13.261265938 seconds. The retained lower comes from the second fresh seed LP
with one installed network-cut batch; the MIP receives two fresh batches.
The MIP's reported discovery bound is excluded. No historical starts, cuts,
bounds, factors, basis or tree are loaded. The first MIP point sufficed, so
carry execution and start admission remain **untested**.

The conventional arm retains original DC angles, flows, costs and all source
binaries, starts with an empty security cache, and uses ordinary proof with
no first-start family, projected cuts, seed LP or carry. Its first allocation
is 595 native seconds inside a 600-second process limit, with a 600-second
aggregate process budget and 1,800-second whole limit. At most three cold
proof calls are permitted; another call requires newly witnessed original
security rows. Its terminal record reports a target miss, as detailed below.

Both arms use unmodified official HiGHS commit
[`d547a3ad8af5399651187fb0e133cf0e42615b82`](https://github.com/ERGO-Code/HiGHS/commit/d547a3ad8af5399651187fb0e133cf0e42615b82).
This is an application/formulation and allocation-policy bundle, with no
solver-kernel patch. The new control-only seven-stage disk admission and
completed-candidate binding revision preserves the previously frozen
conventional formulation and solve policy. Both arms target the same declared
hard-zero problem; their formulations and allocation policies differ as
described above. Exact source, arm, case, original-input and current-model
hashes are in the evidence.

## Why the conventional run did not complete

The sole proof solve returned normally at its native time limit, reporting
595.35 native seconds, a master incumbent cost of 11,897,581.748871416 and a
2.7% master gap. Current-master row, bound and all 28,080 binary checks passed;
all 48,780 hard-zero variables and every positive-slack category were zero.
The complete literal scan nevertheless found a new violated security pair,
with a maximum conservative violation of 72.83990428152744 MW at zero-based
hour 34, line l1202. The pair is monitored index 1201 and outage index 830.
This master cost is not a full-target upper; the printed 2.7% is not a
full-target interval.

The run appended 72 original rows for that pair over all 36 hours and both
signs. Only 2.153253078 process seconds remained, below the 5-second launch
margin, so no second solve was launched. The final independent source/direct-DC
worker correctly remained unrun because the returned control point failed full
literal checking. No claim is made that every intermediate incumbent was checked.
The numerical proof lower of 11,576,857.067234231 applies after the frozen
printed-bound allowance; it is not an exact certificate. The raw outcome is
`actual_or_whole_time_censoring`, with the contained-process budget binding
rather than the 1,800-second whole-run cap. No watchdog kill or surviving
process was reported; the controller returned its target-miss status.

The raw log retains an `Inconsistent max bound violation` diagnostic of
1.27e-8 and the expected time-limit warning. The existing numerical checks
and tolerances were not relaxed; warning-free execution is not claimed.
Independent terminal audit passed 4,352 assertions, verifying all 921 frozen
source files, including 906 inherited pins unchanged, and all three checkpoint
bundles. The separate archive addendum verified those bundles and the terminal
capsule against the recorded upload/readback evidence. Audit and archival
success do not change the scientific target miss or supply a feasible upper.

## Timing boundary and retained history

Both arm clocks start from the same pinned original serialized MPS and source
data. Each whole clock includes input loading, fresh transformation/factors,
export/readback, numerical and physical checks, local checkpoint creation,
shutdown and cleanup, through process reap. The contained solver ledger is
measured process time, not native solver time. Remote archival occurs after
exit and is measured separately under the same revised rule for both arms;
the recorded administrative endpoint precedes final archive-pointer fsync.
The candidate's 156.399073098-second physical-check process is already included
in its 328.407928192-second whole figure.

Preparation before either arm took 52.067110116 process seconds. Its measured
components include 26.215966230 seconds of common original-model generation,
5.762050814 seconds of common API readback, 7.830856826 seconds of
candidate-specific projection/serialization and 2.561938423 seconds of
candidate-specific API prevalidation. These components are not an exhaustive
sum. No optimization or presolve was called during preparation. The timed
candidate rebuilds fresh projection factors; prevalidation artifacts are
verification authority, not solver input or reused optimization state.
Acquisition, environment setup/build and later independent audit are also
outside the arm clocks. No earlier and current timings are combined.

October was preselected, but the earlier attempt failed its original
120-second remote-acknowledgement deadline despite on-time bytes. That failed
outcome remains preserved. A subsequent saved-point diagnosis exposed its
result before this fresh operational revision. October is therefore
**case-exposed validation**, not untouched heldout evidence. December remains
unopened. The [June comparison](SCUC_REFERENCE_RESULTS.md), prior failures,
negative results and existing correctness advisories remain historical records.

[Compact evidence](evidence/scuc_october_v1.json) records exact commitments,
terminal classifications, audit results and archive hashes. Hashes identify retained evidence; they are not
public retrieval links. Full matrices, vectors and current runners are not
bundled. The current full method still has no published, validated portable
entrypoint; the older source and fixed tiny replay exercise the earlier
aggregate formulation. Further fresh cases and matched experiments are needed
before any stable MILP acceleration or repeatability claim.

Source data: [UnitCommitment.jl October1354 instance](https://axavier.org/UnitCommitment.jl/0.3/instances/matpower/case1354pegase/2017-10-01.json.gz).
The existing [dataset attribution and license notices](README.md#license-and-attribution)
continue to apply.
