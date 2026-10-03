# Pristine HiGHS early-integer replay

This kit runs the retained PG89 early-integer method on the exact pristine official HiGHS development commit [`d547a3ad8af5399651187fb0e133cf0e42615b82`](https://github.com/ERGO-Code/HiGHS/commit/d547a3ad8af5399651187fb0e133cf0e42615b82). It starts a new standard-options research lineage. Both arms previously enabled a private outer-gap option; those options and all research source patches are absent here. Historical timings, bounds and acceleration claims are not transferred to this runtime.

The included `replay/` contains the measured package's executable code, with three documentation/lineage files replaced for public use and a regenerated package manifest. The measured manifest is `f48ac4f80167e2eb677ad5167864fde02c8208334ef5a7e2c6c3c5ffee28daec`; the public manifest is `13d4857ffae6b6565c66d27c2190d8b8829ff1236d79230787c8d2fa50178373`. All 41 other files are byte-identical, including every executable, payload, test and source-inventory file. The [equivalence record](EXECUTABLE_EQUIVALENCE.json) lists those hashes. The full PG89 study retains its measured `f48ac4…` identity. The separate public `13d485…` invocation passed preparation, preflight, the tiny pair and offline verification in 34.184 seconds, with checked objective 660 in both arms and clean teardown; see the [public tiny audit](evidence/pristine-public-tiny-terminal-audit.json). This is integration evidence, not a performance sample.

Of its 33 payload files, 32 are byte-identical to the prior corrected replay; the remaining file removes private options and rejects enabled root credit. The source/build adapter binds the new source and both native libraries. Neither the algorithm nor the model, checkers, tolerances or time budgets changed.

Use this README as the consumer recipe and [VALIDATION.md](VALIDATION.md) for the recorded outcomes. The immutable replay documentation and equivalence record retain their pre-execution status; the linked public tiny audit supplies the later execution result. Keep all new files, logs and outputs outside `replay/`. Its inventory rejects extra files, including Python bytecode.

The [validation summary](VALIDATION.md) records exact fixture and tiny-workflow evidence, plus the outstanding platform and coverage limits. The full unit suite is **399/400**, not a full pass. The completed fresh [nine-pair PG89 study](https://github.com/de1tydev/HiGHS/blob/fc0e7087d05f3b521eb44ebc77714b7596e6debd/research/rins_budget/pristine_pg89_results/RESULTS.md) reports the measured `f48ac4…` run; the public package has equivalent executable bytes and its own tiny validation. Neither the tiny result nor this kit establishes production readiness. [Report instructions](REPORT_TEMPLATE.md) and an [unfilled nine-pair template](REPORT_TEMPLATE.json) are provided for additional fresh studies. The [historical correctness advisory](https://github.com/de1tydev/HiGHS/blob/ff204bb95d5acb8b1c6dfe08f299002a5aa6620e/research/rins_budget/CORRECTNESS_ADVISORY.md) remains applicable to its archived results.

## Environment and paths

Use Linux/glibc with `/proc`, ELF loader diagnostics, the required process/limit primitives, Git, CMake, Ninja, GCC/G++, and a clean, already provisioned Python 3.12 environment without `.pth`, `sitecustomize` or `usercustomize` hooks. The exercised versions were GCC/G++ 14.2.0, CMake 4.4.3, Ninja 1.13.2, Python 3.12.14, NumPy 2.3.5 and SciPy 1.17.0. See [requirements](replay/requirements.txt) and [provenance](PROVENANCE.json). Dependency installation and compatibility with other stacks have not been established by this kit.

Set these shell variables to absolute paths before using the commands:

- `KIT`: this directory; `PACKAGE="$KIT/replay"`
- `REPLAY_PYTHON`: the clean scientific Python interpreter
- `TOOLS_PATH`: a PATH containing the selected CMake, Ninja, Git and system tools
- `SOURCE`, `BUILD`, `DATA`, `WORK`: four distinct, fresh directories, outside the kit
- `BUILD_ENV`, `TEST_OUT`: fresh external directories for build environment and test output

Create the parent directories first. Keep source/build/data/work paths disjoint, without whitespace or colons. Do not relocate a prepared work tree. The replay uses a 7 GiB per-process address-space limit, a 4 GiB file-size limit and sampled 2 GiB free-memory/free-disk floors. Inherited hard limits must permit these values; the free-memory check is not a reservation of RAM.

## Verify the package and reconstruct the source

First compare `RELEASE_MANIFEST.json` with its separately distributed SHA256, then verify every published file. This verifier only reads files and uses the Python standard library.

```sh
set -eu
export PYTHONDONTWRITEBYTECODE=1
PACKAGE="$KIT/replay"
"$REPLAY_PYTHON" -I -S -B "$KIT/verify_files.py"

test ! -e "$SOURCE"
git clone --no-checkout https://github.com/ERGO-Code/HiGHS.git "$SOURCE"
git -C "$SOURCE" -c core.autocrlf=false checkout --detach \
  d547a3ad8af5399651187fb0e133cf0e42615b82
test "$(git -C "$SOURCE" rev-parse HEAD)" = \
  d547a3ad8af5399651187fb0e133cf0e42615b82
test "$(git -C "$SOURCE" rev-parse 'HEAD^{tree}')" = \
  788b41e141fa455509c71593e1718b7b71168320
"$REPLAY_PYTHON" -I -S -B "$KIT/verify_files.py" --source "$SOURCE"
```

The complete 1006-file inventory, excluding only `.git`, is authoritative. Its SHA256 is `efe7df3ad01442deb3be411ea903d24b073db219f62b9d6abe15981e1a0a7cc5`. No moving branch, patch application, source overlay or old solver library is part of this recipe.

## Build the CLI and both libraries together

The source is built out of tree. The clean configure environment and explicit flags avoid ambient toolchain overrides. Build and link work use two jobs, including the explicit `-flto=2` linker settings required by this package.

```sh
test ! -e "$BUILD"
test ! -e "$BUILD_ENV"
mkdir -p "$BUILD_ENV/home" "$BUILD_ENV/tmp" "$BUILD_ENV/cache"
env -i PATH="$TOOLS_PATH" HOME="$BUILD_ENV/home" TMPDIR="$BUILD_ENV/tmp" \
  XDG_CACHE_HOME="$BUILD_ENV/cache" LANG=C LC_ALL=C TZ=UTC \
  cmake -S "$SOURCE" -B "$BUILD" -G Ninja \
  -DCMAKE_C_COMPILER=/usr/bin/gcc -DCMAKE_CXX_COMPILER=/usr/bin/g++ \
  -DCMAKE_BUILD_TYPE=Release -DFAST_BUILD=ON \
  -DBUILD_CXX=ON -DBUILD_CXX_EXE=ON \
  -DBUILD_SHARED_LIBS=ON -DBUILD_SHARED_EXTRAS_LIB=ON \
  -DBUILD_TESTING=ON -DALL_TESTS=ON -DHIPO=OFF -DHIGHSINT64=OFF \
  -DCMAKE_C_FLAGS= -DCMAKE_CXX_FLAGS= \
  '-DCMAKE_C_FLAGS_RELEASE=-O3 -DNDEBUG' \
  '-DCMAKE_CXX_FLAGS_RELEASE=-O3 -DNDEBUG' \
  -DCMAKE_EXE_LINKER_FLAGS=-flto=2 -DCMAKE_SHARED_LINKER_FLAGS=-flto=2
env -i PATH="$TOOLS_PATH" HOME="$BUILD_ENV/home" TMPDIR="$BUILD_ENV/tmp" \
  XDG_CACHE_HOME="$BUILD_ENV/cache" LANG=C LC_ALL=C TZ=UTC \
  cmake --build "$BUILD" --parallel 2
"$REPLAY_PYTHON" -I -S -B "$KIT/verify_files.py" --source "$SOURCE"
```

This produces the CLI, shared main library, shared extras library and tests from the same source. Preparation checks build flags, actual library targets and aliases, and compiler/configuration hashes. It binds the new machine's runtime bytes; identical binary hashes across machines are not claimed. The integer C API is int32. A version-only invocation does not establish that extras was actually loaded; real solves are checked for both providers.

Run the selected regressions and the configured suite while preserving failures:

```sh
test ! -e "$TEST_OUT"
mkdir "$TEST_OUT"
FOCUSED_RC=0
(cd "$TEST_OUT" && "$BUILD/bin/unit_tests" \
  'issue-3171,dual-bound-relaxation-unbounded,[highs_test_presolve],[highs_test_presolve_rules],[highs_options]' \
  -w NoTests) >"$TEST_OUT/focused.log" 2>&1 || FOCUSED_RC=$?
CTEST_RC=0
env -i PATH="$TOOLS_PATH" HOME="$BUILD_ENV/home" TMPDIR="$BUILD_ENV/tmp" \
  XDG_CACHE_HOME="$BUILD_ENV/cache" LANG=C LC_ALL=C TZ=UTC \
  ctest --test-dir "$BUILD" --parallel 1 --no-tests=error \
  --output-on-failure --test-output-size-failed 20000 \
  >"$TEST_OUT/ctest.log" 2>&1 || CTEST_RC=$?
printf 'focused=%s\nctest=%s\n' "$FOCUSED_RC" "$CTEST_RC" \
  >"$TEST_OUT/status.txt"
```

Inspect `status.txt` and the retained logs before proceeding. The reference environment's one affinity/default-core-count failure is explained in [VALIDATION.md](VALIDATION.md); preserve and diagnose any new failure rather than silently treating it as equivalent. The CTest output cap limits printed failure details, not its underlying test execution or all files written by CTest. Allow adequate disk space for detailed unit output.

## Prepare and run the tiny integration

The three hash-pinned public inputs are required even for tiny. Use `fetch-data` only for a new `DATA` directory, or use an existing directory containing the exact three files listed in [DATA_SOURCES.json](replay/DATA_SOURCES.json). Preparation verifies both compressed and decompressed hashes. It does not accept substituted dates or models.

```sh
"$REPLAY_PYTHON" -I -S -B "$PACKAGE/prepare_replay.py" fetch-data --data "$DATA"
"$REPLAY_PYTHON" -I -S -B "$PACKAGE/prepare_replay.py" prepare \
  --source "$SOURCE" --build "$BUILD" --data "$DATA" \
  --python "$REPLAY_PYTHON" --work "$WORK"
"$REPLAY_PYTHON" -I -S -B "$PACKAGE/prepare_replay.py" preflight --work "$WORK"
TINY_RUN_RC=0
"$REPLAY_PYTHON" -I -S -B "$PACKAGE/prepare_replay.py" run \
  --work "$WORK" --tiny --arm pair --out "$WORK/runs/tiny" || TINY_RUN_RC=$?
TINY_VERIFY_RC=0
"$REPLAY_PYTHON" -I -S -B "$PACKAGE/prepare_replay.py" verify \
  --work "$WORK" --out "$WORK/runs/tiny" || TINY_VERIFY_RC=$?
printf 'run=%s\nverify=%s\n' "$TINY_RUN_RC" "$TINY_VERIFY_RC" \
  >"$WORK/tiny-status.txt"
if [ "$TINY_RUN_RC" -ne 0 ]; then exit "$TINY_RUN_RC"; fi
if [ "$TINY_VERIFY_RC" -ne 0 ]; then exit "$TINY_VERIFY_RC"; fi
```

Preflight loads/checks scientific and native providers but generates no model or solve. Tiny uses two hours, one outage, seed 0, A then early, a 10-second aggregate actual solver-process budget per arm, 2 seconds of charged MIP grace and 180 seconds of arm containment. Its result is an integration check, not a useful performance sample. The offline verifier is attempted even when the run returns nonzero; both statuses are retained and the original failure takes precedence.

The portable pure tests are `replay/tests/test_method.py` and `test_portable.py`, invoked individually with `"$REPLAY_PYTHON" -I -S -B`. The unchanged `test_official_adapter.py` compares other historical packages and is not a standalone consumer test. `verify_files.py` supplies source/package verification without those dependencies.

The documented entrypoint is `prepare_replay.py`, which uses the consumer launcher and mechanical local runtime bindings. Legacy `release_gate.py` and the disabled direct entrypoint of `cold_screen_pair.py` remain preserved payload code, but are not this consumer flow; their historical release-file references are not required inputs.

## Explicit fixed PG89 replay

After the tiny pair and offline verification succeed, an individual pair can be run in a fresh output directory:

```sh
PAIR_RUN_RC=0
"$REPLAY_PYTHON" -I -S -B "$PACKAGE/prepare_replay.py" run \
  --work "$WORK" --case 2017-05-01 --seed 211 --arm pair \
  --out "$WORK/runs/may-211" || PAIR_RUN_RC=$?
PAIR_VERIFY_RC=0
"$REPLAY_PYTHON" -I -S -B "$PACKAGE/prepare_replay.py" verify \
  --work "$WORK" --out "$WORK/runs/may-211" || PAIR_VERIFY_RC=$?
printf 'run=%s\nverify=%s\n' "$PAIR_RUN_RC" "$PAIR_VERIFY_RC" \
  >"$WORK/may-211-status.txt"
if [ "$PAIR_RUN_RC" -ne 0 ]; then exit "$PAIR_RUN_RC"; fi
if [ "$PAIR_VERIFY_RC" -ne 0 ]; then exit "$PAIR_VERIFY_RC"; fi
```

The fixed panel uses May 1, June 1 and September 1, 2017, each with seeds 211/212/213. Pair order alternates A/early and early/A over those nine entries. Each arm retains 36 hours, all 192 specified outages, the complete original-source checks and a 1% numerical gap. Limits are 600 aggregate actual solver-process seconds, 1800 arm-containment seconds and charged 60-second MIP grace per arm. Both arms use two threads, parallel off, presolve on and full solution style 0. Only discovery adds `mip_max_improving_sols=1`.

A starts an empty cold integer security loop. Early performs one discovery then a fresh cold proof. Only independently reconstructed original violated rows persist. Discovery points and lower bounds never supply a proof certificate; no historical cuts, incumbents, bases, bounds, solver state or time measurements are reused.

Exit code 2 can indicate a clean incomplete outcome or a failure: inspect `RESULT.json`, arm records, cleanup evidence and the verifier, not just the exit code. A clean incomplete first arm still runs its mate. Integrity, resource, cancellation or cleanup failures stop dependent work. A complete fixed-panel report must retain all nine declared rows and all eighteen arm outcomes, including censored, failed and unrun entries; follow [REPORT_TEMPLATE.md](REPORT_TEMPLATE.md).

## License and attribution

Replay code is distributed under the included [MIT license](LICENSE.txt), with all per-file notices retained. The pristine solver's [upstream MIT license](https://github.com/ERGO-Code/HiGHS/blob/d547a3ad8af5399651187fb0e133cf0e42615b82/LICENSE.txt) and third-party notices remain part of the verified source tree. Inputs come from the [UnitCommitment.jl 0.3 instance catalogue](https://axavier.org/UnitCommitment.jl/0.3/instances/). PG89 derives from [MATPOWER case89pegase](https://github.com/MATPOWER/matpower/blob/7.1/data/case89pegase.m), with [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) attribution. Code licensing does not replace dataset attribution. This kit bundles source/metadata only: no PG89 datasets, solver binaries, native libraries, generated models or large raw logs.
