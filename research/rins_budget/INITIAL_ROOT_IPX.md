# Experimental initial-main-root-only IPX selection

## Preliminary result

The February 1 tuning instance, seed 0, took 564.48 solver seconds with the
unchanged engine selection and 465.27 seconds with initial-root-only IPX, a
17.6% reduction in this matched pair. Both met the requested 1% gap and passed
the independent source-data primal/objective checker with numerical-zero load
shedding and zero line overflow. This is a promising exploratory result, **not
an established substantial or stable acceleration claim**. The frozen policy subsequently failed to reach the target on both preselected
held-out dates in either arm; see the complete hold-out results below. The
February-only improvement must not be presented as stable acceleration.

| Same binary, 2 threads, seed 0 | Control | Initial root IPX |
|---|---:|---:|
| Solver seconds | 564.48 | 465.27 |
| Process seconds, including I/O | 567.59 | 468.22 |
| Solver child CPU seconds | 734.36 | 635.79 |
| Solver child peak RSS, KiB | 2,089,300 | 1,870,492 |
| Independently checked objective | 19,051,753.24219772 | 19,070,270.83555942 |
| Gap using checked incumbent | 0.4794319343% | 0.5760830525% |

The two incumbents differ; this is time to a common gap target, not a comparison
at an identical objective. Dual bounds come from HiGHS; only primal feasibility
and objective are independently checked. The custom 36-hour PEGASE1354 model is
**base-network UC, not N-1**. It retains the source's soft penalty/slack policy.

The candidate ran first, then a fresh control. Both used the same combined
binary, two HiGHS scheduler threads, one B&B worker (`parallel=off`), outer-gap
return enabled, no warm start, and 600 solver seconds with a separate 660-second
watchdog and 7 GiB address-space cap. There was one protocol deviation: a brief
system-monitor installation/smoke overlapped the control at about
15:33:50–15:34:08 UTC. Observed monitor CPU was mostly below 1%, without a build.
The possible host/network/I/O noise is disclosed rather than silently ignored;
its overhead was not measured. The single pair cannot establish repeatability.

Diagnostics show one selected IPX invocation, 60 IPX iterations, 7,839 crossover
iterations, a valid basis and no simplex fallback. The root call ran from
17.386230 to 192.789127 solver seconds. Ordinary parent validation accepted the
final heuristic candidate at 465.244093 seconds. This confirms actual engine
work and valid completion, not just an option label or a faster root phase.

Exact records and test/build hashes are in
[the paired record](recorded_results/pg1354-initial-root-ipx-600.json) and
[build metadata](recorded_results/root-ipx-build.json).

## Completed held-out-date check

The same binary, flags, seed 0, source/model hashes and 600-second request were
retained. August ran control then candidate; November ran candidate then control.
No policy was retuned between these arms.

| Held-out date | Control | Initial root IPX |
|---|---|---|
| August 1 | 600.05 s, 6.83% final gap | 608.03 s, 4.58% final gap |
| November 1 | 600.05 s, no incumbent | 630.13 s, no incumbent |

All four ended with status "Time limit reached". Neither date reached 1% in either
arm, so their
unknown target times are censored and **no target-time speedup ratio is defined**.
August's two available primals pass independent source checks with numerical-zero
shedding and zero overflow. November produced no primal: validation was
unavailable, not a failed check of a claimed feasible solution, and this does
not establish infeasibility. The larger candidate overshoot, 30.13 seconds, is
retained; none of the processes was killed by the 660-second watchdog.

IPX materially shortened each initial LP and improved some bounds, but that did
not establish the requested end-to-end result. Root cut/basis work and incumbent
availability remained bottlenecks. Including February, each arm reached the
requested target on only one of three dates at this seed. More seeds were not
used to turn this failed hold-out check into a favorable aggregate. Defaults
remain unchanged; the research now tests a different, explicitly application-
layer UC-relaxation/network-repair route rather than promoting this option.

Full records and predeclared order/hashes:
[held-out outcomes](recorded_results/pg1354-initial-root-ipx-heldouts.json),
[held-out plan](recorded_results/root-ipx-heldout-plan.json).

## Source behavior

`initial-root-ipx.patch` is independent of the existing outer-gap patch. It
applies to pinned upstream `73cac48c5340d775a477087198611862559be250`, either on
its own or after the exact outer-gap patch. Its SHA-256 is
`533cc510f73fba3ce49bafdad585a3a9b1a3e3ad6a76a79da2b2123393d64e24`.
The production source in this repository remains unchanged by storing it.

The new Boolean advanced option `mip_initial_root_ipx` defaults to false. When
enabled, it overrides the selected engine to IPX only when the relaxation is
all of the following:

- The initial cold LP of the main MIP, before any restart
- The primary `mipdata_->getLp()` object
- Without a valid basis, and without an active parallel-search lock

A valid initial basis skips the experiment permanently. Later basis loss,
restarts, heuristic copies, nested sub-MIPs and nonprimary worker LPs do not
reactivate it. The restart guard is necessary because upstream resets the
first-LP flag during setup. Parallel-enabled search may still use IPX for its
initial serial root; active worker LPs are excluded.

Shared `mip_lp_solver` and `mip_ipm_solver` are never changed. Existing option
restoration, crossover and error-to-simplex fallback remain in place. Analytic
centering and upstream IPM recovery calls are untouched; the option does not
promise that no other IPX work can occur through ordinary upstream behavior.
No proof criterion, tolerance, objective cutoff, candidate acceptance or
termination status is changed. A different root basis can nevertheless alter
all downstream search, even though downstream engine settings remain fixed.

`InitialRootIPX select`, `result`, and `complete` diagnostics record a persistent
selection count, actual iteration/crossover counts, basis and status, fallback,
and elapsed time. Zero IPX iterations are inconclusive about engine work;
presolve-to-empty or an exhausted limit can return without iterating.

## Verification and limitations

Before timing, the frozen combined HIPO=OFF Release build passed:

- 166/166 CTest entries, 49.04 seconds
- 1,259,678 assertions across 342 full unit cases
- 326 assertions across 9 focused root-IPX cases
- 1,349 assertions across 60 MIP/options/IPX cases
- Independent code review and replay checks

Coverage includes default-off metadata, actual IPX work/crossover basis, warm
basis skipping, unchanged later/global options, min/max with objective offsets,
presolve on/off/empty, invalid/infeasible/unbounded/time-limit behavior, copied
and nested LPs, and a real parallel-enabled root integration. Limitations matter:
restart and active-worker guards were tested through controlled internal state;
the small parallel integration does not claim that extra search workers were
needed. Forced IPX numerical-error fallback is untested, although its source is
unchanged. Unbounded coverage is a known rowless fixture, not a generated IPX
ray. Meson registration was updated but not executed. This experiment did not
build with HIPO enabled.

## Replay

Follow [OUTER_GAP.md](OUTER_GAP.md) for the pinned checkout, common options,
model generation, fresh result directories, watchdog, checkpoints and source
checker. Apply this additional independent patch before the shared build:

```sh
git -C "$WORK/outer-gap" apply --check "$PACKAGE/initial-root-ipx.patch"
git -C "$WORK/outer-gap" apply "$PACKAGE/initial-root-ipx.patch"
cmake -S "$WORK/outer-gap" -B "$WORK/build-root-ipx" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON -DALL_TESTS=ON \
  -DBUILD_EXAMPLES=OFF -DHIPO=OFF -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build "$WORK/build-root-ipx" --parallel 4
ctest --test-dir "$WORK/build-root-ipx" --output-on-failure --parallel 1
```

Use this exact same binary for both options files:
`options/initial-root-ipx-choose.options` and
`options/initial-root-ipx-root-ipx.options`. They differ only in the new flag;
set a unique improving-solution checkpoint path for each arm. The time limit is
600 seconds, random seed 0, and the relative gap 1%. Preserve incomplete runs,
status/exit codes, all warnings and the original-model checker output.

Unlike the old cumulative-resource harness, `process_measure.py` returns the
specific solver child's `wait4` CPU/RSS and kills the process group and reaps
the solver child on a
watchdog or catchable Python cancellation. `test_process_measure.py` checks
separate child memory peaks, nonzero exits, timeout and exception cleanup.
Uncatchable process termination cannot be made cleanup-safe by Python. This
helper is reusable orchestration support; it does not itself validate a MIP
certificate. A finite status-valid bound and a successful independent primal
check are still required.

The two held-out source dates can be downloaded through the existing manifest:

```sh
python3 "$PACKAGE/scuc/download_data.py" \
  --case case1354pegase_2017-08-01 --case case1354pegase_2017-11-01
```

Generate both with the same published network-only exporter, 36 hours. Frozen
expected generated-model hashes are in
[the held-out model manifest](recorded_results/pg1354-heldout-models.json).
Do not change ratings, penalties, formulation or policy after seeing an arm.
