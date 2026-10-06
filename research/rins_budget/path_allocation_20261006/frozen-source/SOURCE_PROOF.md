# Source proof and explicit limitations

References below use pristine official commit
`d547a3ad8af5399651187fb0e133cf0e42615b82` line numbers. The research-fork solver
is not a reference. No compiled or numerical checks have been run for this probe.

## Original lifetimes and work preserved

`highs/mip/HighsPathSeparator.cpp:394–411` is the eligible attempt and original
setup block. Four empty vectors reserve `lp.num_col_ + lp.num_row_` elements;
`rhs(pathLen)` value-initializes every entry to zero; the two transform-output
vectors begin empty. Those exact statements and their order stay unchanged.
The only before/after setup additions read clocks and diagnostic scalar state.

The destruction timer is declared after `indexPos` and before all seven vectors.
Reverse destruction order therefore destroys `tmpSolval`, `tmpUpper`, `rhs`,
`isIntegral`, `upper`, `solval`, and `inds` before sampling the timer endpoint;
`indexPos` is destroyed afterward. The inner `cutVals`, `maxFrac`, `downSum`,
and `fSum` scope has already ended before the timer is armed. Trivial scalar
lifetimes and the ending branch are included. The timer is not armed during
exception unwinding before the normal block end; failed/aborted executions are
not valid complete observations.

No vectors move to another scope. No extra clear, reserve, resize, assign, swap,
copy, read of uninitialized elements, custom allocator, or global state is
introduced. `aggregatedPath` and `indexPos` lifetimes remain original. Random
calls, selection predicates, coefficient updates, rhs comparisons, delta,
transformation initialization, cut generation and admission remain unchanged.
The transform expression is evaluated once into a boolean with its original
arguments, then the same original `if (!result)` branch is taken. All added
branches control diagnostic scalars/output only, not solver state.

This establishes source-level noninterference with solver decisions/arithmetic,
not a bitwise-runtime theorem: code generation, elapsed-time decisions, allocation
failures, and scheduling may still respond to instrumentation overhead.

## Early failures, truncated rhs, and scratch semantics

- `HighsTransformedLp.cpp:183,364,384` can fail before the output resizes at
  `438–439`. Prior `tmpUpper`/`tmpSolval` size and contents can survive such a
  failure. The caller sets `pathLen=k` and breaks before consuming them. The
  observer reads only size/capacity, including on failure, never contents.
- Transform failure can also occur after both resizes (`475`, `486`); growth is
  still counted. In the assertion-disabled unused-bound path, outputs may be
  only partly overwritten. No caller reads that failed row's output.
- A successful transform resizes both outputs to `numNz` then assigns every
  `upper[j]` and `solval[j]` in the retained range (`438–482`). Shrinking doesn't
  release capacity. A later successful longer row must overwrite all newly
  accessible outputs too. This is existing within-attempt reuse, not new reuse.
- The transform may mutate the failed aggregated row and internal bound state.
  The probe performs the call unchanged and neither restores nor retries it.
- The first rhs may reject a transformed row (`HighsPathSeparator.cpp:427–432`),
  and nondecreasing rhs rejects later rows (`433–436`). Both set `pathLen=k`.
  `rhs` itself retains its original allocated size; only the accepted prefix is
  consumed by the cut loop. On every new attempt the constructor zeroes all
  original rhs entries again. Reusing rhs in a future change would require
  resetting every element to zero, not merely resizing an already same-size
  vector. This probe makes no such change.
- `initMultiRowTransform` at `HighsTransformedLp.h:68–70` resets bound types per
  attempt and remains in the original position. Successful outputs and the
  same-bound consistency conditions cannot be inferred from vector emptiness.
- The four union vectors start empty and append only a first-seen index. Reuse
  would require clearing logical sizes even after an early failure. `inds` can
  later be reordered, shrunk, replaced by untransformed original indices, and
  shrunk again during finalization. The other parallel arrays are no longer
  read after this cut-finalization path. The probe leaves all of that intact.

## Capacity accounting

For each eligible attempt, the four reserves plus nonempty rhs constructor
create five observable zero-to-positive capacity transitions. `requested` is
the actual reserve target or constructor length. The payload uses `sizeof` at
the candidate build: `HighsInt`, `double`, `HighsBool` (the latter is `uint8_t`
in `highs/util/HighsType.h:19`), so no packed `vector<bool>` estimate is used.

Tmp outputs each have exactly one possible `resize` per transform call, and no
other operation in transform changes their capacity. A before/after increase
therefore identifies one capacity-triggered reallocation request. Its requested
payload is the resulting size times element width; its observed capacity
payload uses the complete resulting capacity, not the incremental growth.
An early pre-resize failure contributes zero, even if the stale vector remains
nonempty. A successful no-growth resize contributes zero allocation requests;
the observer does not claim to count all logical resize calls.

The first four vectors' inserted indices are unique in the domain of LP columns
and row slacks, bounded by the reserve target. Later `inds` shrink at
`HighsPathSeparator.cpp:531–532`; `untransform` assigns original column indices
at `HighsTransformedLp.cpp:606`; `finalizeAndAddCut` at
`HighsCutGeneration.cpp:1293–1349` uses data pointers and only shrinks vector
sizes. Thus on the baseline standard library there should be no additional
capacity-triggered growth beyond those reserves. The final-capacity check flags
any violation instead of guessing how many hidden operations occurred.
`rhs` never grows within an attempt. Any nonzero `capacity_anomalies` is a hard
stop for interpreting the measurements.

These are C++ vector-operation/capacity observations, not allocator instrumented
measurements. They exclude allocator metadata, size classes, thread caches,
page mapping, system calls, live/peak RSS, simultaneous old/new buffers, and
allocations in hash tables, nested aggregated rows, cut vectors, vector sums or
other solver code. Same-capacity replacement allocations cannot be observed;
the first-five inference relies on the inspected operations and standard-library
behavior, not merely a final snapshot. All counts/payload sums use 64-bit
unsigned counters but contain no saturation logic; overflow invalidates a run.

## Timers and remaining verification

Two clock pairs per eligible attempt measure setup and normal destruction. No
timer is placed in a coefficient or append loop. The independent empty-pair
sample is deliberately reported separately. Its mean can screen out spans
comparable to clock overhead, but does not model branch/counter overhead,
cache effects, scheduling noise or diagnostic printing. Clock samples are not
kernel work, and a mechanically subtracted result must not be called measured
allocator time. Setup includes rhs zeroing that reuse still needs; tmp growth
inside transform is counted without attributing transform time to allocation.

The companion separator observer is copied byte-for-byte from the publication;
it modifies only `HighsSeparation.cpp`, while the new patch modifies only
`HighsPathSeparator.cpp`. Both apply to the same official base and do not add
cache options. It uses the already published C++11 `std::function` form.
The new source uses C++11 features only by inspection. Apply checks and source
review do not substitute for compilation, runtime/default-off checks, sanitizer
checks or cut-level/numerical verification, none of which this worker performed.
