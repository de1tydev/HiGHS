# Combined SCUC screening: all nine pairs improve, final consistency gate fails

Completed historical measurements, 2026-10-02. Publication does not constitute a new benchmark.

The combined candidate reduced solver-process time and complete standalone-equivalent end-to-end (E2E) time in **all nine confirmation pairs**. The median paired reductions across those observations were **45.7012% solver** and **34.5375% E2E**. All 18 arms completed with valid one-percent numerical certificates, with no timeout, regression, dropped or replaced case.

**The predeclared experiment nevertheless failed.** It required at least 30% median paired reduction on both endpoints **for each date separately**, plus strict improvement of both endpoints in every pair. February's median E2E reduction was **25.0394%**, below 30%. The overall descriptive median does not override that failure. The declared route is complete; no extra seed, repeat or retuning is included.

## Comparison and decision

Both arms solve the same original 36-hour preventive DC SCUC model from public PEGASE89 inputs, at the same 1% certified target, with the same executable and libraries, two solver threads, parallel search off, presolve on, the existing outer-gap policy enabled and initial-root IPX disabled.

- **A, cold integer control:** empty initial security-pair set, no LP discovery, root-child credit disabled, original complete separator
- **B, combined candidate:** empty initial pair set, cold LP discovery, unchanged direct-root child-credit policy enabled, and the reviewed exact-output separator with optimized rating preparation

Every A arm used two integer stages; every B arm used two LP stages followed by one fresh integer stage. Only validated eligible security pairs and the valid integer-master bound ledger persisted within an arm. There was no transferred primal point, incumbent, basis, LP bound, factorization, rating table or historical cut cache. “Cold” refers to application state; operating-system page caches were not claimed to be flushed.

Reduction is `100 × (1 − B/A)` within a fixed date/seed pair. Medians below are medians of these paired reductions, not ratios of pooled time totals or marginal medians.

| Date | Confirmation seeds | Median solver reduction | Median E2E reduction | Predeclared date gate |
|---|---|---:|---:|---|
| 2017-02-01 | 3, 4, 5 | 36.9286% | **25.0394%** | **Fail: E2E** |
| 2017-08-01 | 1, 2, 3 | 42.2445% | 34.5375% | Pass |
| 2017-11-01 | 1, 2, 3 | 48.9415% | 36.1520% | Pass |
| All nine, descriptive only | Nine pairs | 45.7012% | 34.5375% | **Overall experiment fails** |

## Every confirmation outcome

The table preserves the frozen execution order. Times are seconds, rounded to six decimals. The [CSV](confirmation_pairs.csv) and [confirmation projection](confirmation_projection.json) retain the original floating-point values, source/check identities, certificates, resources and stage breakdowns.

| Seq. | Date | Seed | Order | A solver s | B solver s | Reduction | A E2E s | B E2E s | Reduction | B caps |
|---:|---|---:|:---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2017-11-01 | 1 | BA | 56.427522 | 25.137819 | 55.4511% | 66.939164 | 38.271709 | 42.8261% | 1 |
| 2 | 2017-08-01 | 1 | AB | 81.903901 | 47.304006 | 42.2445% | 92.334359 | 60.444403 | 34.5375% | 0 |
| 3 | 2017-02-01 | 3 | BA | 38.979154 | 24.584698 | 36.9286% | 49.526335 | 37.434175 | 24.4156% | 1 |
| 4 | 2017-02-01 | 4 | AB | 48.505943 | 24.204234 | 50.1005% | 58.955859 | 37.250144 | 36.8169% | 1 |
| 5 | 2017-11-01 | 2 | AB | 63.751162 | 34.616110 | 45.7012% | 74.197925 | 47.373901 | 36.1520% | 1 |
| 6 | 2017-08-01 | 2 | BA | 98.315804 | 44.854975 | 54.3766% | 108.620682 | 57.925623 | 46.6716% | 0 |
| 7 | 2017-08-01 | 3 | AB | 61.203453 | 41.246553 | 32.6075% | 71.731713 | 54.436238 | 24.1113% | 0 |
| 8 | 2017-02-01 | 5 | BA | 44.547110 | 28.404944 | 36.2362% | 55.452340 | 41.567392 | 25.0394% | 1 |
| 9 | 2017-11-01 | 3 | BA | 45.915445 | 23.443728 | 48.9415% | 56.477869 | 37.116515 | 34.2813% | 0 |

Solver reductions ranged from **32.6075% to 55.4511%**; E2E reductions ranged from **24.1113% to 46.6716%**. August seed 3 was the weakest observed pair on both endpoints. All nine solver reductions reached 30%; six E2E reductions did. Linear interpolation of the nine ordered observations gives descriptive p10/p90 reductions of 35.5104%/54.5915% solver and 24.3548%/43.5952% E2E. These finite-sample summaries are not population tail guarantees or confidence intervals.

Five B arms each applied one actual root-credit cap, with **zero exhausted-credit skips**. Those caps occurred in all three February arms and November seeds 1 and 2. A applied none. The other four B arms remain in the results. This bundle comparison does not isolate a component's causal contribution; it does not attribute the full improvement to the solver kernel, root credit or the separator alone.

## Correctness and scope

All 18 **final** points passed original-source, loaded-matrix, integrality and objective checks. The certificates used fully checked original integer primals and conservative top-level original-master MIP lower bounds, never LP-discovery or nested-child bounds. Primal feasibility and objective were independently checked. The lower bounds are original-master HiGHS numerical MIP bounds with a conservative display allowance; their provenance and gap arithmetic were audited, without an independent exact or rational proof of the lower bound. Final numerical gaps were 0.9590%–0.9998% at the unchanged `1e-5` validation tolerance. Different valid objectives and search paths are permissible at this identical target.

Every complete direct security check covered all **192 source-listed line outages**, **14,721 eligible line/outage pairs** and **529,956 pair-hours**, with 193 fresh topology factorizations reported by the retained checker. The independent audit verified **45 API fidelity receipts**, **27 original integer-source check receipts** and **108 selected-module receipts**. Intermediate cold-screen points can violate undiscovered security constraints by design; the 27 source-check receipts must not be described as 27 fully secure points. The complete security-feasibility claim applies to the 18 final points.

August's final points contain approximately **312.105451 MWh of source-allowed shedding in both arms at every seed**. The unchanged source charges 1000 per MWh, approximately 312,105.451 of objective cost. February and November have zero final shedding. Every final point has zero overflow, including zero total shared overflow. Thus this is feasibility of the original penalty-based model, not a zero-shed operating guarantee. It covers preventive DC constraints and the listed line contingencies, not AC feasibility, generator outages or all 210 line outages.

## Timing and resources

Solver time is actual aggregate solver-child process wall time, including LP discovery inside each arm's 600-second allowance. Nested-child heuristic time is not charged twice. B permits at most three LP calls, 10 process seconds each and 30 total; observed B arms used two. Actual debits, rather than clipped budgets, determine accounting.

The co-primary E2E interval starts before arm directory/runtime/source work and ends after every final check and durable summary write. It includes fresh per-arm source preparation, model generation and API readback, LP and integer solves, all checks and remaining overhead. Full common definition-import/plan-archival setup is charged to **each** standalone-equivalent arm. It is an in-program endpoint: interpreter launch is excluded, while pair serialization and pair archival are reported separately. Initial dataset acquisition is campaign provisioning outside arm timing; numerical/source preparation remains inside each arm.

The outer confirmation phase starts before argument parsing, runtime checks, prerequisite reads and its one-use marker, and includes final confirmation serialization and artifact hashing. It took 1050.877846 seconds: 1047.527157 seconds of pair intervals and 3.350688 seconds of disclosed phase overhead. Each pair interval ends after durable pair.json serialization, before writing its own archival receipt. The outer phase includes those pair-receipt writes but excludes its own final receipt write. Whole-phase time is not an alternative benchmark endpoint.

The completed campaign controller returned exit code 1 because the declared performance gate failed. All solver and auxiliary children exited cleanly; none was watchdog-killed. Peak child RSS per arm ranged from **248,780 to 447,768 KiB** under the unchanged 7 GiB process-address limit. The 120-second auxiliary watchdog and 60-second MIP containment grace were unchanged. Per-child CPU/RSS accounting is retained; parent RSS is explicitly a cumulative shared-process peak, so a second arm can inherit an earlier peak. These observations came from a shared Linux host and do not establish dedicated-core or portable-host timing.

## Development and prior exposure

The separate familiar **February seed-0 development pair**, in AB order, reduced solver time from 37.271707 to 23.479711 seconds (**37.0039%**) and E2E from 47.715000 to 36.462959 seconds (**23.5818%**). It passed the predeclared 20%-both advancement screen with actual credit activation. It is excluded from every nine-pair confirmation statistic; see its [separate projection](development_projection.json.gz).

February was already familiar from seed-0 development and earlier nested-RINS experiments at seeds 1 and 2. Before any combined outcome, the reserved February confirmation seeds were amended from 1/2/3 to **3/4/5**, preserving sequence positions, arm orders, thresholds and budgets. This did not make the February date unseen. August seeds 1/2/3 test transfer on a familiar date previously examined at seed 0. November was a new input date selected and recorded **before its official lookup/download**; no combined numerical outcome informed that selection. The [frozen-design projection](frozen_design_projection.json) preserves this history and the amendment's exact raw identity.

Three seeds per date on one network topology are a small descriptive consistency check. Shared-host variation, serial execution and prior development exposure limit extrapolation. This is not a general MILP speedup, a production security guarantee or evidence for larger grids. Earlier failed individual LP-prescreen and root-credit gates remain failed.

## Evidence and replay status

The [artifact index](README.md) links complete projected outcomes, raw-artifact hashes, the 395-entry historical runtime inventory, the 983-entry solver source inventory and exact compressed/decompressed data identities. Paths are sanitized logical labels; original raw hashes and new projection hashes remain distinct.

- Original confirmation JSON SHA-256: `ae232a009a9a72bcfa3808333f6de20b36c0d7092b4861c90fbbbf7a53f04fbf`
- Final independent audit SHA-256: `7a21253492738216cb13cc76c8251285ff262709865947dc2c66134fa84bbc23`
- Measured runtime freeze SHA-256: `4e51bb2fe6595d65fc67da1d136172b40df6cba6d6970d45e8793c9da2c982e3`
- Frozen campaign plan SHA-256: `eab118a92b85e1a38f2f64eb52c8d6faa2821e2438d6d6fd5549e219231fbbaa`

The [portable Linux replay](../portable_combined_replay/README.md) is available with a separately recorded tiny correctness/equality validation. It has **not been performance-measured on the production cases**; the historical timings above do not become measurements of that source/runtime-binding refactor.
