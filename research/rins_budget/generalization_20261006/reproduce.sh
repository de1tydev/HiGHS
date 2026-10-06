#!/usr/bin/env bash
# Fresh official build and serial small-scale diagnostics. Does not fetch blocked data.
set -euo pipefail
SCUC_RESEARCH_DIR=$(cd "$(dirname "$0")" && pwd)
SCUC_PACKAGE_DIR=$(cd "$SCUC_RESEARCH_DIR/../current_scuc" && pwd)
SCUC_REPLAY_ROOT=${1:?Pass an absolute fresh directory outside the checkout}
[[ "$SCUC_REPLAY_ROOT" = /* && ! -e "$SCUC_REPLAY_ROOT" ]]
mkdir -p "$SCUC_REPLAY_ROOT"
python3.12 -m venv "$SCUC_REPLAY_ROOT/venv"
SCUC_PYTHON="$SCUC_REPLAY_ROOT/venv/bin/python"
"$SCUC_PYTHON" -m pip install --no-compile numpy==2.3.5 scipy==1.17.0 threadpoolctl==3.6.0 cmake==3.31.10 ninja==1.13.2
export PATH="$SCUC_REPLAY_ROOT/venv/bin:$PATH"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export LANG=C LC_ALL=C TZ=UTC PYTHONHASHSEED=0 PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
SCUC_SOURCE="$SCUC_REPLAY_ROOT/source"
SCUC_BUILD="$SCUC_REPLAY_ROOT/build"
git clone https://github.com/ERGO-Code/HiGHS.git "$SCUC_SOURCE"
git -C "$SCUC_SOURCE" checkout --detach d547a3ad8af5399651187fb0e133cf0e42615b82
cmake -S "$SCUC_SOURCE" -B "$SCUC_BUILD" -G Ninja -DCMAKE_BUILD_TYPE=Release -DFAST_BUILD=ON \
 -DBUILD_SHARED_LIBS=ON -DBUILD_SHARED_EXTRAS_LIB=ON -DHIPO=OFF -DHIGHSINT64=OFF \
 -DDEBUGSOL=OFF -DZLIB=ON -DCUPDLP_GPU=OFF -DHIPDLP_HIP=OFF -DBUILD_TESTING=ON \
 -DALL_TESTS=ON -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++ -DCMAKE_C_FLAGS= \
 -DCMAKE_CXX_FLAGS= '-DCMAKE_C_FLAGS_RELEASE=-O3 -DNDEBUG' '-DCMAKE_CXX_FLAGS_RELEASE=-O3 -DNDEBUG' \
 -DCMAKE_EXE_LINKER_FLAGS=-flto=2 -DCMAKE_SHARED_LINKER_FLAGS=-flto=2 -DCMAKE_BUILD_RPATH_USE_ORIGIN=ON
 timeout 1200 cmake --build "$SCUC_BUILD" --target highs-bin highs highs_extras --parallel 2
cd "$SCUC_PACKAGE_DIR"
"$SCUC_PYTHON" -B native/build_assess.py --source "$SCUC_SOURCE" --build "$SCUC_BUILD" --cxx g++
"$SCUC_PYTHON" -B native/make_runtime_manifest.py --source "$SCUC_SOURCE" --build "$SCUC_BUILD"
export LD_LIBRARY_PATH="$SCUC_BUILD/lib"
"$SCUC_PYTHON" -B tools/run_pure_tests.py
"$SCUC_PYTHON" -B "$SCUC_RESEARCH_DIR/bounded.py" --out "$SCUC_REPLAY_ROOT/tiny-outer" --seconds 240 -- \
 "$SCUC_PYTHON" -B -s -m tests.run_tiny_components --suite transition --seed 1 \
 --highs "$SCUC_BUILD/bin/highs" --runtime-manifest "$SCUC_BUILD/runtime-manifest.json" --workdir "$SCUC_REPLAY_ROOT/tiny"
"$SCUC_PYTHON" -B "$SCUC_RESEARCH_DIR/profile.py" --source "$SCUC_SOURCE" --build "$SCUC_BUILD" --out "$SCUC_REPLAY_ROOT/profile"
for app in sparse_start profile_detail; do
 g++ -std=c++17 -O2 -I"$SCUC_SOURCE/highs" -I"$SCUC_BUILD" "$SCUC_RESEARCH_DIR/$app.cpp" \
  -L"$SCUC_BUILD/lib" -lhighs -Wl,-rpath,"$SCUC_BUILD/lib" -o "$SCUC_REPLAY_ROOT/$app"
done
"$SCUC_PYTHON" -B "$SCUC_RESEARCH_DIR/test_history.py"
"$SCUC_PYTHON" -B "$SCUC_RESEARCH_DIR/smoke_history.py" --adapter "$SCUC_REPLAY_ROOT/sparse_start" --out "$SCUC_REPLAY_ROOT/history-smoke"
for model in dcmulti gesa2; do
 for seed in 1 2; do
  "$SCUC_PYTHON" -B "$SCUC_RESEARCH_DIR/bounded.py" --out "$SCUC_REPLAY_ROOT/detail-$model-$seed" --seconds 75 -- \
   "$SCUC_REPLAY_ROOT/profile_detail" "$SCUC_SOURCE/check/instances/$model.mps" "$seed" "$SCUC_REPLAY_ROOT/detail-$model-$seed.tsv"
 done
done
