# Validation evidence and limits

This record describes the pristine official commit `d547a3ad8af5399651187fb0e133cf0e42615b82` and replay manifest `f48ac4f80167e2eb677ad5167864fde02c8208334ef5a7e2c6c3c5ffee28daec`, validated on October 3, 2026. It is a new development-reference lineage. The exact identities and exercised tool versions are in [PROVENANCE.json](PROVENANCE.json).

## Source and runtime

All 1006 official source files matched the complete Git tree `788b41e141fa455509c71593e1718b7b71168320`, including SHA256 and Git blob checks. The build used Release, FAST_BUILD, CLI/main/extras together, int32, HIPO off, two jobs and `-flto=2` linker settings. Real solve logs bound the actual main and extras libraries to the selected build. The tested binary hashes are provenance, not a promise that another compiler or filesystem location produces the same bytes.

The public 45-file package has three rewritten documentation/lineage files and a regenerated manifest; its other 41 files are byte-identical to the measured package, including all executables, payloads, tests and the source inventory. [EXECUTABLE_EQUIVALENCE.json](EXECUTABLE_EQUIVALENCE.json) records both identities and the unchanged hashes. The full PG89 measurements remain bound to the measured `f48ac4…` package. The separate public `13d485…` tiny invocation now passed, as recorded below. The immutable replay documents and equivalence record retain the pre-execution status present when their bytes were frozen; this validation record adds the later outcome.

Source/package inventories and the recipe were checked without launching a solver or loading a native library while preparing this kit. A network clone, fresh dependency installation, fresh rebuild and full fresh-consumer setup were not rerun for the kit.

## Narrow mathematical and integration checks

- The official #3270 three-column LP returned exact `Unbounded(10)` with presolve on and off, clean API status and exact input readback. Its feasible origin and ray `(1,1,0)` with objective slope `-5` establish unboundedness for that fixture. This checks that reproduction, not every presolve path or the SCUC workload.
- The retained #3179/issue-3171 regression passed original-space Decimal feasibility checks. Its independently recomputed objective was `42215.525000540`, consistent with the golden objective `42215.5250005` under the retained relative `1e-10` allowance. Passing this fixture is not an independent global optimality proof.
- The public #3180/#3181 compatibility fixture passed original-space primal/objective consistency with presolve on and off. Both runs retained four scaling/cost warnings. Presolve on reduced to empty with no reported Repair LP count; presolve off reported 0. Dynamic execution of the guarded #3181 retry remains **unestablished**. The two Decimal objectives differ, so no exact on/off objective equality is claimed.
- The focused official regressions and presolve/options checks passed 937 assertions in 65 cases.
- The tiny pair and its offline verifier completed with checked objective 660 in both arms. Both final certificates use proof provenance only: upper 660, conservative numerical lower `659.9999899995`, gap approximately `1.5152272681e-8`. Each stage checked all sixteen model-readback fields; all 48 expected primal columns were present. Final original-source and outage residuals were zero. The [independent tiny audit](evidence/tiny-terminal-audit.json) records artifact/source checks and clean teardown. Its timings are integration evidence only.

## Separate public-package integration

The actual public package manifest `13d4857ffae6b6565c66d27c2190d8b8829ff1236d79230787c8d2fa50178373` passed a fresh preparation, preflight, tiny pair and offline verification using the existing pinned official source/build and inputs. All four stages completed with clean teardown in 34.184 seconds total. Both arms produced checked upper 660, numerical lower `659.9999899995` and relative gap approximately `1.5152272681e-8`, with proof-only certificates, the same sixteen-field readback and complete original-source/outage checks.

The [independent public tiny audit](evidence/pristine-public-tiny-terminal-audit.json), SHA256 `d9fbb2095567e189bb60d9c950d5fa18b287c95dc4890b2c0c3b0896b24db6d3`, verified 2786 runtime artifact pins, all 1006 source files, 50 path/hash references, both requested certificates and cleanup. This records an actual public-package invocation. It did not perform a fresh network clone, dependency installation or rebuild, and its timing supports no performance comparison.

The offline verifier checks retained artifact, provenance, debit and numerical-certificate consistency. It does not provide an independent exact dual proof.

## Full-suite result remains qualified

The official unit suite completed **400 cases: 399 passed, one failed**. `AffinityReducedCoreCount` reported 5 available cores rather than 1. In this Linux namespace the CPU topology files under `/sys` were absent. Upstream's fallback uses `(hardware_concurrency()+1)/2` and does not incorporate the known affinity mask. The test also does not check whether its affinity-setting call succeeded, so its log alone does not prove that restriction was applied.

This is an environment-triggered default-core-count limitation. Explicit nonzero thread counts bypass that lookup; the replay uses two threads and retained fixtures use one. The diagnosis does **not** turn the suite into a pass.

The full CTest invocation passed entries 1–5, then its unit-test entry failed and generated extensive output. That CTest process was stopped by a log-size guard, with clean teardown. The remaining entries 7–169 were run separately and all 163 passed. Thus all other configured CTest entries passed, but there is no successful complete CTest invocation to report. The large raw unit output is retained with its source evidence and is not bundled here.

## Interpretation

These checks support a bounded correctness-recovery and tiny-integration result on this runtime. They establish neither universal solver correctness, production readiness, dynamic #3181 retry coverage nor performance superiority. The completed fresh [nine-pair PG89 report](https://github.com/de1tydev/HiGHS/blob/fc0e7087d05f3b521eb44ebc77714b7596e6debd/research/rins_budget/pristine_pg89_results/RESULTS.md) retains every declared outcome under the measured `f48ac4…` package identity. Its executable bytes match the public `13d485…` package, but the original result bindings remain unchanged. Historical measurements remain under their [published advisory](https://github.com/de1tydev/HiGHS/blob/ff204bb95d5acb8b1c6dfe08f299002a5aa6620e/research/rins_budget/CORRECTNESS_ADVISORY.md); do not pool timings across the old custom and new pristine runtimes.
