# Adaptive per-line checkpoint — 2026-10-05

The completed June 1, 2017, PEGASE1354 36-hour integer trial is a
**validated negative result**: checked original physical upper
**$13,831,712.357075134**, numerical integer lower **$13,479,885.498915201**,
relative gap **2.5436247449%**, above the 1% target. Full source, literal-network
and direct physical checks pass, including the negligible-slack guard.
The interval remains open; there is no held-out result or accepted speed ratio.
[Compact evidence](evidence/adaptive_line_v1.json) records the measured stages,
qualifications and provenance hashes.

This is measured research evidence only. **The published source and fixed tiny
replay remain the earlier aggregate formulation.** This checkpoint adds no
adaptive source or newly validated portable adaptive replay, and no portable
36-hour entrypoint. Earlier reports and warnings retain their historical scope.

## Method and preceding gates

The application-layer adapter introduces line/hour eta columns as lines become
active and installs their sparse support rows. It uses pristine official HiGHS
development commit
[`d547a3ad8af5399651187fb0e133cf0e42615b82`](https://github.com/ERGO-Code/HiGHS/commit/d547a3ad8af5399651187fb0e133cf0e42615b82),
with `parallel = off`, `threads = 2`, no private HiGHS patches or default changes.
Two fresh LP seeds feed the existing first-discovery-only schedule: one discovery
MIP with `mip_max_improving_sols = 1`, then two fresh proof MIPs with checked
incumbent carry. No historical basis or search tree is transferred. The second
seed's support is promoted without another solve; its exact LP certificate
continues to identify the original one-batch LP2 snapshot.

The preceding offline audit passed its declared saved-data arithmetic scope:
30 targets by 39 banks, 589 emissions, 518,909 sparse entries and 17,670 row
checks. It did not establish an LP/MIP endpoint or a new physical upper.
The actual installed-bank reprice was $14,249,565.926249204, above the checked
prior carry upper by $108,810.14696388991. Serialized sparse coefficients were
checked exactly, but not independently regenerated from a retained full LODF
array; no new physical scan was performed. The earlier run remains preserved.

The continuous adaptive LP closed its numerical full-scope interval after two
solves and one installed batch: exact current-matrix lower
$13,474,893.024913887, numerical upper $13,474,893.031143501, absolute difference
$0.0062296148389577866. Two active lines added 72 eta columns, 19 rows and
16,739 cut nonzeros. The final generic LP stationarity residual
**3.519913479976822e-5 exceeds 1e-5**; the recorded gate substituted the
independently reproduced exact current-matrix certificate. This is neither
integer feasibility nor an exact physical-DC lower certificate.

Failed tiny05 remains preserved: a receipt-cache `TypeError` prevented completion.
The isolated V2 correction restored that cache interface without changing
numerical policies. Tiny06 passed the $1540.5 full integer reference, original
and physical checks, and adaptive column/carry checks. Its candidate stopped
naturally; a separately labeled changed-master component verified native and
CLI start admission and contributed no candidate endpoint. The discovery event
stop was not activated by this tiny fixture. An earlier broad source-check
attempt invoked synthetic direct-DC factorizations; it is not a pure or
factorization-free check. These records are not new validation runs for this
publication.

## Integer result and accounting

The three masters used **2, 3 and 3 active lines**. Four installed batches and
five point evaluations produced **70,480 cut nonzeros**. Both carries rebuilt
all 108 current line/hour etas, preserved 141,804 retained binary64 values and
passed exact/native current-master checks and actual CLI start admission.
The final trace records **99 elementary requests**; the top-level **80** is the
earlier installed-state tally. All caps passed.

Call 3 supplied the selected original witness. All **28,080 binaries** were
exact without rounding. Direct checks covered **1,288 source-listed outages**
and **66,360,168 nonself pair-hours**, with zero violated pairs after shared
slack; 703 unlisted outages remain excluded. Shedding and reserve shortfall
were zero; shared overflow was **1.2199093362141868e-6 MWh**.

The final lower is call 3's printed MIP bound minus its frozen rounding
allowance. It is a numerical bound for the **literal binary64 LODF integer
model**, separate from the checked physical upper. The exact seed LP lower is
$13,474,893.024913887; the discovery-call bound is excluded. There is no exact
MIP certificate or exact physical-DC lower claim. Native
`HighsStatus::Warning` returns remain recorded for all three calls; the two
proof calls ended at TimeLimit. The raw `source_soft_model_complete: false`
means the 1% interval was not qualified, despite passing source/physical checks.

The charged seed/carry/MIP process ledger was **541.3893418869993 / 600 seconds**;
phase wall was **1046.7180666299973 seconds**, and exact outer wall through reap
was **1053.7303618150036 / 1800 seconds**. Whole times include checking, output,
archival and cleanup. Native profile clocks can overlap and are not added to
the ledger. There was no resource failure, watchdog kill or surviving
descendant. Child exit 2 records failed advancement. All nine archive stages
were acknowledged and cleaned up.

The read-only terminal audit matched 828 source pins and 303 loaded-runtime
files. The verified raw base is **93,197,151 bytes**, SHA-256
`4710baa3414b5778468133875f45182c8e4dc132eb90c691d4bdfd4e9620fa88`,
covering 134 raw artifacts with a pre-acknowledgment STATE snapshot. The final
post-acknowledgment supplement contains **95 members**, **8,176,579 bytes**,
SHA-256 `3cf18ff618495e003538ef5d6c8f04f130deacb1ffafbdb78497689cbd81f6f6`.
The two archives together retain raw models, points, checks and final terminal
records. This publication performed only JSON, hash and privacy readback;
it adds no solver run, numerical revalidation, test or CI result.
