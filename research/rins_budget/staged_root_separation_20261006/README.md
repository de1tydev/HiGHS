# Staged root separation: skips observed, cost screen failed

The fixed four-call pilot produced genuine child-root separator skips on both
models, but failed its predeclared cost screen. **This prototype is not promoted;
the experiment stops without tuning, repeats, additional cases or a larger
campaign.** Terminal audit confirmed the frozen source, runtime, schedule, raw
telemetry, final native fields and independently recomputed original-matrix
checks. It confirmed mechanism PASS and combined cost-screen FAIL.

| Model, seed 1 | OFF wall (s) | ON wall (s) | Wall change | CPU change | Useful ON skips |
| --- | ---: | ---: | ---: | ---: | ---: |
| dcmulti | 2.638312561 | 3.458159852 | +31.1% | +35.7% | 6 |
| gesa2 | 0.531143442 | 0.341597679 | -35.7% | -36.4% | 1 |

The gate required **both** models to reduce whole-process wall time by at least
10%, with no process-tree CPU increase above 10%. dcmulti failed both conditions;
gesa2 passed. The separate mechanism gate passed both models. These are four
exposed observations in a fixed order, not a stable or general speed estimate.
There is no SCUC or full-application CLI performance result here.

## What the prototype changes

The exact [source patch](SOURCE_DELTA.patch) applies to pristine official HiGHS
development commit `d547a3ad8af5399651187fb0e133cf0e42615b82`. It introduces
`mip_staged_root_separation`, a Boolean option whose default is **false**.
Both pilot arms use the same rebuilt binary and identical instrumentation.
No callback or other experimental solver-body patch is mixed into this source.
The research repository's compiled solver and production defaults are unchanged.

With the option enabled, only explicit main-MIP and heuristic-child root calls
with serial-MIP configuration and the matching domain/LP are eligible. Nonroot
and parallel-MIP paths keep their existing behavior. After the implied-bound,
clique and tableau stages, the prototype selects cheap cuts and resolves a
nonempty batch before path/mod-k/machine separation. Ordinary integral or bound
closure can then omit the remaining separators. Otherwise it reconstructs the
transformed LP and aggregator from fresh state and continues. Existing root
evaluation owns admission and closure; pool and LP aging are bounded to at most
one ordinary aging pass per round. Native error/limit/unbounded exits do not
count as useful skips.

All seven useful skips occurred in child roots: dcmulti had two integral and four
bound-closure skips; gesa2 had one integral skip. Neither main root produced a
useful skip. Actual skips do not establish net work saved:

- dcmulti's main-plus-child root path calls increased from 152 to 183, with path
  time 1.035906 to 1.218734 s and observed root `resolveLp` calls 165 to 337.
  Native total nodes increased 3 to 7 and LP iterations 11,461 to 16,057
- gesa2's path calls decreased 37 to 20, while root `resolveLp` calls increased
  45 to 50. Native nodes remained 1; total LP iterations fell 1,954 to 1,293.
  Its entire gain cannot be attributed to the single omitted path call:
  staging also changed subsequent cut selection, solves and search trajectory

## Correctness and measurement

All four calls finished with native `Optimal` at the requested 0.01% relative
gap and passed the unchanged independent original-matrix checker. Original
objectives were unchanged within each pair: 188182 for dcmulti and
25779856.371697918 for gesa2. Bounds and integrality residuals were zero; maximum
row residual was 1.4e-12 against tolerance 1e-6. Exact final native dual bounds,
gap strings and objective-recomputation errors are retained in
[RESULTS.public.json](RESULTS.public.json). The primal checker is not an
independent dual proof, and these requested-gap results do not claim exact
mathematical optimality.

The [fixed protocol](PILOT_CONTRACT_v2.json) was declared before the candidate
build and runs. The sequence was dcmulti OFF, dcmulti ON, gesa2 ON, gesa2 OFF,
all seed 1, `threads=2`, `parallel=off`, 20 native seconds and 30 contained process
seconds per call. The two scheduler threads do not enable parallel MIP.
Whole-process wall includes startup through exact process reap. CPU is the
serial `RUSAGE_CHILDREN` user-plus-system difference around each invocation,
counted once. The raw before/after OS snapshots were not persisted, so the
recorded deltas cannot be independently reconstructed from those snapshots.
Exporters were separately reaped before solve measurements.
The entire export/solve/check phase finished in 7.276920361 s within its 240 s
cap, with clean resource, timeout and descendant-cleanup checks.

Diagnostic root timers are nested observations, never added to OS wall or CPU.
`cheap_lp_*` is a subset of `lp_*`; aging-triggered `lp0_*` solves are separate.
RSS is a health-sampled summed process-tree observation, not an exact or unique
physical-memory peak. Public hashes identify retained raw evidence; raw logs,
machine-local paths and the containment harness are not bundled here.

## Qualification and setup record

Before the pilot, the focused suite passed 9 cases / 289 assertions, targeted
regressions passed 119 / 1,389, and selected CTest passed 167 / 167. The full
native suite passed 408 / 409 cases (1,260,340 / 1,260,341 assertions). Its sole
failure, `AffinityReducedCoreCount` reporting `5 == 1`, was already reproduced
against the official library in this same runtime. **The full suite did not
pass completely.** The pristine-versus-option-OFF triangle check had identical
solution bytes, native bounds, nodes and iterations, and zero original-matrix
residuals. Focused tests cover default-off behavior, opt-in triangle min/max and
offset cases, root handoff, guarded states, cut-pool bookkeeping and nonroot
parity. Both ON pilot runs exercised normal main-root cut-row deletion and LP0
refresh: 18 rows for dcmulti and 77 for gesa2, each ending in a valid fractional
optimal LP state. Those LP0 optimizations took zero simplex iterations. No
dedicated LP0 stress fixture or early-stop aging deletion that reopens a
fractional state was demonstrated. Controlled injected statuses are not observed
numerical defects.

The first build stopped safely on a `/proc` health-sampling ESRCH race. A narrow
build-wrapper correction for vanished sampled processes allowed the unchanged
source build to resume successfully; the failed build receipt is retained.
A separate no-solve preflight rejected a literal `ldd` path spelling containing
`bin/../lib`; comparing the exact resolved target corrected it. These were setup
events, not failed pilot solver calls. No source, threshold or option changed in
response to the measured pilot results.

## Build and opt in

This package contains a patch, fixed protocol and compact result; it is **not a
standalone research-harness replay bundle**. The following builds the prototype
from a clean checkout at the pinned commit. Copy `SOURCE_DELTA.patch` beside that
checkout first; run from the checkout. Use GCC/G++, CMake, Ninja and zlib.

```sh
git checkout --detach d547a3ad8af5399651187fb0e133cf0e42615b82
git apply --check ../SOURCE_DELTA.patch
git apply ../SOURCE_DELTA.patch
cmake -S . -B build-staged -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DFAST_BUILD=ON \
  -DBUILD_SHARED_LIBS=ON -DBUILD_SHARED_EXTRAS_LIB=ON \
  -DHIPO=OFF -DHIGHSINT64=OFF -DDEBUGSOL=OFF -DZLIB=ON \
  -DCUPDLP_GPU=OFF -DHIPDLP_HIP=OFF -DBUILD_TESTING=ON -DALL_TESTS=ON \
  -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++ \
  -DCMAKE_C_FLAGS= -DCMAKE_CXX_FLAGS= \
  '-DCMAKE_C_FLAGS_RELEASE=-O3 -DNDEBUG' \
  '-DCMAKE_CXX_FLAGS_RELEASE=-O3 -DNDEBUG' \
  -DCMAKE_EXE_LINKER_FLAGS=-flto=2 -DCMAKE_SHARED_LINKER_FLAGS=-flto=2 \
  -DCMAKE_BUILD_RPATH_USE_ORIGIN=ON
cmake --build build-staged --parallel 2
build-staged/bin/unit_tests '[staged-root-separation]'
```

Rebuild consumers against these matching headers and library; internal class
layouts changed. Do not inject this library into a prebuilt, differently patched
test executable. Confirm the executable loads its matching newly built library.
Runtime hashes identify the recorded build, not a promise of bit-identical
binaries from a different compiler or machine.

For an opt-in invocation, make a fresh `pilot-output` directory in that checkout
and create `pilot-output/staged.options`:

```text
time_limit = 20
threads = 2
parallel = off
random_seed = 1
mip_rel_gap = 0.0001
mip_abs_gap = 0
log_dev_level = 2
write_solution_to_file = true
solution_file = point.sol
log_file = native.log
mip_staged_root_separation = true
```

From `pilot-output`, run:

```sh
../build-staged/bin/highs ../check/instances/dcmulti.mps --options_file staged.options
```

Set the experimental option to `false` for OFF; use fresh output directories per
call. The option may also be set through
`Highs::setOptionValue("mip_staged_root_separation", true)`.
This simple invocation does not reproduce the original containment, resource
measurement or independent-matrix checking; those are requirements for a new
research replay, alongside the frozen order and conditions in the protocol.

The root repository [MIT license](../../../LICENSE.txt) applies. This is an
unpromoted research checkpoint, with no upstream issue, PR or master change.
