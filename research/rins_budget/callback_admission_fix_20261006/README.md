# Callback incumbent admission: objective-coordinate fix

This isolated patch fixes a callback path that passed an original-space objective into an internal incumbent comparison expressed in reduced minimization coordinates. On official HiGHS `d547a3ad8af5399651187fb0e133cf0e42615b82`, the frozen four-case regression missed early admission in three cases. The same unchanged regression passes all four cases with the patch. All four cases still reached their correct final optimum on the unmodified reference, so this is an incumbent-admission defect, not a demonstrated incorrect optimality result or speedup.

The patch is supplied as a research artifact and was applied only to a separate source/build for qualification. It is not applied to the default user pipeline or the projected SCUC/history runtime. The two C++ fixtures and patch retain their original frozen bytes; their preparation-time source comments do not describe the completed qualification status below. No tests, builds or optimizer calls were repeated to prepare this public package.

## Change and source argument

The one-file [patch](callback_objective_mapping.patch), SHA256 `dfdd9b75b76e4190f958de71fe0cd77bdceeb4509457f4adff730a5c4caa5056`, changes only `highs/mip/HighsMipSolverData.cpp`.

Let F be the feasible candidate's full original objective including its original offset, and s be +1 for minimization or −1 for maximization. If f_reduced is the **current presolved model's offset**, objective preservation gives:

    s * F = f_reduced + g
    g = s * F - f_reduced

The internal incumbent bound is expressed in g. The callback previously passed F into `addIncumbent`; the patch passes g, calculated from the existing `HighsCDouble` objective before conversion to double. It subtracts `mipsolver.model_->offset_`, which already includes sense normalization and presolve constants. Multiplying that reduced offset by sense again would be incorrect. The adjacent explanatory comment's bracket is corrected as well.

This matches the existing initial-incumbent, postsolve and worker mappings in the pinned source: `HighsMipSolverData.cpp` around lines 836–859 and 1262–1265, `HighsMipWorker.cpp` around 109–112, and maximizing normalization in `presolve/HPresolve.cpp` around 6588–6595. Original feasibility/objective computation, reduced-primal mapping and downstream postsolve/original-space rechecks remain unchanged. The strict improvement checks and final bound update are not bypassed; the patch supplies no dual certificate and changes no stopping rule.

A candidate-only `std::isfinite` check rejects a nonfinite mapped double before it can define an incumbent cutoff. It does not reject a finite candidate merely because the incumbent is +infinity. `HighsCDouble` is compensated double arithmetic, not an extended-exponent type; this guard and the finite-range fixtures do not establish arbitrary extreme-range overflow handling. No new tolerance, saturation or objective scaling is introduced.

## Recorded qualification

| Check | Unmodified reference | Patched candidate |
| --- | --- | --- |
| Original four-case early admission | 1 PASS; 3 FAIL_ADMISSION | 4 PASS |
| Six fixed negative-offset follow-ups | 6 PASS | 6 PASS |
| Native callback tags | Not rerun as a full reference group | 16 cases / 513 assertions passed |
| Native MIP/solution/presolve/user-scale tags | Not rerun as a full reference group | 111 cases / 888 assertions passed |
| Full native unit executable | Not run in full | **399/400 cases passed; one affinity assertion failed** |
| Selected CTest set | Not run | **167/167 passed** |

Focused groups overlap the full native suite and must not be added as independent coverage.

The original cases are minimization/maximization with offsets 0 and +100. Min/offset0 already passed; min/offset100 and both maximization cases failed early admission on the reference. The observed AfterSetup and EvaluateRootNode0 boundaries had zero LP iterations; final feasibility and independently recomputed objective passed on both builds.

The six additional cases use offset −100 and improving, distinct equal-objective, or worse feasible submissions under both senses. All pass on reference and candidate. Equal/worse cases establish early bound stability, not retention of a particular equal-valued incumbent vector. The fixtures use presolve off, feasibility-jump off, one thread, zero relative gap and a one-second native limit per case. Missing hooks or failed preconditions are INCONCLUSIVE; final optimality alone cannot make early admission pass. The broader native tests complement these deliberately small fixtures.

The full candidate suite retained one `AffinityReducedCoreCount` failure: expected 1 core, observed 5. A subsequent exact-filter check reproduced the same failure using the **same unit-test executable with the unmodified reference library**; the loaded `highs::parallel::available_core_count` symbol was bound to that reference library. This establishes same-runtime reference recurrence of that test failure. It does not convert the candidate's 399/400 result into an all-green suite, nor provide a full reference-suite comparison. No full-suite repeat or reference rebuild was performed.

CTest excluded only `unit-test-build` and `unit_tests_all`, the redundant build and full-unit wrappers. The full unit executable had already been run directly, and its failure is retained above. See [compact results](evidence/RESULTS.public.json) and [runtime/source identities](evidence/IDENTITIES.public.json). Library hashes, not the shared base githash alone, distinguish patched and reference execution.

## Replaying in an isolated checkout

These commands describe the interfaces; publication preparation did not execute them. `HIGHS_SOURCE` must be a separate clean checkout at the exact base commit, `BUILD` a fresh build directory, and `CALLBACK_PACKAGE` this directory. Do not apply the patch or reuse a CMake cache in a production/reference checkout. Use compatible compiler/CMake/Ninja tools; a new build is not byte-identical or qualified merely because it uses these commands.

```sh
set -eu
test "$(git -C "$HIGHS_SOURCE" rev-parse HEAD)" = d547a3ad8af5399651187fb0e133cf0e42615b82
test -z "$(git -C "$HIGHS_SOURCE" status --porcelain)"
git -C "$HIGHS_SOURCE" apply --check "$CALLBACK_PACKAGE/callback_objective_mapping.patch"
git -C "$HIGHS_SOURCE" apply "$CALLBACK_PACKAGE/callback_objective_mapping.patch"
GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.abbrev GIT_CONFIG_VALUE_0=10 \
cmake -S "$HIGHS_SOURCE" -B "$BUILD" -G Ninja \
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
cmake --build "$BUILD" --parallel 2 --target highs highs-bin highs_extras unit_tests \
  capi_unit_tests call_highs_from_cpp call_highs_hipdlp call_highs_from_c_minimal
```

The frozen fixtures require native githash `d547a3ad8a`. The temporary Git configuration above requests ten-character abbreviation without editing repository configuration. Verify the generated hash; do not rewrite the fixtures to conceal a mismatch. Record source, patch, compiler/options, executable, actual loaded `libhighs` and extras identities separately.

Compile each unchanged fixture against matching source and generated headers:

```sh
for fixture in callback_admission_regression callback_admission_followup; do
  g++ -std=c++17 -O2 -Wall -Wextra -Wpedantic \
    -I"$HIGHS_SOURCE/extern" -I"$HIGHS_SOURCE" \
    -I"$HIGHS_SOURCE/highs" -I"$BUILD" \
    "$CALLBACK_PACKAGE/$fixture.cpp" -L"$BUILD/lib" \
    -Wl,-rpath,"$BUILD/lib" -Wl,-rpath-link,"$BUILD/lib" \
    -lhighs -pthread -o "$BUILD/$fixture"
done
```

Run each fixture separately with exact reap, recording its TSV and linked-library identity. The recorded original-four run used an eight-second envelope; each six-case run used ten seconds. The reference original-four executable is expected to return a diagnostic failure on the three documented cases. Qualification filters and selected CTest command were:

```sh
"$BUILD/bin/unit_tests" '[highs-callback],[highs_callback]'
"$BUILD/bin/unit_tests" '[highs_test_mip_solver],[highs_check_solution],[highs_test_presolve],[highs_user_scale]'
"$BUILD/bin/unit_tests"
ctest --test-dir "$BUILD" -E '^(unit-test-build|unit_tests_all)$' \
  --parallel 1 --timeout 60 --output-on-failure
```

The independent terminal audit verified 528 checks and 243 file hashes. The original wrapper receipts did not retain the requested `--seconds` value; exact allocations were recorded retrospectively from the executed launch commands and cross-checked against receipt timing and cleanup flags. They are not represented as prospectively stored receipt fields.

Each is a separate bounded operation; the commands alone do not reproduce the qualification owner's cleanup, loader traces or output accounting. Apply any reference-library override only in that test process, verify the loaded symbols, and retain failures and inconclusive outcomes. No timing benefit, SCUC improvement, general arithmetic guarantee or correctness claim about newer upstream versions follows from this qualification.
