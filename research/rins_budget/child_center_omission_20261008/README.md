# Serial child analytic-center omission: NO-GO

**Not recommended.** This default-OFF experimental ablation missed its frozen
advancement gate. The route is closed without retries, discarded samples or
retuning. The patch is retained for inspection; it is not enabled in the solver
source by this publication.

## Frozen pilot

The same qualified Release binary ran four fresh sequential processes on one
exposed May-2017 PG89 stage-2 master, in OFF / ON / ON / OFF order, seed 211,
threads=2, parallel=off and a 1% numerical gap. Each call had a 90-second native
limit and 150-second process containment; aggregate process debit was capped
at 600 seconds and the full cohort at 900 seconds.

| Run | Omission | Process wall(s) | Process-tree CPU(s) |
|---|---|---:|---:|
|1|OFF|49.176317|66.946432|
|2|ON|77.647735|77.570328|
|3|ON|43.303253|45.014192|
|4|OFF|45.248376|62.975597|

The required paired wall improvement was at least 15% in **both** comparisons,
with no more than 5% CPU increase in either:

- Run 2/run 1: 57.90% slower and 15.87% more CPU. Both gates fail.
- Run 3/run 4: 4.30% faster and 28.52% less CPU. The wall gate still fails.

All samples are retained. The large ON-repeat variation is unexplained; no
outlier exclusion, pooled replacement statistic or favorable-only claim is used.
Even the faster ON sample misses the wall threshold. This does not establish
that omission is universally harmful; it rejects advancement under this study.

## Mechanism and checked result

Every run retained one main-root AC launch and completed synchronization.
OFF had 33 child launches; ON had 33 child skips and zero child launches. Native
IPX-AC call counts were 34/1/1/34. Each run retained 29 completed child calls,
one top-level node, 25,817 reported LP iterations and incumbent-admission events.
These iteration totals use native heuristic accounting conventions, not raw
child-pivot counts. Native AC clocks overlap other work and are not CPU time
or additive removable wall time.

All four solution files are byte-identical. Each has recomputed objective
2,654,109.36241149, printed native lower bound 2,627,716.0632 and conservative
numerical gap 0.9944314886%. An independent Decimal parser checked the original
MPS and every primal directly: maximum row residual 7.5401267770808425e-10,
zero integrality residual, within the fixed 1e-5 feasibility tolerance. Lower
bound display padding accounts for the native 12-significant-digit report.
This is not an exact dual certificate.

All calls exited 0 without timeout, interruption or remaining descendant.
Measured process debit was 215.375680468s; cohort elapsed was 216.953650403s.
Timing includes process startup through complete reap; preparation and later
read-only audit are separate. No host-wide load control is claimed.

The master has 21,096 columns, 24,468 rows, 82,479 nonzeros and 1,296 integer columns.
Its security rows are incomplete. This is neither full-SCUC validation nor a
1354-bus result, and the input was already exposed.

## Patch boundary

[child-center-omission.patch](child-center-omission.patch) adds two advanced
options, both default false:

- `mip_omit_child_analytic_center`: omit optional center work only when
  `submip && option && parallel == off`.
- `mip_analytic_center_diagnostics`: print per-root launch/skip decisions,
  including otherwise silent children. These are decisions, not completion
  certificates; diagnostics are identical in both pilot arms.

Main-root AC and parallel=on/choose behavior stay unchanged. Skipped child state
is empty/Notset/uncomputed; no task is spawned or falsely synchronized. Optional
center fixing and central rounding are omitted, while ordinary LP re-evaluation,
separation, limits, candidate validation and parent/global proof bounds remain.
The new HighsOptions layout requires consistently rebuilt headers and binaries.

The patch targets official commit
`d547a3ad8af5399651187fb0e133cf0e42615b82` **after** the isolated
[official minimal correctness patch](../correctness_3357_3367_20261007/combined-minimal-correctness.patch).
It does not apply those prerequisite corrections itself. Its SHA-256 is
`2accff0ed5c7f3ae4b4995ebc09cbe45de250ac6f9799cf29a0f280fd5cb3299`.

## Qualification and retained limits

- Matched assertion-enabled focused suites: 118 cases/904 assertions per arm.
- Both assertion and Release builds: 38 custom cases; 8 native flugpl processes
  with two fresh instances each; 4 transformed/public-rerun processes with two
  solves each. Genuine child omission under min/max offsets is covered.
- Release CTest remains literally 168/169 passing. Only
  AffinityReducedCoreCount fails (5==1), reproduced using each arm's own matching
  executable/library. Missing CPU topology leaves the known environment
  limitation. A fresh affinity-excluded aggregate passes 399 cases and
  1,260,054 assertions. No system affinity/topology changes were made.
- No dynamically observed internal restart, active-AC terminator interruption,
  successful injected-stale-center test, or organic depth>1 fixture is claimed.
  Restart/task cleanup is source-reviewed; depth 3 was direct construction.
- Initial sparse-matrix harness errors and unsupported internal-solver reuse
  failures occurred in both reference and candidate. They remain documented in
  [REPLAY_INDEX.md](REPLAY_INDEX.md), with full original records retained.

[RESULTS.json](RESULTS.json) contains all four samples, fixed gates, exact
identities, qualification results and limits. [REPLAY_INDEX.md](REPLAY_INDEX.md)
explains compact offline replay and evidence retrieval. No additional solver
build or solve was performed to publish this report.
