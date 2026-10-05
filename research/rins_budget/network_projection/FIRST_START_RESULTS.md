# First-start cumulative inequalities: continuous bound milestone

Recorded 2026-10-05 on the 36-hour PEGASE1354 June 1, 2017 case.
This evidence-only checkpoint records a completed ten-row negative and a
separately frozen complete-family LP diagnostic. The published aggregate source,
fixed tiny replay, normal HiGHS builds and defaults are unchanged.

The complete family raises the certified lower endpoint from
$13,474,893.024913887 to **$13,736,286.335665341**, an uplift of
$261,393.3107514549. It closes 73.2564878613% of the original unresolved
interval and exceeds the predeclared 25% / $89,204.83304031193 advancement gate.
Against the retained checked upper of $13,831,712.357075134, the remaining
numerical interval is $95,426.02140979283, or **0.6899075035%** of that upper.

This is a continuous bound milestone on matching mathematical data. The lower
certificate covers the literal binary64 projected/LODF model; the upper is a
historically acquired numerical physical/source witness. Its acquisition is
outside the current clock. No fresh integer solve, fresh 600-second time-to-1%
result, acceleration ratio or exact physical-DC lower certificate is claimed.

## Inequality and source proof

For a unit g initially off for at least its longest startup delay, let C[g]
be the unchanged literal binary64 longest-delay startup cost, u[g,t] its binary
on status, and sc[g,t] its nonnegative startup-cost variable. Add, for a prefix
ending at t:

    sum(sc[g,s], s=0,...,t) - C[g]*u[g,t] >= 0

If u[g,t]=1, the original binary transition and start/stop exclusivity rows
force a first in-horizon startup at some k<=t, with no earlier shutdown.
The initial off-history guard places the prior shutdown outside the relevant
cold-cost window. The literal startup epigraph therefore requires
sc[g,k]>=C[g]. All other sc terms are nonnegative, proving the prefix row.
If u[g,t]=0, nonnegativity proves it directly. The argument includes t=0 and
a startup in the final modeled hour, without imposing future horizon completion.

Construction checks the original binary authority, literal transition,
exclusivity and startup-history rows, sc lower bounds, and finite nonnegative
monotone costs with increasing integral delays. Initial-on units and shorter
off histories are excluded. C[g] is copied exactly, never rounded upward.
The source proof is supported by exact finite tests over 109,440 schedules in
1,600 tiny parameter cases, including boundary histories and counterexamples
to omitted guards. These tests do not enumerate the full fleet model.

## Frozen experiments and measured outcomes

Both candidates append rows to the same original saved LP matrix, preserve
all prior coefficients, bounds, domains, names and objective, and add no columns.
Every variable remains continuous in these diagnostics; the inequalities rely
on the separately verified original binary model. Each diagnostic made one
fresh native solve without an imported basis or solution start.

| Observation | Ten-row diagnostic | Complete family |
| --- | ---: | ---: |
| Added rows / nonzeros | 10 / 292 | 5,148 / 100,386 |
| Total columns / rows / nonzeros | 141,878 / 157,809 / 658,634 | 141,878 / 162,947 / 758,728 |
| Certified lower endpoint | $13,504,534.26736893 | $13,736,286.335665341 |
| Uplift from original lower | $29,641.2424550429 | $261,393.3107514549 |
| Original unresolved interval closed | 8.3070730152% | 73.2564878613% |
| Predeclared 25% advancement gate | Failed | Passed |
| Separate numerical 1% retained-upper comparison | Failed | Passed |
| Raw stationarity maximum | 0.005636384529680072 | 2.9103830456733704e-10 |
| Raw quality checks | Stationarity failed | All passed |
| Exact-certificate loss from native objective | $0.0056548044085502625 | $4.842877388000488e-8 |
| Native cumulative seconds | 11.0375854969 | 8.4772613049 |
| Worker launch through reap seconds | 12.9415186330 | 10.4620348170 |
| Outer launch through reap seconds | 33.3121583800 | 28.9343782750 |

The ten-row rule chooses one greatest-deficit prefix per eligible unit from the
frozen baseline LP, breaking exact ties at the earliest hour and requiring a
deficit greater than 1/100000 dollars. Its 8.307% improvement misses the fixed
gate; this remains a closed negative. Native Optimal, primal and objective
checks passed, but raw stationarity exceeded 1e-5. Only that failed threshold
was replaced by the prospectively admitted exact current-matrix certificate;
no other acceptance gate or tolerance was changed.

The distinct complete-family rule uses no LP point for selection: enumerate
all 36 prefixes for each of the 143 source-eligible units, in source order.
The complete candidate starts from the original baseline, not the ten-row
candidate. Its improvement over the ten-row lower is $231,752.068296412.
The unchanged retained integer witness satisfies all 5,148 added rows exactly.

## Certificate, witness and timing scope

The exact certifier binds the stored matrix and retained row dual, projects
row signs as needed, and chooses a rational global contraction so residual
column costs have finite support on their original bounds. The recorded
complete-family contraction is 72057594037927936/72057594037927951; it resolves
73 unsupported uncontracted columns, leaving zero negative-infinity terms.
Exact rational row and column support sums yield the reported downward
binary64 lower endpoint. Interval closure uses (L-L0)/(U-L0); the separate
numerical gap is (U-L)/U. The baseline is the matching saved LP lower, not a
later numerical MIP bound.

The retained upper passed original source/objective and all 28,080 binary
checks, plus direct physical checks across 1,432 monitored lines and 1,288
listed outages. The source has 1,991 lines; checking the listed outages does
not establish all-line-outage coverage. Shedding and reserve shortfall are
zero; shared overflow is 1.2199093362141868e-6 MWh. Source, solution, checker,
objective and scope identities were rebound before reuse. The physical scan
was not repeated in these LP diagnostics.

Both runs use the pristine official development commit
`d547a3ad8af5399651187fb0e133cf0e42615b82`, with recovered identical native
binary bytes in a new October 5 runtime cohort. Current qualification was
minimal; the historical full test suite was not rerun. Each run met its fixed
30-second preparation, 45-second native cumulative, 60-second worker,
30-second certificate and 150-second whole-phase ceilings, with clean process
reaping. Complete-family preparation through native readback took 6.9819255450
seconds, certification/gate/export/readback 2.8367851940 seconds, and the phase
including archive completion 28.8841242220 seconds. The outer 28.9343782750
seconds is the authoritative launch-through-reap measurement. Native cumulative
time is separate from native-call wall time and process wall time. These are
single observations, with no cross-cohort timing ratio.

Independent source and terminal reviews passed. The terminal audits checked
matrix/dual identity, recorded rational enclosures, contraction and bound-sum
consistency, fixed gates, raw quality, retained-upper scope and final process
and archive accounting. They did not rerun the certifier; the complete-family
terminal audit relied on the prior source/append proof.

## Evidence and limits

[Compact evidence](evidence/first_start_v1.json) records the exact rational
certificate values, source/model/solution/checker/audit hashes and final capsule
SHA256 commitments, including post-archive process accounting. Full case matrices,
vectors and the complete-family runner are not bundled in this update. Those
hashes identify retained evidence; they do not establish a portable complete-family
replay. The published fixed tiny replay continues to exercise its earlier
aggregate formulation only.

The earlier startup-epigraph candidate's formula could not be recovered, so
novelty or overlap relative to that treatment remains unresolved. No result
from a later integer pipeline, held-out case or general performance study is
included here.
