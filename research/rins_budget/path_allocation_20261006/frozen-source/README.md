# Path-mixing allocation probe v1 — source-only proposal

Status: independently reconstructed diagnostic source; not compiled or executed.
No workspace reuse, coefficient cache, solver-parameter tuning, or speedup claim.
The unpublished `0f17aaa0f48b8b0d461c2684326cfbb3c6e5f474` and its uncommitted
path work were unavailable and have **not** been recovered.

Patch base: pristine official HiGHS
`d547a3ad8af5399651187fb0e133cf0e42615b82`, never the older research-fork solver.
All deliverables are in this new sibling directory; official source is untouched.
The published `cmir_cache_20261006/NEXT_EXPERIMENT.md` supplies the hypothesis,
not evidence that allocation dominates. This proposal deliberately narrows its
suggested full panel to the two diagnostic slots in `DIAGNOSTIC_GATE.md`.

## Deliverables

- `path-allocation-probe.patch`: the new, standalone one-file diagnostic patch
- `separation-cost-profile.patch`: unchanged published separator-cost observer
- `combined-diagnostic.patch`: concatenation of those independent file patches,
  directly applicable to the pristine official commit
- `source/highs/mip/HighsPathSeparator.cpp`: complete proposed path source
- `SOURCE_PROOF.md`: accounting, semantic reasoning, and limitations
- `DIAGNOSTIC_GATE.md`: fixed two-model diagnostic decision and stopping rule
- `MANIFEST.json`: source and artifact hashes with validation scope

Apply `combined-diagnostic.patch` once in a **separate candidate copy** of the
official source. Do not apply the individual patches again. The pristine
reference build stays unmodified. Build configuration and all numerical
execution belong to the parent task; this deliverable does not run them.

Both observers use existing `log_dev_level >= 2`. At lower levels the new
observer makes no clock calls, vector observations, or log writes. Default-off
does not mean zero machine-code/branch/stack overhead. All seven vectors remain
declared, reserved, populated, and destroyed at their original per-attempt scope.

## Output

Every `separateLpSolution` invocation emits one `PATH_MIX_COST` line followed by
exactly seven `PATH_MIX_VECTOR` lines, in this fixed order: `inds`, `solval`,
`upper`, `isIntegral`, `rhs`, `tmpUpper`, `tmpSolval`. `submip` and `depth`
preserve scope. Parse these as a contiguous invocation group, including groups
with zero eligible attempts. Do not infer global IDs from repeated depths.

`eligible` means `aggregatedPath.size() > 1` at the original mixing eligibility
test. `requested_rows` sums that original size; `usable_rows` sums the retained
prefix after transform failure or rhs rejection. `mixing_ready` counts prefixes
still longer than one. Failure/rejection counters partition truncated attempts.

Each vector reports **inferred capacity-growth requests**, minimum requested
element payload, sum of complete newly observed capacity payloads, summed final
capacity payload over its attempt lifetimes, and largest single observed
capacity payload. These are neither allocator hooks nor resident/peak memory.
In particular, summing capacities across lifetimes does not yield live memory.
`capacity_anomalies > 0` invalidates the first-five-vector accounting.

`scratch_init_seconds` brackets just the original seven vector declarations,
four reserves, and rhs value-initialization. `scratch_destroy_seconds` brackets
their normal-scope destructors. Neither includes transforms, union insertion,
cut arithmetic, hash-table setup/destruction, or inner cut-vector destruction.
The tmp vectors' later resize allocations are counted but **not individually
timed**. There are no per-element clocks. These block times include clock/branch
overhead, allocator work, rhs zeroing and ordinary vector setup/destruction;
they are not pure malloc/free times and are not wholly removable by reuse.

`path_body_seconds` covers the instrumented function body before diagnostics
printing, excluding invocation-local vector destruction after that body.
Published `SEP_COST name=path` still wraps the complete separator call, including
its instrumentation, the 32-pair clock sample and new output. These are distinct
inclusive observations; do not add either whole-path measure to the block times.

`clock_pair_seconds` is the **sum**, not mean, of `clock_pair_samples=32` empty
back-to-back steady-clock intervals after the path-body endpoint. Report it
separately. It is only a resolution/overhead proxy, not a calibrated overhead
subtraction. Instrumentation, formatting and I/O may perturb the solver.

No transformed-input or cut digests are added: the source argument proves that
the observer does not write those values; numerical equivalence remains a
parent-owned gate. The supplied diagnostics cannot establish cut-by-cut identity
from output alone, allocator-dominated runtime, or a workspace-reuse speedup.
