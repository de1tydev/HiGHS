# Seed revision addendum

The seed-v3 release gate uses only the existing transition suite with `--seed 1`.
The optional transition-test seed defaults to 0 and accepts only 0 or 1. The
legacy changed-master suite accepts only its existing seed 0 and has no new
scientific component or call. It is not part of this release execution gate.
All original timing, fixture, exact map/value, binary and known-overflow checks
are retained. No seed-v3 tiny has been executed during source implementation.

The historical description below belongs to the base release; current resource
gates are unchanged from resource v2 and are authoritative in PROTOCOL.json.

# Fixed tiny replay: execution coverage

These are test-only runners. The production `current_scuc run` interface still
requires the supported 36-hour PEGASE1354 family. No tiny flag or production
family bypass was added. `test_fixed_triangle.py` checks the production horizon
rejection without constructing a model.

The data come from the existing three-bus/two-hour `fixture()` definition in
`network-projection-full-runner-v1/tiny_integration.py`. The only fixture delta
is the already-declared `[0.]` to `[1.]` startup costs from the existing integer
tiny suites. Both runners retain exactly this same fixed data; neither searches
for a fixture or tunes limits, solver options, mathematical thresholds, or cuts.

The candidate must retain its known nonpass: zero load shedding and reserve
shortfall, but 2.25 MWh shared overflow. A successful test is reported as
`test_passed=true`, `candidate_passed=false`, with
`production_advancement_qualified=false`. It is not a production success or a
performance/comparator claim.

## Commands, after execution authorization

From the package root, using the pinned interpreter with NumPy 2.3.5, SciPy
1.17.0, and threadpoolctl 3.6.0:

```sh
python -B -s -m tests.run_tiny_components --suite changed-master --highs /absolute/path/to/highs --runtime-manifest /absolute/path/to/runtime-manifest.json --workdir /absolute/fresh/tiny-changed-master
python -B -s -m tests.run_tiny_components --suite transition --highs /absolute/path/to/highs --runtime-manifest /absolute/path/to/runtime-manifest.json --workdir /absolute/fresh/tiny-transition
```

Each work directory must be fresh, outside the installed package, and on a
reviewed 4 KiB allocation filesystem. Run the commands sequentially, only after
the currently active numerical slot is released. The native runtime manifest
must qualify the official source build, matching library/extras/helper, build
evidence, guarded source files and installed dependencies.

The changed-master runner ports
`heldout-projected-binding-v2/tiny.py`. It retains the existing adaptive
iteration, and the existing separately labelled changed-master carry/proof
component when the candidate naturally stops after one call. That component
cannot supply candidate endpoints. It checks exact mapping, `.17g` start
roundtrip, standalone native assessment, actual CLI start acceptance, explicit
tiny full-integer parity, and both physical checkers.

The transition runner ports `discovery-proof-transition-tiny-v1/tiny.py` and
its existing quality assertions. It requires exactly two seed LPs, a cold
discovery reaching SolutionLimit, the existing unchanged-master transition,
one carry preparation and proof MIP, and one tiny full-reference MIP. It
revalidates the checked discovery point, source options and exact prefix,
consumes the transition once, and checks proof start admission. If the fixed
fixture does not exhibit that predefined transition, the test fails. It does
not substitute another fixture or alter the schedule.

## Resource envelope per command

- Outer contained worker allocation: 180 seconds, watchdog at 179 seconds,
  with the measured endpoint after exact wait4 reap and any adopted cleanup
- Existing worker deadline: 170 seconds from worker entry; existing individual
  MIP slots: 80 seconds process and 20 seconds native; carry: at most 30 seconds
- Exactly two seed LPs, 60 seconds cumulative native seed time, and existing
  exact-certificate attempt caps; no additional seed solve
- Address space: 7 GiB; sampled owned-process-tree RSS: 6 GiB; required sampled
  memory and disk headroom: 2 GiB each
- Python output file limit: 512 MiB; native output file limit: 64 MiB; core dumps
  disabled inside native scopes
- Conservative whole-storage launch admission: 26,974,885,888 available bytes
  (25.122 GiB), including the inherited 2 GiB free floor and launch margin
- One-thread numerical BLAS, HiGHS two threads with parallel off, the existing
  discovery/proof typed options, and single numerical lock
- No deletion or archival; retain all artifacts and receipts until review

The parent launcher also records complete elapsed time, including static
runtime/config verification outside the 180-second worker slot. Each test
creates fresh source, matrix, factors, points and receipts; no historical
numeric output is input. It records the exact test sources, runtime mappings,
loaded Python/native identities, process measurements and final result hash.

## Required review evidence

Inspect `TEST-RESULT.json`, `tiny-worker-process.json`, `run/result.json`, native
limit and assessment receipts, proof start-admission evidence, exact arithmetic
checks, independent physical checks and loaded-runtime records. The wrapper
must report both `test_passed=true` and `candidate_passed=false`.

For portability, repeat both commands from a second unrelated directory
containing only this package, the pinned dependencies, a verified official
native installation and these synthetic test sources. Use two new work
directories. Preserve the source hashes and confirm no recovered checkout,
old prepared case, remote Library identity, warm start or prior cached factor
appears among inputs or loaded paths. This repeat is a separate explicitly
scheduled numerical window, not something these launchers perform silently.

Execution on 2026-10-06: the changed-master harness stopped before carry on
its existing exhausted-support assertion; that coverage failed and was not
retried. The separately prescribed transition suite passed from a second
byte-identical package directory, including actual native assessment and proof
admission. The candidate correctly remained a nonpass with 2.25 MWh overflow.
See ../VALIDATION.md for exact limits. No production-size run or timing comparison
was performed.
