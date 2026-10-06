# Portable resource revision v2 validation

## Full June CLI result

The CLI completed one invocation on the already exposed
`case1354pegase_2017-06-01.json.gz` fixture with its full 36-hour production scope.
The saved result reports `passed: true`, `result_complete: true`, and
`checked_one_percent_integer_interval`; the outer process exited 0 and reports
clean execution. A read-only independent terminal audit passed: source/native,
option, point, exact-LP certificate and numerical-MIP bound bindings were checked,
along with all seven checkpoint chains and 107 unique sealed artifacts. The audit
verified saved QA evidence and byte identities; it did not repeat scientific
computation or execute a solver. Its original receipt digest and selected fields
are included in the public result evidence.

The compact [public result evidence](evidence/june-cli-result.json) maps each
reported field to a named original receipt, SHA256, byte count and JSON pointer.
Raw inputs, large point/model artifacts, binaries and private launch paths are
not distributed with this source package.

The final checked upper is 13,779,019.591303479. The selected lower,
13,741,689.973312583, is a numerical MIP bound from proof call 2: printed token
`13741689.9735` minus the 0.000187416899735 allowance. Its interval gap is
0.27091635760831925%, within the one-percent target. This MIP lower is not an
exact rational certificate. Separately, the exact second-seed LP lower
13,736,286.327225514 supports a 0.3101328349% interval with that final upper.
The exact LP evidence applies to its literal projected matrix and the hard-zero
load-shedding/reserve integer domain. Neither lower certifies the physical DC
optimum, original soft optimum, or a domain that allows merely negligible shedding.
`physical_dc_lower_bound_certified` remains false.

All 28,080 original binaries passed their type/bound/integrality checks without
rounding, with maximum binary residual 0. Both the independent source checker
and direct DC checker passed over all 1,288 listed outages and 66,360,168
pair-hours. Load shedding and reserve shortfall were 0 MWh. Shared overflow
was 9.483655958320015e-7 MWh; its 0.004741827979160008 objective cost is included
in the checked upper. This is a numerical physical witness under the retained
checks and tolerances, not exact physical certification.

The run completed actual cold discovery, unchanged-master carry, native point
assessment, and admission of that complete start into proof call 2. The source
and target master MPS hashes are identical. Production new-line/changed-master
carry was not exercised.

### Clock boundaries

- Enclosing owner process, launch through exact reap/cleanup: 502.937512081 s
  against its 2,460 s allocation
- CLI's own elapsed time: 502.87312598300196 s, including preparation
- Preparation: 51.463910113001475 s against its 600 s allocation
- Candidate process, launch through exact reap/cleanup: 448.7702826079985 s
  against its 1,800 s allocation; candidate internal time: 443.75673583200114 s
- Actual seed/MIP/carry process ledger: 147.79511367700616 s against 600 s,
  comprising seed 74.79242738600442 s, discovery MIP 10.33871221300069 s,
  carry 19.556663975003175 s, and proof MIP 43.10731010299787 s
- Physical worker: 156.39971917300136 s, including source checker
  59.992785210000875 s and direct separator 88.2330842750016 s

The physical checks are included in whole-run time. These nested clocks overlap;
they must not be added together or compared as a speed ratio. No comparator ran.
The owner records sampled peak tree RSS of 1,721,798,656 bytes, complete resource
accounting, exact child reap, `wait4` ECHILD, no owned survivors and no watchdog
kill. All seven local fsync/hash checkpoints were verified. Sampled RSS is not
a certified instantaneous maximum; one successful run does not establish
full-size memory fit across cases. Optional external archival is outside timing.

## Prelaunch evidence

The source manifest is
`3465ac32efaf90225a34178593ea7748a04f4becb2af85e4fddfb74e375c63c0`.

- 1 import-only test and 61 pure in-process tests passed, 62 total. This includes
  both bound-runtime source-only tests. The complete successful log is
  [prelaunch-pure-tests.log](evidence/prelaunch-pure-tests.log)
- 71 SQLite equivalence checks passed against the new witness implementation,
  covering query results, serialization bytes and hashes, ordering, negative
  compile/readback cases and injected allocation failures. Fixed triangle
  records exercise serialization only; the saved December dataset is empty
- A resource-only child smoke passed with inherited CORE 0, AS 7 GiB and
  FSIZE 512 MiB. It exercised no model, physical computation or HiGHS call
- An independent focused review passed 9 admission and 4 process-contract tests
  and found no implementation blocker, subject to its prelaunch prerequisites.
  These are overlapping focused checks, not 13 extra distinct suite cases

[The curated evidence summary](evidence/prelaunch-validation-summary.json)
contains test outcomes, qualification readbacks and original receipt hashes.
The [source-delta receipt](evidence/prelaunch-source-delta-verification.json)
and [independent review receipt](evidence/prelaunch-independent-review.json)
are byte-identical historical prelaunch records. Their unlaunched/output-absent
fields describe the time of those checks.

The first pure invocation from outside the source working directory passed all
61 in-process tests but failed the import-only subprocess with ModuleNotFoundError.
Rerunning from the source directory passed all 62 without code changes. The
initial failure is disclosed and its original log hash is retained in the summary.

To repeat the pure checks, run `python -B -s tools/run_pure_tests.py` from this
source directory with `CURRENT_SCUC_TEST_RUNTIME_MANIFEST` naming a verified
runtime manifest. The SQLite harness is `tests/sqlite_resource_equivalence.py`;
`--baseline` names the preserved baseline package, `--saved-physical` names the
retained December physical evidence, and `--out` must be fresh and external to
the source bundle. The saved physical evidence is not distributed here.

## Historical coverage and limits

The baseline numerical record is preserved verbatim in
[BASE_VALIDATION.md](provenance/BASE_VALIDATION.md), with commands in
[tests/TINY_REPLAY.md](tests/TINY_REPLAY.md). It covers a two-hour synthetic
unchanged-master carry through native assessment, proof admission and independent
physical/reference checks. The candidate correctly remained a nonpass with
2.25 MWh shared overflow. The older changed-master harness stopped before carry
on an exhausted support assertion.

Production new-line/changed-master carry remains unexercised. Cancellation and
crash/OOM behavior, general SCUC/MILP coverage and Windows support are not
established. This single already exposed case is a usability result, not an
independent holdout, performance comparison, reproducibility study or production
readiness claim. Historical runs are not a matched timing comparator.

Publication preparation only copied files, curated nonruntime metadata and
verified file hashes. No build, solver, model generation or test was run for the
publication projection. The source/test/runtime-manifest bytes remain unchanged.
