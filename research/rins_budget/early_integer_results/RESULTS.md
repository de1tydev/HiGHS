# Early integer discovery: PG89 confirmation

**Correctness advisory — 2026-10-02:** The pinned solver reproduced an incorrect optimality claim on an official upstream fixture. Historical 1% gap and time-to-1% acceleration claims below are provisional pending corrected-reference revalidation; historical SCUC impact is unknown. Original results remain archived. [Read the evidence and current limitations](../CORRECTNESS_ADVISORY.md) before using this research.

The fixed early-only method passed the predeclared confirmation rule: all 18 arms obtained valid original-source 1% numerical certificates, and the candidate was strictly faster on both measured endpoints in all nine pairs. Each date also exceeded the required 30% median paired reduction on both endpoints.

| Date | Eligible pairs | Median solver-wall reduction | Median arm-E2E reduction | Date gate |
|---|---:|---:|---:|---|
| 2017-05-01 | 3/3 | 75.4421% | 65.7788% | Pass |
| 2017-06-01 | 3/3 | 66.1512% | 54.8522% | Pass |
| 2017-09-01 | 3/3 | 60.2334% | 52.3251% | Pass |

Across all nine eligible pairs, the median reductions were 65.5174% solver wall and 54.8522% arm E2E. The worst paired reductions were 55.2811% and 48.9598%; the best were 77.0994% and 66.3636%. No incomplete pair was omitted: 18 completed arms, zero censored arms, zero unrun arms.

## Every paired outcome

Times are seconds. A is the ordinary cold integer loop; E is early integer discovery followed by cold proof. The arrows in timing cells are A → E, regardless of execution order.

| Date | Seed | Run order | Solver A → E | Reduction | Arm E2E A → E | Reduction |
|---|---:|---|---:|---:|---:|---:|
| 2017-05-01 | 211 | A → E | 119.917371 → 29.449171 | 75.4421% | 153.484963 → 52.524336 | 65.7788% |
| 2017-05-01 | 212 | E → A | 91.002231 → 31.379967 | 65.5174% | 123.562311 → 54.962947 | 55.5180% |
| 2017-05-01 | 213 | A → E | 109.111949 → 24.987324 | 77.0994% | 141.235341 → 47.506450 | 66.3636% |
| 2017-06-01 | 211 | E → A | 79.513775 → 22.022400 | 72.3037% | 111.643936 → 44.906509 | 59.7770% |
| 2017-06-01 | 212 | A → E | 66.991819 → 23.586346 | 64.7922% | 99.023312 → 46.058303 | 53.4874% |
| 2017-06-01 | 213 | E → A | 67.739898 → 22.929154 | 66.1512% | 100.445873 → 45.349123 | 54.8522% |
| 2017-09-01 | 211 | A → E | 99.183661 → 44.353821 | 55.2811% | 131.072077 → 66.899459 | 48.9598% |
| 2017-09-01 | 212 | E → A | 107.321063 → 42.294605 | 60.5906% | 138.945807 → 65.386598 | 52.9409% |
| 2017-09-01 | 213 | A → E | 93.989587 → 37.376453 | 60.2334% | 126.439991 → 60.280103 | 52.3251% |

Every control used three cold proof MIPs. Every candidate used exactly one discovery MIP and one fresh cold proof MIP: 45 solver processes in total, with no retries. Discovery selected all independently reconstructed valid original rows; only those rows persisted. Initial discovery selected 9 pairs in May, 8 in June, and 7/11/11 across September seeds. Control final masters held 12 pairs in May/June and 11 in September; candidate final masters held their discovered 9/8/7-or-11 pairs. Fewer selected rows did not waive any final source checks.

## Scope, policy and clocks

The source family is PG89: 89 buses, 12 units, 210 lines and 77 finite-rated lines, with 36 hourly periods, 192 listed outages and 529,956 eligible original pair-hours checked at each complete source check. Inputs were reserved before the development result; May had disclosed prior metadata-only exposure. The nine date-major blocks used seeds 211, 212 and 213 and globally alternating arm order. These are results for this custom DC security-constrained unit-commitment formulation and this cold comparator. They are not a comparison against the prior LP bundle, a larger-case transfer, or a universal HiGHS speedup claim.

Both arms used the same pinned existing A runtime, baseline separator, options, model generation, exact API readback and independent original-source checker. HiGHS reports version 1.15.1, based on official commit `73cac48c5340d775a477087198611862559be250` with the existing opt-in instrumented outer-gap, initial-root-IPX and root-child-credit patches. This is not unmodified upstream-default behavior: the exact common options are retained in the JSON projection, including two solver threads and `parallel = off`. There was no new kernel build.

Retained host metadata records AMD EPYC 9V74, 9 exposed logical CPUs and approximately 9.7 GiB RAM. Logical-CPU visibility is not a CPU quota or exclusive-allocation claim; no 80-core allocation is claimed. The candidate alone set `mip_max_improving_sols = 1` on its first integer call, with ordinary `mip_rel_gap = 0.01` and a requested ceiling of min(300, actual remaining solver seconds). Discovery vectors and every discovery upper/lower bound were excluded from proof, even if the discovery status was Optimal. No start, basis, solver state, repair, LP screen or constructive seed was carried. Later calls were fresh cold unrestricted 1% proofs.

Each arm retained a 600-second aggregate actual solver-process budget and 1800-second containing-process deadline. The ordinary 60-second MIP watchdog grace was charged. The hard per-process address-space cap was 7 GiB; 2 GiB MemAvailable/free-disk thresholds were sampled availability guards, not continuously reserved allocations. All returns and child cleanup were clean.

Solver wall means the measured whole solver process, including model import, output, nested work and exact reap. Arm E2E means containing-process Popen through exact wait4 reap, including startup, full verification, generation/readback, all solving, independent checking and durable arm output. It excludes redundant controller-only prelaunch integrity/health checks, supervision setup before its timer, inter-arm archival/statistical writes and final reporting. Those controller intervals were not separately measured. No total-campaign elapsed/cost claim is made. The code and endpoint definitions were not changed mid-campaign.

The sum of the 45 measured solver intervals was 1113.150595 seconds. The sum of the 18 containing-arm intervals was 1609.727438 seconds; this is a sum of the declared arm endpoints, not an inferred campaign stopwatch or an invented debit for the excluded administration.

## Final points, objectives and actual slack

Primal feasibility, unchanged objective and original outage constraints were independently checked. Lower bounds are HiGHS numerical global bounds with the retained conservative printed-precision allowance; they are not independently proved exact or rational dual certificates.

All 18 exact certified points were re-read and bound to their source, solution, check, model, expected-matrix and API-report hashes. All 57,672 shedding variables, 49,896 shared-overflow variables and 648 reserve-shortfall variables were exactly zero, without clipping. The reserve category is r1/Spinning. These zeros were checked from the points and were not inferred from soft-model feasibility.

Unrelaxed base overload was exactly zero in all points. Maximum raw unrelaxed outage overload was 0 MW in May, 2.5693225325085223e-11 MW in June and 2.2737367544323206e-13 MW in September. The small positive numerical residuals are retained, not rounded to zero, and are below the unchanged 1e-5 source tolerance.

Paired incumbents need not have identical objectives within the common 1% certificate target. The table reports true source cost; full-precision certificate U, checked linear cost, matrix objective, signed objective overpayment and exact point/check hashes are in [result.json](result.json). U remains max(source linear cost, matrix linear objective), so tiny summation differences are preserved.

| Date | Seed | True source cost A | True source cost E | E − A | Identical column point |
|---|---:|---:|---:|---:|---|
| 2017-05-01 | 211 | 2678903.091965951 | 2682838.636270283 | +3935.544304 | No |
| 2017-05-01 | 212 | 2678903.091965951 | 2682838.636270284 | +3935.544304 | No |
| 2017-05-01 | 213 | 2697018.691704277 | 2682838.636270286 | -14180.055434 | No |
| 2017-06-01 | 211 | 2691621.760565661 | 2691621.760565654 | -6.51926e-09 | No |
| 2017-06-01 | 212 | 2691621.760565662 | 2691621.760565653 | -8.3819e-09 | No |
| 2017-06-01 | 213 | 2691621.760565656 | 2689538.830309071 | -2082.930257 | No |
| 2017-09-01 | 211 | 2789915.943409024 | 2797547.679650182 | +7631.736241 | No |
| 2017-09-01 | 212 | 2789915.943409023 | 2789915.943409023 | +0 | Yes |
| 2017-09-01 | 213 | 2789915.943409024 | 2789915.943409024 | +0 | Yes |

## Retained validation and limitations

The exposed February seed-0 development pair is separate: it passed its 20% development threshold by only 0.108866 seconds on arm E2E. It is not pooled into these nine confirmation pairs. Eighteen pure binding/gate/controller tests passed before confirmation. The independent terminal audit passed every certificate, debit, seed/options binding, model readback, selector, raw-file identity and original-row transition. Terminal point reporting also passed its separate validation checks.

Two prerequisite status-fixture reporting assumptions were corrected before confirmation: an ordinary successful-write filename accidentally matched a broad diagnostic regex, and text-exported solution numbers cannot be required to equal API doubles bitwise. The narrow fixture correction used the exact write announcement, official writer replay, and independent checks of both vectors. Both failed harness receipts and all three already completed processes were retained; only the fourth predeclared status process was subsequently launched. There were zero solver repeats and no production parser, feasibility tolerance or experimental-policy changes.

All three source dates, both arms and all seeds are reported. There was no performance-dependent stopping, source substitution or policy rescue. Passing this scoped confirmation does not automatically release further numerical work. Larger-case transfer and portable replay validation remain separate deliverables.

## Provenance

[result.json](result.json) includes every pair, date gate, overall median and worst/best tail, per-arm objectives and physical slack, exact point/check/source/model hashes, fixed options, runtime/source fingerprints, exposure and order, and retained correction evidence hashes. This projection contains no private workspace paths, commands, binaries or large raw models. It summarizes retained evidence; it does not itself reproduce the benchmark.

Public source inputs:

- [case89pegase/2017-05-01](https://axavier.org/UnitCommitment.jl/0.3/instances/matpower/case89pegase/2017-05-01.json.gz), compressed SHA256 `a13b8da591278afec5d14ef7c787bfd7c0c6a3f91c526511bfee051294c9be4c`
- [case89pegase/2017-06-01](https://axavier.org/UnitCommitment.jl/0.3/instances/matpower/case89pegase/2017-06-01.json.gz), compressed SHA256 `65730d0a6ca7ded7947af1e682761aead3cf709f43e657ec6662c403580a123d`
- [case89pegase/2017-09-01](https://axavier.org/UnitCommitment.jl/0.3/instances/matpower/case89pegase/2017-09-01.json.gz), compressed SHA256 `727fda066143f885c6924ffbc0518121689d7175eca16acb2aee7e8237ae91a8`

Input source notices and attribution are preserved with the canonical source evidence. This compact projection redistributes neither the datasets nor large models; the code license does not replace the source-data attribution requirements.
