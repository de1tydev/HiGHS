# Corrected early-integer PG89 replay

This kit reconstructs the separately validated corrected replay alongside the preserved historical package. It uses the same early-integer method, source model, common options, checks and resource limits, with the official #3179 and #3181 correctness backports. It makes no new performance claim. Read the [historical correctness advisory](../CORRECTNESS_ADVISORY.md): corrected runs do not relabel or repair archived results.

The kit is an additive overlay. Its manifest identifies an exact 49-file replay package with all 33 historical payload files unchanged. The external instructions here are the corrected source recipe. The reconstructed package retains its original README, compatibility record and proposal-status metadata as creation-time evidence; their older 983-file/pending descriptions are not the current recipe or an approval requirement.

## Requirements and validation scope

Use Linux/glibc with the existing ELF loader and process primitives, Git, CMake, Ninja, a C++ compiler, and an already provisioned clean Python interpreter without `.pth`, `sitecustomize` or `usercustomize` startup hooks. The exercised stack is Python 3.12.14, NumPy 2.3.5 and SciPy 1.17.0. This kit installs no dependencies and makes no broader platform or fresh-installer compatibility claim.

The corrected source/build, runtime binding/preflight and tiny replay were validated locally. The historical local export and four-overlay assembly below were executed in fresh directories and matched the exact 49-file package and all 33 payloads. Source reconstruction from the already local official base object plus the five patches matched all 984 inventory files. Network clone/download, dependency installation, a fresh rebuild and a full fresh-consumer setup were not re-executed for this kit. Builds on another machine produce a new runtime identity and new timings, not necessarily identical binary bytes.

Set `PUBLICATION` to a checkout of `https://github.com/de1tydev/HiGHS` containing commit `3ed0d24b76ccf87c7e075a19772a76e696c5493c`, `KIT` to this kit's directory, and `REPLAY_PYTHON` to the clean interpreter. Choose absolute fresh paths for `BASE_SNAPSHOT`, `BASE_ARCHIVE`, `CORRECTED`, `SOURCE`, `BUILD`, `DATA` and `WORK`; create their parents first. Keep package/source/build/data/work locations disjoint. Loader/build paths must contain neither whitespace nor a colon. Do not relocate prepared work.

## Assemble the exact replay package

First verify the seven file hashes listed in this kit's `RELEASE_MANIFEST.json`. Then export the pinned historical package and apply only the four frozen overlay files to a new copy:

```sh
set -eu
export PYTHONDONTWRITEBYTECODE=1
test ! -e "$BASE_SNAPSHOT"; test ! -e "$BASE_ARCHIVE"
mkdir "$BASE_SNAPSHOT"
git -C "$PUBLICATION" archive --format=tar --output="$BASE_ARCHIVE" \
  3ed0d24b76ccf87c7e075a19772a76e696c5493c \
  research/rins_budget/portable_early_integer_replay
tar -xf "$BASE_ARCHIVE" -C "$BASE_SNAPSHOT"
HISTORICAL="$BASE_SNAPSHOT/research/rins_budget/portable_early_integer_replay"
test ! -e "$CORRECTED"
mkdir "$CORRECTED"
cp -a "$HISTORICAL/." "$CORRECTED/"
for FILE in PACKAGE_MANIFEST.json SOURCE_TREE.sha256 prepare_replay.py CORRECTED_REFERENCE_PROPOSAL.json; do
  cp "$KIT/overlay/$FILE" "$CORRECTED/$FILE"
done
"$REPLAY_PYTHON" -I -S -B - "$HISTORICAL" "$CORRECTED" <<'PY'
from pathlib import Path
import hashlib, json, sys
old, new = map(Path, sys.argv[1:])
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
for root, expected, count in [(old, '62c97392d77cd0af2eb8056ea1167222ad969c82e9efa59c0196dcb5ebaa9743', 48),
                              (new, '79e6c0c9832d5322a2406545b855f86d6eab15ed93c6980d7f4cf9894f0eb34f', 49)]:
    assert sha(root/'PACKAGE_MANIFEST.json') == expected
    m = json.loads((root/'PACKAGE_MANIFEST.json').read_text())
    assert not any(p.is_symlink() for p in root.rglob('*'))
    assert {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()} == set(m['files']) | {'PACKAGE_MANIFEST.json'}
    assert len(m['files']) + 1 == count
    assert all(sha(root/name) == value for name, value in m['files'].items())
assert sum(name.startswith('payload/') for name in m['files']) == 33
assert all((new/name).read_bytes() == (old/name).read_bytes() for name in m['files'] if name.startswith('payload/'))
PY
```

Keep this kit's README, manifest and correction patches outside `CORRECTED`; its strict file inventory rejects extras, including bytecode. Preserve both original inputs.

## Reconstruct and build the corrected source

Start from the pinned official base, retain the three existing research patches, and apply the two included backports in this order:

```sh
test ! -e "$SOURCE"; test ! -e "$BUILD"
git clone https://github.com/ERGO-Code/HiGHS.git "$SOURCE"
git -C "$SOURCE" checkout --detach 73cac48c5340d775a477087198611862559be250
for PATCH in outer-gap-heuristic initial-root-ipx root-child-credit; do
  git -C "$SOURCE" apply --check "$CORRECTED/patches/$PATCH.patch"
  git -C "$SOURCE" apply "$CORRECTED/patches/$PATCH.patch"
done
for PATCH in pathcut-3179-backport incumbent-repair-3181-backport; do
  git -C "$SOURCE" apply --check "$KIT/patches/$PATCH.patch"
  git -C "$SOURCE" apply "$KIT/patches/$PATCH.patch"
done
cmake -S "$SOURCE" -B "$BUILD" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DFAST_BUILD=ON -DBUILD_SHARED_LIBS=ON \
  -DBUILD_TESTING=ON -DALL_TESTS=ON -DHIPO=OFF -DHIGHSINT64=OFF
cmake --build "$BUILD" --parallel 2
ctest --test-dir "$BUILD" --output-on-failure --parallel 1
```

Preparation below verifies the exact 984-file source tree, build flags, executable and library aliases. The tree inventory SHA256 is `dba407bb01e868fa4711cb1664590f4fe4250000b5ebab63323d88c72f5a469b`. Do not substitute a whole newer upstream branch.

[#3179](https://github.com/ERGO-Code/HiGHS/pull/3179), merged as `28339ce4b57bf8858036cbb36f4fc66d97fedd06`, supplies the unchanged production correction plus official test/fixture. Its local backport adapts only insertion context for the absent upstream issue-3170 test; the issue-3171 test body and fixture remain unchanged. The complete patch is required, not its production-only subset. [#3181](https://github.com/ERGO-Code/HiGHS/pull/3181), merged as `ae53450f395cf0a278858868b64813ea99bb4767`, contributes the exact one-file, eight-line production addition. This is a custom combined-corrected reference with the existing research patches, not pristine upstream-default HiGHS.

## Prepare, preflight and run a fresh tiny pair

The three public input files and both compressed/decompressed hashes remain fixed. Skip `fetch-data` only when those exact files already occupy `DATA`.

```sh
"$REPLAY_PYTHON" -I -S -B "$CORRECTED/prepare_replay.py" fetch-data --data "$DATA"
"$REPLAY_PYTHON" -I -S -B "$CORRECTED/prepare_replay.py" prepare \
  --source "$SOURCE" --build "$BUILD" --data "$DATA" \
  --python "$REPLAY_PYTHON" --work "$WORK"
"$REPLAY_PYTHON" -I -S -B "$CORRECTED/prepare_replay.py" preflight --work "$WORK"
TINY_RUN_RC=0
"$REPLAY_PYTHON" -I -S -B "$CORRECTED/prepare_replay.py" run \
  --work "$WORK" --tiny --arm pair --out "$WORK/runs/tiny" || TINY_RUN_RC=$?
TINY_VERIFY_RC=0
"$REPLAY_PYTHON" -I -S -B "$CORRECTED/prepare_replay.py" verify \
  --work "$WORK" --out "$WORK/runs/tiny" || TINY_VERIFY_RC=$?
if [ "$TINY_RUN_RC" -ne 0 ]; then exit "$TINY_RUN_RC"; fi
if [ "$TINY_VERIFY_RC" -ne 0 ]; then exit "$TINY_VERIFY_RC"; fi
```

Preflight imports/checks native and scientific providers but does not generate a model or solve. Tiny uses two hours and one outage, A then early, 10 aggregate actual solver-process seconds per arm, 2 seconds charged MIP grace and 180 seconds arm containment. The hard 7 GiB address-space and sampled 2 GiB memory/disk guards remain unchanged. Use the existing pure tests in `CORRECTED/tests/test_method.py` and `test_portable.py` under `-I -S -B`.

Both successful tiny completion and successful offline verification are prerequisites for production. The commands always attempt the identical verifier even after an incomplete or failed tiny run, retain both statuses, and exit with the original run failure first or the verifier failure otherwise. Production is a separate explicit invocation, for example `run --work "$WORK" --case 2017-05-01 --seed 211 --arm pair --out "$WORK/runs/may-211"`. Other dates are June 1 and September 1, 2017; seeds are 211/212/213. Both arms retain all 192 specified outages, 36 hours and the original 1% full-source checks. Production limits remain 600 aggregate actual solver-process seconds, 1800 arm-containment seconds and charged 60-second MIP grace per arm. All models/checks are fresh inside the arm. No historical cuts, points, incumbent/basis/bound state or timing is reused.

A clean incomplete first arm still runs its requested mate; fatal integrity/resource/cancellation/cleanup failures stop dependent execution. Exit code 2 can mean incomplete or failed, so inspect retained results rather than infer the cause. `verify` is an offline artifact/debit/certificate consistency check, not an exact dual proof. No full-panel campaign, retry or performance conclusion follows automatically from a successful tiny pair.

## Limits and attribution

Reference-v2 passed all 168 configured tests and the official #3179 regression. The public #3180 MIP checks are compatibility evidence only: all four reported Repair LPs=0, so dynamic #3181 repair coverage and reproduction of that defect were not established. Feasible primals and solver-reported lower bounds do not establish independent optimality, and the conditional repair retry can still fail.

Historical 1% and time-to-1% claims remain archived with their advisory. Fresh corrected-runtime outcomes require their own complete report/audit; never pool historical timings or compute cross-runtime acceleration percentages. No performance numbers are included here.

Retain the included HiGHS/package license and source notices. Inputs come from the [UnitCommitment.jl 0.3 catalogue](https://axavier.org/UnitCommitment.jl/0.3/instances/); PG89 derives from [MATPOWER case89pegase](https://github.com/MATPOWER/matpower/blob/7.1/data/case89pegase.m) under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). This kit includes no PG89 input datasets, binaries or large models; the complete #3179 patch includes its small official MPS regression fixture. Code licensing does not replace data attribution.
