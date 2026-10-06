# Fixed SCUC seed-sensitivity panel: 6/6 passed

All six predeclared invocations passed the unchanged one-percent interval, full physical/original/source QA, negligible-slack, process-cleanup and resource-budget gates. Source and policy were fixed throughout.

| Run | Date (2017) | Seed | Selected L | Checked U | Numerical MIP L | Exact seed-LP L | Selected gap % | Numerical MIP gap % | Exact LP gap % |
|---:|---|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | June 1 | 1 | numericalMIP | 13776319.428000957 | 13743386.290112566 | 13736286.327225516 | 0.239056143 | 0.239056143 | 0.290593587 |
| 2 | October 1 | 1 | exactLP | 11738459.752050288 | not eligible | 11732175.309109934 | 0.053537202 | unavailable | 0.053537202 |
| 3 | December 1 | 1 | exactLP | 12016750.470473891 | not eligible | 12015900.154340617 | 0.007076090 | unavailable | 0.007076090 |
| 4 | December 1 | 2 | exactLP | 12016725.450692963 | not eligible | 12015900.154340627 | 0.006867897 | unavailable | 0.006867897 |
| 5 | October 1 | 2 | exactLP | 11738652.701783188 | not eligible | 11732175.309109941 | 0.055180035 | unavailable | 0.055180035 |
| 6 | June 1 | 2 | numericalMIP | 13777580.392077880 | 13741578.885012584 | 13736286.327225516 | 0.261305005 | 0.261305005 | 0.299719281 |

## Clocks

| Run | Preparation s | Actual seed/MIP/carry ledger s | Candidate start-through-reap s | CLI reported s | Complete invocation: outer start-through-reap s |
|---:|---:|---:|---:|---:|---:|
| 1 | 52.581287 | 153.093458 | 453.952806 | 509.363121 | 509.433473 |
| 2 | 50.891724 | 103.613913 | 335.894655 | 388.941965 | 388.985885 |
| 3 | 51.073010 | 92.999358 | 321.298711 | 374.589025 | 374.647932 |
| 4 | 52.886880 | 89.019775 | 315.807710 | 370.854697 | 370.898433 |
| 5 | 50.930780 | 94.387457 | 324.271393 | 377.490339 | 377.540004 |
| 6 | 52.689846 | 150.064749 | 444.048621 | 499.474721 | 499.536396 |

| Clock (seconds) | Minimum | Median | Maximum | Ceiling |
|---|---:|---:|---:|---:|
| Preparation, CLI observed | 50.891724 | 51.827149 | 52.886880 | 600 |
| Actual seed/MIP/carry ledger | 89.019775 | 99.000685 | 153.093458 | 600 |
| Candidate start-through-reap | 315.807710 | 330.083024 | 453.952806 | 1800 |
| Physical worker start-through-reap | 154.493559 | 159.377689 | 160.869159 | 300 |
| CLI reported | 370.854697 | 383.216152 | 509.363121 | nested in outer |
| Complete invocation: outer start-through-reap | 370.898433 | 383.262945 | 509.433473 | 2460 |

These clocks are nested and must not be summed. Complete invocation includes interpreter startup through exact child reap and cleanup. CLI reported elapsed starts at main entry and is sampled immediately before the final CLI RESULT.json write and stdout output; those final operations are included by the outer clock. Post-exit auditing, cloud archival/readback and duplicate cleanup are separate administration. All individual preparation workers stayed within 300 seconds.

Selected endpoint gaps ranged from 0.006867897% to 0.261305005% (median 0.054358619%). Exact seed-LP gaps ranged from 0.006867897% to 0.299719281% (median 0.054358619%). These summarize different date/seed observations, not repeated measurements of one case.

Load shedding and reserve shortfall were zero in all six runs. Shared overflow ranged from 1.65398660101e-07 to 1.02261742541e-06 MWh (median 9.49100353864e-07), below the unchanged 1e-5 MWh threshold.

## Coverage and limits

- Every PASS checked all 28,080 original binary values without rounding, all 1,288 listed outages, 66,360,168 unsigned pair-hours / 132,720,336 signed security rows, and 1,289 direct factorizations, with original-matrix, independent source and direct-DC QA
- Actual selected seed 1/2 was verified through CLI, hashed arm/result provenance, both LP native calls, every typed MIP option readback/native argv, and executed carry evidence; Python hashing stayed at 0
- Across the panel: 12 LP solves, 8 MIPs, 2 carry preparations; local checkpoint counts were 7, 5, 5, 5, 5, 7
- June seed1 exercised the unchanged-master discovery-to-proof exception and feasible start admission
- June seed2 naturally exercised changed-master row-growth carry: 162,951 to 162,954 rows, 762,252 to 764,895 nonzeros, with 141,878 columns unchanged. Active lines remained [1201, 1378] and the map hash was unchanged. Exact carry QA covered every column, row and binary; retained/original point hashes were bound to the selected source, and the native CLI admitted the start as feasible
- The June seed2 carried point was a target-feasible diagnostic point with material overflow, not a previously approved physical endpoint. The later selected endpoint passed full production quality and physical QA
- New-line/column-growth carry and third-MIP execution were not observed. Row-growth coverage does not substitute for those paths
- Native d547a3ad8af5399651187fb0e133cf0e42615b82 binaries, source pins, all artifact/point/certificate bindings, actual nested clocks and exact-child cleanup were verified from saved evidence and file hashes; no scientific checker was rerun

Maximum sampled owner-tree RSS was 1698381824 bytes (6 GiB cap). Minimum sampled available memory was 7430471680 bytes and minimum sampled free disk was 19619000320 bytes (2 GiB floor each).

## Interpretation

- All six predeclared invocations passed the unchanged one-percent/full-QA/budget gate; no outcome was removed or replaced.
- These medians and extrema summarize the fixed six observations across three different exposed dates and two solver seeds. They do not estimate same-seed repeatability, independence, failure probability, reliability or unseen-case generalization.
- Complete invocation uses the outer start-through-reap receipt and includes CLI cleanup. The CLI-reported elapsed clock is a separate, nested quantity. Post-exit audit, cloud archival/readback and duplicate cleanup are administration outside these numerical clocks.
- Selected numerical-MIP lowers exist only for the two June rows. October and December select exact seed-LP lowers; no eligible numerical-MIP lower is inferred for those four rows.
- Both lower families are scoped to the hard-zero integer full literal serialized-LODF subset. U is a numerically checked physical witness; physical DC lower-bound certification remains false.
- June seed2 carried a target-feasible diagnostic source point before final physical QA. Its carried source had material overflow and was not production-quality eligible; the later selected endpoint passed the complete quality gate.
- No conventional comparator, historical timing ratio, outcome-driven option change, replacement run, optimizer/checker rerun, forced new-line growth or third MIP was added.

## Bound domains and public evidence

The hard-zero subset fixes shedding and reserve shortfall to zero. Its lower
bounds are not valid for the original soft optimum or for the broader
negligible-shedding domain. Numerical MIP L is display-allowance-adjusted and
is not an exact certificate. Exact seed-LP L is a certificate for the serialized
projected literal-row matrix. The checked physical U does not turn either L
into a certified physical-DC lower bound. No general production-readiness claim
is made.

The [six-run evidence index](evidence/seed-panel-summary.json) links each
field-mapped terminal audit. [The final descriptive audit projection](evidence/seed-panel-final-audit-summary.json)
binds the extrema, medians, complete coverage description and original audit
hashes. Original full raw receipts remain separately retained; this public
package contains compact selected records, code and documentation, not native
binaries or datasets. No optimizer, scientific checker, test or build was run
for this publication projection.

## Post-exit administration

All six terminal and closure archives passed actual-byte/member readback verification.
Raw original evidence was retained. Recorded cleanup removed only recoverable
campaign archive/readback duplicates after successful verification. The saved
[administration projection](evidence/seed-panel-administration.json) preserves
receipt hashes, selected fields and derivation metadata.

| Run | Measured assembly + verification s | Measured terminal readback verification s | Filesystem mtime-to-closure span s |
|---:|---:|---:|---:|
| 1 | 16.950334 | 4.142915 | 2808.580862 |
| 2 | 10.227675 | 2.921133 | 332.783207 |
| 3 | 10.502041 | 2.710478 | 199.200649 |
| 4 | 10.616687 | 2.935377 | 146.333163 |
| 5 | 10.440639 | 2.551274 | 197.034236 |
| 6 | 15.059569 | 4.364485 | 518.634144 |

The last column is the explicitly filesystem-derived difference between the
immutable outer receipt mtime and closure verified_at. It includes audit work,
archival/readback, pauses, waiting and interruptions; it is not a monotonic
continuous-compute measurement or transfer-only time. The two measured columns
are components within that span, not additive independent clocks. Upload duration
was not measured uniformly and remains unavailable.

The large run01 pause happened after completed solver/QA work. It does not extend
or get stitched into that invocation’s scientific clock. None of these
post-exit quantities changes the reported complete outer invocation, candidate
window or solver-process ledger.

Run06 had one explicit archive transfer failure before finalization. A retry
through the same helper succeeded, followed by actual terminal and closure
readback. The failed receipt hash is retained in the administration projection.
This did not repeat a scientific invocation; no transfer time is inferred.
