# Chronological security-row cache: restored June1354 test

**Negative result: neither arm reached a checked 1% full-SCUC result.** Learning two security-pair identities from May avoided June's first integer-discovery solve and produced a better restricted-master incumbent. The warm arm still left three security pairs violated and exhausted its solver budget. No acceleration ratio or advancement to reserved confirmation dates is claimed.

## Fixed experiment

This is a new, same-runtime experiment after the [October 4 interruption](../INTERRUPTION_20261004.md). It does not complete the interrupted attempt or combine measurements across machines. Both arms used pristine [official HiGHS development commit d547a3ad8af5399651187fb0e133cf0e42615b82](https://github.com/ERGO-Code/HiGHS/tree/d547a3ad8af5399651187fb0e133cf0e42615b82), without private solver patches. The rebuilt reference retained its qualified test result: 168/169 CTest entries and 399/400 unit cases; the documented automatic-core-count affinity test remains unmet. Explicit two-thread settings were used.

The inputs were the exposed development dates May 1 and June 1, 2017, on PEGASE1354, using 36 hours and the existing custom preventive DC formulation. Original costs, initial conditions, fixed-output units and source-allowed soft slacks were retained. This is not a claim of parity with UC.jl's default formulation. Coverage is all **1,288 specified outages and 66,360,168 eligible pair-hours**, rather than every possible single-line outage.

One fresh May full-temporal LP relaxed only integrality, using IPX without crossover. Its complete original-column primal passed the continuous matrix and base-physical checks. The full outage scan produced two violated pair identities; every fresh identity was retained. The probe was not a full-security feasible incumbent. Known starting-basis and absolute-dual-residual diagnostics were classified under a prospective selection-only rule; no LP optimality certificate, dual bound, point, basis, fixed commitment or solver state was transferred.

June used seed 0 in the fixed order **E then W**:

- E started with no security rows, used first-integer discovery, added witnessed original rows, and began a fresh proof solve
- W reconstructed the May identities with June's original data and began proof directly; complete current-date checking and online separation remained mandatory

This tests a combined cache and discovery-scheduling policy, not cache-only causality or a solver-kernel change. May had one 300-second actual solver allowance. Each June arm had 600 aggregate actual solver seconds, 600 seconds per helper and an 1,800-second whole-arm envelope. Every solve, restart, check and archival pause was counted under the corresponding clock. The target remained 1%; no failed case was replaced and no additional seed or reserved date was run.

E's proof model and W's initial model were byte-identical: May had supplied the same two pairs that E discovered. W therefore had more of its fixed target budget available for proof, but that did not complete the full problem.

## Terminal result

| Quantity | E: cold discovery then proof | W: earlier-date cache, proof first |
| --- | ---: | ---: |
| Actual solver-process wall, summed | 598.014189353 s | 597.127125652 s |
| Native solve calls | 2 | 1 |
| Final native status | Time limit | Time limit |
| Independently recomputed final source cost | 15,474,465.043516662 | 13,880,877.36469879 |
| Full-source feasible incumbent | Yes, with paid shedding | No |
| Numerical gap using checked feasible point | 12.0082099% | Unavailable |
| Diagnostic restricted-master gap | 12.01% | 1.91% |
| New security pairs / violating hours | 0 / 0 | 3 / 5 |
| Maximum emergency violation after shared slack | Below 1e-5 tolerance | 24.70705253695087 MW |
| Raw load shedding | 1,479.0441367624076 MWh | 2e-13 MWh |
| Shared overflow | 0 MW | 0 MW |
| Checked 1% completion | No | No |

W's lower-cost point and almost-zero shedding do not establish full-SCUC feasibility. Its 1.91% gap applies only to the restricted master. E's source-feasible point does not meet the gap target and relies on substantial source-allowed load shedding. Lower bounds come from HiGHS, with the fixed display-rounding allowance; they are not independently proved dual or rational bounds. Original-matrix and source primal checks retain tolerance 1e-5.

## Costs and durability

Fresh May acquisition cost **481.063206118 seconds** in total, including **205.382268334 solver seconds**, **91.513880420 checker seconds** and **152.607978894 seconds inside archival boundaries**. Its two-pair cache is charged once. Raw June whole-arm times were **1,069.233193923 seconds for E** and **842.968367617 seconds for W**, including archival boundaries of 123.112742248 and 63.211072152 seconds. The single-use warm total, including May, was **1,324.031573735 seconds**.

The first restored comparison was prospectively designated a **completion/quality test**, not clean end-to-end acceleration evidence. Whole clocks continued through compression, coordinator waiting, upload/readback, verification and cleanup. These pauses were measured and never subtracted. Both solver totals were below 600 seconds and both whole-arm totals below 1,800 seconds. Final native processes exited cleanly; neither arm was killed by the watchdog.

Exact compact measurements, source/input/model/point hashes and named durable-archive hashes are in [result.json](result.json), bound by [SHA256SUMS](SHA256SUMS). The complete source and contract were archived before launch; terminal native/check stages retained model, point and checker evidence, followed by separate final accepted or incomplete episode capsules. Uploaded archives were read back and byte-verified. These archives are retained in owner-controlled storage; the hash inventory is not a public raw-data download mirror. This checkpoint publishes results, not a newly validated portable replay entrypoint.

## Next question

The cache reduced repeated work but did not cover the final point's security constraints. New work must prospectively choose valid candidate rows or discover them early enough to leave proof time. Adding the observed June pairs and calling that unseen success would be invalid. A separate source review is also checking root-cut stopping rules; the observed plateau is not yet evidence that cutting can safely be shortened without harming the final solve. Existing historical failures, correctness advisories and the separate pristine PG89 result remain unchanged.
