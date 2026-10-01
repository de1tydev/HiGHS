# Opt-in heuristic return at the outer MIP gap

## Outcome and scope

This experiment has **not established a substantial or stable speedup**. One
matched seed on the custom 36-hour PEGASE1354 base-network UC model completed
in 585.58 solver seconds with the change enabled, versus 602.55 seconds with
observation only: a 2.8% difference. The two arms returned the identical final
incumbent. This is useful evidence of the intended early-return mechanism,
not a multi-instance performance claim or a new recommended default.

The benchmark is base-network UC, not N-1. It retains the public source's
penalized shedding/slack semantics. Both final incumbents have only numerical
zero shedding and zero line overflow. The original-data checker independently
verified feasibility and objective; the dual bound remains HiGHS's reported
bound. “Optimal” below means the requested 1% relative-gap stopping criterion,
not exact zero-gap optimality.

| Same binary, seed 0 | Observe only | Early return enabled |
|---|---:|---:|
| Solver status | Time limit reached | Optimal at requested gap |
| Solver seconds | 602.55 | 585.58 |
| Process seconds including I/O | 605.05 | 588.31 |
| First qualifying direct-child candidate, solver elapsed seconds | 583.325445 | 585.444736 |
| Parent acceptance, solver elapsed seconds | 602.539165 | 585.565628 |
| Delay after qualifying candidate | 19.213720 | 0.120892 |
| Final source-checked objective | 19,051,753.24219772 | 19,051,753.24219772 |
| Final gap using checked incumbent | 0.4794319343% | 0.4794319343% |

The observer arm exceeded its 600-second solver request by 2.55 seconds. Both
were allowed a separate 660-second process watchdog; neither was killed. Setup
and independent checking were outside the solver limit and reported separately.
The enabled arm's first qualifying candidate occurred later in absolute time,
so the 19-second avoided return delay must not be presented as a deterministic
end-to-end saving. Root LP timings also varied between runs. Repeatability and
held-out cases remain unestablished.

The complete compact measurements, CPU/RSS, input/library hashes, candidate
logs, and source-check residuals are in
[`recorded_results/pg1354-outer-gap-600.json`](recorded_results/pg1354-outer-gap-600.json).
Both extracted incumbent files have SHA-256
`a1c1c88a5b6e5648e4dc070dfaf9ac303de59bed93a4abb27233bcb4dddb45ae`.

## What the patch changes

`outer-gap-heuristic.patch` applies independently to the pinned upstream source
`73cac48c5340d775a477087198611862559be250`; do not stack it with the RINS ablations.
Its SHA-256 is `e1d1c2df245c9723f80bdd2d1a5c5cb817bae2d9c474795bd97c2892170990ae`.
The repository's production source/defaults are not changed by storing this
artifact. When applied, two advanced options are added, both false by default:

- `mip_heuristic_outer_gap`: enable the return goal
- `mip_heuristic_outer_gap_log`: observe and log the same goal

An immediate heuristic child of the main serial MIP may return a feasible
candidate once it satisfies a conservative snapshot of the outer solver's gap.
It sets only the child's local solution-limit status. Shared termination state,
parent candidate validation, parent proof/stopping tests, objective cutoffs,
and numerical tolerances remain unchanged. No restricted child dual bound is
exported as an outer bound. Nested children and parallel B&B workers are not
eligible for this goal.

For normalized minimization, let q be the child candidate's postsolved original
zero-offset objective, L the snapshotted parent offset-free lower bound, and O
the parent's current presolve offset. The absolute gap is q-L; the relative
criterion uses abs(q+O). The implementation checks q >= L and the ordinary
absolute or relative tolerance predicate with finite, long-double intermediates.
It does not invert a positive-objective threshold, and does not add a child's
presolve offset twice. Cost vectors, objective senses, offsets, serial scope,
and candidate feasibility are guarded before activation. This covers negative,
zero, offset, and original maximization objectives without relaxing the target.

`OuterGap child` logs launch, first qualifying candidate, return, snapshot and
actual local-stop status. `OuterGap parent` logs normal validation/acceptance,
improvement, elapsed time and the then-current outer gap. Logging requires the
ordinary output route to be enabled. Stopping is cooperative: it cannot interrupt
an LP, presolve pass, or deeper heuristic already executing between checks.

## Correctness evidence

The frozen patch passed an independent code review with no identified
correctness blocker and these Release-build checks before the paired run:

- Focused outer-gap tests: 218 assertions across 5 cases
- MIP/options tests: 1,010 assertions across 50 cases
- Full CTest: 166/166 entries, 27.16 seconds
- Full unit executable: 1,259,349 assertions across 333 cases

Tests exercise min/max objectives, negative/zero/cross-zero values, nonfinite
inputs, missing/infeasible incumbents, child presolve offsets, actual stopped
returns, ordinary parent acceptance, observation-only behavior, nested scope,
and nonactivation under parallel B&B. A real fixed-column integration uses
current parent offset 400. These checks establish tested behavior, not a formal
proof or broad performance validation.

## Replay

First prepare the pinned checkout and the PEGASE1354 MPS following
[`scuc/README.md`](scuc/README.md). Set PACKAGE to this package, WORK to a new
working directory, MODEL to that generated MPS, and INPUT to its source JSON.gz.
The model must match the published SHA-256; do not silently change penalties,
slack policy, ratings, or formulation between arms.

```sh
PIN=73cac48c5340d775a477087198611862559be250
git clone https://github.com/de1tydev/HiGHS.git "$WORK/outer-gap"
git -C "$WORK/outer-gap" checkout --detach "$PIN"
git -C "$WORK/outer-gap" apply --check "$PACKAGE/outer-gap-heuristic.patch"
git -C "$WORK/outer-gap" apply "$PACKAGE/outer-gap-heuristic.patch"
cmake -S "$WORK/outer-gap" -B "$WORK/build-outer-gap" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON -DALL_TESTS=ON \
  -DBUILD_EXAMPLES=OFF -DHIPO=OFF -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build "$WORK/build-outer-gap" --parallel 4
ctest --test-dir "$WORK/build-outer-gap" --output-on-failure --parallel 1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
for ARM in observe enabled; do
  OUT="$WORK/outer-gap-$ARM-seed0"
  mkdir "$OUT" || exit 1  # refuse an already used directory
  cp "$PACKAGE/options/outer-gap-$ARM.options" "$OUT/options.txt"
  printf 'mip_improving_solution_file = %s/incumbents.txt\n' "$OUT" >> "$OUT/options.txt"
  # Linux limits below reproduce the 7 GiB address-space cap and 660s watchdog.
  (ulimit -v 7340032; /usr/bin/time -v timeout 660 \
    "$WORK/build-outer-gap/bin/highs" "$MODEL" \
    --options_file "$OUT/options.txt" --random_seed 0 --time_limit 600 \
    --solution_file "$OUT/final.sol") > "$OUT/solver.log" 2> "$OUT/process.log"
  python3 "$PACKAGE/scuc/large_cases/extract_checkpoint.py" \
    "$OUT/incumbents.txt" --columns 313776 --output "$OUT/incumbent.json"
  python3 "$PACKAGE/scuc/check_solution.py" "$INPUT" "$OUT/incumbent.json" \
    --mode network > "$OUT/source_check.json"
done
```

Retain all exit codes, incomplete runs and watchdog outcomes; a recovered
checkpoint alone does not establish a valid dual bound or deadline success.
Check for ignored matrix coefficients. Compare the source-checked objective
with a finite status-valid solver bound and record any solver-limit overshoot.
The historical Python runner imposed the same address-space cap and killed at
660 seconds; the shell replay uses GNU timeout and therefore has slightly
different shutdown semantics. It is a recipe for new measurements, not a
bit-identical runner archive. Run arms sequentially on an otherwise idle host;
record exact compiler, CPU, loaded library and model hashes.
