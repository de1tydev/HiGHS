# Portable early-integer replay

This opt-in package runs the confirmed early-only policy against the ordinary cold integer outer loop on three fixed public PG89 inputs. It does not enable a HiGHS default or compare against the earlier LP-screening bundle. New local runs have their own runtime identities and timings; they do not inherit the historical performance result.

The model is the retained custom DC security-constrained unit-commitment formulation, not an AC formulation or a call to the UnitCommitment.jl optimizer. The supported production inputs are May, June and September 2017 PG89: 89 buses, 12 units, 210 lines, 77 finite-rated lines, 36 hourly periods and all 192 listed outages. Each full source check covers 529,956 eligible original pair-hours. Seeds are fixed to 211, 212 and 213. The tiny triangle is a separate two-hour, one-outage correctness fixture.

The [published nine-pair confirmation report](https://github.com/de1tydev/HiGHS/blob/e4397c35c768cd7f4377121254d065d1d4692824/research/rins_budget/early_integer_results/RESULTS.md) records the historical result and its limits.

## Method and limits

Both arms start with empty security pairs and use identical A flags, baseline separation and fresh cold processes. The early arm makes one discovery MIP with `mip_max_improving_sols = 1`, ordinary `mip_rel_gap = 0.01`, and min(300, actual remaining) requested seconds. It retains only independently reconstructed valid original rows. Discovery U/L, vectors, bases and solver state do not enter proof. Clean no-point/no-new-row discovery still transitions once to cold proof. Later proof calls restore the unlimited improving-solution default and retain the original 1% target.

Every matrix/API field, original source constraint, objective and outage check remains mandatory. Primal feasibility and objective are independently checked. Lower bounds are HiGHS numerical global bounds with the retained conservative printed-precision allowance, not independently proved exact/rational dual certificates. Actual shedding, shared overflow and reserve shortfall must be read from a returned point; soft-model feasibility alone does not imply zero slack.

Production limits are 600 aggregate actual solver-process seconds and 1800 containing-process seconds per arm. The ordinary 60-second MIP grace is charged. The tiny route has 10 actual solver seconds per arm, 2 seconds charged grace and 180 seconds per-arm containment. All processes retain the hard 7 GiB address-space cap and sampled 2 GiB MemAvailable/free-disk guards; those guards are not continuously reserved memory. No automatic retry or parameter rescue occurs.

Solver debit includes launch, import, nested work, output, normal overshoot and exact reap once. Arm E2E is containing-process launch through exact reap, including generation/readback, all solving, complete checking and durable arm output. Redundant controller preflight and inter-arm archival are outside that endpoint and are not separately timed. The reported arm intervals are not a total-campaign stopwatch.

## Requirements

- Linux/glibc with ELF shared libraries, process groups, `wait4`, `pidfd_open` and `RLIMIT_AS`
- A clean, startup-hook-free Python installation; the validated versions are Python 3.12.14, NumPy 2.3.5 and SciPy 1.17.0
- Git, CMake, Ninja and a C++ compiler if building rather than binding an existing exact build
- Shared HiGHS with 32-bit `HighsInt`; HIPO and 64-bit indexing are disabled in the fixed build
- Fresh, disjoint package/source/build/data/work locations and enough space for the unchanged conservative allocation guards

The inherited inspector accepts Python >=3.11 but records and pins the actual runtime. Other versions are not a validated compatibility matrix. The selected installation must have no `.pth`, `sitecustomize` or `usercustomize` startup hooks. A clean virtual environment can be created without pip, then populated from a separate installer:

```sh
python3.12 -m venv --without-pip "$REPLAY_ENV"
python3 -m pip --python "$REPLAY_ENV/bin/python" install -r "$PORTABLE/requirements.txt"
REPLAY_PYTHON="$REPLAY_ENV/bin/python"
```

`PORTABLE`, `REPLAY_ENV`, `REPLAY_PYTHON`, `SOURCE`, `BUILD`, `DATA` and `WORK` below are caller-chosen absolute paths. Create their parents first. Data/work paths may contain ordinary spaces; library/build paths used by the loader must contain neither whitespace nor a colon. Control characters in paths are rejected. Do not relocate a prepared work directory; prepare a fresh binding instead.

## Exact source and build

HiGHS reports 1.15.1, based on official commit `73cac48c5340d775a477087198611862559be250` with the three included existing opt-in instrumented patches. It is not unmodified upstream-default behavior. Both arms use the same common options, including two solver threads, `parallel = off`, outer-gap behavior on, initial-root-IPX off and near-target-root-budget off.

The following creates a new source/build; it is not necessary when binding an existing exact source and build. Preparation verifies the 983-file patched source inventory, CMake configuration, executable, library aliases and flags.

```sh
set -eu
test ! -e "$SOURCE"
test ! -e "$BUILD"
git clone https://github.com/ERGO-Code/HiGHS.git "$SOURCE"
git -C "$SOURCE" checkout --detach 73cac48c5340d775a477087198611862559be250
for PATCH in outer-gap-heuristic initial-root-ipx root-child-credit; do
  git -C "$SOURCE" apply --check "$PORTABLE/patches/$PATCH.patch"
  git -C "$SOURCE" apply "$PORTABLE/patches/$PATCH.patch"
done
cmake -S "$SOURCE" -B "$BUILD" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DFAST_BUILD=ON -DBUILD_SHARED_LIBS=ON \
  -DBUILD_TESTING=ON -DALL_TESTS=ON -DHIPO=OFF -DHIGHSINT64=OFF
cmake --build "$BUILD" --parallel 4
ctest --test-dir "$BUILD" --output-on-failure --parallel 1
```

## Data, preparation and runtime preflight

`DATA_SOURCES.json` fixes the public URLs and compressed/decompressed hashes. Fetch creates a fresh directory; it never replaces existing input. Alternatively, copy those exact three `.json.gz` files into a data directory before preparation. No dataset or large model is bundled.

```sh
python3 -I -S -B "$PORTABLE/prepare_replay.py" fetch-data --data "$DATA"
python3 -I -S -B "$PORTABLE/prepare_replay.py" prepare \
  --source "$SOURCE" --build "$BUILD" --data "$DATA" \
  --python "$REPLAY_PYTHON" --work "$WORK"
python3 -I -S -B "$PORTABLE/prepare_replay.py" preflight --work "$WORK"
```

Preparation performs source/build/data/package checks and isolated interpreter metadata inspection. Preflight imports the selected scientific/native providers, checks scalar ABI/symbol identities and records `--version` loader evidence; neither step generates a model or runs optimization. They are separate provisioning costs. Local runtime manifests are generated automatically.

## Fresh tiny and production runs

Every output must be a new directory below `WORK/runs`; existing output is refused. Baseline means A; early means one discovery followed by cold proof. Pair mode uses the fixed globally alternating order for the chosen date/seed; tiny is baseline then early.

```sh
python3 -I -S -B "$PORTABLE/prepare_replay.py" run \
  --work "$WORK" --tiny --arm pair --out "$WORK/runs/tiny"
python3 -I -S -B "$PORTABLE/prepare_replay.py" verify \
  --work "$WORK" --out "$WORK/runs/tiny"

python3 -I -S -B "$PORTABLE/prepare_replay.py" run \
  --work "$WORK" --case 2017-05-01 --seed 211 --arm pair \
  --out "$WORK/runs/may-211"
```

Use `--arm baseline` or `--arm early` for a single arm. Other accepted dates are `2017-06-01` and `2017-09-01`; other accepted production seeds are 212 and 213. A single-arm or incomplete result never produces a paired speed ratio. A clean incomplete first arm does not skip the other requested arm; fatal status/identity/resource/cleanup errors stop dependent work and preserve explicit unrun arms. Exit status 0 means all requested arms certified; status 2 means incomplete or failed, with evidence retained.

`RESULT.json` contains exact timings, certificates, outcomes and output provenance. Each arm retains raw solver logs, options, measured process receipts, generated models/API readbacks, independent checks, role projections, ledger and complete-process receipt. `verify` rechecks the retained file graph, raw checks, actual commands, source/seed/options, solver debits and numerical certificate arithmetic without a new model, API call or solve. It is consistency/provenance verification, not a new exact dual proof.

## Diagnostic path compatibility

A consumer path may contain a benign word such as “warning”. A narrow adapter recognizes only present full lines `readMPS: Trying to open file <bound model>`, `Writing the solution to <bound solution>` and `Set option solution_file to "<bound solution>"`. Read/write announcements require the announced bound file to exist; the option echo only binds the requested path and does not assert a point exists. It preserves the raw log and records every recognized line/hash. Duplicate, foreign, prefixed or suffixed announcements remain fatal; every real warning/error and all original status/identity/primal gates remain active. Absent I/O announcements or absent solution files do not themselves remove the original clean no-point discovery-to-proof transition.

This is a separately reviewed portability compatibility change, not a modification of frozen performance evidence. Differential replay of retained solver reports and readback diagnostics is source-only; the fresh tiny additionally exercises a keyword-containing output path. Broader loader-path restrictions remain unchanged.

## Tests, provenance and data attribution

```sh
python3 -I -S -B "$PORTABLE/tests/test_method.py"
python3 -I -S -B "$PORTABLE/tests/test_portable.py"
```

These are pure tests and run no optimizer or scientific import. `SOURCE_LINEAGE.json`, `COMPATIBILITY.json` and `PACKAGE_MANIFEST.json` identify preserved method files and explicit local-binding/diagnostic changes. Runtime and output receipts identify a new consumer run; historical timings are never substituted.

Inputs come from the [UnitCommitment.jl 0.3 instance catalogue](https://axavier.org/UnitCommitment.jl/0.3/instances/), with the corresponding [UC.jl v0.3.0 code](https://github.com/ANL-CEEESA/UnitCommitment.jl/tree/v0.3.0). The hosted input hashes in `DATA_SOURCES.json` identify the data independently of the UC.jl code version. PEGASE89 derives from the [original MATPOWER case89pegase](https://github.com/MATPOWER/matpower/blob/7.1/data/case89pegase.m), under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); retain its attribution when redistributing data. HiGHS and the implementation code retain their included source/license notices. Code licensing does not replace source-data attribution. No credentials, binaries or large raw models are shipped.
