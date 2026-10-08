# HiGHS MILP and SCUC acceleration research

**Child analytic-center ablation — 2026-10-08: NO-GO.** A default-OFF,
serial-child-only omission retained checked outcomes but failed both frozen
15% paired wall-improvement gates; the first pair also exceeded the CPU limit.
All four samples and timing variation are retained. The route is closed without
retuning; the experimental patch is not recommended or enabled.
[Audited negative result, patch and compact replay support](child_center_omission_20261008/README.md).

**Bounded reference qualification — 2026-10-07:** The isolated d547 plus
#3357/#3367 candidate passed matched assertions-enabled regressions and two
full-source SCUC checks. Original Release CTest remains **168/169 passing**
with a retained affinity exception; a separate clean aggregate passes 399 cases.
The tiny case presolved empty. One exposed May PG89 cold-control arm reached a
checked-primal/solver-bound gap of 0.9800408554%, with zero raw slacks and
substantial root/internal-MIP work. This is no speed comparison or exact dual
proof. [Qualification, option-audit correction and replay limits](reference_qualification_20261007/README.md).

**Correctness checkpoint — 2026-10-07:** Pristine d547 reproduces narrow
branch-marker/stabilizer and presolve-structure failures that an isolated
official-patch candidate fixes. Both Release 3359 arms pass at objective 25.
[Results, reproduction instructions and limits](correctness_3357_3367_20261007/README.md).
This does not establish historical SCUC impact, promote a global reference, or
add a performance claim. Solver-reported MIP bounds and independently recomputed
LP certificates have different qualifications, described in that checkpoint.

**Historical-advice qualification — 2026-10-07:** A fixed May-to-June
commitment repair failed. Exact current-model row arithmetic independently
identified a capacity-plus-hard-reserve deficit, and a standalone pure-Python
[advice abstention check with tests](history_adequacy_20261007/README.md)
now rejects such necessarily infeasible hint blocks. Passing does not establish
dispatch or network feasibility. This adds no solver-speed or learned-generalization
claim and does not change the current SCUC pipeline.

**Network-projection checkpoint — 2026-10-05:** The June PEGASE1354
continuous relaxation covering all source-listed outages closed to $0.006292
in 59.249878 charged seconds, but retained 601 fractional binary values.
A fresh integer candidate produced a physically checked witness with zero
shedding/reserve shortfall and negligible overflow. It used 541.000663 charged
solver-process seconds and 978.461844 whole-invocation seconds; its 2.9323%
numerical gap missed the 1% target. No acceleration ratio or held-out release
follows. See the [audited results and preserved failures](network_projection/RESULTS.md)
and [core source with validated fixed synthetic replay](network_projection/README.md).

**Pristine-reference revalidation — 2026-10-03:** A fresh matched study on
pinned official development commit `d547a3ad` passed all nine fixed pairs,
with median reductions of **63.85% solver time and 54.03% full-arm time**.
All 18 final points passed the original source checks with zero shedding,
overflow and reserve shortfall. Every date passed the fixed median criterion;
the worst individual full-arm reduction was 28.32%. See the
[new report and all outcomes](pristine_pg89_results/RESULTS.md).
This is a new lineage without private solver patches, not a repair of historical
bounds or a larger-case/general-MILP claim. The known affinity test limitation
and the numerical-bound qualification are retained.

**Additional correctness advisory — 2026-10-03:** The two-fix reference used
for the PG89 revalidation below also reproduces the official #3270 continuous-LP presolve
failure. Its SCUC trigger is unknown. The primal checks and recorded timings
remain evidence, but the 1% endpoint and time-to-1% interpretation are provisional
pending a new reference and revalidation. [Read the new evidence and limits](CORRECTNESS_ADVISORY.md#additional-presolve-counterexample--2026-10-03).

**Correctness advisory — 2026-10-02:** The pinned solver reproduced an incorrect optimality claim on an official upstream fixture. Historical 1% gap and time-to-1% acceleration claims below are provisional pending corrected-reference revalidation; historical SCUC impact is unknown. Original results remain archived. [Read the evidence and current limitations](CORRECTNESS_ADVISORY.md) before using this research.

**Corrected-reference update — 2026-10-02:** Fresh matched PG89 revalidation
with the isolated official #3179 and #3181 fixes passed all nine fixed pairs.
Median reductions were 66.05% in solver-process time and 56.19% in arm end-to-end
time. All 18 arms met the original 1% endpoint with zero shedding, overflow and
reserve shortfall. See the [new report and every outcome](corrected_pg89_results/RESULTS.md)
and the [additive corrected replay kit](portable_early_integer_corrected_replay_v1/README.md).
These new measurements do not revise the historical numbers or establish
general MILP or larger-case acceleration.

This directory is an opt-in research package. It does not change the production
solver, its build, or its defaults. All solver checkouts below are pinned to
HiGHS commit `73cac48c5340d775a477087198611862559be250` (source version 1.15.1).
The patches are separate artifacts, not an enabled solver optimization.

The historical [early-integer discovery confirmation](early_integer_results/RESULTS.md)
passed its fixed nine-pair PG89 gate: all 18 arms obtained independently checked
original-source 1% numerical certificates. Median reductions were 65.52% in
solver-process wall time and 54.85% in arm-process E2E; every pair improved both
endpoints. The comparator is the cold integer screening loop, not the earlier
LP bundle. This is scoped evidence on three dates of one network, with no
change to normal solver defaults. The report preserves every outcome,
objective/slack check and clock boundary. The [portable early-only replay](portable_early_integer_replay/README.md)
now includes the runnable workflow; its [separate tiny validation](portable_early_integer_validation/RESULTS.md)
preserves the two development failures and the artifact-only verifier correction.
The separately bounded [June1354 transfer](june1354_early_transfer/RESULTS.md)
left both arms incomplete and establishes no larger-case speedup.

The [combined SCUC replay](portable_combined_replay/README.md) includes the full
LP-screening pipeline, root-child-credit patch recipe, original-model checks and
a validated tiny example. The [nine-pair result](combined_results/COMBINED_SCUC_RESULTS.md)
reports every historical outcome, including the failed February end-to-end
threshold. The portable entrypoint passed a separate correctness/equality check;
its runtime has not been performance-measured on the production cases.

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
- `initial-root-ipx.patch`: a default-off initial-main-root-only engine
  experiment. See [`INITIAL_ROOT_IPX.md`](INITIAL_ROOT_IPX.md) for its guarded
  scope, preliminary result and validation limits
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
