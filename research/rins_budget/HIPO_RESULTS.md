# Negative same-build HiPO experiment

The one-seed exploratory comparison did not improve time to a checked 1% gap:

| Same binary, 2 threads, seed 0 | `mip_lp_solver=choose` | `mip_lp_solver=hipo` |
|---|---:|---:|
| Solver status | Optimal at requested gap | Time limit reached |
| Solver seconds | 542.36 | 604.15 |
| Process seconds including I/O | 545.21 | 607.12 |
| First root LP start / finish, coarse seconds | 18 / 250 | 17 / 320 |
| Final independently checked objective | 19,051,753.24219772 | 19,291,428.10835994 |
| Final gap using checked incumbent | 0.4794319343% | 1.7158810389% |
| Reached requested 1% gap | yes | no |

Both solutions pass the same original-data primal/objective checker with only
numerical-zero shedding and zero line overflow. This is the custom 36-hour
PEGASE1354 **base-network UC**, not N-1 or production-security certification.
The model and source hashes are unchanged from the previous experiments. Dual
bounds are reported by HiGHS, not independently verified. No coefficients were
reported dropped. HiPO exceeded the requested solver time by 4.15 seconds;
neither process hit the separate 660-second watchdog or 7 GiB address-space cap.

Only the no-basis LP engine varied in this pair. Both arms used the same new
HiPO-enabled binary, two HiGHS scheduler threads, `parallel=off` (one B&B worker),
outer-gap stop/log enabled, and `mip_ipm_solver=choose`. No initial incumbent was
supplied. BLAS/OMP/MKL environment thread limits were one. The order was choose
then HiPO, with no competing builds/tests. This fixed-order one-seed screen is
not a broad backend ranking or stable-speedup study. Comparing its control with
the earlier one-thread run would mix thread count and build changes.

## Build and backend verification

The pinned upstream source plus the exact reviewed outer-gap patch was built
with `HIPO=ON` and `BUILD_OPENBLAS=ON`, Release GCC 14.2.0, CMake 4.4.3, Ninja
1.13.2, automatic LTO, four build jobs. The normal optional-dependency recipe
fetched official OpenBLAS v0.3.30, commit
`993fad6aebbce34a97d3f8c34d6d79d35b64cc48`, from
https://github.com/OpenMathLib/OpenBLAS.git. Preserve upstream dependency licenses
and third-party notices when redistributing a build. No binary is included here.

The actual OpenBLAS cache says `DYNAMIC_ARCH=OFF`, despite an earlier configure
message saying it was being enabled. Runtime reports
`OpenBLAS 0.3.30 NO_LAPACKE NO_AFFINITY COOPERLAKE SINGLE_THREADED`, thread count
one and parallel backend zero. Thus these results describe that fixed-kernel
build; they do not establish performance for a differently tuned BLAS build.

All 182 CTest entries passed in 46.23 seconds, including the additional BLAS
checks; the full unit executable passed 1,259,919 assertions across 339 cases.
An explicit adlittle LP smoke using `--solver hipo` reported Running HiPO,
Threads: 2, and optimal crossover. The large MIP logs identify OpenBLAS; the
source selects HiPO for explicit `mip_lp_solver=hipo` on cold LPs, and no fallback
error appeared. MIP inner-solver output is normally suppressed, so we do not
claim a direct per-iteration HiPO trace for the large run. Analytic-center
centering still forces IPX; its clock label must not be used as HiPO evidence.

The official recipe can be reproduced from the separately patched checkout:

```sh
cmake -S "$WORK/outer-gap" -B "$WORK/build-hipo" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON -DALL_TESTS=ON \
  -DBUILD_EXAMPLES=OFF -DHIPO=ON -DBUILD_OPENBLAS=ON \
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build "$WORK/build-hipo" --parallel 4
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  ctest --test-dir "$WORK/build-hipo" --output-on-failure --parallel 1
```

Use the model generation, fresh output directories, checkpoint recovery,
watchdog, and independent check from [OUTER_GAP.md](OUTER_GAP.md), substituting
this one binary and `options/hipo-choose.options` or `options/hipo-hipo.options`.
Keep thread count, outer-gap settings and every other option matched. Check the
actual loaded `libhighs`, extras and BLAS library hashes, not just the executable.

## Resource-accounting correction

The original harness used cumulative `RUSAGE_CHILDREN`. The shell executed the
second Python arm in-place after waiting for the first, so the second arm
inherited the first arm and checker resource counters. Its raw CPU/RSS fields
are **not valid per-arm measurements** and have been omitted from the published
record. Wall/solver times, statuses, solution checkpoints and primal checks are
unaffected. The first control's solver CPU was 706.01 seconds; the joint
cumulative child maximum RSS was 2,030,644 KiB. Exact HiPO CPU and peak RSS cannot
be reconstructed. The cumulative CPU difference gives only a 725.32-second
upper bound because it still includes the first driver/checker. RSS maxima
cannot be subtracted. Future measurements use child-specific `wait4` resources.

Compact records and exact hashes:
[paired results](recorded_results/pg1354-hipo-600.json),
[build metadata](recorded_results/hipo-build.json).
