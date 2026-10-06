# Current projected SCUC candidate

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
python -B -m current_scuc run \
  --instance /data/case1354pegase.json.gz \
  --highs /opt/highs/bin/highs \
  --workdir /runs/fresh-name
```

The runtime manifest is discovered beside the native prefix. An explicit
`--runtime-manifest` supports another layout. JSON and gzip JSON inputs are
accepted; the runner performs no downloads. The work directory must be fresh
and outside the source package.

The candidate requires 26,974,885,888 free bytes on a 4 KiB allocation filesystem.
Preparation has a separate 600-second bound; the candidate has a 1,800-second
window and one 600-second seed/MIP/carry process ledger. `RESULT.json` records
complete CLI elapsed time and points to the detailed candidate result.
Exit status 0 requires all existing interval, physical, slack, resource and
local receipt gates; status 2 records a stopped, failed or incomplete candidate.

Checkpoints hash/fsync existing immutable artifacts and unique state snapshots.
Outputs are retained. Optional archival is external. The exact lower certificate
is for the current literal-row projected matrix;
`physical_dc_lower_bound_certified` remains false.

## Validation limits

52 pure tests passed. A fixed two-hour synthetic transition test passed from a
second byte-identical package directory: actual unchanged-master carry, native
assessment, proof start admission, and independent physical/reference checks.
Its candidate correctly remained a nonpass because shared overflow was 2.25 MWh.

The separate older changed-master harness stopped before carry on its exhausted
support assertion. Changed-master carry and cancellation/kill behavior are not
claimed validated by these runs. The portable production CLI has not had a
production-size run, and no performance claim is made.

See [VALIDATION.md](VALIDATION.md) and [tests/TINY_REPLAY.md](tests/TINY_REPLAY.md)
for exact coverage and commands. Source/file/AST attribution is in
[SOURCE_PROVENANCE.json](SOURCE_PROVENANCE.json), with deliberate binding changes
in [BINDING_REVIEW.md](BINDING_REVIEW.md).

[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) preserves the software and input
source notices. The MIT code license does not relicense input data.
