# CMIR fixed-scale coefficient cache v1 — preregistration

2026-10-06, before patch execution. Official baseline d547a3ad8af5399651187fb0e133cf0e42615b82.
Motivation: prior 14 diagnostics show gesa2 root separation takes 37–53% of
parent MIP time and dcmulti sub-MIPs 76–81% in detailed runs. Static review
identifies an O(n^2) CMIR complement trial loop: every trial recomputes
scaled coefficient, floor and fractional part for every integer coefficient,
although trial scale is fixed and only one coefficient is complemented.
This attribution is a hypothesis until the logging pilot observes cache hits.

Mechanism: memoize the exact binary64 tuple (coefficient * fixed scale,
fast_floor(scaled + kHighsTiny), scaled - floor) per row entry. Refresh when
coefficient bits change; cache lifetime is one complement-loop invocation.
No trial omitted, no summation reordered, no cut/efficacy threshold changed,
no restricted bound used. Bit-identical keys include signed zero. The original
path remains behind default-false mip_cmir_cache_coefficients. Independent
mip_cmir_cache_log false by default reports work counts only in mechanism runs.
Potential regressions: allocation/cache traffic, small rows, codegen changes.
No learned heuristic, parameter-tuning or RINS budget change is included.

Gate 1: deterministic scalar-reference comparisons, signed zero, sign reversals,
near-integer values and scales, plus sanitizer cache-only checks. Verify options
copy/default/readback. Gate 2: one logged gesa2 seed-1 candidate run, 60 native /
75 outer seconds, to establish nonzero reuse without treating its timing as a
speed result. Stop/deny performance claim if no hits or invalid output.

Gate 3 fixed full diagnostic panel: egout, flugpl, dcmulti, gesa2, lseu, gt2,
plus the already exposed cached two-hour triangle original-subset.mps. Seeds
1,2,3, one official baseline and one enabled candidate per model/seed, reversing
order for even seed. All available at registration; preserve any future missing
input. All native limits 60s, outer 75s, two scheduler threads, parallel off,
0.01% MIP gap. Serial processes, no concurrent builds. Neither this small panel
nor the triangle is unseen SCUC evidence. Preserve status, objective, dual,
nodes, iterations, solution bytes, actual wall, timeout, logs and primal checks.
Pair unchanged original model bytes and solver options except new off/on flag.
Use a native-matrix readback plus independent Python row/bound/integer/objective
arithmetic to check all returned points. No independent dual proof is claimed.
Report every pair and regressions, not only geometric means. Official vs patched
default-off seed-1 pairs on dcmulti/gesa2 check default behavior before on-panel.

Keep as an experimental patch only if scalar/correctness gates pass. Do not
recommend enablement without a useful consistent measured improvement; a failed
speed gate stops v1 and motivates a separately preregistered follow-up rather
than outcome-based panel replacement. A provisional practical gate is >=5%
median wall reduction among baseline >=0.5s pairs, with no >20% regression in
that same group and no newly failed/timed-out pair. Short-case overhead remains
reported. Three seeds are diagnostic, not statistical reliability evidence.

Data access blocker remains exact public URLs:
https://axavier.org/UnitCommitment.jl/0.3/instances/matpower/case1354pegase/2017-01-15.json.gz
https://axavier.org/UnitCommitment.jl/0.3/instances/matpower/case1354pegase/2017-04-15.json.gz
https://axavier.org/UnitCommitment.jl/0.3/instances/matpower/case1354pegase/2017-07-15.json.gz
Observed response: HTTP/1.1 403 Forbidden to CONNECT, server envoy,
URLError(OSError('Tunnel connection failed: 403 Forbidden')). This is a proxy
access rejection, not origin 404 or a SCUC solver failure; the specific policy
rule was not disclosed. Approved retry also failed. No further alternate-path
attempt. Minimum missing inputs are these three unmodified public UC.jl 0.3
files via an authorized provision path; original source/hash must be retained.
No matching 1354 source/model was found in the workspace repository/cache.
The fixed triangle MPS and official bundled general MILPs are lawfully available
and are used only as exposed development data.
