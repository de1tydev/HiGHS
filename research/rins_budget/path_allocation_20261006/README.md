# Path-allocation probe: negative v1 result

**The prespecified materiality gate failed on both development models. The v1
route is closed; no workspace reuse was implemented.** The fixed campaign
completed all six calls on a newly rebuilt own-cloud HiGHS baseline.

| Model | Eligible attempts A | Setup + destruction S (s) | Path body P (s) | Clock proxy O (s) | S/P | Failed screens |
|---|---:|---:|---:|---:|---:|---|
| dcmulti | 45,418 | 0.015508886 | 1.118601341 | 0.0023781913125 | 1.386453% | S < 10O; S/P < 5% |
| gesa2 | 5,368 | 0.001968013 | 0.156819036 | 0.0002492666250 | 1.254958% | S < 5 ms; S < 10O; S/P < 5% |

The gate required both models to pass A ≥ 32, S ≥ 5 ms, S ≥ 10O, and S/P ≥ 5%,
plus all process, primal, reference, and accounting checks. Setup/destruction
was a small measured portion of path work, and neither model cleared the
clock-signal screen. This supports the fixed stop decision, not further tuning.

S times only the initial seven-vector setup and normal-scope destruction,
including necessary initialization, ordinary vector work, and observer effects.
Growth of tmpUpper/tmpSolval during transformation is counted but is not
separately timed. Consequently, these approximately 1.3% shares are **not a
rigorous upper bound on every possible reuse benefit**. O is an empty-clock-pair
proxy, not total instrumentation overhead. Capacity-growth observations infer
vector requests, not malloc calls or live/peak memory. The experiment makes no
speed-ratio, statistical-reliability, allocation-dominance, optimization-promotion,
or SCUC-transfer claim. No retiming, reuse implementation, or expanded panel
follows under v1.

## What completed

Four fresh qualification calls (official/candidate, log_dev_level=0), followed
by two candidate observers (log_dev_level=2), used seed 1 and the frozen options.
All process, original-matrix primal/objective, reference status/bounds/gap,
node/LP-count, point-byte, and diagnostic-accounting checks passed. Status
`Optimal` is tolerance-based; the primal checker is not an independent dual
certificate, and output parity is not cut-by-cut identity.

The six solver process slots totalled 10.370310491 s; the entire enclosing
campaign took 10.772822216 s. These nested times must not be added. All six
outcomes, process error fields, numerical checks, failed materiality screens,
main/sub-MIP/depth reductions, fixed limits, and raw artifact bindings are in
[RESULTS.json](RESULTS.json) and [FIELD_MAP.json](FIELD_MAP.json).

The independent terminal audit passed 3,573 checks over 2,121 distinct hashed
files. It independently reduced raw diagnostics and replayed the frozen text
parser. It checked retained primal reports for artifact concordance and
tolerances without rerunning the scientific checker. See [AUDIT.json](AUDIT.json).

## Frozen identity and setup context

The official and candidate base is HiGHS
`d547a3ad8af5399651187fb0e133cf0e42615b82`. Only the two observer source files
differ in the candidate. The source manifest is
`7031f650b51a4eb4fbf042b87022694067466e0d221dd9335eb35b7eb7f9466a`;
the combined patch is
`ebf898a0f1b18e956121eedd325352350f57af3e067bde42545b504e1b7151c2`.
[PROVENANCE.json](PROVENANCE.json) binds source trees, code, models, binaries,
libraries, build configuration, dependencies, and verified private raw capsules.
No prior saved-cloud timing was reused. Unpublished commit
`0f17aaa0f48b8b0d461c2684326cfbb3c6e5f474` was not recovered or reused. The two
earlier CMIR cache versions remain rejected and were not rerun.

Build/setup costs are separate: initial official build 172.583999272 s,
metadata-width rebuild 186.848240646 s, observer build 177.793555182 s. The
metadata correction changed the abbreviated commit identifier from seven to
ten characters without changing source code; its failed first helper build is
retained. These costs are not benchmark improvements.

Restoration validation was 1 import-only test plus 89 guarded pure methods
(2 initially skipped), then 2 runtime-fixture completions. The initial
wrong-working-directory import failure remains recorded. The restored fixed
tiny test took 13.957982890 s enclosing time: component PASS with the expected
2.25 MWh shared-overflow quality NONPASS. Separately, 13 synthetic observer
parser/status/parity fixtures passed before launch. [SETUP.json](SETUP.json)
preserves these distinctions and receipts.

## Reproduction

The 14 files in [frozen-source](frozen-source/) are byte-identical to the
prelaunch source-manifest entries, including the actual observer patches,
six-slot runner, strict parser, tests, and original gate/addendum. Its README
describes the historical source-only stage; this README records the terminal
result. The public JSON files are explicitly mapped projections, not native raw
receipts. Raw logs, datasets, matrices, point files, and binaries are not included.

Use Linux, Python 3.12, and separate caller-supplied official/candidate sources
at the commit above. Apply `frozen-source/combined-diagnostic.patch` once to
the candidate copy only. Configure both builds with the arguments recorded in
SETUP.json (GCC 14.2.0, Release, HIGHSINT64=OFF, HIPO=OFF), using `git config
core.abbrev 10` before configuring. Finish all builds before numerical work.
Supply the published research checkout at
`2d8e65ca069f90b75c4ae38a6115b5ac7c40132c`; its required files are hash-bound
in PROVENANCE.json. Build its `cmir_cache_20261006/export_model.cpp` against
the official library only. The standard exporter command is:

```sh
g++ -std=c++17 -O2 -I"$OFFICIAL_SOURCE/highs" -I"$OFFICIAL_BUILD" \
  "$RESEARCH_ROOT/export_model.cpp" -L"$OFFICIAL_BUILD/lib" -lhighs \
  -Wl,-rpath,"$OFFICIAL_BUILD/lib" -o "$EXPORTER"
```

Then run the explicit replay command below with a new output directory. The
wrapper checks frozen source/dependency identities and preserves the 600-second
enclosing guard. It launches only the fixed runner; it does not build or retry.
`RESEARCH_ROOT` is the published `research/rins_budget/cmir_cache_20261006`
directory, with its `current_scuc` sibling intact. Caller builds must correspond
to the supplied sources; recorded binary hashes are provenance, not a promise
that other environments produce identical machine code or timings.

```sh
python3 -B reproduce.py \
  --official-source "$OFFICIAL_SOURCE" --candidate-source "$CANDIDATE_SOURCE" \
  --official-build "$OFFICIAL_BUILD" --candidate-build "$CANDIDATE_BUILD" \
  --research-root "$RESEARCH_ROOT" --exporter "$EXPORTER" --out "$NEW_OUTPUT"
```

The replay command executes up to six optimization calls and is not a request
to reopen this completed route. Pure fixture checks, if separately desired,
are `python3 -B -m unittest -v test_parse_probe test_run_probe` from
`frozen-source`. No builds, tests, solvers, or scientific checker were run while
preparing this public projection. See [notices](THIRD_PARTY_NOTICES.md).
