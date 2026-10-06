# Checked-history interface v1

The fixed generic-MILP qualification passed: **15 pure test methods and all six
functional arms**, with eight actual optimizer calls and two deliberate failure
helpers. Every arm returned independently checked objective 13. The complete
functional invocation took **9.760229961 s**. A separate data-only admission
recovered **9,360 exact commitment labels from one genuine June window**.
See [RESULTS.md](RESULTS.md) for measured outcomes, provenance and limitations.

## Interface

- `june_label.py` validates the recovered endpoint through 30 fixed member pins,
  three independently supplied archive anchors, and source/point/checker receipt
  links. It reuses audited physical evidence without rerunning physics or
  executing archived code. No caller `checked` flag or label-supplied trust
  anchor can admit a label
- `history.py` validates synthetic labels against their bound original model
  and point, then wraps the existing retrieval rule. Admission digests detect
  later record mutation. UTC-normalized windows count once across seed
  replicas; future, overlapping, incompatible and late labels are excluded.
  Three-neighbor unanimity abstains when fewer than three windows qualify
- `driver.py` gives the sparse-start probe its own process cap, checks a complete
  returned point against the original matrix, and starts a fresh ordinary
  original-model process with that point or no start. Fallback uses the same
  remaining ledger. Integrity, resource, cancellation and cleanup failures
  stop. The solve CLI currently accepts only small synthetic fixtures
- `sparse_probe.cpp` uses public HiGHS APIs. Native completion can temporarily
  fix internal bounds; all sixteen external model fields are checked before
  and after each run, and the final process reloads the original model. No
  probe upper/lower bound, basis, cut or search state is transferred

## Replay and scope

Build the small C++17 adapter against the pinned existing HiGHS headers,
generated build headers and shared library, with `-ldl` and a 60 s external
limit. Then run `run_functional.py --adapter PATH --library PATH --out FRESH`
under a 360 s external owner. Each of the six arms has a 30 s ceiling; a probe
has a 5 s process allocation, and the final process uses the remaining arm
allowance with 5 s reserved for final checking. Failure hooks are confined to
the test harness. Outer receipts include startup, writes and exact reaping.

A concrete Linux invocation from this directory is below. `HIGHS_SRC` and
`HIGHS_BUILD` point to the same pristine commit and build described in the
[current package instructions](../current_scuc/README.md); use that package's
Python dependencies. `OUT` must be a fresh existing parent directory. These
wrappers set the documented process limits and record exact reaping.

```sh
set -eu
: "${HIGHS_SRC:?Set the pristine source directory}"
: "${HIGHS_BUILD:?Set its existing shared-library build directory}"
: "${OUT:?Set a fresh existing output parent directory}"
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python3 -B ../generalization_20261006/bounded.py --out "$OUT/build-owner" --seconds 60 -- \
  g++ -std=c++17 -O2 -I"$HIGHS_SRC/highs" -I"$HIGHS_BUILD" sparse_probe.cpp \
  -L"$HIGHS_BUILD/lib" -lhighs -ldl -Wl,-rpath,"$HIGHS_BUILD/lib" -o "$OUT/sparse_probe"
python3 -B ../generalization_20261006/bounded.py --out "$OUT/functional-owner" --seconds 360 -- \
  python3 -B -s run_functional.py --adapter "$OUT/sparse_probe" \
  --library "$HIGHS_BUILD/lib/libhighs.so.1.15.1" --out "$OUT/functional"
```

For the separately bounded data-only replay, use
`june_label.py --recovery-root PATH --out FRESH_JSON` under a 60 s owner. The
observed label-availability timestamp is in October 2026, not June 2017. One
window cannot form a three-neighbor consensus or train January/April 2017.
The frozen `current_scuc` and solver kernel are unchanged. This is functional
interface evidence, with no large-SCUC solve, generalization or speed claim.
