# Current projected SCUC candidate: portable seed revision v3

A standalone research implementation of the current adaptive per-line SCUC
candidate: two LP seed solves, exact projected-matrix lower certificates, cold
integer discovery, checked incumbent carry and proof calls, and two independent
direct-DC final checks. It is separate from the earlier
[`network_projection` aggregate formulation](../network_projection/).

This revision adds only the optional solver seed. All six predeclared sensitivity
runs passed the unchanged one-percent interval, full QA, negligible-slack and
resource/cleanup gates. Complete outer invocation times were 370.898–509.433
seconds; selected endpoint gaps were 0.006868–0.261305%. These are descriptive
results across three exposed dates and two seeds. See [SEED_PANEL.md](SEED_PANEL.md).
All six terminal and closure archives passed actual readback verification;
post-exit administration is reported separately.

## Install and run

Initial scope: Linux x86-64, little endian, 32-bit `HighsInt`, Python 3.12,
NumPy 2.3.5, SciPy 1.17.0 and threadpoolctl 3.6.0; supported UC.jl 0.3
PEGASE1354 instances with a 36-hour horizon. Unsupported features, dimensions
and horizons are rejected. No dataset or native binary is included.

```sh
python -m pip install --no-compile .
```

Build the official HiGHS commit
`d547a3ad8af5399651187fb0e133cf0e42615b82` using
[native/BUILD.md](native/BUILD.md). The installation must provide matching
`libhighs`, `libhighs_extras`, the v3 assessment helper, guarded source files and
a locally generated runtime manifest. No HiGHS rebuild or patch was introduced
for this seed revision.

```sh
/usr/bin/prlimit --core=0:0 --as=7516192768:7516192768 \
  --fsize=536870912:536870912 python -B -s -m current_scuc run \
  --instance /data/case1354pegase.json.gz \
  --highs /opt/highs/bin/highs \
  --workdir /runs/fresh-name \
  --seed 1
```

`--seed` defaults to `0`. It accepts a canonical decimal integer from 0 through
2,147,483,647. One selected seed is set once on the fresh LP handle and retained
for both LP solves, then passed to every discovery/proof MIP. Hash-bound arm
metadata, worker results, native command receipts and carry checks record
`solver_random_seed`. Python hashing remains fixed at 0; no environment seed
override is accepted. Official HiGHS private child-seed handling is unchanged.
The unused legacy `option_probe.validate_invocation` remains zero-only;
production option readback uses `options.py` and the selected-seed profile.

The runtime manifest is discovered beside the native prefix; use
`--runtime-manifest` for another layout. JSON and gzip JSON inputs are accepted;
the runner performs no downloads. The work directory must be fresh and outside
the source package. Use a clean qualified startup environment as described in
[native/BUILD.md](native/BUILD.md).

The fixed resource policy requires 16 GiB (17,179,869,184 bytes) before
preparation and 11 GiB (11,811,160,064 bytes) before the candidate on a 4 KiB
allocation filesystem. The 2 GiB free floor, 1 GiB launch margin, all phase
reservations and mathematical caps remain unchanged. Qualified SQLite uses
MEMORY temporary storage with strict compile/readback checks.

The supervising owner must enforce CORE 0, AS 7 GiB and FSIZE 512 MiB before
starting the CLI interpreter, with one bounded 512 MiB log and 128 MiB outer
receipt. The example applies the required limits before Python starts; the CLI
also checks them before preparation. The independently measured 2,460-second
outer owner is external. This command alone does not reproduce that owner's
timeout, exact reap/cleanup accounting or bounded outer outputs.

Preparation has a separate 600-second bound; the candidate has a 1,800-second
window and one 600-second seed/MIP/carry process ledger. `RESULT.json` records
reported CLI elapsed time from main entry, sampled before its final JSON write
and stdout output, and points to the detailed candidate result. The outer
start-through-reap clock covers the complete invocation, including interpreter
startup, that final write/output, exit and cleanup.
Exit 0 requires all interval, physical, slack, resource and local receipt gates;
exit 2 records a stopped, failed or incomplete candidate. These clocks are
nested, not additive. Post-exit archival is separately measured administration.
Outputs and local immutable hash/fsync checkpoints are retained.

## Evidence and limits

Independent source review passed 90 pure tests, including 28 focused seed tests;
the unchanged SQLite resource harness passed 71 checks. Actual empty native
handles read back seeds 0/1/2 without optimizer calls. The seed-1 fixed transition
tiny passed its component gate with two LP solves and three total MIPs including
its reference, and correctly remained a candidate quality NONPASS with 2.25 MWh
overflow. It exercised unchanged-master carry and native proof-start admission.

The panel tests two selected solver seeds on three already exposed dates. It
does not establish same-seed repeatability, statistical reliability, unseen-case
generalization or general production readiness. No conventional comparator or
speed ratio is part of it. Numerical MIP lower bounds and exact seed-LP lower
certificates are reported separately. Both concern the hard-zero shedding and
reserve integer subset of the literal serialized-LODF model; neither certifies
the physical DC optimum or the original soft optimum. The physical upper is a
numerically checked witness. `physical_dc_lower_bound_certified` remains false.

See [VALIDATION.md](VALIDATION.md), [SEED_REVISION.md](SEED_REVISION.md) and
[SEED_PANEL.md](SEED_PANEL.md). June seed1 exercised unchanged-master carry. June seed2 exercised changed-master
row-growth carry (three rows, 2,643 nonzeros), with columns, active lines and map
unchanged. Its carried diagnostic point was not a previously admitted physical
endpoint; the later selected endpoint passed full quality and physical QA.
New-line/column-growth carry and a third production MIP were not observed.
Cancellation and crash/OOM behavior remain untested.

Executable source, tests, native build files, licenses and the runtime source
manifest are byte-identical to the reviewed seed-v3 package.
[PUBLICATION_PROJECTION.json](PUBLICATION_PROJECTION.json) records this mechanical
projection. No test, solver, build or scientific checker was rerun to prepare it.
[ARTIFACT_MANIFEST.json](ARTIFACT_MANIFEST.json) inventories the final public bytes;
[PUBLICATION_CHECKS.json](PUBLICATION_CHECKS.json) records the static readback.

[SOURCE_PROVENANCE.json](SOURCE_PROVENANCE.json),
[BINDING_REVIEW.md](BINDING_REVIEW.md) and the records under
[provenance/](provenance/README.md) retain explicitly historical attribution.
[SEED_REVISION.json](SEED_REVISION.json) and
[RESOURCE_REVISION.json](RESOURCE_REVISION.json) are labeled historical records
with private receipt locations removed and receipt hashes retained. Their old
unpublished/unlaunched flags do not describe current execution or repository
status. [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) preserves software and
input source notices. The MIT code license does not relicense input data.
