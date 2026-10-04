# Interrupted chronological-cache experiment, 2026-10-04

The June PG1354 cold/warm comparison has **no completed, auditable paired result**. At 01:55:54 UTC, the execution connection failed during session recovery. The replacement workspace did not contain the source checkout, builds, unpublished adapter, or local experiment artifacts. The original process's final state cannot be established from the replacement environment.

The last independently verified public checkpoint is [9a820016](https://github.com/de1tydev/HiGHS/commit/9a8200169d6397b5094f4f74b2033c1ca8397f22). Its published reports and [pristine replay kit](portable_pristine_reference_replay_v3/README.md) remain available. Those published results are separate from this interrupted, unpublished experiment.

## Observations returned before the interruption

These observations survive in completed execution and review records. The missing raw files are not reconstructed or represented as still available.

- A prospective, primal-only May training acquisition was reported and reviewed as accepted. It used pristine official HiGHS `d547a3ad8af5399651187fb0e133cf0e42615b82`, one full-temporal original-objective LP with integrality relaxed, IPX, and crossover off. It transferred only security-pair identities, never an LP bound, optimality certificate, basis, incumbent, or solver state.
- The full reported acquisition cost was **368.870966473 seconds**, including **224.552564188 solver seconds**, **103.942095471 checker seconds**, and **1.372750942 cache-construction seconds**. Cache construction was already included in the total. The checks covered the original continuous model and 1,288 specified outages / 66,360,168 pair-hours, yielding two witnessed May pair identities. Tiny positive source-allowed slacks were retained. This was acquisition feasibility evidence, not an acceleration result.
- Known initial-basis and absolute-dual-residual diagnostics were retained under a separately reviewed, prospective selection-only policy. The earlier warning-based admission failure and separate saved-point diagnosis were not relabelled as a pass.
- The declared June order was **E then W**. E began with empty security rows, integer discovery, and a fresh proof solve. W was to begin with the newly learned May identities and proof directly, followed by complete current-source checking and online separation. Thus the comparison concerned the combined cache and discovery-scheduling policy, not cache-only causality or a solver-kernel change.
- E's two solver processes returned normally, taking **211.541034542** and **386.172960833 seconds**, or **597.713995375 seconds** combined. The second log reported a time limit and a **14.4% master gap**. Its final original-source/outage checker had not returned a confirmed result before the connection failed. E therefore has no verified 1% full-SCUC result.
- W's launch and terminal state are **unknown**. It is not recorded as completed, failed, or definitely unrun. No speed ratio, full-SCUC certificate, or warm-policy success is inferred.

Recorded identities are historical anchors, not downloadable artifacts: adapter freeze `378cbabaa7a1e6e363e65b1b1dfb2e132f0edf385844d6556838161340906b91`; May episode `2bba70e2a11a1eae23203a2cd70b425f5548751d8e76464755a9f0d98deb8c1b`; May cache freeze `d3b06f3bc4beaae86ac347a9519dc620c5fef60f2bc648eb9d7eda1b9da4ff7c`. The complete corresponding source manifest, point, witnesses, raw logs and final June receipts are currently unavailable.

## Recovery boundary

Recovery starts from the verified public checkpoint with a fresh runtime fingerprint, rebuilt reference, and new admission checks. A new comparison must declare and execute both arms on that runtime; pre-interruption E measurements cannot be combined with a new W. The interrupted attempt remains in the research history. Reserved confirmation inputs remain reserved.

Before further expensive experiments, the adapter and exact contract will be stored durably before launch. Terminal stages will retain sufficient source identities, points, checks, cost/cleanup receipts and hashes in durable storage. Research archival time will be reported separately from measured solver and user-relevant invocation time; unavailable raw evidence will not be manufactured from these observations.
