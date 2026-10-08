# HiGHS #3332 isolated correctness investigation

## Result and scope
The exact restored d547 + #3357/#3367 research reference misclassifies the official fresh six-column, two-row MIP as Infeasible with presolve enabled. Both restored assertion-enabled and Release libraries reproduce this; both presolve-off controls return Optimal with objective −4 and original-model feasible primals.

The isolated official #3332 patch repairs the fixture in both assertions-enabled and Release builds: presolve on and off return Optimal −4 with directly checked original-model feasible primals. All three existing narrow regression families also pass in both fixed build modes. Source identity, build identity, raw results and the optimum proof were independently checked; no blocker was found within this narrow scope.

This investigation does not upgrade to PR head. No SCUC instance, performance experiment, global reference promotion, native Catch test execution, or full-suite rerun was performed. Earlier native-suite results and their known AffinityReducedCoreCount caveat remain historical evidence only.

## Provenance
- Base: d547a3ad8af5399651187fb0e133cf0e42615b82, with archived minimal #3357/#3367 changes.
- All 1006 restored source files match the qualified candidate manifest.
- Existing assertion and Release libraries match archived SHA256 identities and pass six narrow #3357/#3364/#3359 qualification calls on this boot.
- Upstream #3332 merge: 4591d1de08ed2e3bed529ec2c35220a80c4cb9db, 2026-10-06 13:30:14 UTC.
- Source: https://github.com/ERGO-Code/HiGHS/commit/4591d1de08ed2e3bed529ec2c35220a80c4cb9db
- Exact patch applies cleanly to the two-fix reference; only highs/presolve/HPresolve.cpp, highs/presolve/HPresolve.h, and check/TestMipSolver.cpp change.

## Mechanism
The patch centralizes the existing strictly-implied-for-dual predicate, preserving its singleton-specific feasibility tolerance. It invalidates stale row-dual implied bounds when either real column bound tightens or an implied column bound relaxes enough to lose the corresponding dual constraint side. Four calls occur immediately after bound assignment in changeColLower, changeColUpper, changeImplColLower, and changeImplColUpper. Only row-dual bounds sourced from that column and affected coefficient sign/side are reset. Column traversal avoids invalidating a caller's row traversal via splaying. This is an internal presolve deduction issue in a newly constructed model, not a model-reuse regression.

## Independent optimum proof
The objective is 4*x4 − 2*x5. Bounds x4 >= 0 and x5 <= 2 prove objective >= −4 globally. The exact witness [-10,-5,2,0,0,2] obeys every variable bound and required integrality constraint; its row activities are [33,11], satisfying row 0 >= −13 and row 1 = 11. It attains −4, proving the optimum independently of HiGHS.

Each solver result is also directly checked against all original bounds, integrality requirements, both row expressions, and the independently recomputed objective. Fresh processes and fresh Highs objects are used for each presolve mode; threads=1 is explicitly set. Runtime loader traces confirm the exact intended DSO. Timing fields are diagnostic observations only and are not performance evidence.

## Build and coverage limits
Fixed libraries use the corresponding archived reference compilation configuration, with Debug assertions enabled via -O1 -g1 and no NDEBUG for the assertion build. HConfig.h and common translation-unit command equivalence are independently reviewed. Build jobs are limited to two and builds are serialized. BUILD_TESTING=OFF: the official model is exercised through a standalone driver, not the Catch test binary.

The regression controls cover the four #3357 cases, the rule-only #3364 CSC invariant, and #3359 objective 25 plus direct original-model feasibility. These are bounded compatibility checks, not exhaustive presolve safety or full-suite certification.

## Compact replay
Use a separate clean checkout at d547a3ad8af5399651187fb0e133cf0e42615b82. Apply reference-3357-3367.patch to create the exact two-fix reference. Save that tree separately; apply upstream3332.patch to a copy to create the isolated fixed tree. The latter is the three-file official merge delta, not a PR-head upgrade. Its sha256 is 781d089d76a97da1351a3b0f1bf38ebc7a4158dbe1146952598490c91754247a.

Configure each source tree separately with Ninja, GCC/G++, BUILD_SHARED_LIBS=ON, BUILD_SHARED_EXTRAS_LIB=ON, BUILD_TESTING=OFF, ALL_TESTS=OFF, FAST_BUILD=ON, HIGHSINT64=OFF, DEBUGSOL=OFF, HIPO=OFF, CUPDLP_GPU=OFF, HIPDLP_HIP=OFF, ZLIB=ON, CMAKE_EXPORT_COMPILE_COMMANDS=ON. For the assertion build use CMAKE_BUILD_TYPE=Debug and both CMAKE_C_FLAGS_DEBUG and CMAKE_CXX_FLAGS_DEBUG set to "-O1 -g1". For Release use CMAKE_BUILD_TYPE=Release and CMAKE_EXE_LINKER_FLAGS/CMAKE_SHARED_LINKER_FLAGS set to "-flto=2". Build the highs target with two jobs, serializing all builds. Verify assertion commands contain no NDEBUG.

For each selected source/build tree, compile the unchanged tested standalone driver (SRC and BUILD are absolute paths):

    g++ -std=c++11 -O1 -g1 -mpopcnt -I"$SRC" -I"$SRC/highs" -I"$SRC/extern" -I"$BUILD" fixture3332.cpp -L"$BUILD/lib" -Wl,-rpath,"$BUILD/lib" -lhighs -pthread -o fixture3332
    env -u LD_PRELOAD -u LD_AUDIT LD_LIBRARY_PATH="$BUILD/lib" LD_DEBUG=libs OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 ./fixture3332 on
    env -u LD_PRELOAD -u LD_AUDIT LD_LIBRARY_PATH="$BUILD/lib" LD_DEBUG=libs OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 ./fixture3332 off

Run each command in a separate process; inspect loader traces and hash the selected DSO. The driver sets threads=1, constructs a fresh model, and checks status, objective, original bounds/rows and integrality. Reference/on intentionally returns exit 1 after detecting the wrong Infeasible result. The other six arm/build/mode combinations return exit 0 and objective −4. Preserve failures; do not treat the reference/on exit as an infrastructure error. The tested driver prints a literal backslash-n after its result line; that formatting quirk does not affect any mathematical check.

The compact publication contains source and machine-readable results, not native binaries. DSO hashes describe this tested build cohort; rebuilding elsewhere can legitimately produce different bytes. Existing #3357/#3364/#3359 driver sources and historical qualification remain in the neighboring correctness_3357_3367_20261007 and reference_qualification_20261007 directories. Historical timings are not pooled with this cohort.

## Smallest next qualification proposal (not executed)
Before admitting a corrected research reference, run the native presolve/MIP-focused Catch inventory against the exact three-fix source with assertions enabled; include the newly added official #3332 case and retain the existing three regression families. Compare the same focused inventory against the two-fix reference, treating this known #3332 failure explicitly. Then run one full Release native suite on the corrected source to test interactions, retaining the historical affinity exception literally and investigating any new failure. If isolating that exception, report the complete raw suite separately from a fresh-process exact-exclusion aggregate; never relabel the original run as fully passing.

Admission should be a separate reviewed decision based on these results and explicit solver-thread settings. Do not enable the child analytic-center omission experiment. No large SCUC/performance campaign is proposed here, and this fixture gives no evidence that any previously studied SCUC model triggered the bug.
