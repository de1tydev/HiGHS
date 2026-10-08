# Replay index and preserved limitations

## Compact public packet

This directory publishes the exact default-OFF patch, corrected C++ fixtures,
all four measured samples and a standard-library offline Decimal checker.
It intentionally omits solver binaries, large raw logs and the full MPS/solution
bundle. Their immutable identities and retained capsule names are below.
The public packet alone is **not a self-contained solver replay**.

`replay_audit.py EVIDENCE_ROOT --output NEW_REPORT.json` accepts the extracted
pilot capsule. It reads `frozen-inputs/master.mps`, the corresponding expected
model JSON, and all four `run-XX` directories. It checks exact artifact hashes,
parses the original MPS independently, recomputes every primal/objective with
Decimal, verifies retained process receipts and reproduces both fixed ratios.
It launches no solver, loads no solver library and uses no network. The optional
output must be a new file. Run with ordinary Python 3, without `-O`.

This offline check cannot recreate historical process scheduling or host load.
Original runtime/source/loader verification is preserved in the full audit.
The checker validates the recorded evidence; it does not confer a new bound
certificate or full-SCUC feasibility claim.

## Retained capsules

The study owner retains these archives separately. Filenames and SHA-256 hashes
identify them without embedding private storage links or access mechanisms:

| Capsule | SHA-256 | Contents |
|---|---|---|
| highs-child-center-qualified-terminal-20261007T2359.tar.gz | 382a37db4fbee3cd37c6b0ed0b7251332e9600d47d4cda78025e7713249aa75a | Full qualified source, assertion/Release binaries, corrected and failed fixtures, all native test logs, source/terminal reviews and frozen pilot proposal |
| highs-child-center-pilot-prelaunch-final-20261008T0009.tar.gz | 8f5969847b9ad9eeed8d06485f5e65d2e31345958584e4b4c238a1dd727be1d7 | Frozen input/runtime copies, complete native option readbacks, exact model fidelity check and final launch/checker sources |
| highs-child-center-pilot-no-go-terminal-20261008T0020.tar.gz | 2a0a90cfe2bc6b13a6542aba43ae90b34bfb7df8842c118ece3c809882a4c598 | All four logs/solutions/measurements, independent Decimal audit, prelaunch evidence, negative result and frozen runtime/input copies |

All three archives were returned and hash-verified. Qualification archive
membership was checked for all 2,951 members; pilot terminal membership for
all 78 members. No public download availability is asserted here. Access to the
retained capsule is necessary for full offline replay; there is no guessed URL
or substitute model.

## Exact patch target and historical build settings

Start with official HiGHS commit
`d547a3ad8af5399651187fb0e133cf0e42615b82`, apply the adjacent
[isolated minimal correctness patch](../correctness_3357_3367_20261007/combined-minimal-correctness.patch),
then this directory's `child-center-omission.patch`.
Do not assume the active research branch solver files equal that official base.
The patch is an artifact only; this publication does not edit the active solver
core. Both added options remain false by default.

Historical builds used GCC/G++ 14.2.0, Ninja, two compile jobs, shared library,
BUILD_SHARED_EXTRAS_LIB=ON, BUILD_TESTING=ON, ALL_TESTS=ON, FAST_BUILD=ON,
HIGHSINT64=OFF, DEBUGSOL=OFF, HIPO=OFF, CUPDLP_GPU=OFF, HIPDLP_HIP=OFF and
ZLIB=ON. Assertions-enabled solver flags were `-O1 -g1`, without NDEBUG;
Release was `-O3 -DNDEBUG` with `-flto=2` linker flags. Full compile commands and
configuration hashes are in the qualification capsule. Native tests kept their
original thread settings; custom fixtures and pilot explicitly used two threads.

The corrected `fixtures/*.cpp` are source-level qualification support:

- `ac_fixture.cpp`: 12-binary exact-enumeration knapsack, main/direct-child
  activation matrix, min/max offsets, odd-cycle infeasibility, unboundedness and
  zero-node/time limit paths. Depth 3 is direct construction, not organic nesting.
- `native_ac_fixture.cpp`: native `check/instances/flugpl.mps`, fresh internal
  solver objects, presolve off/on, completed main and child center handling.
- `transformed_ac_fixture.cpp`: public Highs min/max offset and clearSolver/rerun
  paths, with genuine internally created children and original-matrix checks.

Candidate fixture compilation defines `ABLATION_OPTIONS`; reference compilation
omits it and uses the matching qualified reference headers/DSO. Fixtures retain
C++ assertions even when linked to the Release solver. HighsOptions layout
changes make cross-ABI header/executable/library mixing invalid. These files do
not authorize additional performance calls or restore the rejected route.

## Failed attempts remain part of the evidence

1. The first assertion build began before durable upload completion and overlapped
   two source-review refinements. A subsequent final-source dependency rebuild
   completed before any numerical fixture used the candidate. Intermediate and
   final build identities remain separate.
2. Initial custom matrix construction appended to the default start vector and
   omitted matrix dimensions. It produced 32 candidate aborts and six exits 0;
   all six matched reference checks aborted. An inconsistent-bound infeasible
   fixture also returned a warning instead of the expected clean passModel result.
   These are harness failures, not successful qualification runs. The corrected
   fixture set dimensions/starts properly and used a valid odd-cycle model.
3. The first native harness reused a single-use internal HighsMipSolver after
   injecting stale center state. Second calls produced bad_alloc in six of eight
   candidate and three of four reference processes; first calls passed. Corrected
   tests use fresh internal objects. No successful injected-stale-state test is
   claimed. Public clearSolver/rerun is separately covered.
4. Two early-exit reference child centers reported SolveError while corresponding
   candidate centers reported Optimal, with computed=false in both, unchanged
   objective/bound and no center consumption. The auxiliary-status cause was not
   established; numerical default-OFF parity does not mean exact internal-state
   parity.
5. Release CTest remains 168/169 passed with AffinityReducedCoreCount failing
   5==1. Own-compatible reference/candidate controls reproduce it. The fresh
   affinity-excluded aggregate is additional evidence, not replacement of the
   failure. No automatic-thread/affinity qualification follows.
6. An unused prelaunch checker had a whitespace typo in the native child-complete
   log pattern. It was fixed and re-frozen before any of the four calls, with the
   original prepared checker/manifest retained. No numerical retry occurred.

Full initial source/binaries, raw failed logs and receipts remain in the named
capsules. None was silently overwritten or reclassified as passing.

## Coverage boundaries and study closure

No dynamic internal restart, active-AC terminator/nonzero-timeout interruption,
successful deliberate stale-state injection or organically nested depth>1
fixture is established. Lifecycle safety is source-reviewed; serial children
are excluded from the existing ordinary root/tree restart predicates. Parallel
exclusion was tested in direct children, not an observed concurrent parent tree.

The four performance calls themselves did show deeper real child-root events,
but they are one exposed input/seed and not an exhaustive lifecycle test. All
outcomes, caps and samples remain fixed in RESULTS.json. No retuning, extra
seed, fresh input, larger SCUC solve or follow-on benchmark was run after NO-GO.
