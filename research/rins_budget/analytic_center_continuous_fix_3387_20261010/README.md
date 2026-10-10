# Candidate guard for continuous-column analytic-center fixing (#3387)

Recorded 2026-10-10. This is a narrowly tested candidate, **not a fully qualified replacement reference**.

## Actual reference failure

The exact previously qualified Release and assertions-enabled DSOs, built from `d547a3ad8af5399651187fb0e133cf0e42615b82` plus the minimal #3357/#3367 and #3332 backports, both return **Optimal 0** with presolve off on the immutable [#3387 MPS](https://github.com/akatsukiwork0320/highs-analytic-center-repro/blob/9cb7a19b5485374943e5756af786780f0e8c8abf/small_repro_17digit.mps). The exact optimum is **1**. Presolve on returns 1 on both. This is a locally observed failure of those exact reference DSOs, not merely an upstream report or an execution of current upstream latest.

Input Git blob: `22afeec6fe42d56c1cd924a7b76d06601a5f77bc`. Baseline Release DSO SHA256: `b2c073c6c16f6af5e8c73b232a01fcf230ca0773e1d199c6423c4e7a1dec1aac`; assertion DSO: `1cd1ee2a86caf402e3d4a97fef182feccd07fbeed62387c9b32f8b6babc12651`.

Both off logs report one continuous column fixed at the analytic center. This work did not collect a new debugger trace identifying that column; the specific y-bound trace remains evidence from the [original report](https://github.com/ERGO-Code/HiGHS/issues/3387).

The exact witness sets g=v=1, f=0, r=y=k, z1=z2=z4=1 and other z=0. The parsed binary64 k is 4722366482869645/2361183241434822606848. All exact rational row residuals are zero, 560+779+131=1470, and g reaches its explicit upper bound 1. See EXACT_ORACLE.json.

## Exact candidate

`continuous-ac-fixing-candidate.patch` inserts three lines in `highs/mip/HighsMipSolverData.cpp`: two comment lines and `if (mipsolver.isColContinuous(i)) continue;` before the proximity test. Patch SHA256: `9815fb51d9c931a7b1a87ef6d372a97d1df3eb587a57051f4cf7e2eda895fe28`.

Only that file differs among 1006 verified reference source files. The patch leaves analytic-center calculation, synchronization, central rounding, ordinary domain propagation and integer/implicit-integer handling unchanged. A continuous coordinate near a bound does not establish that the coordinate is fixed throughout the feasible region. This guard stops making those unsupported continuous-column cuts; ordinarily provable reductions remain available through existing machinery.

## Narrow results

- Eight main candidate solves: MAX g and equivalent MIN -g, presolve off/on, Release/assertion builds. All return Optimal with expected objective +1 or -1.
- Ten unchanged native tests: issue-2173, MIP-maximize, MIP-infeasible-start, get-fixed-lp-semi, implied-row-dual-bound-invalidation on both builds. All pass, 88 assertions total.
- Six prior-backport processes: #3357 domain stack/stabilizer fixture, #3364 rule-only CSC fixture and #3359 objective-25/primal-check fixture on both builds. All pass; #3357 covers four combinations per build. Original fixture sources are pinned in BACKPORT_SOURCE_PINS.json and preserved in the earlier correctness checkpoint directory.
- One additional portable-replay smoke check passes the Release/MAX/presolve-off case. This is separate from the eight-arm matrix.

All eight main tiny solves use threads=1, seed=0, a ten-second solver limit and a thirty-second process cap. Existing profiling (`highs_analysis_level=128`, `log_dev_level=1`) directly shows AC calculation, synchronization and one IPX(AC) call in every presolve-off arm. Presolve-on terminates earlier; no AC execution is claimed there. Native tests preserve their original per-test thread settings and are not globally thread-pinned. Their unchanged runner hashes, actual loader initialization and exact candidate DSOs were checked. Results are correctness observations, never timing comparisons.

Candidate DSO SHA256 values:

- Release: `12e11b36c5162e6bc0cc0357b5a5a9e69305e6cca8956951e497b71a8643edcb`
- Assertions: `7eeb2ec9d64af48ae0833df4e1a2c104d974e123aaec32d3463976513db54f7e`

## Replay

Use the already-built matching local DSO, or independently build the exact reference source plus the patch. New compiler builds need not reproduce the recorded binary hash. Build/configuration fingerprints are in CANDIDATE_RUNTIME_IDENTITY.json. Preserve source and runtime identities separately.

The portable Python driver uses only the standard library and the explicitly supplied native DSO; it installs nothing. Verify a locally rebuilt DSO against its own recorded build hash, or use the recorded hash for recovered candidate bytes. For example:

    timeout 30s env -u LD_PRELOAD -u LD_LIBRARY_PATH python3 replay_fixture.py --library /absolute/path/libhighs.so.1.15.1 --sha256 12e11b36c5162e6bc0cc0357b5a5a9e69305e6cca8956951e497b71a8643edcb --model small_repro_17digit.mps --presolve off --expected-objective 1

Change presolve to on for its paired arm. Use small_repro_min_negative.mps and expected objective -1 for the equivalent minimization arm. Use the assertion DSO and its hash for the assertion pair. The driver prints options, solver return/model status, objective, solution, library hash and actual loader mappings, and fails if status/objective differ from the expectation. Recorded logs contain historical absolute paths; they are provenance, not required replay paths.

## Limits

No full-suite rerun or production qualification was performed. The retained integer proximity-based fixing is not established safe by this work. The guard can weaken reductions and increase search; there is no performance measurement. No SCUC run, historical certificate recheck, upstream correctness claim, default/reference promotion or deployment is implied. The original presolve-off counterexample requires caution with solver-reported bounds; it does not itself refute independent exact certificate arithmetic from unrelated work.
