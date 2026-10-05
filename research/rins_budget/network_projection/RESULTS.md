# Network projection checkpoint — 2026-10-05

The full listed-outage continuous relaxation closed to **$0.006291721** in
**59.249878 charged seconds**. The subsequent integer candidate produced a
checked witness but **missed the 1% target: 2.932266553%** after
**541.000663 solver-process seconds**. These are component and negative results;
there is no accepted speed ratio or held-out release.

The source is the June 1, 2017, PEGASE1354 36-hour instance. The native reference
is pristine official HiGHS development commit
[`d547a3ad8af5399651187fb0e133cf0e42615b82`](https://github.com/ERGO-Code/HiGHS/commit/d547a3ad8af5399651187fb0e133cf0e42615b82).
The [earlier correctness advisories](../CORRECTNESS_ADVISORY.md) and
[pristine reference validation limits](../portable_pristine_reference_replay_v3/VALIDATION.md)
remain unchanged, including the recorded 399/400 suite outcome and affinity test
failure. These measurements do not repair older solver lineages or establish a
production solver improvement.

## Scope and method

The transformation removes the network angles, flows and shared overflow from
the master, preserves the other coefficients and source bounds, and adds one
network-value epigraph per hour. A fresh sparse network oracle recovers flows,
evaluates the complete declared contingency scope, and emits global lower cuts.
The continuous lower uses exact rational arithmetic on the stored binary64
projected matrix. Recovered upper costs use original source costs and actual
shared overflow, never the epigraph value as a substitute.

There are 1,432 monitored lines and 1,288 source-listed outages among 1,991
source lines. Scope is all normal limits and all listed nonself contingency
pairs: **66,360,168 pair-hours**, **103,104 signed normal rows**, and
**132,720,336 signed security rows**. The 703 unlisted outages are excluded.
Zero-LODF identities and both signs count. The original two-pair MPS provides
the mapping; it is not a complete full-contingency MPS, and no giant full MPS
was built.

## Full continuous result

Two LP solves and one 36-hour cut batch gave a lower of
**$13,474,893.024853207** and an independently recovered numerical upper of
**$13,474,893.031144928**. Native cumulative LP time was **9.016856909 seconds**;
charged time includes preparation, certificates, oracle work, checks and
serialization. The complete phase including archival and cleanup was
**74.723592 seconds**. It added 48,544 balance-plus-cut nonzeros.

The persisted lift passed complete virtual-row scanning and an independent
alternative scan of all signed rows, including 25,735,536 zero-LODF rows. The
final conservative virtual-row violation was zero. Original matrix row and
bound residuals were 8.07246e-8 and 4.10808e-10. Shedding and reserve shortfall
were zero. Summed shared overflow was 1.2337918633420488e-6 MWh over hourly
periods, costing $0.0061689593; it was not exactly zero.

**This point is fractional:** 601 of 28,080 original integer columns exceed
1e-5 fractionality (285 commitment, 187 startup, 129 shutdown). It is not an
integer SCUC solution. The exact lower concerns the literal binary64 LODF
model; it is not an exact physical-DC outage lower bound. The upper is a
numerically checked witness, not an exact-real primal proof.

See [the compact recorded result](evidence/full_continuous.json).

## Integer result: advancement target missed

The final original cost was **$13,887,551.433527654**. The eligible numerical
MIP lower, after the original printed-bound allowance, was
**$13,480,331.407815196**. Their gap was **2.932266553%**, above 1%.
All 28,080 source-derived binary declarations and values passed; maximum
integrality residual was 1e-13. Both direct physical checkers passed for all
1,288 listed outages and 66,360,168 nonself pair-hours.

Shedding and reserve shortfall were zero. Shared overflow totaled
**1.0219748674e-6 MWh**, maximum **9.7874817584e-8 MW**, cost **$0.0051098743**.
The small protective slack does not make the missed bound target a success.

Fresh two-LP seeding consumed 58.167166 seconds. Three cold MIPs then consumed
121.196262, 121.256001 and 240.381234 seconds. Their shared process ledger was
**541.000663 seconds of 600**; full invocation time was **978.461844 seconds
of 1,800**, with peak sampled tree RSS 2,548,023,296 bytes and clean cleanup.
The unused process budget was not used for another solve. No prior point,
factor, cut, incumbent start, basis or search tree was supplied.

All three outcomes matter. The first two provisional gaps were 3.6801% and
9.3327%, with 19.587332 and 186.907552 MWh of shared overflow. The third removed
material network slack but left the proof interval open. The method used two
seed cut batches and two between-master batches. The final lower is numerical
solver evidence for the literal binary64 LODF integer model, not an exact tree
proof or a certified physical-DC lower bound.

See [every recorded master and final checks](evidence/integer_v2.json).

## Earlier rejected outcomes remain rejected

- Continuous v1 rejected its second returned dual: stationarity residual
  7.247591446457591e-5 exceeded 1e-5 after 26.805964 charged seconds. No control
  ran. This does not by itself establish false native optimality
- The revised two-pair continuous candidate used the exact certificate and
  closed in 38.586295 charged seconds. Its monolithic control was rejected at
  stationarity residual 0.0011857424287882168, so the paired phase failed and
  supplies no accepted speed comparison
- Integer v1 stopped after its first MIP because its diagnostic filter rejected
  `callSolveMip return of HighsStatus::Warning`. The pinned source maps clean
  TimeLimit to that return. It charged 183.116893 process seconds and
  262.268134 whole seconds; no original upper was admitted. V2 corrected this
  specific parser incompatibility and ran afresh
- A separate **189.596018-second** saved-point diagnosis checked that v1 point
  physically. Its recovered original cost was $13,991,584.096555904, with
  19.587332235681064 MWh of shared overflow. It did not rescore v1, compute an
  admitted phase gap, or count as an in-budget optimization result

The [earlier outcome summary](evidence/prior_outcomes.json) and
[saved-point diagnosis](evidence/saved_point_diagnosis.json) preserve these
failures and separate accounting. Hashes identify the recorded source and
terminal evidence. This public checkpoint carries compact summaries and core
source, not the complete large run archives.

## What can be replayed here

The [consumer recipe](README.md) provides the core transformation, full oracle,
exact certificate, source-derived integer restoration, and a fixed synthetic
continuous/integer demonstration. Its small explicit reference is suitable for
checking the implementation. The new portable tiny adapter passed its bounded
continuous/integer integration with separate $1540.5 references; the
[validation record](VALIDATION.json) identifies the tested code and audit
limits. Its synthetic 1.5 MWh shedding is distinct from June's zero-shedding
witness. The 36-hour production CLI workflow is not exposed or validated as a
portable entrypoint by this package.
