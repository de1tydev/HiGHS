#!/usr/bin/env bash
# Requires a separately restored official source/build and checked triangle.
# Positional arguments: official-source official-build triangle-mps fresh-root
set -euo pipefail
CACHE_RESEARCH=$(cd "$(dirname "$0")" && pwd)
CACHE_OFFICIAL_SOURCE=$(realpath "${1:?official source}")
CACHE_OFFICIAL_BUILD=$(realpath "${2:?official build}")
CACHE_TRIANGLE=$(realpath "${3:?checked synthetic original-subset.mps}")
CACHE_OUT=${4:?fresh absolute output root}
[[ "$CACHE_OUT" = /* && ! -e "$CACHE_OUT" ]]
[[ $(git -C "$CACHE_OFFICIAL_SOURCE" rev-parse HEAD) = d547a3ad8af5399651187fb0e133cf0e42615b82 ]]
mkdir -p "$CACHE_OUT"
CACHE_PYTHON=${SCUC_PYTHON:-python3.12}
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
# Native original-model reader used only for independent arithmetic QA.
g++ -std=c++17 -O2 -I"$CACHE_OFFICIAL_SOURCE/highs" -I"$CACHE_OFFICIAL_BUILD" "$CACHE_RESEARCH/export_model.cpp" \
 -L"$CACHE_OFFICIAL_BUILD/lib" -lhighs -Wl,-rpath,"$CACHE_OFFICIAL_BUILD/lib" -o "$CACHE_OUT/export_model"
for version in v1 v2 separation; do
 CACHE_SOURCE="$CACHE_OUT/source-$version"
 CACHE_BUILD="$CACHE_OUT/build-$version"
 git clone --no-hardlinks "$CACHE_OFFICIAL_SOURCE" "$CACHE_SOURCE"
 git -C "$CACHE_SOURCE" checkout --detach d547a3ad8af5399651187fb0e133cf0e42615b82
 CACHE_PATCH="$CACHE_RESEARCH/cmir-cache-$version.patch"
 if [[ "$version" = separation ]]; then CACHE_PATCH="$CACHE_RESEARCH/separation-cost-profile.patch"; fi
 git -C "$CACHE_SOURCE" apply "$CACHE_PATCH"
 cmake -S "$CACHE_SOURCE" -B "$CACHE_BUILD" -G Ninja -DCMAKE_BUILD_TYPE=Release -DFAST_BUILD=ON \
  -DBUILD_SHARED_LIBS=ON -DBUILD_SHARED_EXTRAS_LIB=ON -DHIPO=OFF -DHIGHSINT64=OFF -DDEBUGSOL=OFF \
  -DZLIB=ON -DCUPDLP_GPU=OFF -DHIPDLP_HIP=OFF -DBUILD_TESTING=ON -DALL_TESTS=ON \
  -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++ -DCMAKE_C_FLAGS= -DCMAKE_CXX_FLAGS= \
  '-DCMAKE_C_FLAGS_RELEASE=-O3 -DNDEBUG' '-DCMAKE_CXX_FLAGS_RELEASE=-O3 -DNDEBUG' \
  -DCMAKE_EXE_LINKER_FLAGS=-flto=2 -DCMAKE_SHARED_LINKER_FLAGS=-flto=2 -DCMAKE_BUILD_RPATH_USE_ORIGIN=ON
 timeout 1200 cmake --build "$CACHE_BUILD" --target highs-bin highs highs_extras --parallel 2
 if [[ "$version" = separation ]]; then
  "$CACHE_PYTHON" -B "$CACHE_RESEARCH/paired.py" --official "$CACHE_OFFICIAL_BUILD" \
   --candidate "$CACHE_BUILD" --source "$CACHE_OFFICIAL_SOURCE" --triangle "$CACHE_TRIANGLE" \
   --exporter "$CACHE_OUT/export_model" --out "$CACHE_OUT/separation" --stage cost-profile
  "$CACHE_PYTHON" -B "$CACHE_RESEARCH/summarize_separation.py" "$CACHE_OUT/separation"
  continue
 fi
 CACHE_TEST=cache_test.cpp
 if [[ "$version" = v2 ]]; then CACHE_TEST=cache_v2_test.cpp; fi
 g++ -std=c++17 -O2 -fsanitize=undefined,address -fno-omit-frame-pointer -I"$CACHE_SOURCE/highs" \
  -I"$CACHE_BUILD" "$CACHE_RESEARCH/$CACHE_TEST" -o "$CACHE_OUT/test-$version"
 "$CACHE_OUT/test-$version"
 g++ -std=c++17 -O2 -I"$CACHE_SOURCE/highs" -I"$CACHE_BUILD" "$CACHE_RESEARCH/options_test.cpp" \
  -L"$CACHE_BUILD/lib" -lhighs -Wl,-rpath,"$CACHE_BUILD/lib" -o "$CACHE_OUT/options-$version"
 "$CACHE_OUT/options-$version"
 for stage in mechanism default-off panel; do
  "$CACHE_PYTHON" -B "$CACHE_RESEARCH/paired.py" --official "$CACHE_OFFICIAL_BUILD" \
   --candidate "$CACHE_BUILD" --source "$CACHE_OFFICIAL_SOURCE" --triangle "$CACHE_TRIANGLE" \
   --exporter "$CACHE_OUT/export_model" --out "$CACHE_OUT/$version-$stage" --stage "$stage"
 done
 "$CACHE_PYTHON" -B "$CACHE_RESEARCH/summarize.py" "$CACHE_OUT/$version-panel/results.json" "$CACHE_OUT/$version-panel/summary.json"
done
