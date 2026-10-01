# Canonical SCUC MPS export v2

Use this additive route for new inputs from the frozen SCUC generators. It fixes
fixed-binary serialization and requires an actual HiGHS API readback before an
export is accepted. The existing v1 generators remain the historical replay
route. Their formulation and files are unchanged.

The exporter delegates source construction to one of the two hash-pinned
generators. It then writes an unambiguous MPS and compares the loaded model with
the complete source `Model`. This path performs no optimization or presolve.
See [the loader-fidelity audit](../LOADER_FIDELITY.md) for historical impact,
[PROOF.md](PROOF.md) for the serialization argument, and
[RESULTS.md](RESULTS.md) for the executed checks and exact model hashes.

## Requirements

- Python 3, NumPy and SciPy; the existing `scuc/requirements.txt` applies
- A supplied HiGHS shared library exporting the C API used by `readback.py`
- A Linux ELF runtime exposing `dladdr` through the process handle
- A 32-bit `HighsInt` build (`HIGHSINT64=OFF`); this is the integer ABI width,
  not a requirement for a 32-bit operating system

The executed checks used Python 3.12.14, NumPy 2.3.5, SciPy 1.17.0 and HiGHS
1.15.1. `Highs_getSizeofHighsInt` must report four bytes before array calls.
The actual addresses of five key C API functions are resolved with `dladdr`;
their real library path and SHA-256 must match the supplied DSO. The DSO is
hashed again after each read. No compilation is needed when a compatible
shared library is already available. Other platforms and 64-bit `HighsInt`
builds are outside this readback implementation's supported contract.

## Reproduce the tiny input-only tests

Run these commands from the repository root. Set `HIGHS_LIBRARY` to your
existing shared library. Both output directories must be new.

```sh
python -m pip install -r research/rins_budget/scuc/requirements.txt
export HIGHS_LIBRARY=/path/to/libhighs.so.1
python research/rins_budget/scuc/canonical_v2/test_export.py \
  --library "$HIGHS_LIBRARY" \
  --output-dir /tmp/scuc-canonical-v2-tests
```

All 11 tests use tiny synthetic models. They include actual loader calls,
expected rejection of the v1 defect and dropped coefficients, and a subprocess
test of the CLI. A passing suite has `passed: true`, `tests_run: 11`, zero
failures/errors, and `optimization_or_presolve_called: false` in
`TEST_REPORT.json`. Expected-failure fixture reports inside it have
`passed: false`; those rejections are required for the suite to pass.

The bundled `fixtures/on_negative.json` regenerates the exact old failing MPS
without distributing that MPS or its logs. The test requires SHA-256
`3198718762c421b792622804f80c27bd5973b355e9404cd62b4986e801a1187c` for the v1
regeneration and checks all fields after v2 serialization.

## Export the bundled source through the recommended route

```sh
mkdir /tmp/scuc-canonical-v2-example
python research/rins_budget/scuc/canonical_v2/export_v2.py \
  research/rins_budget/scuc/canonical_v2/fixtures/on_negative.json \
  --generator research/rins_budget/scuc/large_cases/generate_network_only.py \
  --mode network --hours 3 \
  --output /tmp/scuc-canonical-v2-example/on_negative.v2.mps \
  --library "$HIGHS_LIBRARY"
```

For another source, replace the input, hours and output. The original
`research/rins_budget/scuc/generate.py` supports `uc`, `network` and `n1`.
The single-point extension shown above supports `network` only. `--pairs`
accepts the original generator's selected monitored/outage-pair JSON. These
choices preserve the source generator's modeling scope.

The CLI writes the MPS, `.meta.json`, `.readback.json` and `.readback.log`.
Acceptance requires successful exit, `api_fidelity_verified: true` in metadata
and `passed: true` in the readback report. Existing output or sidecar/log files
are rejected. On failed readback the evidence is retained and the process
exits unsuccessfully; file existence alone does not mean acceptance. The
runtime reports naturally record the caller's resolved paths and library
identity, so review those reports before redistributing them.

## Strict API contract

`verify_model(model, path, library, log_path)` compares dimensions; ordered
column/row names; every column lower/upper bound, objective coefficient and
integrality flag; objective sense/offset; every row lower/upper side; and every
CSC start, row index and coefficient. Equality is numeric elementwise equality
with no finite tolerance. Only infinities are normalized through
`Highs_getInfinity`; signed zero has ordinary numeric equality. An unexpected
Hessian, any non-OK read status, any warning/error/ignored/dropped diagnostic,
or any field mismatch fails the gate. No reader cutoff is changed.

`write_model(model, path)` alone returns `api_fidelity_verified: false` and is
not a complete acceptance gate. A caller must check the result of
`readback.verify_model`. `readback.verify_expected(expected, path, library,
log_path)` accepts a complete independently constructed expectation, including
a continuous fixed-commitment LP. The expected dictionary uses the keys from
`export_v2.intended_model`: scalar `num_col`, `num_row`, `num_nz`, `sense`,
`offset`; ordered `col_names`, `row_names`; arrays `col_lower`, `col_upper`,
`col_cost`, `row_lower`, `row_upper`, `integrality`, `a_start`, `a_index`,
`a_value`. Sparse starts have `num_col + 1` entries; indices and integrality
use int32. Never derive the expectation from the already loaded model.

`load_model` is a raw diagnostic read that permits warning status so defects
can be inspected. It is not acceptance. The bound validator checks this
writer's supported section/marker/bound subset, not arbitrary MPS syntax.
Independent expected-data construction remains the caller's responsibility.

## Package lineage

`export_v2.py` and `readback.py` are byte-identical to the frozen v2 modules.
`PACKAGE_MANIFEST.json` records their hashes, generator pins, the synthetic
fixture, all package files and the public test adaptation. The test changes
only path/fixture-preservation plumbing and the required `--library` argument;
all 11 regression bodies and acceptance checks are retained, with the old MPS
comparison using its published expected hash. Full models, raw logs, shared
libraries and binaries are generated or supplied locally, not bundled here.
