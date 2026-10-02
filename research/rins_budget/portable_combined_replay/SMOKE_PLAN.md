# Portable replay smoke plan

Status: tested v2 completed this bounded procedure successfully on the recorded
runtime: three real-NumPy scalar tests, 32-bit HighsInt and exact symbol/provider
checks, one tiny A/B pair, five actual API readbacks and exact three-path checker
equality on all five witnesses. The public copy changes documentation, test-report wording and the expected
raw source hash for the module-docstring edit, with a separate manifest identity.
Normalized AST evidence verifies unchanged mathematical and orchestration
function bodies. See the
[validation receipt](../portable_validation/VALIDATION_RESULT.json).

The failed v1 preflight is retained: its version-only invocation had not loaded
the lazy extras DSO, and no tiny model or solve ran. V2 corrected that observation
without relaxing the actual solver or API identity guards. The procedure below
remains the bounded validation to perform on a new runtime.

The historical campaign is complete and failed its strict confirmation gate.
Publication and this procedure do not promote the method or reopen that result.

The intended outcome is narrow: show that relocated source/runtime bindings run
the frozen tiny A/B experiment and preserve the original mathematical and checker
results. It does not measure production speed or establish natural root-credit
activation. Stop after the tiny result and equality receipts are reviewed.
Development and confirmation are separate experiments with their original gates.

## 1. Finish source review before any numerical launch

Review the annotated historical comparison, exact v1-to-v2 functional diff,
public-copy change list and their identity receipts. Require:

- Unchanged mathematical, policy, complete-checker, exporter/readback, separator
  and tiny-fixture bytes, except explicitly documented binding-only changes
- Unchanged constants, seed schedule, budgets, stop/censor behavior, activation
  requirements and development/per-date confirmation gates
- Release pins independent of newly generated local runtime observations, so a
  modified local manifest cannot self-authorize changed math or data
- Exact official source commit plus outer-gap, initial-root-IPX and
  root-child-credit patches in that order; all 983 source inventory entries match
  and no unlisted source file is accepted
- The original compressed and decompressed hashes for all three PEGASE89 inputs,
  including the correct November case89pegase file
- Fresh output refusal, disjoint resolved paths, traversal/symlink containment,
  stale-bytecode exclusion, strict JSON parsing and deterministic fixed plan
- Clean environment and startup-hook rejection without importing scientific
  packages, probing a solver API, loading a model or preparing a numerical cache
- Symmetric source/runtime checks and the original charged timing boundaries;
  any execution-time binding overhead remains inside the charged setup/arm work

The inherited contract/credit/pair-policy/combined tests and the portable binding
tests belong in the pure/mocked review. They must mock process, model, API and
topology work. Inspect test imports and collection behavior before execution.
Do not include separator factorization tests in that pure suite. Retain exact
test commands, source identities and complete results; report a failed test
without converting it into a successful review by omission.

The standard-library runner explicitly skips three tests requiring actual NumPy
scalars. Validate those separately in the selected clean scientific environment,
with their original model/process/API/topology mocks intact:

- `test_contract.SourceWrapperTests.test_trusted_numpy_base_and_residual_cross_boundary`
- `test_contract.TrustedScalarTests.test_finite_numpy_real_only_and_no_input_mutation`
- `test_contract.TrustedScalarTests.test_reject_nonfinite_bool_complex_arrays_and_coercibles`

Retain a separate receipt for the actual scalar tests, including exact source and
runtime identities. A pure-suite skip is not a pass, and a scalar pass is not a
model, solver or topology test.

## 2. Prepare an isolated host and interpreter

Finish the pinned build and correctness tests before the tiny phase. Use the
README's tested clean-environment provisioning steps and startup-hook rejection,
and record the interpreter and scientific/native dependency identities.

Use an otherwise idle Linux/glibc host, a fresh replay directory and the pinned
Release/shared/FAST_BUILD/HIPO-off/HighsInt32 build from the README. Hold CPU
affinity and power settings constant; record the actual host/runtime. No other
build, test, benchmark or diagnostic may contend with the run. Retain
full local provenance while excluding credentials and inherited configuration.

## 3. Prepare, freeze and validate the runtime

Use the README's source-only `prepare` command with explicit research-package,
source, build, data, interpreter and fresh work roots. Do not supply prior run
outputs, generated source scopes, topology/factorization caches or solution files.
Record preparation separately from benchmark timing.

Use the documented run entry point:

```sh
python3 -I -S -B "$PORTABLE/prepare_replay.py" run \
  --work "$WORK" --phase tiny --run-reviewed
```

Require the runtime records to identify the resolved Python executable and
installation files, Python/NumPy/SciPy versions, native BLAS/SuperLU libraries,
OS/libc, CPU, compiler/build configuration, binary, main DSO, SONAME target and
extras DSO. Check that clean-environment values alone are recorded, assertions
remain enabled, and no startup hooks or inherited bytecode enter execution.

Before passing arrays through the C API, require the configured/header integer
mode and actual `Highs_getSizeofHighsInt` result to agree with the existing
32-bit reader. Verify bound C-symbol provenance from actual function addresses.
For the version-only executable observation, require the exact main library;
check an observed extras library against the exact pin, but permit its absence
when it has not been initialized. For every actual solver process, require both
the exact main and extras libraries under the unchanged solver checks. A
successful `dlopen`, library symlink or `ldd` output alone is insufficient.
Reject ABI or observed-DSO mismatch; do not change reader dtypes or relax actual
solver-library checks to complete the run. Retain failed preflight receipts and
logs, and stop before the tiny driver if preflight fails.

## 4. Run exactly the frozen tiny A/B pair

Use the existing two-hour triangle fixture and fixed AB order, with 20 aggregate
actual solver-process seconds per arm. Preserve the two-second MIP containment
grace and twenty-second helper watchdog. Do not add warmups, repetitions,
alternate seeds, larger budgets or a production dataset to this smoke.

Acceptance requires all of the following:

- A starts from empty pairs, makes zero LP calls, has empty first-integer pairs,
  and discovers missing pairs over at least two integer rounds
- B discovers pairs through the existing LP path and then creates a fresh integer
  master; no point, LP bound, basis or numerical cache is reused
- Both arms finish with original complete-source objective-660 certificates,
  finite/status checks, original primal tolerance and conservative gap treatment
- Every generated master has exact actual-C-API equality for all mathematical
  fields and bounds, with LP transformation changing integrality alone
- Selector, input/output and loaded-module receipts identify the frozen source;
  checker JSON remains unchanged by selector metadata
- Every reaped solver child is charged before checks, all watchdog overshoot is
  retained, and resource/credit telemetry is valid
- Arm, common setup, completion, pair/phase archival and full launch-to-exit
  receipts retain their distinct meanings and durable endpoints

An incomplete or invalid arm is a failed smoke outcome. Preserve its outputs and
the frozen safe-counterpart/stop behavior; do not silently restart or substitute
the budget for a missing completion time. Any later diagnostic attempt must use
fresh output and remain a separately identified attempt; it cannot replace the
failed observation or a measured campaign outcome.

## 5. Compare every tiny witness with the frozen checks

First require the existing, separately charged A-versus-B complete-check equality
replay on **every** emitted tiny witness. Include all available intermediate and
final solution witnesses covered by the original replay, not only the final
objective-660 point. Use each witness's exact source/solution bytes for both
checker paths and retain the comparison receipt.

The same tiny invocation then writes `run_v1/tiny/frozen_core_replay/RESULT.json`.
It invokes `frozen_core_check.py` in a fresh clean child for every witness and
requires byte-identical output against both selector checkers, with no excluded
fields. This direct entry point bypasses selector dispatch while retaining
portable path/runtime bindings and the same historical mathematical core.
The public source map records its module-docstring normalization and matching
strict source-hash literal; mathematical and orchestration function bodies match.

Retain this frozen-core comparison using those same witnesses and the exact
historical mathematical/checker implementation and its explicit source-byte map. Document the explicit relocation needed
to run that core on the new runtime. Compare checker output and all mathematical
fields, including status, objective, violations, bounds and integrality. Pin
the witness, checker, source-model and comparison-code identities in the receipt.
Use the same selected runtime for portable/frozen-core checks so the comparison
isolates the publication bindings.

The implemented checker-output comparison excludes no fields. Public receipt
copies may sanitize explicitly identified path/provenance metadata only, after
the exact local comparison. Do not normalize or round numbers, add a tolerance,
erase missing fields, coerce statuses, replace a witness or suppress a failed
comparison. A receipt must show any metadata sanitized and why. A hash match
for source alone is not a substitute for checking the output of each witness.
Do not regenerate the production campaign or compare fresh timings to historical
ones as part of this equivalence step.

## 6. Review the bounded result and stop

The review packet should contain:

1. Release/source/data validation and exact publication diff identities
2. Pure/mocked test results, separately labeled from numerical checks
3. Provisioning, runtime/ABI/loaded-library and source/runtime integrity receipts
4. The retained tiny plan, both complete arm outcomes, per-master API fidelity
   and selector/module records, and distinct timing/resource receipts
5. A/B complete-check equality and frozen-core comparison receipts for every
   tiny witness, including any mismatch or failure
6. A compact pass/fail decision with no performance or promotion claim

Keep raw models, solutions, binaries, datasets and large logs local. Public
summaries may sanitize path/provenance fields only; retain numerical evidence and
all failed/incomplete outcomes. Treat only the recorded runtime as tested until another
complete smoke passes. Do not extrapolate a tiny pass to production speed,
root-credit activation, another ABI or another operating system.

The historical nine-pair confirmation remains **STOP / NO PROMOTION** even if
this portability smoke passes: all 18 historical arms were valid and B was faster
in all nine pairs, but February's median end-to-end improvement was 25.04% against
a required 30%.
A later production replay is a new experiment under the unchanged frozen gates,
with its own retained outcome.
