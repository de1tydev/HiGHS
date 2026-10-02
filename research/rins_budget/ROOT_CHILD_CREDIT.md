# Default-off root-child credit: development gate failed

Recorded 2026-10-02 UTC. Keep the normal HiGHS defaults. The opt-in child-credit
policy activated correctly on the prescribed PEGASE89 February seed-0 pair, but
the observed reductions were **11.53% in solver-process wall time and 8.67% in
standalone-equivalent end-to-end time**. Both are below the predeclared 20% gate.
The campaign stopped with no held-out runs or post-result retuning. This single
pair does not establish stable or general acceleration.

## Result and scope

Both arms used the same binary, two threads with parallel MIP search off, 1% gap,
presolve on, outer-gap return enabled, initial-root IPX disabled, and the same
cold security-screening policy. The only MIP option difference was
`mip_heuristic_near_target_root_budget = false` versus `true`. Observation logging
was enabled in both. The optimized separator from the separate complete-check
experiment was not used.

The public input was `case89pegase_2017-02-01`, restricted to 36 hours. This is a
custom preventive DC unit-commitment formulation with 89 buses and 210 lines.
Security checks cover all **192 line outages listed by that input**, not all 210
line outages, AC feasibility, or generator contingencies. Original objectives,
penalties, ratings, and tolerances were unchanged.

| Measurement | Credit off | Credit on | Observed reduction |
|---|---:|---:|---:|
| Aggregate LP + MIP solver-process wall, s | 26.086530524 | 23.079722669 | 11.5263% |
| Standalone-equivalent E2E, s | 38.293260040 | 34.971760308 | 8.6738% |
| Independently checked incumbent U | 3,534,678.7624266683 | 3,534,678.7624266683 | Same |
| Adjusted solver-reported master lower bound L | 3,499,824.9019100014 | 3,499,824.9019100014 | Same |
| Numerical relative gap | 0.986054543% | 0.986054543% | Same |
| Load shed, MWh / maximum overflow, MW | 0 / 0 | 0 / 0 | Same |
| Root-child calls / applied caps / skips | 2 / 0 / 0 | 3 / 1 / 0 | One cap activated |

This was one control-then-candidate pair at seed 0 on a shared host. There were
no repeat measurements, order balancing, confidence intervals, or held-out
validation. Host noise and order effects are unquantified. The measured
reduction is an observation, not a promised speedup.

Both arms started from an empty security-pair cache and independently ran two
LP-discovery solves, discovering the same twelve original line/outage pairs,
then a fresh integer master. Only validated pairs carried forward; no primal,
basis, or LP bound was reused. The allocated budget was 600 actual solver-process
seconds per arm, including LP discovery (up to three calls, 10 seconds each and
30 aggregate). Both arms completed within budget. The final source checks
covered 14,721 monitored/outage pairs and 529,956 pair-hours.

The incumbent was independently checked against the matrix and original source
at tolerance 1e-5, including direct outage refactorization. The lower bound is a
HiGHS numerical report from the original integer security master, which is a
relaxation of the complete security model. It is **not an independently proved
dual bound**. The printed token 3499824.90195 was reduced by
0.0000399982490195 before computing the gap. Thus this is a tolerance-based
numerical gap assessment, not an exact rational certificate. The source-cost
recomputation was 3,534,678.7624266716, consistent with U to numerical precision.

The terminal audit checked all six actual API readbacks and raw solver logs,
identical corresponding model bytes, runtime identities, final primal checks,
all listed outages, budgets, CPU/RSS, elapsed-time arithmetic, and child events.
The loaded API normalized 1,296 lower-bound and 9 upper-bound negative zeros to
positive zero in every stage. Row-bound byte hashes therefore differ from the
expected arrays, while every value compares exactly equal; no tolerance was
expanded. The review found no new numerical or resource failure.

## What the credit policy did

The scheduling policy is restricted to direct serial main-root reduced-cost and
root-RENS children. It excludes nested solves, search RINS/RENS, parallel-lock
contexts, and multiple MIP workers. `threads = 2` does not mean two active MIP
search workers here; the actual eligible root context had one worker.

A child that returns an accepted parent-incumbent improvement earns credit equal
to its measured solver interval. Subsequent eligible children may spend that
credit when the parent is above its relative/absolute stopping target and no
more than twice the relative target. Credit is anchored to both authoritative
objective representations and the restart epoch. A restart or changed anchor
clears it. Exhausted credit can skip an eligible child; no skip occurred in this
pilot. Both the policy and its diagnostic option are advanced and default off.
Normal candidate validation, proof handling, and shared termination priority are
preserved. Restricted child bounds never become global lower bounds.

The observed candidate sequence was:

1. An uncapped root reduced-cost child ran 5.149598598 s and returned an accepted
   improvement, earning that much credit
2. Root-RENS entered near a 1.4014% parent gap and received a 5.149598598 s cap.
   It ran 5.165372610 s, retaining a 0.015774012 s cooperative overshoot. Local
   status was time limit (13); shared termination remained unset (0). Its
   candidate was accepted but did not improve the incumbent, leaving zero credit
3. An ordinary parent restart cleared the ledger. Another uncapped root
   reduced-cost child ran 6.914916754 s and produced no accepted improvement

The control root-RENS ran 15.169149637 s without further incumbent improvement.
Its logged proposed cap was observational only; no control limit or scheduling
changed. The candidate saved about ten seconds in that one child, but additional
post-restart work reduced the net benefit. The new child was normal restart work,
not a retry triggered by an infeasibility result.

Cooperative caps may overshoot. Actual child solver intervals debit credit;
parent preparation/import and untimed cleanup are outside that local credit
interval. All such work remains inside parent-process/E2E timing. Nested child
time is not added again to the aggregate process budget.

## Timing and validation

Solver-process wall is measured from each LP/MIP child launch through exact reap.
E2E includes generation, runtime/API validation, LP separation, integer source
checking, and durable arm summaries. Each standalone-equivalent arm is charged
the full common setup interval, 0.286102228 s. These are in-program
standalone-equivalent timings, not two separately cold OS-process measurements.
Arm completion receipts follow the arm endpoints. The retained 72.986938725 s
pair interval includes those receipts but ends before final pair calculations
and pair.json serialization; despite its raw field name, it is not total wall
time including final archival. CPU and peak RSS for children use
per-child wait4 receipts; parent peak RSS is cumulative across the shared pair
process and must not be treated as independent per-arm peak memory.

Before the pilot, the frozen implementation passed 168/168 CTest entries;
352 unit cases with 1,259,988 assertions; 23 focused cases with 1,020 assertions
in both Release and ASAN/UBSAN builds; and 18 C-API old-control/off/observe runs
forming six exact triples. LeakSanitizer was disabled. Independent source/build
review and 85 driver mock tests preceded numerical work. Natural root wiring and
prepared-parent timeout/acceptance tests are separate evidence, not application
speedup measurements. The two-hour triangle integration passed six API readbacks
and both objective-660 completions, but had no root-child activation.

The final independent audit passed retained-result integrity and confirmed
**STOP / NO ADVANCE** under the 20%-on-both gate. It verified retained artifacts
and arithmetic without another solve. Source replay and validation summaries are
in [root-child-credit-validation.json](recorded_results/root-child-credit-validation.json).
Full-precision measurements, exact retained-raw hashes, source provenance, and
terminal review metadata are in
[root-child-credit-feb-seed0.json](recorded_results/root-child-credit-feb-seed0.json).

## Source replay and the limit of this publication

This publication supplies the source patch and matched options. It does **not**
supply a portable reproduction of the measured cold-screen E2E driver: that
harness contains fixed local source/runtime pins and is not published here.
Retained raw artifact hashes establish identity, but the compact projection is
not a complete raw-data archive. Do not describe these files as an independently
runnable reproduction of the reported E2E result.

The patch chain below was independently applied to a fresh archive of official
commit `73cac48c5340d775a477087198611862559be250`; all 983 frozen source files
matched exactly with no extra files; see the
[source replay check](recorded_results/root-child-credit-source-replay.json).
The recipe was checked without a rebuild or
solve during publication preparation. Existing public dependency patches are
required in this order:

1. `outer-gap-heuristic.patch`
2. `initial-root-ipx.patch`
3. `root-child-credit.patch` (SHA-256
   `03041fda1e20fcf0a3fcae6489c7cbb1a8d03769377567ab7ac2ae64fa3ad9c1`)

Set PACKAGE to this research-package directory and WORK to a new working
directory. Apply patches to a fresh pinned source checkout, never to the existing
research branch's official source files:

```sh
set -eu
: "${PACKAGE:?Set PACKAGE to the research-package directory}"
: "${WORK:?Set WORK to the replay working directory}"
PACKAGE=$(cd "$PACKAGE" && pwd)
mkdir -p "$WORK"
WORK=$(cd "$WORK" && pwd)
for OUTPUT in "$WORK/root-credit" "$WORK/build-root-credit"; do
  if [ -e "$OUTPUT" ] || [ -L "$OUTPUT" ]; then
    printf 'Refusing to reuse existing output: %s\n' "$OUTPUT" >&2
    exit 1
  fi
done
PIN=73cac48c5340d775a477087198611862559be250
git clone https://github.com/de1tydev/HiGHS.git "$WORK/root-credit"
git -C "$WORK/root-credit" checkout --detach "$PIN"
for PATCH in outer-gap-heuristic initial-root-ipx root-child-credit; do
  git -C "$WORK/root-credit" apply --check "$PACKAGE/$PATCH.patch" || exit 1
  git -C "$WORK/root-credit" apply "$PACKAGE/$PATCH.patch" || exit 1
done
cmake -S "$WORK/root-credit" -B "$WORK/build-root-credit" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DFAST_BUILD=ON -DBUILD_SHARED_LIBS=ON \
  -DBUILD_TESTING=ON -DALL_TESTS=ON -DHIPO=OFF
cmake --build "$WORK/build-root-credit" --parallel 4
ctest --test-dir "$WORK/build-root-credit" --output-on-failure --parallel 1
```

The measured build used GCC 14.2.0. New builds will have their own binary and
library hashes; the JSON records the measured runtime identities for provenance.
For a new **direct-MPS kernel experiment**, use the same new binary and identical
MPS bytes in both arms, the matched `options/root-child-credit-off.options` and
`options/root-child-credit-on.options`, seed 0, unique solution/log destinations,
and explicit identical time limits. Record loaded library identities, statuses,
exit codes, watchdog outcomes, and all overshoot. The common discovery options
are retained as `options/root-child-credit-lp.options` for reference only.

Direct-MPS runs omit cold discovery, model generation, actual-API validation,
separation, original-source checks, and archival costs. They cannot reproduce or
validate the reported standalone-equivalent E2E times or the original-source
numerical gap on their own. No instructions here change official solver defaults.
