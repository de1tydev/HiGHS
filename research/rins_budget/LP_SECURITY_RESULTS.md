# Cold security screening with LP discovery

## Outcome

On one February PEGASE89 instance and seed, LP cut discovery reduced measured
solver-process time by **27.24%** and complete standalone-equivalent elapsed
time by **14.17%**. Both results have the same checked 0.98605% numerical gap.
The predeclared development gate required at least 20% on both metrics, so this
policy's campaign stopped. No held-out or multiseed run followed. This is a
useful one-case application-layer result below the advancement target, not
established stable acceleration or a solver-kernel speedup.

| Cold pipeline | Solver process s | Standalone-equivalent E2E s | Integer rounds | LP discovery calls |
|---|---:|---:|---:|---:|
| Integer screening from an empty pair set | 36.915915 | 46.317049 | 2 | 0 |
| LP discovery, then the same integer loop | 26.858685 | 39.752561 | 1 | 2 |

There was one serial run per arm, baseline first, seed 0. Host noise and
repeatability remain unmeasured. Both final master MPS files and final solution
files are byte-identical across arms. The final MIP process itself took
25.279010 versus 25.647250 seconds; the benefit comes from cheaper security-row
discovery before that common master, not a faster solution of those same bytes.

## Scope and fixed policy

Input is public PEGASE89, 2017-02-01, 36 hours: 89 buses, 12 generators and
210 lines in the unchanged custom preventive DC UC formulation. Checks cover
exactly the 192 source-listed non-islanding outages and 14,721 eligible pairs
(529,956 pair-hours). This does not claim all 210 line outages, AC feasibility,
generator outages or UnitCommitment.jl default-formulation parity. Original
penalized shedding and shared line-overflow variables remain in the model.
Source provenance and limitations are documented in [scuc/README.md](scuc/README.md).

Both arms start with an explicit empty pair list, no incumbent and no basis.
No earlier 12- or 23-pair screen is imported. Cold refers to those optimization
inputs; hardware and operating-system caches are not flushed. Every integer
round restores the source model and has no warm start from the previous round.

The baseline solves an integer master, checks every listed outage, adds all
violated original pairs, and repeats. The candidate first runs at most three
continuous LPs, each capped at 10 actual solver-process seconds and 30 total.
Only integrality is relaxed; original rows, bounds, fixed commitments, costs
and penalties stay identical. Verified LP points select original security
rows through fresh direct outage factorization. Only the pair set reaches the
integer loop: no LP primal, basis, upper bound or lower bound is carried over.

Each arm has 600 actual solver-process seconds summed across all LP/MIP calls.
The same binary uses two threads, parallel search off, presolve on, seed 0 and
a 1% MIP target. The previously published outer-gap option is enabled in both;
initial-root IPX is disabled. LP discovery uses dual simplex. Source version
is 1.15.1 at base commit `73cac48c5340d775a477087198611862559be250`.

## What the measured work contains

The baseline's first integer master took 11.636905 seconds and found 12 pairs.
Two candidate LPs took 0.654738 and 0.556697 seconds and independently found
the same pair set. The second LP had no new violation. Both pipelines then
solved the identical 12-pair integer master.

| Accounted component, seconds | Integer screening | LP discovery |
|---|---:|---:|
| Model generation and actual API readback | 2.814194 | 4.277140 |
| LP solving | 0 | 1.211435 |
| LP separation | 0 | 3.468331 |
| Integer solving | 36.915915 | 25.647250 |
| Integer/source checks | 4.668430 | 2.463104 |

Full elapsed time also includes orchestration, hashing and durable output.
The common 0.351155-second Python-definition/setup cost is charged in full to
each standalone-equivalent arm. The actual pair elapsed time counts it once.
Solver time includes launch, input reading, presolve, solving, output and
reaping. Generation and checking are separate from its 600-second allocation
and fully counted in E2E. Removing validation time would overstate the gain.
Child CPU/RSS comes from exact-child wait4 accounting; the shared Python
parent's peak RSS is explicitly cumulative across the pair. No time or
resource-limit overshoot was hidden.

## Numerical and implementation validation

All five generated models passed exact actual-library API comparison of every
name, bound, cost, row limit, integrality flag and CSC matrix entry. Matching
LP/MIP models differ only in integrality. The API normalizes some row-bound
negative zeros to positive zero; elementwise numerical bounds are equal, while
the corresponding raw-byte hashes differ. No coefficient was dropped. Every
emitted complete final stage MIP point was checked against its original
integer matrix and the unmodified original source checker. Improving-solution
checkpoint saving was disabled; this is not a claim to check every internal
incumbent visited by HiGHS.

Final U is 3,534,678.7624266683 and the conservatively adjusted master L is
3,499,824.9019100014, giving gap 0.9860545%. Both final points use zero load
shedding and zero overflow. The largest raw emergency excess is about
2.26e-11 MW, below the unchanged 1e-5 checking tolerance. The source feasible
set is contained in every selected-row master, so a valid original-objective
master bound remains a lower bound for the full source model. The primal and
objective are independently checked; the dual bound is reported by HiGHS.
This is a numerical certificate, not an exact rational proof.

The final implementation passed 68 source/synthetic tests and independent
review. A meshed three-bus smoke exercised real cut discovery, five actual
API readbacks, two baseline MIP rounds versus two LPs plus one MIP, and the
known secure objective 660 in both arms.

An earlier real pilot exposed a wrapper compatibility bug: the frozen source
checker returned a finite NumPy scalar of 4.092726157978177e-12 for a tiny
positive base overload, and a built-in-type-only guard rejected it. The fix
normalizes finite real scalar measurements only at the trusted checker-return
boundary; booleans, arrays, complex values and nonfinite values still fail.
Models, tolerances, budgets and solver policy did not change. That incomplete
pilot is retained without a paired claim, and both arms above were rerun fresh.

[Compact records](recorded_results/pg89-cold-lp-screen.json) include per-stage
status, wall/CPU/RSS, input/output/runtime hashes, fidelity and source checks,
all outage IDs, the failed earlier pilot and the exact advancement decision.
This checkpoint publishes measured outcomes; it does not provide a portable
replay harness. The next separate hypothesis concerns near-target sub-MIP heuristic effort
using solver-observable progress and explicit caller identification, with no relaxed optimality tolerance.
