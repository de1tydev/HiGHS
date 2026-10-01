# Loader fidelity and the canonical v2 input route

A retrospective read-only audit found exact loaded-model identity for eight
of the nine distinct historical public SCUC matrices. The ninth, the original
full-static February PG89 N-1 smoke, loses 33,840 roundoff-scale coefficients
on loading. That discrepancy and the run's lack of an incumbent were already
disclosed in the [initial measured results](README.md#initial-measured-results-not-ab-evidence).
Its lower bound was never used for the successful screened certificate.

A separate failing synthetic tiny exposed a fixed-binary serialization defect:
the v1 writer emits `BV` then `FX`, and the HiGHS MPS reader ignores the second
assignment to the same endpoints. The tiny loses exactly three fixed-one
restrictions, with all other model fields equal. The same first bad incumbent
was reproduced by the pristine baseline. This is evidence of an input-loader
failure, not evidence that a root-basis change caused it. Mixed synthetic tests
also reproduce the loss of fixed-zero restrictions.

For new inputs use [canonical_v2](canonical_v2/README.md), which emits only
`FX` for a fixed binary, keeps integer markers, and requires complete actual
C API readback equality. The historical v1 generators, records and model
identities remain available for exact replay. The v2 bounds change does not
fix dropped matrix coefficients or silently modify historical files.

## Audit scope

The audit used an unchanged HiGHS 1.15.1 library built from source commit
`73cac48c5340d775a477087198611862559be250`, SHA-256
`d93351005887232f8cbe3a4057690eddba492108f087a3edb22b00d2f1e9dda8`.
It called `Highs_readModel`, `Highs_getLp` and name/dimension queries without
optimization, presolve, model generation or a library build. The actual
`HighsInt` width was four bytes. Ten distinct MPS hashes covered nine
historical matrices plus the failing tiny, across 27 unchanged input paths.

Every row/column name and index, bound, integrality flag, objective coefficient,
objective sense/offset, row side and matrix coefficient was compared. Numeric
equality was exact in the parsed binary64 values, with only API infinity
normalization. Sparse semantic comparison tolerated storage-order differences
without hiding coefficient changes. The source projection independently
checked every column name/order, bound, integrality flag and cost from source
JSON using the frozen variable definitions. Rows and matrix coefficients were
compared with the frozen MPS, not independently rederived from network physics.

The compact [audit results](canonical_v2/loader_audit_results.json) contain
complete model hashes and report hashes. Model names there are descriptive
relative identifiers, not bundled MPS downloads. No large models, logs, loaded
arrays or binaries are included in this addition.

| Historical matrix | SHA-256 prefix | Columns / rows / loaded nonzeros | Result |
|---|---|---|---|
| PG1354 February network | `b0c7cacfc021` | 313,776 / 381,268 / 1,232,543 | Exact |
| PG1354 August network | `b411c661945d` | 313,776 / 381,052 / 1,230,857 | Exact |
| PG1354 November network | `385aa2a2662a` | 313,776 / 381,052 / 1,230,390 | Exact |
| PG89 February screened | `c3c8dc7c4541` | 21,096 / 24,540 / 82,695 | Exact |
| PG89 August screened round 1 | `c326ec5eb368` | 21,096 / 24,540 / 82,695 | Exact |
| PG89 August screened round 2 | `be58b4cffd9c` | 21,096 / 25,332 / 85,071 | Exact |
| PG89 February network | `c66078c82109` | 21,096 / 23,676 / 80,103 | Exact |
| IEEE118 February UC | `8f58b96a2313` | 23,724 / 33,066 / 132,642 | Exact |
| PG89 February full-static N-1 | `31327d0fd93f` | 21,096 / 1,083,588 / 3,066,303 | 33,840 coefficients dropped; containment not established |

All nine historical matrices have zero duplicate-bound records and zero
changed bounds. The eight exact matrices also have unchanged integrality,
objective, row sides and coefficients, with no loader warnings. The full-static
matrix exported 3,100,143 nonzeros; only 3,066,303 remain loaded. The dropped
entries affect 33,840 rows and 6,804 signed free flow variables across 189
lines. There are 16,920 entries of each sign, with magnitudes from
2.7276414905003523e-20 to 9.573115855378062e-15. No entries were added or
changed to another nonzero value.

The original full-static smoke used a 45-second limit and seed 0, ending after
45.79 solver seconds (50.94 total) with no incumbent, a solver-reported bound
of 9930.11812664 and infinite gap. The existing publication excludes that bound
from the screened certificate and makes no speedup claim from the initial
runs. The retrospective check found no reference to the full-static hash or
bound in the 16 published recorded-results JSON files it inspected.

## Interpretation and limits

This audit is retrospective validation, not evidence that a historical
preflight was performed. It does not change the interpretation or labeling of
earlier performance observations, independently prove a solver dual bound,
establish stable speedup, or certify general parity with original power-system
physics. Derived reformulations and intermediate models need their own checks.

For minimization, if the loaded model differs only by relaxed bounds while
every other field is identical, a valid loaded-model lower bound also bounds
the intended model. This applies to the failing tiny's three [1,1] to [0,1]
changes. An independently checked intended-model primal and a solver-reported
bound from that relaxation can support the same numerical gap, conditional on
the solver bound being valid. It remains a solver-reported bound. Any changed
coefficient, row, objective, integrality or narrowed bound needs a separate
containment argument; the full-static discrepancy is not automatically a
relaxation.

The corrected tiny's SHA-256 is
`9f422b3ca2755ffa8dd0b8a7758a753bf1ca4a41b3031c99aa2755da1bf254d9`.
The February PG1354 v2 source export is byte-identical to its historical
`b0c7cacfc0219693039e30721541aecadc881b1b6f628add1a993483a1b3b060`
model. Both results include complete source-to-loaded equality. See
[validation results](canonical_v2/RESULTS.md) and the
[serialization proof](canonical_v2/PROOF.md) for reproducible tiny checks and
the precise preservation claim.
