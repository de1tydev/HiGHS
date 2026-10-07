# Minimal HiGHS correctness checkpoint: #3357 and #3367

Recorded and independently audited on **2026-10-07** against official HiGHS
[`d547a3ad8af5399651187fb0e133cf0e42615b82`](https://github.com/ERGO-Code/HiGHS/commit/d547a3ad8af5399651187fb0e133cf0e42615b82).
The pristine Release baseline reproduces a branch-marker/stabilizer regression
and an invalid presolve CSC row index. The isolated combined candidate passes
both narrow checks. This checkpoint does **not** promote the candidate to the
research's global reference or establish a performance result.

## Recorded results

| Check | Pristine baseline | Combined candidate |
|---|---|---|
| #3357, lower and upper branches, symmetry on | Both fail: branch marker lost; x not stabilized | Both pass: one branch retained; x stabilized |
| #3357, lower and upper branches, symmetry off | Both pass: redundant branch removed | Both pass: removal preserved |
| Issue #3364, rule-only LP presolve | Fails: `nz=1 row=-1 num_row=4` | Valid CSC: 4 rows, 7 columns, 9 nonzeros |
| Issue #3359, ordered MPS, presolve on | Optimal, objective 25; primal checks pass | Optimal, objective 25; primal checks pass |

All four #3357 cases preserve bounds in both arms. The six separate regression
processes returned the expected exits: baseline `3357/3364/3359 = 1/1/0`,
candidate `0/0/0`. [RESULTS.json](RESULTS.json) preserves the compact observations
and audited runtime identities. Publication preparation only copied and checked
existing evidence; it performed no new builds or solves.

Both libraries were Release (`NDEBUG`); fixture checks remain active. The
#3359 baseline pass means this Release case does not independently demonstrate
the equation-size repair. Its original-model feasibility, integrality and
objective are recomputed by the driver; that is not an independent optimality
or dual certificate. No single-fix ablation arm was run.

## Exact candidate and fixture provenance

[combined-minimal-correctness.patch](combined-minimal-correctness.patch) is
**+17/−19 across exactly two source files**:

- [Official PR #3357](https://github.com/ERGO-Code/HiGHS/pull/3357): cumulative
  changes from commits
  [`7a50c326ca6f93d98479ebce1909f503f22e759a`](https://github.com/ERGO-Code/HiGHS/commit/7a50c326ca6f93d98479ebce1909f503f22e759a)
  and [`1309ab32179eebc624d077afb02e7066d0fe0eed`](https://github.com/ERGO-Code/HiGHS/commit/1309ab32179eebc624d077afb02e7066d0fe0eed),
  +15/−19 in `HighsDomain.cpp`. Only hunk offsets and source/index metadata were
  adapted to d547; the official changed and context lines are retained.
- [Official PR #3367](https://github.com/ERGO-Code/HiGHS/pull/3367): the net two
  executable additions from
  [`340f76fafea1b8256bc7610154e291d442b2fd66`](https://github.com/ERGO-Code/HiGHS/commit/340f76fafea1b8256bc7610154e291d442b2fd66),
  `storeRow(i)` and `reinsertEquation(removerow)` in `HPresolve.cpp`.

Both PRs were observed open/unmerged in the 2026-10-07 source snapshot. No
whole PR head, unrelated intervening commits, or upstream test changes are
included in the candidate patch. The audit compared all 1,006 tracked source
files and found only those two differences; the candidate diff matched the
frozen patch byte for byte.

The two standalone C++ fixtures are preserved unchanged from the reviewed,
executed sources:

- [domain_stack_fixture.cpp](domain_stack_fixture.cpp) constructs `x=2y`,
  `z=2w`, performs real propagation/compression/reload, and gives the known
  pair-swap symmetry to the real stabilizer. It does not run an optimizer,
  symmetry detector or orbital fixing. Its symmetry-off stabilizer call is
  diagnostic only.
- [pr3367_regression.cpp](pr3367_regression.cpp) adapts the public
  [issue-3364 test at immutable PR head b116e43c](https://github.com/ERGO-Code/HiGHS/blob/b116e43c9dfce28217cee376d8a207dcf0aaf13c/check/TestPresolveRules.cpp#L1225)
  and separately loads [3359.mps](3359.mps). The 5×7 input preserves numeric
  row order A/B/i/D/E; corrected labels do not change the numbers. Its direct
  presolver input path resets integrality, so this is **rule-only LP structural
  coverage**, not a MIP solve. The model is the unchanged
  [official ordered MPS](https://github.com/ERGO-Code/HiGHS/blob/b116e43c9dfce28217cee376d8a207dcf0aaf13c/check/instances/3359.mps),
  Git blob `969b6207a2ac07975de1ed84ae4ecdddf6055145`; preserve row/column order.

The fixtures are small source-owned drivers with explicit checks and no added
test framework. The [HiGHS MIT license](HiGHS-LICENSE.txt) accompanies upstream
code/data. [PUBLICATION_MANIFEST.json](PUBLICATION_MANIFEST.json) records file
hashes, source identities and provenance.

## Manual compile and invocation

These Linux/x86-64 commands compile only the two drivers against **already
built, matching** baseline and candidate Release shared libraries. Use the
same compiler and ABI settings as each library. The recorded configuration
used GCC 14, C++11, `HIGHSINT64=OFF`, `DEBUGSOL=OFF`, `HIPO=OFF` and shared
`libhighs.so.1.15.1`. Internal APIs require each arm's exact source headers,
generated `HConfig.h`/`highs_export.h`, and library; do not mix arms or modes.

Prepare two separate d547 source/build pairs. Keep the baseline pristine.
Apply the supplied patch only to the separate candidate source before building
its Release library. Set `BASE_SOURCE`, `BASE_BUILD`, `CAND_SOURCE`, and
`CAND_BUILD` to those absolute directories. Run this from this checkpoint's
directory; `CXX` may select the matching compiler:

```sh
set -eu
: "${BASE_SOURCE:?Set the pristine d547 source directory}"
: "${BASE_BUILD:?Set its matching Release build directory}"
: "${CAND_SOURCE:?Set the d547 plus supplied patch source directory}"
: "${CAND_BUILD:?Set its matching Release build directory}"
CHECKPOINT="$(pwd -P)"
OUT="$(mktemp -d)"
for arm in baseline candidate; do
  if [ "$arm" = baseline ]; then
    src="$BASE_SOURCE"; build="$BASE_BUILD"
  else
    src="$CAND_SOURCE"; build="$CAND_BUILD"
  fi
  for fixture in domain_stack_fixture pr3367_regression; do
    "${CXX:-g++}" -std=c++11 -O2 -DNDEBUG -mpopcnt -Wall -Wextra \
      -I"$src/extern" -I"$src" -I"$src/highs" -I"$build" \
      "$CHECKPOINT/$fixture.cpp" \
      -L"$build/lib" -Wl,-rpath,"$build/lib" \
      -Wl,-rpath-link,"$build/lib" -lhighs -pthread \
      -o "$OUT/$arm-$fixture"
    env LD_LIBRARY_PATH="$build/lib" ldd "$OUT/$arm-$fixture"
  done
done
printf 'Drivers are in %s\n' "$OUT"
```

Before invoking, verify each printed `libhighs` resolution is the intended
arm's library, compare source hashes with the manifest, and record your local
library/binary hashes. Recorded library hashes identify the audited build;
independent rebuilds need not be byte-identical. Ensure no inherited
`LD_PRELOAD` substitutes a library.

Run each case as a separate process, serially. GNU `timeout` supplies simple
outer limits here; it is not the original run's resource supervisor. The 3359
driver additionally requests one thread and a 30-second native solve limit.

```sh
set +e  # The two baseline regressions intentionally return 1.
for arm in baseline candidate; do
  if [ "$arm" = baseline ]; then build="$BASE_BUILD"; else build="$CAND_BUILD"; fi
  env LD_LIBRARY_PATH="$build/lib" timeout --kill-after=2s 15s \
    "$OUT/$arm-domain_stack_fixture"
  printf '%s 3357 exit=%s\n' "$arm" "$?"
  env LD_LIBRARY_PATH="$build/lib" timeout --kill-after=2s 15s \
    "$OUT/$arm-pr3367_regression" 3364
  printf '%s 3364 exit=%s\n' "$arm" "$?"
  env LD_LIBRARY_PATH="$build/lib" timeout --kill-after=2s 45s \
    "$OUT/$arm-pr3367_regression" 3359 "$CHECKPOINT/3359.mps"
  printf '%s 3359 exit=%s\n' "$arm" "$?"
done
```

Exit 0 means explicit checks passed; 1 means a check failed and requires the
corresponding diagnostic; 2 means setup/precondition failure or the 3359 native
time limit. Timeout/signal exits are inconclusive. Merely obtaining baseline
exit 1 is insufficient: verify the specific failures in the result table.
Enabling assertions only in a driver linked to a Release library is not Debug
coverage; true Debug coverage requires matching assertions-enabled libraries.

## Limits and relation to SCUC endpoints

This gate covers eight domain cases, two direct presolve calls and two tiny
3359 MIP solves. It includes no Debug-library run, full regression suite,
`neos-911970`, full symmetry wrong-optimum reproducer, SCUC run or performance
comparison. It does not establish a historical SCUC trigger or invalidate
historical outcomes. Further reference qualification is separate work.

The baseline already includes the earlier official
[#3179](https://github.com/ERGO-Code/HiGHS/commit/28339ce4b57bf8858036cbb36f4fc66d97fedd06),
[#3181](https://github.com/ERGO-Code/HiGHS/commit/ae53450f395cf0a278858868b64813ea99bb4767),
[#3270](https://github.com/ERGO-Code/HiGHS/commit/4e53e2bcae3fafb3492b231545ade6a59b4ca488) and
[#3318](https://github.com/ERGO-Code/HiGHS/commit/6293630a84612d22e87a542d2f1fd2d1b6f07940)
fixes. These new counterexamples do not imply those repairs were absent.

The newest SCUC endpoint reports distinguish solver-reported numerical MIP
lower bounds from independently recomputed exact current-matrix LP lower
certificates. Those exact certificates concern the hard-zero
shedding/shortfall subset of the literal numerical serialized-LODF model;
physical upper witnesses are numerically checked. They do not certify the
physical-DC optimum or the older soft-shedding domain. Discovering a native
solver defect alone does not refute that independent certificate arithmetic.
Conversely, checking primal feasibility alone does not certify a solver's MIP
lower bound. This checkpoint neither rechecks the SCUC certificate bundles nor
draws a blanket historical-invalidity conclusion.
