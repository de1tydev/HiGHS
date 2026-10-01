# Initial-root basis reuse: failed mechanism gates

## Decision

The tested basis-acquisition route is closed. It did not establish a usable
large-case warm root, a time-to-target improvement, or stable acceleration.
No numerical guard was weakened. Keep ordinary HiGHS defaults. This checkpoint
publishes negative outcome records; it does not supply a supported root-basis
implementation or a complete replay harness.

## Model and protocol

The case is public PEGASE1354, 2017-02-01, 36 hours, using the same custom soft
base-network UC formulation as earlier results. It has 381,268 rows, 313,776
columns, 28,080 binary variables and 1,232,543 nonzeros. It does not include
N-1 constraints or claim UnitCommitment.jl formulation parity. Source SHA-256
is `2f803d52e34534a3c4dde8a62c8501ad53ea09bc1aee48f263d5a323bc349bc5`;
original MPS SHA-256 is
`b0c7cacfc0219693039e30721541aecadc881b1b6f628add1a993483a1b3b060`.

Every candidate constructs fresh inputs. Acquisition fixes unit commitment to
the source initial state throughout the horizon, with startup/shutdown zero,
and solves that restricted LP. Its checked original-model primal and normalized
basis are supplied to a new original MIP, in primal-then-basis order. Acquisition
bounds are restricted and never exported as global bounds. The possible benefit
belongs to the entire pipeline, including the incumbent, not exclusively the
basis. No previous solution or basis is reused.

The protocol uses seed 0, two threads, parallel search off, a 1% relative gap,
and the same outer-gap option enabled throughout. Initial-root IPX is off.
A 7 GiB process address-space cap applies. Acquisition has a 30-second external
process gate; acquisition plus the first accepted main root has a 90-second
gate. A 600-second aggregate solver-process budget would apply after a
successful mechanism, but no candidate advanced to a matched full comparison.
Process wall includes input/read/write/reaping; full arm elapsed time below
includes generation, exact API input checks, transformations and primal checks.

Both original and restricted models pass canonical v2 full-field equality
against the actual HiGHS API before optimization. Every retained complete
primal is checked against the original source and full original MPS. Each run
retained the same checked incumbent, 24,022,827.279373836, with zero shedding
and zero line overflow. This does not change the model's soft-slack semantics.

## Candidate-only outcomes

| Main-root variant | Acquisition s | Main process s | Sum solver s | Full arm s | Outcome |
|---|---:|---:|---:|---:|---|
| Presolve on, surviving-index mapping | 10.060504 | 11.135688 | 21.196192 | 111.401309 | Reject 2,658 excess mapped basics |
| Main presolve off | 9.419677 | 80.631308 | 90.050985 | 186.417549 | Square basis installed; first warm root unfinished at gate |
| Presolve on, independent subset only | 9.519743 | 15.911962 | 25.431706 | 116.581326 | One additional real missing pivot; hint rejected |
| Presolve on, official logical completion | 9.415075 | 16.731178 | 26.146253 | 116.582512 | Square rank-zero verification and installation pass; first warm LP errors |

There is no control arm, global lower bound, successful time to 1%, or speed
ratio for these gates. The 0.050985-second main-off overrun includes termination
and reaping; it is retained. Failure at a declared gate is not proof that an
approach can never finish with more time.

The presolved model had 242,511 rows and 245,169 mapped basic candidates. The
subset-only factorization reported deficiency 2,659, one beyond the unavoidable
2,658 excess entries. The general completion used the official factor routine's
real missing-row information, selected 242,510 original basics plus one logical
replacement, and verified a fresh square factorization had rank zero. No
factorization algorithm or numerical tolerance was changed.

## What caused the last failure

One separate logging-only reproduction used a fresh acquisition and stopped
immediately after the first inner-LP status. It reproduced the failure after
ordinary scaling and factorization. During the first attempted dual-simplex
iteration, before any completed pivot, HiGHS hit its unchanged excessive-primal
value guard: an updated basic primal value had magnitude at least 1e25. The
printed phase-I infeasibility sum was approximately 3.46e27. The LP returned
`HighsStatus::kError`, model status `Not Set`, invalid basis, and one inversion.
The subsequent iteration-info field was -1 in the cleared error state.

This is direct evidence of numerical failure in the actual simplex path.
Rank-zero verification was insufficient. It does not establish a condition
number, an exact singularity proof, or a deterministic mapping/scaling bug.
The earlier event's generic `numerical` category alone was not a diagnosis.
The observation cost 26.420804 aggregate solver-process seconds; it is not a
performance result. A preceding launch was cancelled during generation to
harden stop-on-missing-telemetry behavior; it ran no optimizer.

## Correctness evidence and limits

The final completion build passed 166/166 CTest entries: 382 unit cases and
1,260,908 assertions, including 40 focused root-basis cases with 1,227
assertions. Related alien-basis/MIP/options coverage passed 68 cases. ASAN/UBSAN
passed 49 focused/alien cases and 1,308 assertions; leak detection was disabled,
so there is no leak-check claim. The fresh four-pair tiny smoke passed 12 solver
calls, 12 actual API readbacks and 44 retained primal checks. These small
correctness tests do not establish useful large-case numerical behavior.

Logging-only reproduction changed only first-root output settings and an
immediate returned-status diagnostic. Its new library recompiled one
translation unit and relinked otherwise frozen objects; source/input hashes,
actual loaded library identities and tiny branch behavior were verified.
Controls/acquisitions kept their original logging. No further full solve,
control, threshold adjustment or performance promotion followed the failure.

[Machine-readable records](recorded_results/root-basis-negative.json) retain
all stage CPU/RSS/wall measurements, source/build/patch hashes and raw evidence
hashes. These timings are bounded diagnostics on a shared cloud machine, not
a multiseed benchmark. The next proposed application-layer route compares
fresh cold security screening against short LP-based cut discovery, with all
preparation and checking charged; no outcome for that route is claimed here.
