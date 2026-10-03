# CMIR integer-complement research checkpoint

As of 3 October 2026, the default-off shortcut passes the recorded source, guard, rational-identity, and integration checks. A fixed logged experiment demonstrates that it can remove redundant complement trials on two exposed MIPLIB cases. This checkpoint does **not** establish a stable general speedup, corrected full-SCUC 1% success, or an independent dual-bound proof.

## Source and baseline

The exact [patch](cmir-integer-complement.patch) applies to the custom corrected reference described in the [existing corrected source recipe](../portable_early_integer_corrected_replay_v1/README.md#reconstruct-and-build-the-corrected-source): official HiGHS `73cac48c5340d775a477087198611862559be250`, the existing `outer-gap-heuristic`, `initial-root-ipx`, and `root-child-credit` patches, then official [#3179](https://github.com/ERGO-Code/HiGHS/pull/3179) (`28339ce4b57bf8858036cbb36f4fc66d97fedd06`) and [#3181](https://github.com/ERGO-Code/HiGHS/pull/3181) (`ae53450f395cf0a278858868b64813ea99bb4767`) backports. It includes no separator/phase profiling overlay. The three existing experimental options remain default-off. This is a custom combined-corrected reference, not pristine upstream-default HiGHS.

The two added options, `mip_modk_skip_integer_complements` and `mip_modk_integer_complement_log`, are also false by default. The shortcut is restricted to the initial CMIR scale and exact finite integral/power-of-two guards, including reversible scaling and a conservative `2^52` magnitude/product bound. It changes no feasibility or integrality tolerance. Complementing an integral normalized coefficient across an integral upper bound preserves the MIR row in exact rational arithmetic after substitution. That identity does not promise identical floating-point efficacy decisions, cuts, or search when skipping is enabled. The ordinary final cut-generation and proof paths remain in place.

The patch SHA-256 is `abb786e47f9069897ed89e5bbcf3771745301800a4ccf00849ee4cf7e7497720`. [PROVENANCE.json](PROVENANCE.json) identifies the source lineage, archived evidence digests, observed runtime hashes, and original input hashes. The small JSON files here are explicit projections of retained records, not complete raw manifests or self-contained certificates.

## Completed evidence

- [Source validation](evidence/source-validation.json): 159 focused assertions in 3 cases; 90,318 exact-rational cases; all 168 configured CTest tests, comprising 356 cases and 1,260,159 assertions. The fixed `rgn` default-off comparison preserved solution bytes and recorded result fields. Both `binkar10_1` logged arms passed original-MPS primal checks and numerical 1% endpoints, but produced zero complement summaries and zero observed skips. This remains inactive integration coverage. Exclusion of the non-initial-scale path was verified in source, not dynamically covered.
- [Logged mechanism](evidence/logged-mechanism.json): four fresh same-binary arms at seed 17, in the fixed order air04 OFF then ON, neos-950242 ON then OFF. All four original-MPS GMP-based primal checks and numerical 1% endpoints passed. The GMP checker used rational arithmetic with its recorded `1e-6` linear, integrality, and objective tolerances. Solution bytes, nodes, and simplex iterations matched within each pair. These checks validate primals; the lower bounds remain solver-reported numerical evidence.

| Logged local-loop observation | air04 OFF | air04 ON | neos OFF | neos ON |
|---|---:|---:|---:|---:|
| Skipped complement trials | 0 | 612,021 | 0 | 1,501 |
| Evaluated integer-row terms | 749,113,704 | 0 | 242,473 | 1,013 |
| Measured loop seconds | 3.143686540 | 0.017490755 | 0.001466991 | 0.000049347 |

The timer covers only the local complement trial loop and excludes diagnostic line printing. Logging can perturb timing and stopping. Neos' measured loop cost was negligible. These observations establish the mechanism on the fixed exposed cases; they provide no clean solve-time ratio, general stable-speed claim, reversal of the earlier failed mixed-panel gate, or release of holdout testing.

## Corrected 1354-bus bridge and saved-point recovery

The [bridge projection](evidence/corrected-1354-bridge.json) covers one corrected-runtime OFF-plus-logging profile of the retained June 1, 2017, 36-hour 1354-bus integer master. It has 381,412 rows, 313,776 columns, and 28,080 binaries. Two security pairs learned during historical discovery are already present. Its conditional profile excludes historical discovery and model-generation costs; it is not a cold-SCUC run. No historical incumbent or bound was carried into this solve.

The solver process took 606.499050 seconds against a 600-second budget, an overshoot of 6.499050 seconds. Rounded log counters attribute 479.73 seconds to main-MIP solve work and 111.28 seconds to child-MIP solve work, plus 3.86 seconds of child presolve. The raw printed master endpoint was primal `13872855.3705`, lower bound `13616258.4018`, and gap `1.85% (tolerance: 1%)`. The printed values are rounded and are not an independent bound certificate.

The original invocation failed before its checker read the saved point: it attempted a 4 GiB file-size limit against an inherited 1 GiB hard limit. That failed, late invocation remains unchanged. A separately reviewed checker-only recovery completed in 165.168865 seconds, without rerunning the solve or relaxing limits, and verified the identical saved solution bytes.

At the existing floating-point checker's `1e-5` tolerance, that point passes the retained master checks but **fails full-source security**: 2 omitted pairs / 4 line-hours violate emergency limits, with a maximum residual overload of 3.660719979 MW after shared slack, across 1,288 listed outages and 66,360,168 checked pair-hours. Reported shedding is `2e-13` MWh and shared overflow is zero. No full-source feasible upper bound or full-SCUC 1% success follows.

There are zero visible CMIR summaries. Child MIPs suppress output with `output_flag=false`, and early CMIR returns precede the marker. Therefore this observation cannot establish zero child work, zero callbacks, or shortcut applicability to this corrected case. Earlier hourly trials preceded the official corrections and are not corrected-runtime evidence. The [historical correctness advisory](../CORRECTNESS_ADVISORY.md) continues to apply.

## Apply, build, and test pointers

Use the existing corrected recipe's requirements and source reconstruction steps, including all three research patches and both complete correctness backports in their specified order. First verify its 984-file source inventory. The local corrected reference was rechecked against all 984 inventory entries for this checkpoint, and the exact CMIR patch passed `git apply --check` against it.

Set `CHECKPOINT` to this directory, `SOURCE` to a fresh reconstructed corrected source, `BUILD` to a fresh disjoint build directory, and `PYTHON` to a provisioned Python 3 interpreter. Use absolute paths. From this directory, verify `sha256sum -c SHA256SUMS`. Then apply the additive patch before configuring the candidate:

```sh
set -eu
test ! -e "$BUILD" || exit 1
git -C "$SOURCE" apply --check "$CHECKPOINT/cmir-integer-complement.patch"
git -C "$SOURCE" apply "$CHECKPOINT/cmir-integer-complement.patch"
cmake -S "$SOURCE" -B "$BUILD" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DFAST_BUILD=ON -DBUILD_SHARED_LIBS=ON \
  -DBUILD_TESTING=ON -DALL_TESTS=ON -DHIPO=OFF -DHIGHSINT64=OFF
cmake --build "$BUILD" --parallel 2
"$BUILD/bin/unit_tests" '[cmir_integer_complement]' --success
ctest --test-dir "$BUILD" --output-on-failure --parallel 1
"$PYTHON" -I -S -B "$CHECKPOINT/check_rational_identity.py"
```

The focused C++ tests are part of the exact patch; the rational script is copied unchanged from the validated artifact. The candidate has 986 source inventory files after applying the patch. The strict existing replay preparation pins the 984-file corrected baseline; do not treat it as an already adapted CMIR runner. This checkpoint includes source/test pointers, not a new portable experiment harness. No native build, test, checker, model-generation, or solve was run while assembling it. The reported native results are the earlier completed records; no fresh-consumer rebuild or broader portability claim is made.

## Licenses and omitted payloads

The HiGHS source is MIT-licensed; its unchanged [license](LICENSE.txt) is retained. No MIPLIB model bytes, generated models, saved solutions, binaries, raw private manifests, machine paths, or credentials are included. The three official MIPLIB pages carry ZIB copyright; no separate redistribution permission for those instance payloads was established. Use the official page/download URLs and hashes in `PROVENANCE.json`. air04 is attributed to G. Astfalk, binkar10_1 to H. Mittelmann, and neos-950242 to a NEOS Server submission.

The 1354-bus source comes from the [UnitCommitment.jl 0.3 catalogue](https://axavier.org/UnitCommitment.jl/0.3/instances/) and derives from [MATPOWER case1354pegase](https://github.com/MATPOWER/matpower/blob/7.1/data/case1354pegase.m), whose data notice is [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). See the repository's [source and attribution record](../scuc/README.md#primary-sources-and-attribution--license). Code licensing does not replace dataset attribution or grant instance-data redistribution rights.
