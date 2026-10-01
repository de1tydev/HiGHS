# Input-only validation results

The portable public suite passed all 11 tests against the unchanged baseline
HiGHS 1.15.1 shared library on 2026-10-01. It used the public relative generator
paths, the bundled fixture and a caller-supplied `--library`. It performed no
optimization, presolve or build. Both frozen generators and the bundled
fixture were hashed before and after the suite and were unchanged.

The compact [validation results](validation_results.json) record hashes and
outcomes. Locally generated `TEST_REPORT.json` contains detailed field
comparisons and diagnostics. Expected rejection cases are successful tests
of the gate, not accepted exported models.

| Test | Coverage |
|---|---|
| 01 | Both frozen Model classes; fixed binary 0/1, ordinary binaries, all supported continuous bounds, all three row senses, alternating integer markers |
| 02 | Residual initial up/down time and time-varying must-run in UC, network and N-1; original and network-extension lineages |
| 03 | Exact old tiny hash, three lost fixed-one lower bounds, all other fields equal; corrected v2 passes |
| 04 | Actual v1 loader loses fixed-zero and fixed-one restrictions while retaining integer type |
| 05 | Twelve malformed, duplicate or unsupported bound-record injections rejected |
| 06 | Invalid source bounds, objective, names and integrality rejected before output |
| 07 | Every comparison field independently mutated and rejected |
| 08 | Actual dropped-coefficient warning and matrix difference rejected |
| 09 | Entire MPS byte identity when there are no fixed binaries |
| 10 | CLI mandatory API readback and refusal to overwrite existing output |
| 11 | Complete continuous fixed-commitment LP checked through `verify_expected` |

## Model identities

| Artifact | SHA-256 | Result |
|---|---|---|
| Regenerated tiny v1 | `3198718762c421b792622804f80c27bd5973b355e9404cd62b4986e801a1187c` | Expected rejection: three fixed-one lower bounds lost |
| Corrected tiny v2 | `9f422b3ca2755ffa8dd0b8a7758a753bf1ca4a41b3031c99aa2755da1bf254d9` | Exact loaded equality; three redundant BV records removed |
| Mixed bounds v2 | `bc1a7a771449642d12f303d9b1cc4a72c9ba70211a43045711684a6c437ef20d` | Exact loaded equality from both frozen Model classes |
| Fixed continuous LP | `0c180587c52b9572b8288bb17f5263b26195b860a253bd74e10b594a4c2cc869` | Exact loaded equality; zero integer columns |
| February PG1354 v2 | `b0c7cacfc0219693039e30721541aecadc881b1b6f628add1a993483a1b3b060` | Earlier input-only source export was byte-identical to historical v1 |

The February PG1354 result comes from the earlier frozen validation, not the
portable tiny-only suite. That earlier check compared all 313,776 columns,
381,268 rows, 28,080 integer declarations and 1,232,543 nonzeros with a freshly
constructed source Model, with zero fixed binaries, no loader diagnostics and
all fields equal. Packaging did not regenerate or reread that large model.

## Portable test adaptation

The frozen source test SHA-256 is
`5e4704da3e81c8cae269938ae3eab6fa3734435e51e2ce156319d97f575d38f5`.
The public test retains all 11 tests and changes only:

- Generator paths to `../generate.py` and `../large_cases/generate_network_only.py`
- The implicit library location to required `--library`
- The old smoke-directory dependency to `fixtures/on_negative.json`
- The old MPS comparison to its full fixed expected SHA-256
- Preservation bookkeeping to hash the bundled fixture tree instead of an
  external smoke directory, with the corresponding report key renamed

The exporter and readback modules have no adaptation. Their hashes and the
adapted test hash appear in [PACKAGE_MANIFEST.json](PACKAGE_MANIFEST.json).
No result here measures a stable speedup or validates a root-basis driver.
