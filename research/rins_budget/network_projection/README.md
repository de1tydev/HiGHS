# Network projection source and fixed tiny replay

This opt-in research package accompanies the [audited checkpoint](RESULTS.md).
It does not change normal HiGHS builds or defaults. It contains no case dumps,
solver binaries, stored factors or historical optimization state.

The [conventional June1354 comparison](SCUC_REFERENCE_RESULTS.md) records a
completion contrast on that same exposed case: the projected candidate passed,
while ordinary proof returned no full-target feasible upper within the
600-second contained-process budget. The methods use different formulations
and allocation policies. No speed ratio or general acceleration is claimed.

The [fresh hard-zero SCUC checkpoint](SCUC_TARGET_RESULTS.md) records one
exposed June1354 development sample that passed the 1% integer target:
0.270916% numerical MIP interval and 0.310133% using a separate fresh exact
projected-LP certificate, with all original/source and listed-outage direct-DC
checks passed. The contained-process ledger is 143.402847636 seconds; the whole
invocation including checks and stage archives is 555.937916431 seconds. This
is an evidence-only update with no speed ratio or multiple-case claim. The
current method has no published, validated portable entrypoint; the source and
fixed tiny replay documented below remain the earlier aggregate formulation.

The [first-start cumulative checkpoint](FIRST_START_RESULTS.md) records a
continuous bound milestone: 5,148 source-valid prefix rows close 73.2565% of
the original unresolved interval, giving a 0.6899075% numerical interval against
a retained historical upper. It also preserves the ten-row negative. This is
an evidence-only update; no fresh integer timing result or portable
complete-family replay is claimed.

The [adaptive per-line checkpoint](ADAPTIVE_LINE_RESULTS.md) records passing
offline/continuous scopes and a completed integer negative result: 2.5436247449%
gap with full source/physical quality checks. It adds measured research evidence
only; the published source and fixed tiny replay below remain the earlier
aggregate formulation, with no newly validated portable adaptive replay.

The [four-thread first-discovery checkpoint](PARALLEL_MIP_RESULTS.md) records
a completed negative result: 4.573752009% gap, material shared overflow and
verified main-MIP thread activation, without a speedup claim.

The historical [unified-discovery addendum](UNIFIED_DISCOVERY_RESULTS.md) records a
completed negative result: 3.137885621% gap against the 1% target, with checked
final witness and disclosed controller recovery. It adds no portable replay
claim; earlier result reports remain historical.

**Fixed tiny integration passed.** The audited `--mode both` run completed in
1.769846 seconds from launch through cleanup: four projected LP calls (two
seeds plus two continuation calls), three row additions, and two distinct
integer masters, with separate continuous and integer references at $1540.5.
All 12 binaries and all three direct physical outage checks passed. The
synthetic fixture sheds 1.5 MWh; this is separate from June's zero-shedding
witness. It is an integration check, not a performance sample or a validated
36-hour portable replay.

The [validation record](VALIDATION.json) identifies the executed package
manifest `cd388d9b22352ea19fbe93833013b3c4ac2b14b63ea628411a64e947b6512c82`,
source/runtime hashes and audit limits. Only validation/status prose changed
after that run; the current `MANIFEST.json` identifies this publication. The
terminal audit checked saved primal and certificate components; it did not
recompute the full exact matrix contraction because raw dual vectors are not
bundled.

## Dependencies and existing reference recipe

Use Linux/glibc, Python 3.12, NumPy 2.3.5, SciPy 1.17.0 and threadpoolctl 3.6.0.
Use a clean Python installation without `.pth`, `sitecustomize` or
`usercustomize` startup hooks, as required by the existing pristine replay.
Other stacks have not been validated. No pip-installed `highspy` is needed.

Build pristine official commit `d547a3ad8af5399651187fb0e133cf0e42615b82` using
the existing [source verification and exact shared build recipe](../portable_pristine_reference_replay_v3/README.md#verify-the-package-and-reconstruct-the-source).
Follow its source, build and regression sections, including preservation of
any test failure. This package imports that kit's source inventory, build
identity checks, generator, canonical model exporter and source checker.
Its documented PG89 data-fetch/preparation/run steps are not needed here:
the tiny input is constructed in memory. Keep this directory next to
`portable_pristine_reference_replay_v3` inside `research/rins_budget`.

The native wrapper binds the selected local library hash after verifying the
complete official source and required build configuration. Its C API header,
warning-source text, generator, exporter, readback helper, ABI and bound C
symbols remain checked. It requires both main and extras libraries actually
loaded from the selected build. Local binary bytes are not assumed identical
across compilers. No private solver patches or options are applied.

## Fixed tiny run

Set `PYTHON` to the clean interpreter, `RESEARCH` to this checkout's absolute
`research/rins_budget` path, and `SOURCE` and `BUILD` to the verified external
pristine source and build. Set `OUT` to a new path whose parent exists,
outside the source, build and published package. Never overwrite old results.
Run under an external wall limit and at most two CPU cores. The command below
supplies a 170-second process wall limit; caller-controlled CPU/memory limits
are additionally required when running in a shared environment.

```sh
export PYTHONDONTWRITEBYTECODE=1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1 BLIS_NUM_THREADS=1
"$PYTHON" -I -S -B "$RESEARCH/network_projection/verify_files.py"
LD_LIBRARY_PATH="$BUILD/lib" timeout --signal=TERM --kill-after=5s 170s \
  "$PYTHON" -I -S -B "$RESEARCH/network_projection/replay_tiny.py" \
  --research "$RESEARCH" --source "$SOURCE" --build "$BUILD" \
  --mode both --out "$OUT"
```

The fixed two-hour triangle contains 12 binaries, three listed outages, four
nonself monitored/outage pairs per hour, and 24 signed soft rows. The replay:

1. Generates its subset mapping model and fresh factors, transforms it, and
   checks actual C API input readback
2. Solves exactly two LP seed masters, certifies each current matrix lower,
   recovers and persists each original lift, checks every virtual row, and
   retains both oracle cut batches
3. For continuous validation, continues the same LP handle until tight closure,
   with at most nine projected LP calls and eight row additions, then solves an
   explicit full tiny continuous reference in one additional LP call. These extra cuts and bounds never
   enter the separately retained two-batch integer seed
4. Restores all source-derived binary domains, solves fresh integer masters,
   adds a new oracle cut batch when needed, and requires a genuine second
   changed master before accepting the final 1% interval
5. Checks the explicit full integer reference objective against $1540.5 and
   the recovered candidate objective, then checks direct physical outage
   feasibility from the source data independently of generated LODFs

The continuous LP sequence shares a 30-second native cumulative cap.
Each native MIP is limited to 20 seconds; the full script has a 150-second
internal deadline. Timeout or non-Optimal tiny MIP status is a failure. The
external timeout remains necessary because Python cannot interrupt a native
call reliably. The integer adapter uses fresh public C API handles and no
incumbent/basis/tree transfer. It is distinct from the recorded 36-hour CLI
parser and does not test that parser's TimeLimit handling.

`--mode continuous` skips integer work; `--mode integer` retains exactly two LP
seed solves without requiring continuous closure and skips both continuous
continuation and its separate reference. The historical fixed triangle needed
four continuous LP calls; its first two seed lower bounds were $42 and about
$63, far below the $1540.5 full reference. Both modes accept
only this fixed synthetic fixture. There is no user-supplied case switch.
All checks raise on failure; a written `result.json` with `passed: true` and
successful external process completion are both required. If a hard timeout
prevents a final record, the run is failed/incomplete. Retain logs and outputs.

## Source interfaces and limits

- `src/network-projection-lp-core-v1/`: sorted CSC model validation, literal
  row-signature verification, reversible retained-column transformation,
  numerical primal/dual checks and public C API LP wrapper
- `src/network-projection-full-oracle-v1/`: complete listed-outage identity,
  finite eta caps, fresh oracle evaluation and persisted full-lift checking
- `src/network-projection-certified-lower-v2/certified_lower.py`: exact
  sign-projection/global-contraction weak-duality certificate for the current
  stored binary64 LP matrix and row dual
- `src/integer_bridge.py`: source-derived binary authority and restoration,
  preserving every non-type field; original-matrix integrality checks
- `src/gates.py`: extracted oracle/lower admission checks and cut mapping

The mathematical definitions in these modules are retained from the measured
source, with [function-level AST equivalence](SOURCE_LINEAGE.json). Relative
imports and dependency hashes were adapted, old command-line code was omitted,
and the tiny integration/native integer adapter is new. The library functions
are useful for inspection and integration, but arbitrary-case or 36-hour
portable replay is not validated. Exact lower claims concern stored literal
binary64 coefficients. Physical outage primal checks do not convert them into
physical-DC exact lower bounds.

The optimizer-free controller regression is `tests/test_tiny_schedule.py`. It
checks the known nonclosing seed pattern, continuous exhaustion at nine calls,
cut-name uniqueness, and isolation of the two integer seed batches and lower
baseline. Run it with `python -I -S -B`; it needs only the standard library.

The copied arithmetic suites are
`src/network-projection-certified-lower-v2/test_certified_lower.py` and
`src/network-projection-full-oracle-v1/tests/test_full.py`. They use small
synthetic/adversarial fixtures and no optimizer. Run them with `python -B`
under the same pre-provisioned scientific environment and a 30-second external
limit. Neither suite is a substitute for the native tiny integration.

## License and attribution

Code is covered by the included [MIT license](LICENSE.txt). Reused public
solver/generator/export/checker notices remain in their existing directories.
The measured source dataset is from the
[UnitCommitment.jl 0.3 instance catalogue](https://axavier.org/UnitCommitment.jl/0.3/instances/),
with the repository's [source notices](../scuc/sources/). PEGASE1354 derives
from [MATPOWER case1354pegase](https://github.com/MATPOWER/matpower/blob/7.1/data/case1354pegase.m),
whose dataset attribution and CC BY 4.0 terms remain applicable. Code licensing
does not replace dataset attribution. The bundled triangle is synthetic.
