# RINS budget research: replayable diagnostic and ablation tools

This directory is an opt-in research package. It does not change the production
solver, its build, or its defaults. All solver checkouts below are pinned to
HiGHS commit `73cac48c5340d775a477087198611862559be250` (source version 1.15.1).
The patches are separate artifacts, not an enabled solver optimization.

## What is being compared

- `rins-diagnostics.patch`: observes each serial RINS scope using a steady clock
  and logs local fields to stderr when `HIGHS_RINS_DIAGNOSTICS` exists. It adds no
  search-policy decision. Instrumentation and logging have overhead, and can
  affect time-limit behavior. Even when logging is disabled the patch takes an
  entry timestamp, so use the clean baseline for performance measurements
- `nested-rins-off.patch`: an experimental ablation that retains main-problem
  RINS and skips the guarded RINS call for sub-MIPs. This changes search behavior.
  It is neither a tuned adaptive budget nor a recommendation for new defaults
- `options/no-rins.options`: the existing public option
  `mip_heuristic_run_rins = false`. Unlike the nested ablation, this disables
  both main-level and inherited nested RINS through that option
- `outer-gap-heuristic.patch`: a separately tested, default-off serial heuristic
  early-return experiment. See [`OUTER_GAP.md`](OUTER_GAP.md) for its guards,
  replay commands, and modest one-seed result
- `milp_probe.cpp`: a standalone public C++ API driver, read-only incumbent
  callback, optional built-in profile, and independent final-primal arithmetic
  checks against a snapshot of the original linear model
- `run_paired_probe.py`: portable, sequential fixture runner with explicit
  source, binary, output, seed, time, and gap arguments
- `scuc/`: separately documented public-data custom UC/DC-SCUC generator,
  independent checker, exact separation driver, source notices and manifests

Small zero-gap fixture results do **not** transfer automatically to 1%-gap SCUC.
RINS work observed after the requested 1% gap has already been attained might
never run under that stopping target. A useful local incumbent update also does
not establish net global benefit. Retain negative and incomplete outcomes, and
use harder representative tuning/holdout cases before proposing a policy change.

A separate same-build optional HiPO/OpenBLAS comparison is documented in
[`HIPO_RESULTS.md`](HIPO_RESULTS.md), including its negative outcome.

The completed exploratory measurements and their limits are in
[`RESULTS.md`](RESULTS.md). Compact, sanitized supporting records are in
[`recorded_results/`](recorded_results/), with zero-gap fixtures and 1%-gap SCUC
kept separate. These are historical measured records; a new run creates its own
local output directory and does not overwrite them. `SOURCE_MANIFEST.json`
identifies the frozen patches and SCUC core used for replay.

## Prepare independent pinned checkouts

Use Git, Python 3.9+, CMake, Ninja and a C++11-capable compiler already installed
on your machine. These examples are shell commands for a Unix-like host. Set
`PACKAGE` to this directory and `WORK` to a new local directory; neither path is
hard-coded in the tools. Do not point them at a checkout with uncommitted work.

```sh
PACKAGE="$(pwd)/research/rins_budget"  # run from this repository's root
WORK="$HOME/highs-rins-replay"
PIN=73cac48c5340d775a477087198611862559be250
mkdir -p "$WORK"
for variant in baseline diagnostic nested-rins-off; do
  git clone https://github.com/de1tydev/HiGHS.git "$WORK/$variant"
  git -C "$WORK/$variant" checkout --detach "$PIN"
  test "$(git -C "$WORK/$variant" rev-parse HEAD)" = "$PIN"
done
git -C "$WORK/diagnostic" apply --check "$PACKAGE/rins-diagnostics.patch"
git -C "$WORK/diagnostic" apply "$PACKAGE/rins-diagnostics.patch"
git -C "$WORK/nested-rins-off" apply --check "$PACKAGE/nested-rins-off.patch"
git -C "$WORK/nested-rins-off" apply "$PACKAGE/nested-rins-off.patch"
```

The upstream source is https://github.com/ERGO-Code/HiGHS at the same commit.
Do not stack these patches for the latency comparison. The candidate should
contain only the nested ablation; the baseline should contain no solver edits.

## Exact Release builds and correctness tests

The original compiler/tool versions were GCC 14.2.0, CMake 4.4.3 and Ninja 1.13.2.
Release uses `-O3 -DNDEBUG` with this source's automatic LTO when supported.
Record any different compiler, flags, toolchain, CPU, operating system, library
linkage and LTO behavior; portable replay does not promise identical timings.
Finish all builds/tests before measuring, and keep each configure/build/test log
outside the published source package.

```sh
for variant in baseline diagnostic nested-rins-off; do
  cmake -S "$WORK/$variant" -B "$WORK/build-$variant" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++ \
    -DBUILD_TESTING=ON -DALL_TESTS=ON -DBUILD_EXAMPLES=OFF \
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
  cmake --build "$WORK/build-$variant" --parallel 4
  ctest --test-dir "$WORK/build-$variant" --output-on-failure --parallel 2
  cmake -S "$PACKAGE" -B "$WORK/probe-$variant" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=g++ \
    -DHIGHS_DIR="$WORK/build-$variant"
  cmake --build "$WORK/probe-$variant" --parallel 1
done
# Optional diagnostic correctness pass with logging enabled (not a timing run):
HIGHS_RINS_DIAGNOSTICS=1 ctest --test-dir "$WORK/build-diagnostic" \
  --output-on-failure --parallel 1
python3 -m unittest discover -s "$PACKAGE" -p 'test_probe_helpers.py' -v
```

HIPO/CUDA and external problem collections are not included in this recipe.
The probe CMake project imports the selected build-tree `highs::highs` target;
it is intentionally not added to the production root CMakeLists. On a multi-config
generator, add `--config Release` and use its configuration-specific executable
path. Always verify the selected dynamic library (for example with `ldd` on
Linux or `otool -L` on macOS), since a probe executable's hash alone does not
identify a dynamically linked library. Keep `CMakeCache.txt`, `compile_commands.json`,
the exact diff and library/executable hashes with local experiment evidence.

## Fixture performance screen

The default screen uses ten small bundled MPS fixtures, seeds 0/1/2, two repeats,
one solver thread, parallel search off, a 20-second solve limit, and zero
relative/absolute target gap. Other options remain at source defaults except
the selected RINS treatment and a common 1e-6 MIP feasibility tolerance.

```sh
unset HIGHS_RINS_DIAGNOSTICS HIGHS_PROBE_PROFILE
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python3 "$PACKAGE/run_paired_probe.py" \
  --source-root "$WORK/baseline" \
  --baseline-probe "$WORK/probe-baseline/milp_probe" \
  --comparison global-rins-off --output-dir "$WORK/results-global"
python3 "$PACKAGE/run_paired_probe.py" \
  --source-root "$WORK/baseline" \
  --baseline-probe "$WORK/probe-baseline/milp_probe" \
  --candidate-probe "$WORK/probe-nested-rins-off/milp_probe" \
  --comparison nested-rins-off --output-dir "$WORK/results-nested"
```

Use `--models small_mip --seeds 0 --repeats 1 --limit 5` for a tiny smoke test.
Use `--gap 0.01 --abs-gap 0` explicitly when researching a 1% stopping target;
that is a different experiment. The probe overrides options-file thread count,
parallel mode, seed, limit, gap and feasibility tolerance with the common
controls above. Its CLI is `MODEL OPTIONS SEED TIME_LIMIT [REL_GAP [ABS_GAP]]`.

There is one warm-up per treatment on the first selected fixture, separately
recorded and excluded from measured rows. Each pair runs sequentially, with arm
order alternating by repeat, seed index and model index. Use an otherwise idle
machine; hold CPU affinity/power policy constant between arms and record them.
Do not run builds, tests, other benchmarks or diagnostics concurrently. The runner
records visible CPU/affinity and input/binary/option hashes but does not isolate
the host, enforce power settings, or prove that a binary matches its source.

Outputs are a plan, warm-ups, complete JSONL records, raw local stdout/stderr and
a summary. Existing output directories are refused. Failed/invalid/timed-out
arms remain in the records. A model's aggregate timing ratio is withheld unless
all its arms reach the solver-reported target with valid final primals; inspect
every status, gap and objective rather than selecting only successful arms.
These small, often sub-second instances and two repeats are a mechanism screen,
not a statistically general performance study. Compare paired per-seed results
and search work as well as aggregate medians; ratios of medians can hide regressions.

`solver_seconds` excludes process startup, model read and the independent final
check. `wall_seconds` wraps `Highs::run()`, including common callback overhead;
`process_seconds` also includes loading and checking. Keep these metrics distinct.

## Per-call observation, separate from performance

```sh
HIGHS_RINS_DIAGNOSTICS=1 "$WORK/probe-diagnostic/milp_probe" \
  "$WORK/baseline/check/instances/dcmulti.mps" \
  "$PACKAGE/options/default.options" 0 30 0 0 \
  > "$WORK/rins.stdout.log" 2> "$WORK/rins.stderr.log"
# Separate optional built-in profile on a clean build:
HIGHS_PROBE_PROFILE=1 "$WORK/probe-baseline/milp_probe" \
  "$WORK/baseline/check/instances/dcmulti.mps" \
  "$PACKAGE/options/default.options" 0 30 0 0 \
  > "$WORK/profile.stdout.log" 2> "$WORK/profile.stderr.log"
```

The diagnostic CSV starts with `RINS_DIAG`, followed by: sub-MIP depth, sub-MIP
flag, elapsed seconds, upper before/after, lower before/after, solver-level nodes
before/after, heuristic-accounting iterations before/after, start/end steady-clock
nanoseconds. Calls may nest. Merge overlapping start/end intervals before
computing total time spent anywhere in RINS; summing durations double-counts.
Timestamps are process-local, not UTC. Each interval excludes its own final log
write but includes nested logging. Use only serial runs.

Bounds and incumbents are local presolved minimization-space fields; subproblem
values are not original-problem certificates. Heuristic-accounting iterations
include scaled/truncated sub-MIP work rather than raw LP work. Top-level node
counters do not include sub-MIP nodes. A synchronous unchanged bound or incumbent
does not rule out later domain, conflict, cut, pruning or search-trajectory effects.
Built-in profile clocks may also be inclusive/nested. Native profiling text can
precede JSON; parse the final line beginning with `{`, as the runner does.

## What the independent check does and does not establish

The probe snapshots the original LP before solving and independently recomputes
row activities and the linear objective using long-double accumulations. It
checks ordinary bounds, integer distances and original-row violations at absolute
1e-6 tolerance; objective agreement uses `1e-8 * (1 + abs(objective))`.
Nonfinite solution/accumulation/objective values are rejected. Quadratic,
semi-continuous, semi-integer and implicit-integer models are unsupported.

This validates **only the final primal vector** for that parsed linear model.
It does not independently parse the MPS, certify the dual bound or optimality,
check every intermediate incumbent, or prove presolve equivalence. An absent
primal has `independent_feasibility_checked = false`; the runner treats it as an
incomplete/failed arm. With a nonzero gap, solver status `Optimal` means its
configured stopping test passed, not that the exact optimum was established.

The separate SCUC source checker reconstructs constraints from input JSON and
checks all source-listed supported single-line outages; its stronger
domain-specific scope and numerical/modeling limitations are in
[`scuc/README.md`](scuc/README.md). It still does not independently certify a dual
bound. Retain the generator/checker/driver byte hashes for paired comparisons.

## Licensing and publication boundaries

HiGHS and these research additions use the repository's MIT license
([`../../LICENSE.txt`](../../LICENSE.txt)). Public-data licensing is separate;
preserve the SCUC source notices and dataset attribution, including CC BY 4.0
where applicable. The package excludes downloaded data, model exports, solution
vectors, executables, build trees and large run logs. Reproduction generates
them locally. Do not publish local logs without checking for machine-specific
paths and any private inputs. Final measured summaries, when supplied, must name
the source, target gap, scope, completion criteria and unsuccessful outcomes.

## Publication-time replay guards

The published screening driver requires a new output directory and refuses to certify an original-model bound when HiGHS reports ignored/dropped matrix coefficients. These guards were added after the recorded six-arm experiment. All recorded arms already used fresh directories and had no such warnings, so the observations are unaffected. `SOURCE_MANIFEST.json` at the research-package root retains both the historical measured driver hash and the current published driver hash. Solver-free guard tests are in `scuc/test_driver_hygiene.py`.
