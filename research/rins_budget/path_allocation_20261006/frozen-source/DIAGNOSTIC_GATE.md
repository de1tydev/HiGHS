# Predeclared two-slot diagnostic gate

Freeze before build or numerical execution. This is one mechanism/measurement
gate, not a speed comparison, and not the original 7-model/3-seed cache panel.
The parent owns execution, evidence retention and the decision.

## Inputs and schedule

Use official `d547a3ad8af5399651187fb0e133cf0e42615b82` inputs only:

1. `check/instances/dcmulti.mps`, seed 1,
   SHA256 `a9552af8f0fd228851352ba60b62a64639f8ffd4a01f217afc095eaac4c29a75`
2. `check/instances/gesa2.mps`, seed 1,
   SHA256 `fe43df9f95b79fbceae3b4c5f8a152e9498facf5adf750f6255fe4c693af02c3`

Exactly one candidate diagnostic solve per model, in the order above. No new
models, seeds, cache runs, repetition, or threshold tuning in this gate. These
are already exposed development cases, not independent validation.

Prerequisites: the parent's current-environment pristine build/reference
receipts for these exact seed-1 cases, original-matrix exporter/checker, and
existing process-tree guard must be available and verified. Historical timing
cohorts are not contemporaneous baselines. If reference or default-off
verification is not yet available, stop before this diagnostic gate and report
that prerequisite; do not silently add unbudgeted solver calls. A separate
parent-approved baseline/verification step may supply those receipts.

Build the candidate separately from the untouched official reference with the
same GCC 14.2.0 release configuration. Apply only `combined-diagnostic.patch`.
Record source, patch, binary, library and model hashes plus all build failures.
No compiler/build process may overlap a solver slot. A compile failure stops
this version for source review; it is not permission for an automatic run loop.

Each diagnostic slot uses `time_limit=60`, `threads=2`, `parallel=off`,
`random_seed=1`, `mip_rel_gap=0.0001`, `log_dev_level=2`, and writes the original
point. Keep numerical options identical to the verified fresh reference except
the declared diagnostics level. The existing
`current_scuc/slot_envelope.py::supervise` guard has a 74-second watchdog to
reserve one second of the **75-second outer per-model cap** for kill/reap.
Retain exact-reap receipts; cleanup beyond 75 seconds is a failure, not an
in-budget completion. Native time limit, watchdog, process-tree RSS and
headroom checks remain active.

Keep existing 7 GiB address-space, 6 GiB sampled process-tree RSS, 64 MiB output
file, zero core-dump, 2 GiB available-memory and 2 GiB free-disk bounds. External
BLAS/OpenMP thread limits stay at one. Solver slots are serial. At most 120
native seconds and 150 outer solver-slot seconds across the two diagnostics;
build/export/checker time is separate and must be reported. Do not run published
`paired.py --stage cost-profile` unchanged: that expands to six solves.

## Required evidence and immediate stops

Retain options, raw stdout/stderr, return codes, guard receipts, solutions,
original matrices, checker reports, parsed diagnostic records and every failed
or incomplete slot. Stop before the next slot on timeout, missing input,
nonzero guard/health error, process failure, incomplete log, missing point or
failed independent original-matrix primal/objective check. Never omit a failure
from the denominator. Optimal status is tolerance-based, not an exact dual proof.

Compare status, objective, reported dual bound, gap, node count, LP iterations
and solution bytes against the fresh same-seed reference, allowing only the
already documented objective-token serialization tolerance in the independent
checker. Any other mismatch is a stop for investigation, not grounds to choose
a different seed. This catches trajectory/output changes but does not by itself
prove transformed-input or cut-by-cut identity.

For every invocation group require:

- One cost record and all seven uniquely named vector records, consistent scope
- Finite nonnegative times, payloads and counters; no counter overflow
- `capacity_anomalies == 0`
- Each first-five-vector growth count equals `eligible`
- Four reserve requested byte totals equal `eligible * (num_col + num_row) *
  sizeof(element)`; rhs requested bytes equal `requested_rows * sizeof(double)`
- For each vector, new-capacity payload is at least requested payload; final
  payload is no greater than sum of new-capacity payload
- Tmp-vector growth counts are each at most `transform_calls` and equal each
  other on this standard library; any disagreement needs review, not averaging
- `first_transform_failed <= transform_failed`, `mixing_ready <= eligible`,
  `usable_rows <= requested_rows`, and
  `truncated == transform_failed + rhs_first_rejected + rhs_order_rejected`
- `eligible <= transform_calls <= requested_rows`; exactly 32 clock samples
- Setup and destruction spans sum to no more than the instrumented path-body
  span, subject only to floating-point summation tolerance of 1e-9 seconds

Invalid or absent accounting stops the gate. Preserve main/sub-MIP and depth
breakdowns and zero-attempt groups. Do not sum block times with their inclusive
path-body or separator totals.

## Fixed decision after both valid slots

For each model independently define A = total eligible attempts, S = summed
setup plus destruction seconds, P = summed instrumented path-body seconds.
For invocation j define E_j = `clock_pair_seconds / clock_pair_samples` and
O = sum over invocations of `2 * eligible_j * E_j`. O is an **empty-clock-pair
proxy**, not measured total instrumentation overhead; report S, P and O
separately without claiming S-O is allocator time.

The diagnostic supports considering a separate workspace-reuse proposal only
if **both models** meet every condition:

1. All process, primal/reference and accounting checks above pass
2. A >= 32, establishing repeated eligible attempts
3. S >= 0.005 seconds, S >= 10 * O, and S/P >= 0.05
4. The reported first-five requests and payload identity confirm their repeated
   allocation-capacity requests; no attribution is made to excluded vectors

These are predeclared materiality and clock-signal screens, not speedup targets.
Even passing does not show that all S is avoidable: rhs reset and ordinary
vector work remain, and timing has observer perturbation. A later optimization
requires its own default-off implementation, source/cut-equivalence review,
bounded validation plan, and separate authorization for execution.

If a signal screen fails, report insufficient measured benefit to pursue this
narrow mechanism under v1 and stop. If clock noise/overhead or invalid records
make attribution inconclusive, report that and stop. Do not expand the panel,
rerun until favorable, adjust the thresholds or implement reuse under this gate.
No outcome permits a speedup, release, SCUC-transfer or allocator-dominance claim.
