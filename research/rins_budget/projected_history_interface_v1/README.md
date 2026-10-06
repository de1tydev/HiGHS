# Projected SCUC history probe: negative fixed-pair result

The single exposed June→October commitment-copy trial added **22.986 seconds** of supervised CLI wall and returned the **identical checked final point through cold fallback**. Both October arms passed the unchanged one-percent interval, full original/source/direct-DC checks, negligible-slack and resource gates. The historical method did not improve this fixed case.

This is a research overlay on the published [current projected SCUC candidate](../current_scuc/), using the [checked-history public-API adapter](../checked_history_interface_v1/). The four runtime overlay files, staging script, tiny runner, tests, protocol and [v3 patch](SOURCE_DELTA_v3.patch) are unchanged from the qualified experiment. It is not a portable production feature. See [replay requirements](REPLAY.md) and the [public file manifest](PUBLICATION_MANIFEST.json).

## Fixed October pair

One machine/runtime, October 1, 2017 PEGASE1354 source, 36 hours, seed 1, two threads, parallel search off; cold ran first. Each arm freshly prepared its source model and ran the same two LP seed solves. The history arm then mapped one independently checked June window's 9,360 u values into the current projected master. It transferred no y/z, dispatch, basis, root factorization, search state or prior bound. No replacement run or second seed was used.

| Measured stage | Cold (s) | History (s) |
| --- | ---: | ---: |
| Preparation | 57.518741 | 56.260713 |
| Same-case seed worker, two LP solves | 101.735927 | 98.266166 |
| Historical admission/mapping | — | 1.727044 |
| Contained completion/search probe | — | 29.023987 |
| Post-reap history check | — | 0.002175 |
| Ordinary discovery MIP | 13.464551 | 12.307768 |
| Combined charged ledger | 115.200478 | 141.327140 |
| Final physical worker | 171.542860 | 170.861263 |
| Candidate process, including QA | 364.949111 | 389.391463 |
| **CLI spawn through exact reap/cleanup** | **425.157582** | **448.143773** |

These are nested clocks, not additive stages. The charged-ledger increase was 26.126662 seconds. Full final physical checking stayed on the existing candidate/CLI clocks; historical admission, probe and historical checks were charged to the same 600-second ledger. The owner retained its 2,460-second containment cap, 7 GiB address-space cap, 6 GiB sampled tree-RSS cap, startup/resource gates and exact-reap rules. Owner preflight and its final receipt publication are outside the reported CLI clock. Raw evidence archival and readback administration are also separate.

The complete numerical pair is in [PAIR-SUMMARY.public.json](evidence/PAIR-SUMMARY.public.json); [STAGE-COSTS.public.json](evidence/STAGE-COSTS.public.json) adds preparation, candidate and physical-worker clocks with source receipt hashes. These are observations from one fixed-order pair, not estimates of a general speed ratio or reliability.

## What the history arm actually did

The public API first attempted native completion of the supplied commitments. Its log reported that completion subproblem infeasible in 0.13 seconds. That is a diagnostic of the completion subproblem, not infeasibility of the current SCUC model. The API continued ordinary search and reached the external watchdog; the process was killed and cleanly reaped after 29.023987 seconds. The terminal API metadata and complete-point files were empty.

A later read-only check of the saved master explains a sufficient cause: the copied commitments produce nine minimum-up violations across g11, g46, g53, g79 and g230. These units began June already ON for 24 hours, but began October OFF for 24 hours. Copying ON at hour 0 and OFF at hour 1 therefore forces a new October startup and an impermissibly early shutdown. For example, the initial transition forces y0 ≥ 1, while the next minimum-up row with u1 = 0 forces y0 ≤ 0; alternative y/z or dispatch values cannot resolve that contradiction. This is a sufficient temporal conflict, not an exhaustive diagnosis of every constraint, and required no new optimization. See [saved-row diagnosis](evidence/INITIAL-STATE-DIAGNOSIS.public.json).

No point, incumbent or lower bound seen only in that log was promoted. The failed probe remained an auxiliary attempt; the fresh cold fallback was still logical discovery call 1. It found the final endpoint, so the history arm used two actual integer processes and one ordinary logical call; cold used one integer process. No large-case history-to-proof carry occurred. The separate tiny integration pair had already exercised that path naturally.

The experiment reports completion followed by search as one bounded probe. It does not separate their costs using a new callback, change the adapter to stop on completion failure, or mix such a hypothetical change into these results.

## Same final endpoint and unchanged meaning of PASS

Both arms returned the same full original binary64 lift:
`5e5eac7dfcd8161f9cf5bf37294c6182237f7e1ea20807ea75cf184b8e82b3b9`.

- Checked upper: 11,738,459.752050288
- Selected exact seed-LP lower: 11,732,175.309109934; no probe lower was eligible
- Gap: **0.0535372023%**, below the unchanged 1% target
- Load shedding and reserve shortfall: 0 MWh; positive shared overflow: 1.6539866010134577e-7 MWh, below the unchanged 1e-5 MWh quality threshold
- Full original binary/temporal/matrix and source checks passed, with 1,288 listed outages, 66,360,168 unsigned security pair-hours and zero direct violated pairs

The lower remains a certificate for the declared hard-zero-shedding/reserve integer full literal serialized-LODF subset. It does not bound the original soft optimum or certify a physical-DC optimum. The physical upper is a numerically checked witness; `physical_dc_lower_bound_certified` remains false. All model, map, outage, objective and final physical gates remained unchanged. Compact [terminal audit projections](evidence/TERMINAL-AUDITS.public.json) preserve the original audit identities without machine-local paths.

## History and qualification limits

The source windows are June 1–2 and October 1–2, 2017. June's independently checked label was actually audited in **2026**, and target-time re-admission also occurred in 2026. Those timestamps were retained; no availability was backdated to 2017. This is an explicitly simulated-chronology, already exposed historical-copy baseline with **one window**, not an observed operational replay, a trained model, or an unseen-case generalization result. [CHRONOLOGY.public.json](evidence/CHRONOLOGY.public.json) gives the exact timestamps and input identities. Historical label acquisition is prior setup and is not hidden inside a target-time performance claim.

Before October, the fixed unchanged triangle pair passed its mechanism prerequisite in 21.568028 seconds. Each arm used two LP solves and two integer processes; history naturally followed API-point admission with checked carry/proof. Both tiny scientific candidates correctly remained quality NONPASS because of the fixture's 2.25 MWh overflow. Thirteen pure seam tests had also passed. These are retained historical test results; no tests, solver, native readback or physical checker were rerun to prepare this publication. See [QUALIFICATION.public.json](evidence/QUALIFICATION.public.json).

The public package contains inspectable implementation and compact evidence, not native binaries, input datasets or the authenticated historical recovery capsule. The adapter is pinned to one qualified binary hash; rebuilding equivalent source does not automatically satisfy that pin. No newer large experiment or improvement is included here.
