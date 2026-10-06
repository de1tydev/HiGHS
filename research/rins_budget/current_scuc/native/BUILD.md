# HiGHS runtime build and qualification

The first supported ABI is Linux x86-64, little endian, IEEE binary64, with
32-bit `HighsInt`. HiGHS must be the official ERGO-Code/HiGHS commit
`d547a3ad8af5399651187fb0e133cf0e42615b82` (tree
`788b41e141fa455509c71593e1718b7b71168320`, version 1.15.1).
A bare executable, `highspy`, an arbitrary system `libhighs`, and a manifest
with copied historical ELF hashes do not qualify a local build.

## Prospective new build

These are instructions, not a claim that this package was rebuilt or validated.
Agree a build resource budget before running them. Use a fresh destination;
do not run CMake against a recovered build cache containing old absolute paths.
The prerequisites are Git, a supported GCC/G++ toolchain, CMake, Ninja, and zlib
development headers. No Python environment is created by this recipe.

From the package root, choose absolute source/build destinations:

```sh
export SCUC_SOURCE=/path/to/fresh/HiGHS-source
export SCUC_BUILD=/path/to/fresh/HiGHS-build

git clone https://github.com/ERGO-Code/HiGHS.git "$SCUC_SOURCE"
git -C "$SCUC_SOURCE" checkout --detach d547a3ad8af5399651187fb0e133cf0e42615b82

cmake -S "$SCUC_SOURCE" -B "$SCUC_BUILD" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DFAST_BUILD=ON \
  -DBUILD_SHARED_LIBS=ON -DBUILD_SHARED_EXTRAS_LIB=ON \
  -DHIPO=OFF -DHIGHSINT64=OFF -DDEBUGSOL=OFF \
  -DZLIB=ON -DCUPDLP_GPU=OFF -DHIPDLP_HIP=OFF \
  -DBUILD_TESTING=ON -DALL_TESTS=ON \
  -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++ \
  -DCMAKE_C_FLAGS= -DCMAKE_CXX_FLAGS= \
  '-DCMAKE_C_FLAGS_RELEASE=-O3 -DNDEBUG' \
  '-DCMAKE_CXX_FLAGS_RELEASE=-O3 -DNDEBUG' \
  -DCMAKE_EXE_LINKER_FLAGS=-flto=2 -DCMAKE_SHARED_LINKER_FLAGS=-flto=2 \
  -DCMAKE_BUILD_RPATH_USE_ORIGIN=ON
cmake --build "$SCUC_BUILD" --target highs-bin highs highs_extras --parallel 2
python -B native/build_assess.py --source "$SCUC_SOURCE" --build "$SCUC_BUILD" --cxx g++
python -B native/make_runtime_manifest.py --source "$SCUC_SOURCE" --build "$SCUC_BUILD"
```

The helper build compiles the exact `native_assess.cpp` v3 bytes with C++17,
the matching source/build headers, `libhighs`, and `libdl`; its executable lives
in `bin/` with an `$ORIGIN/../lib` runtime path. The compiler command, compiler
version output, helper source/executable hashes, library hash and HConfig hash
are recorded. The helper has no optimization, presolve, crossover or repair
entry point. Its only assessment operation is `assessPrimalSolution` after
reading the supplied model and point.

The manifest producer independently checks every source file against Git blob
identities and reconstructs the required tree. It records actual compiler
configuration, generated HConfig, meaningful CMake options, local executable and
DSO identities, and the helper receipt. `source_root` and `build_root` may be
outside the Python package. Paths in the manifest are relative to its location.
Rebuilt ELF bytes may differ from the historical execution. Their new identities
are recorded and checked instead of being mislabeled as historical bytes.

A source inventory is provenance, not a signature or a remote attestation of the
compiler. Qualification still verifies actual loaded symbols, ABI, effective
options, model readback, real helper output and scientific checks.

## Recover an already verified build for a bounded portability test

`stage_existing_runtime.py` is an explicit alternative for the existing recovered
current runtime. It has two modes:

```sh
python -B native/stage_existing_runtime.py \
  --recovery-root /path/to/recovery \
  --prefix /path/to/fresh/native-prefix \
  --max-bytes 10485760
# Only after reserving the displayed resource budget, repeat with --stage.
```

The default command is read-only: it hashes the complete recovered source tree
and computes a prospective copy bound. `--stage` creates a compact prefix,
copies only the verified CLI, DSOs, assessment helper, exact guarded source,
build/compiler evidence and notices, and creates a new manifest. It excludes
models, points, bases, cuts, historical results and scientific environments.
The initial inspected input needed 8,477,581 copied bytes, with a conservative
9,526,157-byte total bound. The script recomputes the bound for every invocation.

This mode has exact accepted current native artifact hashes and labels the
runtime `recovered_current_v3`. It does not fabricate a new build receipt or use
the old v1 helper receipt as proof of v3. The exact current helper binary and v3
source are bound, and the actual helper must be exercised afresh.

The recovered ELF files contain historical absolute RUNPATHs. Before launching
Python or HiGHS, use the new prefix explicitly:

```sh
export LD_LIBRARY_PATH=/path/to/fresh/native-prefix/lib
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export LANG=C LC_ALL=C TZ=UTC PYTHONHASHSEED=0 PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
```

`verify_native_mappings` checks `/proc/self/maps` so an old HiGHS DSO or extras
mapping is rejected. `dladdr` additionally binds actual C API symbol origins.
A second-directory test may copy this compact prefix and package while sharing
the existing pinned interpreter and installed Python packages; report that
shared dependency explicitly. It does not establish portability to another OS,
architecture, compiler, machine, or Python environment.

## API and admission boundary

- `discover_runtime(highs, runtime_manifest=None)` is source-only and returns
  `RuntimePaths`. Without an explicit manifest it looks in the executable's
  prefix and `share/current_scuc/`, rejecting missing or ambiguous manifests
- `load_runtime_config(path)` returns the historical scientific driver's local
  config keys with current byte identities. It preserves the venv launcher path
- `runtime_path(relative, cfg=None)` resolves native source/build/helper paths.
  If cfg is omitted, set `CURRENT_SCUC_RUNTIME_MANIFEST` first
- `loaded_python_identities()` checks installed NumPy 2.3.5, SciPy 1.17.0 and
  threadpoolctl 3.6.0 RECORDs and captures file hashes without importing numerical
  extensions. The binding retains that list and pins; installed wheels and
  their notices are not copied. It also binds the interpreter and currently
  mapped platform DSOs, including the allocator
- `verify_loaded_runtime(identities)` checks actual numerical imports and BLAS
  DSO bytes, requiring every BLAS pool to use one thread
- `qualify_capi(runtime)` explicitly loads native code and checks symbols, DSO
  origins, version/githash and 32-bit HighsInt on an empty handle. It does not
  read a model, optimize, presolve, or qualify effective scientific options
- `native_assess_fixture(runtime, workdir)` writes a fresh 1x1 binary model and
  point and returns the genuine helper argv and bounds. The caller runs it in
  its existing contained process runner, with at most 10 seconds and 64 KiB
  output, then calls `validate_native_assess_fixture`. The validator checks
  assessment status, all matrix fields, point/activities and actual loaded DSO

Native qualification runs inside the same outer resource envelope as the
scientific entrypoint. Scientific callers still perform role-specific typed
option readbacks, complete option inventory, source-guarded diagnostic parsing,
same-object LP readback, matrix fidelity, carry assessment and final admission.
Manifest creation or a successful `--version` response is never scientific
validation.
