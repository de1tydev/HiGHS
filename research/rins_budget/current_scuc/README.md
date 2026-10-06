# Current projected SCUC candidate: portable resource revision v2

A standalone research implementation of the current adaptive per-line SCUC
candidate: two LP seeds, exact projected-matrix lower certificates, cold
integer discovery, checked incumbent carry and proof calls, and two independent
direct-DC final checks.

This is separate from the earlier
[`network_projection` aggregate formulation](../network_projection/). Its
historical CLI does not run this method.

## Install and run

Initial scope: Linux x86-64, 32-bit `HighsInt`, Python 3.12, and supported UC.jl
0.3 PEGASE1354 instances with a 36-hour horizon. Unsupported source features,
dimensions and horizons are rejected. No dataset or native binary is included.

```sh
python -m pip install --no-compile .
```

Use a clean environment with NumPy 2.3.5, SciPy 1.17.0 and threadpoolctl 3.6.0.
Build the official HiGHS commit
`d547a3ad8af5399651187fb0e133cf0e42615b82` using
[native/BUILD.md](native/BUILD.md). The installation must provide matching
`libhighs`, `libhighs_extras`, the v3 assessment helper, guarded source files
and a locally generated runtime manifest.

```sh
/usr/bin/prlimit --core=0:0 --as=7516192768:7516192768 \
  --fsize=536870912:536870912 python -B -s -m current_scuc run \
  --instance /data/case1354pegase.json.gz \
  --highs /opt/highs/bin/highs \
  --workdir /runs/fresh-name
```

The runtime manifest is discovered beside the native prefix. An explicit
`--runtime-manifest` supports another layout. JSON and gzip JSON inputs are
accepted; the runner performs no downloads. The work directory must be fresh
and outside the source package.

This resource-only revision requires 16 GiB (17,179,869,184 bytes)
before preparation and 11 GiB (11,811,160,064 bytes) before the candidate on a
4 KiB allocation filesystem. These are fixed gates; the 2 GiB free floor,
1 GiB launch margin, all phase reservations and all mathematical caps remain.
The qualified SQLite connection uses MEMORY temporary storage with strict
compile/readback checks. The supervising owner must enforce CORE 0, AS 7 GiB
and FSIZE 512 MiB before starting the CLI interpreter, with a clean qualified
startup environment and one bounded 512 MiB log / 128 MiB outer receipt.
The ordinary CLI additionally checks those limits before preparation.
The example above applies the required limits before Python starts. Run it
under the clean qualified environment described above. The independently
measured 2,460-second outer owner is external; this command alone does not
reproduce that owner's timeout, reap/cleanup accounting or bounded outer outputs.
Preparation has a separate 600-second bound; the candidate has a 1,800-second
window and one 600-second seed/MIP/carry process ledger. `RESULT.json` records
complete CLI elapsed time and points to the detailed candidate result.
Exit status 0 requires all existing interval, physical, slack, resource and
local receipt gates; status 2 records a stopped, failed or incomplete candidate.

Checkpoints hash/fsync existing immutable artifacts and unique state snapshots.
Outputs are retained. Optional archival is external. The exact lower certificate
is for the current literal-row projected matrix;
`physical_dc_lower_bound_certified` remains false.

## Validation and publication scope

Prelaunch checks passed: 1 import-only test plus 61 pure in-process tests,
71 SQLite equivalence checks, and a resource-only child inheritance smoke.
An independent review found no implementation blocker and separately passed
9 admission and 4 process-contract tests. These checks did not run a solver.

The full CLI completed one already exposed 36-hour June PEGASE1354 case and
reported a checked one-percent integer interval. A read-only independent terminal
audit verified the saved evidence and byte bindings. Full CLI elapsed time was
502.873 seconds; the enclosing start-through-reap
measurement was 502.938 seconds. The checked upper objective was
13,779,019.591303479, with a numerical MIP lower of 13,741,689.973312583
and a 0.270916% gap. The separate exact second-seed LP lower supports a
0.310133% interval; neither lower certifies the physical DC optimum.

Both final physical checks passed over all 1,288 listed outages and 66,360,168
pair-hours. All 28,080 original binaries passed without rounding. Load shedding
and reserve shortfall were zero; shared overflow was 9.483655958320015e-7 MWh,
with its cost included in the upper objective. The run exercised unchanged-master
carry, native assessment and proof-start admission. Production new-line/changed-master
carry remains untested.

This is one exposed-case usability result. There is no comparator or timing
ratio, general MILP or multi-platform result, reproducibility study or production
readiness claim. Cancellation and crash/OOM behavior remain untested.

See [VALIDATION.md](VALIDATION.md) for the exact evidence and limitations and
[RESOURCE_REVISION.md](RESOURCE_REVISION.md) for the six-file resource delta.
The package source, native code, tests, tools, license files and runtime source
manifest are byte-identical to the resource revision under review.

[SOURCE_PROVENANCE.json](SOURCE_PROVENANCE.json) and the original
[extraction review](provenance/BASE_BINDING_REVIEW.md) retain historical baseline
attribution; their former hashes and counts do not describe edited resource
files. [BINDING_REVIEW.md](BINDING_REVIEW.md) explains that scope.
[RESOURCE_REVISION.json](RESOURCE_REVISION.json) is a labeled prelaunch record
whose receipt locations have been removed while keeping receipt hashes.
Its unpublished/unlaunched flags are historical, not current repository status.

[ARTIFACT_MANIFEST.json](ARTIFACT_MANIFEST.json) inventories these public bytes;
the original preprojection inventory is preserved under
[provenance/](provenance/RESOURCE_PRELAUNCH_ARTIFACT_MANIFEST.json).
[PUBLICATION_PROJECTION.json](PUBLICATION_PROJECTION.json) records the mechanical
projection. No test, solver or build was rerun to prepare it.

[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) preserves the software and input
source notices. The MIT code license does not relicense input data.
