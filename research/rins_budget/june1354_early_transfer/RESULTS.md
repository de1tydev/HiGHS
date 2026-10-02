# June1354 early-integer transfer: incomplete pair

Both predeclared seed-0 arms returned cleanly but failed the original-source 1% completion requirement. Both last proof points still violated original outage constraints, and both exceeded the fixed 600-second aggregate actual solver cap. The campaign stopped after the paired clean incomplete result. No completion-time ratio, date median, 30% transfer success, or repeatability claim is available.

The input is the retained [UnitCommitment.jl 0.3 case1354pegase, 2017-06-01](https://axavier.org/UnitCommitment.jl/0.3/instances/matpower/case1354pegase/2017-06-01.json.gz): all 36 hours, 1,354 buses, 260 units, 1,991 lines, 1,288 listed outages and four singleton cost curves. Every check covered all 66,360,168 eligible pair-hours. Source SHA256: `75619cc70715027e9802adca41641c37c5bce65c2a9837cc7885376614a8809c`.

## Endpoints and charged solver calls

| Seed 0 | A | Early candidate |
|---|---:|---:|
| Actual solver-process seconds | 603.618304 | 643.323521 |
| Complete containing-process E2E seconds | 790.200628 | 1009.327061 |
| Full-source primal pass | No | No |
| Valid final certificate | No | No |
| Retried solves | 0 | 0 |

| Call | Requested s | Actual s | Charged overrun s | Clean status |
|---|---:|---:|---:|---|
| A proof | 600.000000 | 603.618304 | 3.618304 | Time limit reached |
| Early discovery | 300.000000 | 242.855248 | 0.000000 | Solution limit reached |
| Early proof | 357.144752 | 400.468273 | 43.323521 | Time limit reached |

All three solver processes returned code 0 without watchdog kills. The fixed 60-second grace was charged, never added to the 600-second aggregate budget. Both containing-arm processes remained inside the 1,800-second containing-process cap, with exact cleanup/reap.

## Printed master reports versus final certificates

| Call | Raw printed primal bound | Raw printed dual bound | Raw printed master gap |
|---|---:|---:|---|
| A proof | 13806823.9718 | 13603314.353 | 1.47% (tolerance: 1%) |
| Early discovery | 15314834.4806 | 13469833.6904 | 12.05% (tolerance: 1%) |
| Early proof | 15971060.6572 | 13614981.988 | 14.75% (tolerance: 1%) |

These are master diagnostics, not full-SCUC certificates. Both final certificate objects are invalid/incomplete with U/L/gap unavailable because neither arm has a full-source checked U. Proof-role lower bounds with the unchanged display-rounding allowance are retained separately in result.json; discovery contributes no eligible U or L.

## Last checked proof points

| Diagnostic | A | Early candidate |
|---|---:|---:|
| True source cost | 13,806,823.971834783 | 15,971,060.65716508 |
| Checker load shedding, MWh | 2e-13 | 1,975.1173377798737 |
| Shared overflow: maximum MW / total MW-hours | 0 / 0 | 0 / 0 |
| Reserve shortfall, MWh | 0 | 0 |
| Original violating pairs / pair-hours | 3 / 24 | 1 / 1 |
| Max emergency excess after original slack, MW | 272.47338756793874 | 34.06608680398631 |
| Max unrelaxed base overload, MW | 0 | 0 |

Each point passed its current master matrix, bounds, objective and integrality checks. Remaining source-security violations prevent full-source feasibility. Penalized shedding, overflow and reserve shortfall are reported separately from feasibility. These are incomplete master points, not completed SCUC solutions. Raw signed exported slack totals, tiny roundoff entries, exact-zero counts, and witness hashes/counts are preserved in result.json without clipping.

## Every measured child process

| Process | Wall seconds | Peak RSS, KiB |
|---|---:|---:|
| A scope | 0.703877 | 24,628 |
| A proof: generation/API readback | 26.745751 | 815,896 |
| A proof: solver | 603.618304 | 2,474,968 |
| A proof: full source/outage check | 154.942183 | 434,944 |
| Early scope | 0.704568 | 24,904 |
| Early discovery: generation/API readback | 25.796535 | 814,812 |
| Early discovery: solver | 242.855248 | 1,489,944 |
| Early discovery: full source/outage check | 152.655130 | 435,216 |
| Early proof: generation/API readback | 25.747158 | 818,356 |
| Early proof: solver | 400.468273 | 1,639,064 |
| Early proof: full source/outage check | 154.073443 | 435,428 |

These child measurements are included in the arm E2E and are not charged twice. RSS is a separate peak for each child, not a simultaneous sum. Existing 7 GiB process, conservative allocation, storage and live availability guards remained active. Separately reported provisioning took 0.914040 seconds for materialization and 2.534005 seconds for runtime identity/ABI preflight; no extra June model preflight occurred.

## Unchanged policy, stopped schedule and evidence

Candidate used one initial integer discovery with improving-solution limit 1, ordinary 0.01 gap and at most 300 requested seconds. It selected two original violated pairs; both signs at all original finite hours added exactly 144 proof rows. All masters kept 313,776 columns and passed full canonical API fidelity. Original costs, singleton perspectives, every outage, common A options and the baseline separator/checker were unchanged. Only the rows carried into fresh cold proof; no vector, start, basis, cutoff, state, LP or constructive seed carried.

The four unrun slots, in frozen order, are seed 1 early, seed 1 A, seed 2 A, seed 2 early. They remain unrun because the seed-0 pair was incomplete. There was no tuning, replacement, extra repeat or rescue.

The public portable CLI remains scoped to PG89. This June experiment used a separate unchanged-policy source/seed/output binding; the projection is evidence, not a public June replay entrypoint. Exact source, protocol, scalar, raw-evidence, runtime, method and witness identities are in [result.json](result.json); [MANIFEST.json](MANIFEST.json) fixes these public files. The retained raw freeze contains 102 files totaling 428,592,054 bytes. No private paths or coordination artifacts are included here.

The method found usable original rows, but first-incumbent latency, two source checks and cold proof did not yield completion under the fixed caps. This one incomplete pair establishes no June speedup, repeatability, cross-case generality or significance. June is now exposed for future method design and cannot be reused as untouched confirmation.

Source attribution remains with the hosted UnitCommitment.jl instance and its embedded PEGASE/MATPOWER/UnitCommitment.jl references.
