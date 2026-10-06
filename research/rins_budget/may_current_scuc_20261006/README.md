# May1354 current-SCUC: single-case PASS

The unchanged [current-SCUC application pipeline](../current_scuc/README.md) passed its fixed one-percent interval, full original/source/direct-DC checks, negligible-slack, budget and cleanup gates on **2017-05-01, seed 0**. This is one already-exposed development case: 36 hours, 260 generators, 1,354 buses and 1,288 listed single-line outages. The complete invocation took **524.865767 seconds** from spawn through exact reap; the nested CLI-reported time was **524.801209 seconds**.

## Endpoint and certificate scope

| Quantity | Result |
| --- | ---: |
| Final checked upper U | 14013064.016813794 |
| Conservative numerical-MIP lower | 13997505.167410025 |
| Numerical-MIP interval gap | 0.11103103065182782% |
| Fresh exact seed-LP lower, rounded down | 13990132.691055497 |
| Separate exact seed-LP interval gap | 0.16364248197812045% |

Both gaps use `(U - L) / U` and independently fall below the fixed 1% target. The MIP lower is numerical, with the unchanged conservative allowance applied to its printed bound. The separate seed-LP bound is certified by exact rational arithmetic for its supplied binary64 projected matrix. It remains attached to its one-batch seed snapshot and is not relabeled as a certificate of the later two-batch master.

The lower domain is the **hard-zero load-shedding and reserve-shortfall integer subset of the literal serialized-LODF model**. The final upper is an independently checked numerical physical witness. Neither lower is an exact lower certificate for the physical-DC problem or a certificate of the original soft optimum. `physical_dc_lower_bound_certified` remains false.

Load shedding and reserve shortfall were exactly zero. Positive shared overflow was **1.0682990705390696e-06 MWh**, below the unchanged **1e-5 MWh** limit. All **28,080 original binary values** passed without rounding. Full original-matrix and literal-source checks, the independent source checker, and the direct-DC separator passed. Direct checking covered **66,360,168 eligible pair-hours**, all 1,288 outages and 1,289 factorizations, with **zero violated pairs or line-hours**.

## Work and clocks

| Clock | Seconds |
| --- | ---: |
| Complete invocation, spawn through reap | 524.8657673799971 |
| CLI reported | 524.8012089370022 |
| Preparation | 55.13371080800425 |
| Candidate process, spawn through reap | 467.01366663200315 |
| Candidate internal | 461.8447777359979 |
| Actual seed/MIP/carry process ledger | 149.9746737119931 |

The ledger comprises seed **82.11390634599957 s**, discovery **15.404850387996703 s**, carry **20.87805458100047 s**, and proof **31.577862396996352 s**. The run used two LP solves, two integer processes and one checked incumbent carry; the proof process admitted the feasible start. The checked provisional objective improved from 14,304,204.364784367 at discovery to 14,013,064.016813608 at proof before final physical validation. The discovery and proof masters were byte-identical. The final master had **141,842 columns, 162,988 rows and 763,835 nonzeros**, within the original **164,080-row cap**. No cap or acceptance policy changed.

These clocks are nested and must not be added. CLI reported time starts at main entry and stops before its final result write/output; the outer clock includes interpreter startup, final output, exit and cleanup. Owner preflight, audit and external archival/readback are separate administration. All owned processes were reaped, with clean exit 0.

Both native MIP logs retain the **7.276e-12** bound-consistency diagnostic. Its existing source-pinned classification added no acceptance threshold and waived no numerical QA. The static audit verified the complete raw-log, I/O-filtered and advisory-filtered hash chain.

## Provenance and interpretation

The independent terminal audit passed **718 checks across 229 hashed files**. The complete 259-member raw archive passed readback; its SHA-256 recoverability fingerprint is recorded in the results JSON. All **70 manifest-pinned application files** match the [already-public source package](../current_scuc/current_scuc/SOURCE_MANIFEST.json). Native HiGHS is the unchanged official development commit `d547a3ad8af5399651187fb0e133cf0e42615b82`. This checkpoint adds results only, with no solver patch. [RESULTS.public.json](RESULTS.public.json) retains exact metrics, source/runtime/input identities and raw-evidence hashes; [PUBLICATION_MANIFEST.json](PUBLICATION_MANIFEST.json) inventories the public bytes. Input notices remain in the [source package](../current_scuc/THIRD_PARTY_NOTICES.md).

This is an application/modeling-pipeline result, not evidence of a HiGHS kernel speedup. No same-runtime conventional May arm was run, so no speed ratio or older-May timing comparison is claimed. One exposed seed-0 observation does not establish repeatability, statistical reliability, unseen-case generalization or commercial readiness.

The earlier [six-run panel](../current_scuc/SEED_PANEL.md) passed 6/6 on exposed June, October and December dates with seeds 1 and 2. May is a separate subsequent challenge, not another member of that predeclared cohort; no pooled statistics are reported. Publication used only stored evidence, static inspection and arithmetic, with no optimizer, build, scientific-checker or test rerun. This compact checkpoint is not a complete replay bundle and includes no dataset or native binaries.
