# Checked-history functional results — 2026-10-06

**PASS:** 15 pure test methods and all six fixed generic-MILP arms. Eight actual
optimizer processes and two deterministic failure helpers ran. All six final
points passed independent original-matrix checks and attained objective **13**,
the optimum found by enumerating the four-binary fixture's 16 assignments.
This qualifies the interface; it establishes no large-SCUC result or speedup.

## Observed paths

| Arm | Probe outcome and final start | Complete arm wall, s |
| --- | --- | ---: |
| Cold | No probe; fresh cold solve | 0.677906 |
| Partial consensus | Two of four binaries suggested; completed point checked and transferred | 0.723533 |
| Infeasible suggestion | Native probe recovered a feasible point; checked complete start transferred | 0.751567 |
| Abstention | Only two eligible windows for k=3; no probe, fresh cold solve | 0.742823 |
| Timeout fixture | Failure helper terminated and exactly reaped; fresh cold fallback | 4.715878 |
| Invalid-point fixture | Incomplete named vector rejected; fresh cold fallback | 0.815340 |

The infeasible-suggestion arm recovered **inside the native probe**; it did not
exercise the cold-fallback branch. The timeout and invalid-point arms used
test helpers in place of the probe optimizer. They qualify deterministic
controller failure handling, not HiGHS behavior on a naturally difficult or
timed-out model. Every actual native call returned Optimal, preserved the
external model fields and option readback, and produced a complete finite
point. Final correctness uses independent enumeration and point checking;
the interface exports no solver lower bound or gap certificate.

The complete functional owner measured **9.760229961 s**, including pure
tests, fixture generation, every arm, output writes and exact process reaping.
This is distinct from the controller's pre-result-write timers. The campaign
had a 360 s ceiling, each arm 30 s, and each probe a 5 s process allocation
with a 4 s watchdog. The intentional timeout helper consumed **4.003445767 s**;
its final solve received the remaining allowance, with no ledger reset. All
owned processes were reaped; there were no resource, cancellation, outer
watchdog or unexpected-cleanup failures. Nested timings must not be summed.

The 15 pure methods include tampered artifacts, invalid points, fabricated
checked flags, nested label mutation, equivalent UTC encodings, duplicate and
conflicting windows, chronology, feature/column ordering, unanimity abstention,
strict named vectors, cold-final routing and terminal integrity-failure handling.
The earlier 13-method result and source-review revision remain retained.

## Genuine historical label admission

A separate data-only invocation admitted the archived case1354pegase
2017-06-01 36-hour endpoint, solver seed 1, final selected call 2. Fresh checks
bound three immutable archives and 30 pinned members to the original source,
313,776-value point, 28,080 u/y/z binary inventory, full original/literal/source/
listed-outage/direct-DC evidence and slack-quality receipts. It extracted
**9,360 literal 0/1 u values** and 36 source-load features without rounding.

The archived audited cost remains **13,776,319.428000957**. This is an existing
checked endpoint, not the result of a new solve. No optimizer, archived script
or physical checker was executed during admission. Its complete outer wall was
**2.440651665 s**; the internal admission timer was **1.792775779 s**. The small
adapter build was separate and took **2.888758450 s** through exact reap.

The conservative observed availability is the archived audit timestamp
**2026-10-06T03:20:07.965065+00:00**; fresh admission completed at
**2026-10-06T16:47:57.272418+00:00**. The June 2017 scenario date does not make
this label available in 2017. Old monotonic fields remain unchanged historical
evidence; fresh validation uses the current clock. This is one exposed
development window, not three neighbors or a chronological training corpus.
No January/April 2017 target may use it as a past label. The preselected Jan 15,
Apr 15 and Jul 15 raw-source access blockers remain unresolved.

## Provenance and interpretation

The adapter links pristine HiGHS commit
`d547a3ad8af5399651187fb0e133cf0e42615b82`, with seed 1, two threads,
parallel off and zero requested relative/absolute MIP gaps. The public
sparse-start API performs private temporary bound fixing during completion;
the adapter verifies all sixteen external model fields before/after run.
The fresh final process receives only an independently matrix-checked complete
point. Such a point is not a full-SCUC physical upper until the separate
source/literal/direct-DC/quality gates pass. No probe bound is promoted.

Tested source pins remain in [SOURCE_REVIEW_v2.json](SOURCE_REVIEW_v2.json).
Its digest is `d3f28f71864a303c616d1c84e1d41952b966c2f72f0f5c0616d7643bfa70cc9e`.
Runtime and test source bytes are unchanged; README and this results document
were written after execution. Exact executable/source identities:

- Adapter source: `1dd90e7da32f73a457b01cb04160870c090b7d2a59410f2bad65587fc22a33bc`
- Adapter executable: `64fc588e461c918ead65bd55c9c0dbaa9667f3047d0ba95734e41ea9b48944ca`
- Loaded HiGHS library: `79b1a12b57066b10494525d15ce7568059ca31d48b8bf6b403f5bf1f31e21ce8`

Retained evidence is identified by these files and SHA-256 values; the raw
run directories are separate from this source directory:

- `checked-history-functional-owner-v1/receipt.json`: `bb8ad40719ad23bca86e75ad93b495b926feba526ef4d91f47a62d7233670ed5`
- `checked-history-functional-v1/summary.json`: `72f12324780b1a04c7fe90ba793506aaa8f6190966433c4d4f946988e4c8fb9b`
- `checked-history-june-label-v1.json`: `f3bf546397a19413cfcacf6926575b8ec9b1a604d633f6fd3ff78b8e22728c88`
- `checked-history-june-admission-owner-v1/receipt.json`: `e48fb9c5d7152069906df988c43cb68a729e45177634a7b903c4649f3041d936`
- `checked-history-build-owner-v1/receipt.json`: `6f10f597813b2f3874f95d463b29c99d39b6bcc17cb3d8b572a2c8bb6b2206d7`

The frozen SCUC package, ordinary HiGHS kernel and earlier negative results
remain unchanged. No annual backtest, target-day prediction, large-SCUC
repair/fallback solve, unseen-case generalization, 600-second production result
or acceleration comparison was performed.
