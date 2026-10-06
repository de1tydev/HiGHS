# Exact CMIR coefficient-cache kernel experiments

These are default-off source patches against pristine official HiGHS
`d547a3ad8af5399651187fb0e133cf0e42615b82`, built with the same GCC 14.2.0
release configuration as the restored official baseline. They are actual
kernel arithmetic changes, not solver-parameter tuning. The checkout's root
solver and the frozen `current_scuc` package remain unchanged; the patches are
built and tested in isolated official worktrees. No commercial comparison or
leaderboard result is implied.

## V1 — rejected for speed

[PLAN.md](PLAN.md) was committed before patch execution. The mechanism caches
normalized coefficient, floor, and fractional part within one fixed-scale CMIR
complement loop, comparing coefficient bits on lookup. It performs every
original trial and preserves efficacy accumulation order, source bounds, cut
validation, and global-bound logic. It does not skip integral complements like
the older `cmir_integer_complement_v1` research checkpoint.

- 480,000 scalar tuple comparisons passed ASan/UBSan, including signed-zero,
  sign reversals, near-integer inputs and six scales. The domain matches the
  existing fast_floor arithmetic; this patch does not fix its pre-existing
  out-of-range conversion behavior.
- Option default/copy/readback checks passed. Both new flags default false.
- Logged gesa2/seed1: 2,245 CMIR calls, 170,943 queries, 43,808 computations
  (127,135 reused). This measures avoided arithmetic, not solve speed.
- Default-off dcmulti/gesa2 seed1 pairs matched official status, objective,
  reported dual bound, nodes, iterations and solution bytes.
- All 21 enabled official/candidate pairs completed, with matching solution
  bytes and independently checked original-matrix primals. No timeout, solver
  failure or primal failure was dropped. Solver status Optimal uses the
  predeclared 0.01% tolerance; it is not an exact dual certificate.
- Among the six pairs whose official runtime was at least 0.5s, median process
  wall change was **+0.4749%**, worst **+29.4556%**. The predeclared practical
  gate (at least 5% median reduction and no >20% regression) failed.
  V1 must remain off; its single -24.9180% observation on dcmulti seed1 does
  not rescue the full experiment. Short-case variance/overhead remains visible.

Complete per-pair data: [V1 summary](evidence/v1/summary.json), with raw logs,
point files, original native matrix readbacks, options and independent arithmetic
checks in [V1 evidence](evidence/v1/). A setup failure is retained: the first
exporter did not compile because a serializer name collided with `std::vector`.
The first mechanism launch stopped before any solver call. Renaming that helper
allowed the identical predeclared mechanism slot to run; no case/seed changed.

## V2 — direct refresh

[V2_PLAN.md](V2_PLAN.md) was committed after rejecting V1 and before V2 solves.
V2 removes V1's per-term key/validity branch and uses 16-byte floor/fraction
entries. Source `flipComplementation` changes only `vals[k]` among coefficient
values. At the first admissible trial all entries are initialized; subsequently
only k is refreshed, including after restoration of a rejected trial. A trial
rejected before evaluation restores its coefficient without touching the cache.
All other algorithm decisions remain original. 3,840,000 tuple comparisons over
accepted/restored/skipped flip sequences passed ASan/UBSan before large panel
execution. V2 is development using the same exposed panel, not new independent
generalization evidence. V2 completed all 21 pairs with independently checked primals and identical
per-pair solution bytes. Logged mechanism: 170,943 queries, 45,724 computations
(including explicit restoration after rejected trials). Default-off checks also
matched. The six >=0.5s official-runtime pairs had median wall change
**-4.2868%**, worst **+11.3154%**. V2 still fails the preregistered 5% median
improvement gate. Its single -42.0859% gesa2 seed1 observation does not establish
a robust speedup. Both versions stay disabled; no third cache threshold is
tuned on this panel. See [complete V2 pairs](evidence/v2/cache-panel-v2/summary.json)
and [all V2 records](evidence/v2/).

Together V1/V2 executed 94 solver calls: two logged mechanism calls, eight
pristine/default-off checks and 84 enabled A/B endpoints. Every returned point
passed the original-matrix arithmetic check. The initial exporter setup failure
had zero solver calls and is separately retained. The largest original row residual across the 84 paired endpoints was
1.98952e-13, largest bound residual 1e-13, and all integer residuals were zero.
No CTest-suite completion,
production-SCUC validation or independent numerical dual proof is implied.

## Next executed direction: separator attribution

[SEPARATION_PLAN.md](SEPARATION_PLAN.md) freezes six cost-profile calls after
rejecting both cache speed gates. The diagnostic patch is based directly on the
official commit, with neither cache patch present. It is enabled only at existing
`log_dev_level >= 2` and times original calls without changing decisions. It
records implied bounds, cliques, tableau, path, mod-k, scheduling separators,
LP reoptimization, pool-size deltas and cuts selected into the LP. These are
diagnostic counts, not cut validity/global-bound certificates. Sub-MIP scope
is retained. The initial diagnostic build failed on a generic lambda unsupported by the
baseline's C++11 compile mode; the compiler log is retained. Replacing its
callable argument with a C++11-compatible std::function preserved the original
algorithm and build flags. No diagnostic solve ran before that build fix.
All six diagnostic calls completed and passed the independent original-matrix
arithmetic checker. Total executed native solver calls for this checkpoint are
therefore **100** (94 cache-stage calls plus 6 attribution calls), with zero
native timeouts or discarded solver/checker failures. The two pre-solve setup/
build errors remain recorded. ASan/UBSan scalar checks also passed at -O3;
assertions remained enabled in the standalone tests.

| Case | Main path s | Sub-MIP path s | Main tableau s | Sub-MIP tableau s |
|---|---:|---:|---:|---:|
| dcmulti seed1 | 0.404144 | 0.823453 | 0.078911 | 0.056339 |
| dcmulti seed2 | 0.109523 | 0.406527 | 0.030400 | 0.052205 |
| dcmulti seed3 | 0.110742 | 0.271004 | 0.036550 | 0.037917 |
| gesa2 seed1 | 0.115729 | 0.034221 | 0.041658 | 0.017683 |
| gesa2 seed2 | 0.165405 | 0.035578 | 0.043951 | 0.018854 |
| gesa2 seed3 | 0.126780 | 0.036634 | 0.051054 | 0.021183 |

[Full component/cut-count summary](evidence/separation/runs/cost-summary.json)
and [raw diagnostic evidence](evidence/separation/) retain all components,
scopes, LP iteration deltas and original matrix checks. These diagnostic times
exclude printing immediately after each call; printing still adds whole-solver
overhead and can perturb execution. They are not matched acceleration ratios.
Path aggregation is the largest measured separator component in all six calls.

The next selected code experiment is path-mixing scratch-vector reuse, described
in [NEXT_EXPERIMENT.md](NEXT_EXPERIMENT.md). It is not yet implemented or timed.
This follows actual attribution rather than another CMIR threshold or failed
RINS scheduling switch. Both cache options remain default off; no performance
promotion or release claim results from this checkpoint.

## Scope and reproduction

The fixed panel is egout, flugpl, dcmulti, gesa2, lseu, gt2 and the previously
checked synthetic triangle original-subset MPS, each seeds 1/2/3. Exact hashes
and source paths are in [INPUTS.json](INPUTS.json). For each seed, official and
candidate order alternates as specified. Each uses two scheduler threads,
parallel off, 60-second native limit, 74-second outer watchdog with one-second
cleanup allowance, 7GiB address space, 6GiB sampled process-tree RSS, 64MiB file
limit and 2GiB memory/disk headroom. No build overlapped a solver run; solver calls were serial.
Timing is fixed-model solver process start-through-exact-reap; model export,
checker and receipt overhead is separately inside whole-arm records, which
must not be treated as a fair end-to-end SCUC comparison.

The new [checker](check_primal.py) uses the **official** library only to read
original MPS arrays, then independently recomputes every original row activity,
variable bound, integer violation and objective in Python without modifying the
point. It is independent arithmetic, not an independent MPS parser or a dual
proof. Numeric feasibility threshold is 1e-6; objective-token comparison also
allows documented floating-point serialization error. All costs are retained.
The triangle is a known material-overflow model; its generic-MIP feasibility is
not a new full N-1 SCUC success. The absent 1354 cases have no fabricated result.

[reproduce.sh](reproduce.sh) takes an official source/build, the cached synthetic
MPS from the already published tiny replay, and a fresh output root. It rebuilds
each patch, runs scalar/option checks and the predeclared stages. Its shell
syntax is checked and constituent commands executed; the entire script is not
rerun as a redundant experiment. The original full HiGHS CTest suite is not
claimed to have run. This remains research, not a release or auto-merge verdict.

The three original public SCUC files remain unavailable due to proxy CONNECT
403 (envoy), whose exact access-policy rule was not disclosed. No bypass or
further network retry was attempted. The previous report now explicitly notes
that a single overwritten urllib receipt does not retain the whole retry
history. Minimum missing inputs remain the three unchanged files listed in
PLAN.md via an authorized input provision path.
