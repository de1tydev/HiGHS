# Portable combined-screening replay

This opt-in research package makes the frozen combined-screening method
inspectable and provides an entry point for a new local replay. The tested v2
snapshot passed runtime preflight, one tiny A/B pair and every-witness checker
equality on the recorded Linux runtime. This public copy changes documentation and test-report wording, plus the
expected source-hash literal corresponding to a module-docstring edit.
Mathematical and orchestration function bodies match tested v2 exactly;
normalized AST evidence records the precise exceptions to byte identity.
It has a distinct release identity. See [validation evidence](../portable_validation/VALIDATION_RESULT.json)
and the [public-copy change record](../portable_validation/PUBLICATION_CHANGES.json).
No solver default is enabled and no method or performance promotion follows.

The completed historical confirmation retained all nine pairs and 18 valid,
complete arms. B was faster in every pair on both recorded endpoints. Overall
medians of paired reductions were 45.70% for solver-process time and 34.54% for
standalone-equivalent end-to-end time. The strict gate nevertheless **FAILED**:
February's median end-to-end reduction was 25.04%, below the required 30% for
each date and each endpoint. The result is **STOP / NO PROMOTION**. A pooled
median cannot replace the failed per-date gate. These are historical observations,
not measurements from this portable package or a guarantee about a new runtime.

## Validation status and the preflight correction

The original v1 preflight failed before any tiny model, solve or equality replay.
Its main C-symbol providers and four-byte `HighsInt` were correct; `--version`
had not initialized the lazily loaded extras DSO. The old preflight incorrectly
required that initialization. The failure receipt is retained. A subsequent
version-only diagnostic retained both raw streams and confirmed the exact main
alias with no extras initialization; the failed launch itself had not archived
those streams.

The corrected v2 requires the exact main DSO during `--version`, rejects any
wrong or duplicate observed provider, and labels absent extras as unobserved.
Actual LP/MIP processes still require the exact main and extras identities;
actual model readback still verifies C-symbol providers, 32-bit ABI and every
mathematical field. Raw preflight streams are now retained on failure.

Tested v2 manifest `5771998b84595f3553f69a25f2ca35c6786f7f139e0481915751798c4f92dc0c`
passed one fresh bounded validation with CPython 3.12.14, NumPy 2.3.5, SciPy
1.17.0 and Linux x86_64/glibc 2.41. All three real-NumPy scalar tests passed.
A used two MIP calls and no LP calls; B used two LP calls and one MIP call.
Both completed at objective 660 within their 20-second solver budgets. All five
actual API model readbacks passed; all five witnesses had byte-identical outputs
across both selector checkers and the direct historical core, with no excluded
fields. Tiny did not activate root-child credit and makes no speed claim.

The complete validation CLI took 53.1370743449952 seconds, including preflight
and equality checks. This is distinct from solver-process time, each arm's
standalone-equivalent endpoint, provisioning and preparation. Full-precision
endpoint definitions and values are in the linked validation evidence. No
production case was solved by the portable validation. The public reporting
copy was not numerically rerun; future runs identify its own manifest.

## Contents and trust boundary

The payload preserves the driver's sibling layout:

```text
payload/
  combined_screening_driver/
  canonical_mps_export/
  lp_security_separator_optimized/
```

Preparation stages these sources into `WORK/replay/`, together with exact pinned
copies of the public `scuc/generate.py`, `scuc/check_solution.py`, and
`process_measure.py` from the enclosing research package. The source release
manifest `PACKAGE_MANIFEST.json` fixes the accepted payload, helper, patch and
input identities. `SOURCE_TREE.sha256` fixes the 983-file patched HiGHS source
inventory. A local runtime receipt binds these identities to the supplied paths
and installed runtime. A local receipt cannot authorize different algorithms or data.

Read the retained [method contract](payload/combined_screening_driver/PROTOCOL.md),
the [root-credit source replay](../ROOT_CHILD_CREDIT.md), and the
[SCUC formulation and provenance](../scuc/README.md). The numerical source,
original complete checker, canonical exporter/readback and policy are preserved;
the publication changes are explicit source/runtime/path/environment bindings.
`SOURCE_IDENTITIES.json` and `SOURCE_DIFF.patch` retain the historical/published
source identities and an annotated, redacted historical comparison. The exact
functional revision-1-to-revision-2 diff is in `REVISION_2_DIFF.patch`. Keep them with `TEST_RESULTS.json`
and any new equivalence receipts when assessing a replay. The original measured
artifacts are not replaced by newly generated files.

## Requirements

- Linux with glibc, ELF shared libraries, process groups, `wait4` and `RLIMIT_AS`
- Python 3.11 or later, NumPy 1.26 or later and SciPy 1.11 or later, installed
  separately before preparation
- Git, CMake, Ninja and a C++ compiler for the pinned source build below
- Shared HiGHS libraries with 32-bit `HighsInt`; 64-bit indexing is unsupported
- Fresh, disjoint source, build, data and replay output locations as applicable

These version floors are declared requirements, not a tested compatibility
matrix. The successful tiny validation used CPython 3.12.14, NumPy 2.3.5, SciPy
1.17.0 and Linux x86_64/glibc 2.41. Other combinations remain untested. Compiler,
libc, CPU and scientific/native-library differences can change trajectories and
timings. This implementation uses Python/ctypes; it does not require `highspy`
or execute UnitCommitment.jl's solver.

Numerical children use `-B -s`; `-s` disables user site packages but does not
disable global startup hooks. The selected Python installation must have no
`.pth`, `sitecustomize` or `usercustomize` startup hooks. Preparation rejects them rather than importing
them. The package is staged fresh without inherited bytecode or `__pycache__`.
The launcher uses an allowlisted environment, controlled thread counts, hash
seed and locale, and fresh work-local home, temporary and cache locations.
Inherited Python injection, preload/audit hooks, proxies, credentials and
application caches are not passed to numerical children. Assertions remain on.

All paths must exclude control characters. Data and replay output paths may
contain ordinary spaces. Main/extras library paths and `LD_LIBRARY_PATH` entries
must contain neither whitespace nor a colon,
because the frozen loader-record parser uses non-whitespace path tokens. macOS,
Windows and musl are outside this package's supported runtime contract.

## Provision the clean Python environment

A generic virtual environment is not guaranteed to satisfy startup-hook checks.
The original base installation contained `distutils-precedence.pth`. The tested
setup used a fresh `--without-pip` environment and copied only the already
installed NumPy/SciPy distributions, metadata and their native-library folders,
excluding bytecode and startup hooks. No download, package installation or
system configuration change was involved.

For that same CPython wheel-layout procedure, set `BASE_PYTHON` to an existing
trusted Python executable, `SCIENCE_SITE` to its NumPy/SciPy `site-packages`
directory, and `CLEAN_PYTHON_ENV` to a new directory whose parent already exists.
This example adds an explicit byte-for-byte copy receipt; preparation separately
pins the actual installation and rejects any remaining startup hooks. It does
not import the scientific packages while provisioning.

```sh
"$BASE_PYTHON" -I -S -B - "$SCIENCE_SITE" "$CLEAN_PYTHON_ENV" <<'PY'
from pathlib import Path
import hashlib, json, shutil, sys, venv
source, target = map(lambda v: Path(v).absolute(), sys.argv[1:])
if target.exists() or target.is_symlink():
    raise FileExistsError(target)
if not target.parent.is_dir():
    raise ValueError("Create the environment's parent directory first")
venv.EnvBuilder(with_pip=False, symlinks=True).create(target)
site = target / "lib" / ("python%d.%d" % sys.version_info[:2]) / "site-packages"
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
pins = {}
for name in ("numpy", "scipy"):
    metadata = list(source.glob(name + "-*.dist-info"))
    if len(metadata) != 1:
        raise ValueError("Need exactly one installed distribution: " + name)
    folders = [source / name, metadata[0]]
    if (source / (name + ".libs")).exists():
        folders.append(source / (name + ".libs"))
    for folder in folders:
        copied = site / folder.name
        shutil.copytree(folder, copied,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))
        for path in copied.rglob("*"):
            if path.is_file():
                digest = sha(path)
                if digest != sha(folder / path.relative_to(copied)):
                    raise ValueError("Copy identity mismatch")
                pins[str(path.relative_to(target))] = digest
with (target / "distribution_copy_sha256.json").open("x") as stream:
    json.dump(pins, stream, indent=2)
PY
REPLAY_PYTHON="$CLEAN_PYTHON_ENV/bin/python3"
```

The recorded validation used this mechanism with CPython 3.12 and the versions
above. Other installation layouts or dependencies must pass the same preparation
and runtime checks; the recipe is not a claim that arbitrary distributions are
compatible. Keep this environment outside the fresh replay work directory.

## Prepare the pinned source and build

The exact upstream commit is
`73cac48c5340d775a477087198611862559be250` (source version 1.15.1).
The enclosing research package also documents a checkout through the public
`de1tydev/HiGHS` repository; the recipe below uses the official
[ERGO-Code/HiGHS repository](https://github.com/ERGO-Code/HiGHS) at that same
commit. Apply the existing public patches in this order:

1. `outer-gap-heuristic.patch`
2. `initial-root-ipx.patch`
3. `root-child-credit.patch`

Set `PACKAGE` to the enclosing `research/rins_budget` directory, `PORTABLE` to
`$PACKAGE/portable_combined_replay`, and `SOURCE`, `BUILD`, `DATA`, and `WORK` to distinct absolute
paths. Set `REPLAY_PYTHON` to the selected Python executable. Source/build/data
provisioning is separate from measured replay; preserve its receipts and logs.
The following is a replay recipe, not a record of a new build or full correctness
suite completed for this corrective source revision.

```sh
set -eu
: "${PACKAGE:?Set PACKAGE to the research-package directory}"
: "${PORTABLE:?Set PORTABLE to this portable package directory}"
: "${SOURCE:?Set SOURCE to a fresh source directory}"
: "${BUILD:?Set BUILD to a fresh build directory}"
: "${DATA:?Set DATA to a fresh data directory}"
: "${WORK:?Set WORK to a fresh replay output directory}"
: "${REPLAY_PYTHON:?Set REPLAY_PYTHON to the Python executable}"
for OUTPUT in "$SOURCE" "$BUILD" "$DATA" "$WORK"; do
  if [ -e "$OUTPUT" ] || [ -L "$OUTPUT" ]; then
    printf 'Refusing to reuse existing output: %s\n' "$OUTPUT" >&2
    exit 1
  fi
done
PIN=73cac48c5340d775a477087198611862559be250
git clone https://github.com/ERGO-Code/HiGHS.git "$SOURCE"
git -C "$SOURCE" checkout --detach "$PIN"
test "$(git -C "$SOURCE" rev-parse HEAD)" = "$PIN"
for PATCH in outer-gap-heuristic initial-root-ipx root-child-credit; do
  git -C "$SOURCE" apply --check "$PACKAGE/$PATCH.patch"
  git -C "$SOURCE" apply "$PACKAGE/$PATCH.patch"
done
```

Build and correctness-test before measuring. Preserve the exact configuration,
compiler/tool versions, build flags and resulting executable/library identities:

```sh
cmake -S "$SOURCE" -B "$BUILD" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DFAST_BUILD=ON -DBUILD_SHARED_LIBS=ON \
  -DBUILD_TESTING=ON -DALL_TESTS=ON -DHIPO=OFF -DHIGHSINT64=OFF
cmake --build "$BUILD" --parallel 4
ctest --test-dir "$BUILD" --output-on-failure --parallel 1
```

The historical build used GCC 14.2.0. The portable check requires empty global
C/C++ flags and the standard `-O3 -DNDEBUG` Release flags. Linker, toolchain,
compiler-launcher and interprocedural-optimization overrides are unsupported;
clear inherited build-flag overrides before configuring. No build is accepted solely because its
version string or checkout commit matches. Preparation validates the exact
patched source inventory, and runtime validation checks the selected binary,
main DSO, SONAME target, extras DSO and required C symbols. The version-only
loader check requires the exact main library and checks the extras library if
initialized; actual solver calls require exact loaded identities for both.
Validation checks the configured/header integer mode and the library-reported
`Highs_getSizeofHighsInt` before passing arrays through the C API. The API reader
uses `ctypes.c_int32`/NumPy `int32` and double/`float64`; it does not silently adapt
to a different ABI.

## Fetch inputs and prepare a new replay

The optional downloader accepts only the three official PEGASE89 first-of-month
inputs: February, August and November 2017. It verifies compressed and
decompressed SHA-256 identities before installation. The URLs have the form
`https://axavier.org/UnitCommitment.jl/0.3/instances/matpower/case89pegase/DATE.json.gz`.
These hosted bytes are pinned independently of the UC.jl code revision. A
changed upstream file fails validation; it is not substituted into the experiment.

```sh
python3 -I -S -B "$PORTABLE/prepare_replay.py" fetch-data --data "$DATA"
```

Input filenames are `case89pegase_DATE.json.gz`. Exact-byte offline copies of
those same inputs are also accepted. November must be case89pegase, not the
similarly dated case1354pegase input. Data files,
generated models, solution vectors, binaries and run logs are local outputs and
are excluded from the source package. No generated topology, rating or numerical
cache is an accepted input.

```sh
python3 -I -S -B "$PORTABLE/prepare_replay.py" prepare \
  --research-package "$PACKAGE" \
  --source "$SOURCE" --build "$BUILD" --data "$DATA" \
  --python "$REPLAY_PYTHON" --work "$WORK"
```

`prepare` performs source-only validation and staging and writes
`WORK/materialization_receipt.json` and the staged driver's `BINDINGS.json` and
`CAMPAIGN_PLAN.json`. It records Python startup directories without importing
scientific packages. It does not import NumPy/SciPy, invoke the HiGHS API,
generate a model, compute a source scope or prepare a numerical cache. It refuses an existing
output directory, file or dangling symlink and does not overwrite, resume or
delete failed work. Preserve failed output for diagnosis; any later replication
requires its own fresh directory.

## Check the source-only package

Run `python3 -I -S -B "$PORTABLE/tests/run_pure_tests.py"` to execute the
standard-library pure/mocked suite without changing the package. The retained
`TEST_RESULTS.json` records that suite's exact counts and its three explicit
scientific-test skips. The separate actual-NumPy run described above passed all
three skipped cases on the tested v2 source; this does
not change the pure suite's original record or turn it into a scientific run.
No solver, C-API, matrix generation or topology runs in the pure-suite command.

## Run a reviewed phase

After source review and preparation, start with the tiny phase:

```sh
python3 -I -S -B "$PORTABLE/prepare_replay.py" run \
  --work "$WORK" --phase tiny --run-reviewed
```

The run entry point first freezes and validates the clean runtime, including
scientific/native dependencies and scalar ABI preflight, then invokes the frozen
driver phase. Runtime freeze/preflight has separate timing and writes
`runtime_inventory.json`, `loader_inventory.json`, `preflight_receipt.json` and the driver's
`REVIEW_MANIFEST.json`; each phase also writes `PHASE.launch_receipt.json`.
`--run-reviewed` is the user's explicit acknowledgement of the contract.
Follow [SMOKE_PLAN.md](SMOKE_PLAN.md)
for the required tiny receipts and equality checks. A successful tiny phase
also rechecks each witness through a direct entry point using the same
historical mathematical/checker implementation, bypassing selector dispatch.
The public source-byte mapping documents the curated module docstring and
matching expected-hash literal. Its
separately charged `run_v1/tiny/frozen_core_replay/RESULT.json` requires
byte-identical output against both selected checkers; it excludes no fields.
The complete tiny/equality steps passed on tested v2. The documentation and
provenance-normalized public copy was not numerically rerun; its function-body
and source-identity correspondence is recorded separately. Preparation or scalar
checks alone do not establish a successful run on another runtime.

The other fixed phase values are `development` and `confirmation`. Each retains
its prerequisite gate. They are not part of the source-only publication or the
tiny smoke plan. The CLI has no arbitrary seed, budget, algorithm, output-option
or option-file override. A one-use `run_v1`
campaign and exclusive phase markers prevent implicit restart or rerun.

## Frozen method and endpoints

A begins with empty security pairs, uses no LP discovery, root child credit off
and the baseline separator. B begins with empty pairs, permits at most three
cold dual-simplex LP calls, each capped at 10 actual process seconds and at 30
aggregate LP seconds, then uses fresh MIP masters with root child credit on and
the optimized separator. Both arms use the same binary and DSOs, two solver
threads, parallel search off, outer-gap policy on, initial-root IPX off, unchanged
logging and the 1% target. Their MIP options differ only in root child credit.
The patched options remain off by default outside this experiment.

Only validated eligible pairs and the existing valid integer-master bound ledger
persist within an arm. No point, LP bound, basis, historical pair set, topology,
rating table or factorization carries across calls or arms. Each source scope,
generation and complete check runs in a fresh pinned interpreter. Canonical
actual-C-API equality covers every mathematical field and all MPS bounds. The
original complete checker reconstructs the source model and directly checks all
listed outages; selector receipts do not alter its JSON output.

Production retains all 36 hours, 89 buses, 12 units, 210 lines, the 192 supplied
line outages and 14,721 eligible pairs. It is a custom preventive DC UC model,
with the source penalties and soft line limits described in the SCUC README.
It does not claim AC feasibility, every possible line outage or generator
security. Primal tolerance remains `1e-5`; finite/status checks, conservative
bound allowances and `(U-L)/max(abs(U),1e-10) <= 0.01` are unchanged. A passing
certificate is numerical, not an independent exact proof of the solver's dual
bound. Dropped/ignored matrix coefficients cannot support an original-model bound.

Each production arm receives 600 aggregate actual solver-process seconds,
including LP work and watchdog overshoot. Every reaped process is charged before
subsequent checks can fail. An incomplete arm has no time ratio; its budget is
not used as a completion time. Helper/resource/integrity failures and cancellation
stop before a later arm. Ordinary incomplete/timeout outcomes retain their safe
counterpart, then stop confirmation and mark later pairs unrun. Failed observations
are retained without replacement runs or tuning.

The co-primary end-to-end endpoint is the original in-program
standalone-equivalent interval: arm setup through final checks and durable summary
fsync, plus the full common definition-import and plan-archival interval charged
to each arm. Scope preparation, fresh numerical imports, generation, API readback,
LP/integer checks, integrity work and remaining overhead keep their existing
boundaries. Pair archival has its own receipt. This endpoint is not cold
interpreter-launch timing, and the full phase is not an arm timing.

Fetch, installation, build, source staging and runtime-freeze provisioning are
recorded separately, as was the historical pre-experiment freeze. The launcher
also records the full benchmark-child launch-to-exit interval and a separate
entrypoint interval that includes preflight when needed. The latter excludes
the launcher interpreter startup and is labeled accordingly. Additional execution-time
binding or validation belongs in the charged setup/arm interval; source-only
preparation must not hide numerical work outside that interval.

Development is February seed 0 in AB order: both arms must complete, B must show
an applied credit cap or exhausted-credit skip, and both paired time reductions
must reach 20%. Confirmation order is November1 BA, August1 AB, February3 BA,
February4 AB, November2 AB, August2 BA, August3 AB, February5 BA, November3 BA.
For each date separately, all three pairs must improve both endpoints strictly,
and each endpoint's median paired reduction must reach 30%. Every B arm records
activation. No pooled substitute, early success or extra repeat changes this gate.
The retained source-exposure record discloses familiar February/August inputs,
earlier February seeds 1/2 exposure and November's input provenance.

## Licensing and data provenance

HiGHS and these research additions use the repository's
[MIT license](LICENSE.txt). Preserve all original source and third-party
notices. NumPy/SciPy and their native BLAS/SuperLU dependencies retain their own
licenses; record the resolved native libraries in local runtime evidence.

The source PEGASE networks are fictitious research data. Their
[case89pegase notice](https://github.com/MATPOWER/matpower/blob/7.1/data/case89pegase.m)
uses [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/).
The code license does not replace the dataset license. Preserve source headers,
the [UC.jl modified BSD notice](../scuc/sources/UCjl_v0.3.0_LICENSE.md), and these
primary references:

- [UnitCommitment.jl v0.3.0 source](https://github.com/ANL-CEEESA/UnitCommitment.jl/tree/v0.3.0),
  [data catalogue](https://axavier.org/UnitCommitment.jl/0.3/instances/) and
  [input format](https://anl-ceeesa.github.io/UnitCommitment.jl/0.3/format/)
- Xavier, Kazachkov, Yurdakul and Qiu,
  [UnitCommitment.jl v0.3](https://doi.org/10.5281/zenodo.4269874)
- Zimmerman, Murillo-Sánchez and Thomas,
  [MATPOWER](https://doi.org/10.1109/TPWRS.2010.2051168)
- Josz, Fliscounakis, Maeght and Panciatici,
  [PEGASE networks](https://arxiv.org/abs/1603.01533), and Fliscounakis et al.,
  [large-scale system data](https://doi.org/10.1109/TPWRS.2013.2251015)

Keep full local receipts for audit. Before sharing a result, sanitize only
machine-specific path/provenance metadata, preserve unsuccessful outcomes and
all numeric evidence, and exclude credentials, private inputs and raw large
artifacts. A tiny success establishes wiring/equivalence only. Any new performance
claim requires the frozen full campaign on that runtime and cannot revise the
historical failed confirmation gate.
