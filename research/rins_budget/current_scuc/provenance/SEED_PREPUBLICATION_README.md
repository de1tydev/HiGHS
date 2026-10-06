# Current projected SCUC candidate: portable seed revision v3

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

An optional `--seed` selects the HiGHS random seed, default `0`. For example,
append `--seed 1` to the command above. It must be a canonical decimal integer
from 0 through 2,147,483,647. The same selected seed is set once on the fresh
LP handle and retained for both LP solves, and passed to every discovery/proof
MIP. The hash-bound arm manifest, worker results, native command receipts and
carry checks retain it as `solver_random_seed`. Python hashing remains fixed
at 0. No environment seed override is accepted. Official HiGHS private child
seed handling remains unchanged.

The runtime manifest is discovered beside the native prefix. An explicit
`--runtime-manifest` supports another layout. JSON and gzip JSON inputs are
accepted; the runner performs no downloads. The work directory must be fresh
and outside the source package.

This revision preserves the v2 resource policy and requires 16 GiB (17,179,869,184 bytes)
before preparation and 11 GiB (11,811,160,064 bytes) before the candidate on a
4 KiB allocation filesystem. These are fixed gates; the 2 GiB free floor,
1 GiB launch margin, all phase reservations and all mathematical caps remain.
The qualified SQLite connection uses MEMORY temporary storage with strict
compile/readback checks. The supervising owner must enforce CORE 0, AS 7 GiB
and FSIZE 512 MiB before starting the CLI interpreter, with a clean qualified
startup environment and one bounded 512 MiB log / 128 MiB outer receipt.
The ordinary CLI additionally checks those limits before preparation.
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

The inherited v2 resource revision passed 62 pure tests and a 71-check SQLite
equivalence harness. Seed-revision validation is recorded in SEED_REVISION.md.
The following numerical coverage belongs to the preserved baseline only: A fixed two-hour synthetic transition test passed from a
second byte-identical package directory: actual unchanged-master carry, native
assessment, proof start admission, and independent physical/reference checks.
Its candidate correctly remained a nonpass because shared overflow was 2.25 MWh.

The separate older changed-master harness stopped before carry on its exhausted
support assertion. Changed-master carry and cancellation/kill behavior are not
claimed validated by these runs. The separate v2 production evidence remains unchanged; this seed revision has
not run a production-size case, and no performance claim is made.

See [VALIDATION.md](VALIDATION.md) and [tests/TINY_REPLAY.md](tests/TINY_REPLAY.md)
for exact coverage and commands. Source/file/AST attribution is in
[SOURCE_PROVENANCE.json](SOURCE_PROVENANCE.json), with deliberate binding changes
in [BINDING_REVIEW.md](BINDING_REVIEW.md).

[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) preserves the software and input
source notices. The MIT code license does not relicense input data.

The separately published/tested source remains immutable. This seed revision has not
been published and has not run a production CLI.
[RESOURCE_REVISION.md](RESOURCE_REVISION.md) describes the exact resource-only
delta and validation. Historical attribution in SOURCE_PROVENANCE.json,
BINDING_REVIEW.md and PUBLICATION_PROJECTION.json describes the baseline;
RESOURCE_REVISION.json supplies the new local delta and source identities.

[SEED_REVISION.md](SEED_REVISION.md) records the narrow seed-only scientific
delta, default-zero compatibility, pure coverage and pending native release
checks. The unused legacy `option_probe.validate_invocation` remains zero-only;
production option readback uses the exact selected-seed profile in `options.py`.
