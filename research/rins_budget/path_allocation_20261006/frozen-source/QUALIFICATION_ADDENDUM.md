# Prospective qualification addendum

Frozen before this six-call campaign. The approved C++ patch remains exactly
`ebf898a0f1b18e956121eedd325352350f57af3e067bde42545b504e1b7151c2`.
The unchanged published separator-cost observer remains included.

The parent has authorized this explicit qualification stage to supply the fresh
reference/default-off prerequisites of `DIAGNOSTIC_GATE.md` in the restored
runtime. The fixed schedule is:

1. dcmulti seed 1, official, log_dev_level 0
2. dcmulti seed 1, candidate, log_dev_level 0
3. gesa2 seed 1, official, log_dev_level 0
4. gesa2 seed 1, candidate, log_dev_level 0
5. dcmulti seed 1, candidate, log_dev_level 2
6. gesa2 seed 1, candidate, log_dev_level 2

Slots 5–6 run only after all four qualification slots and both default-off
parity comparisons pass. Observer results also require parity against their
fresh official reference. Each slot has the unchanged 60-second native limit,
74-second existing watchdog plus one-second cleanup allowance within the
75-second outer cap. The complete budget is at most six optimization calls,
360 native seconds and 450 outer solver-slot seconds. No repeats, replacement
seeds, extra models, or cache experiments are authorized by this addendum.

All existing process-tree/memory/headroom limits, exact-reap receipts, original
matrix arithmetic checks, and accounting/signal thresholds remain unchanged.
Any invalid status, point, guard, parity, or diagnostic counters stop subsequent
slots. A clean native process requires exit code exactly zero; warnings or any
nonzero exit are retained as failed evidence even if the log says Optimal.
A materiality failure alone is evaluated after both valid observer slots;
it never triggers repetition. The original two observer slots retain their
120-native/150-outer aggregate allowance within the expanded campaign budget.

`run_probe.py` is a thin fixed-schedule adaptation of the published `paired.py`.
It imports the unchanged published `check_primal.py` and existing
`current_scuc.slot_envelope` directly. Original matrix loading uses only the
published `export_model.cpp` helper built against the official library, with
`LD_LIBRARY_PATH` explicitly selecting that library. Its two bounded read-only
model exports are separately recorded and are not optimization calls. Build,
export and arithmetic-check time is separate from solver-slot times.

`parse_probe.py` validates the frozen counter identities and emits invocation,
main/sub-MIP/depth, vector-payload, and A/S/P/O summaries plus both-model signal
decisions. These decisions do not establish allocator calls, speedup or complete
cut identity. Every planned slot remains in `results.json`, including unrun
slots after a stop; raw logs/options/points/receipts/checks are retained.

No native operation was performed by the source author. The parent builds the
candidate/exporter and executes the campaign. The following commands assume the
parent's fresh separate candidate build is at `candidate-build`; pass its actual
path if different. Run from the recovery root:

```sh
g++ -std=c++17 -O2 -Iofficial-source/highs -Iofficial-build \
  research-fork/research/rins_budget/cmir_cache_20261006/export_model.cpp \
  -Lofficial-build/lib -lhighs -Wl,-rpath,"$PWD/official-build/lib" \
  -o path_allocation_probe_v1/export_model

python3 -B path_allocation_probe_v1/run_probe.py \
  --official-build official-build --candidate-build candidate-build \
  --official-source official-source \
  --research-root research-fork/research/rins_budget/cmir_cache_20261006 \
  --exporter path_allocation_probe_v1/export_model \
  --out path_allocation_probe_v1/runs --highsint-bytes 4
```

The output root must be new. The runner never rebuilds or retries. The exporter
command is supplied for the parent and has not been executed by the source
author. Parser tests contain only synthetic text fixtures and use no native
binary, solver, model exporter, or original-matrix loading.
