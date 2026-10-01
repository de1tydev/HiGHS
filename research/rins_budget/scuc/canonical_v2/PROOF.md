# Bound serialization and loaded-model equality

## Defect and correction

The frozen writers emit `BV` before considering whether a binary is fixed.
A fixed binary therefore receives both `BV` and `FX 0` or `FX 1`.
`HMpsFF::parseBounds` marks both endpoints defined when it accepts `BV`, then
ignores the later `FX` because those endpoints have already been assigned.
Both intended [0,0] and [1,1] can consequently load as [0,1]. The existing
`INTORG`/`INTEND` markers carry integrality independently of the bound record.

V2 emits only `FX` for fixed binaries and only `BV` for ordinary [0,1]
binaries. Fixed continuous columns retain `FX`; all other supported continuous
columns retain the original `MI`, `LO`, `UP` or implicit-default representation.
Two-sided continuous bounds define separate endpoints. Unsupported binary
intervals and ambiguous duplicate endpoints are rejected.

## Preservation argument

1. Source validation and mathematical construction still use the pinned,
   unchanged generator. Names, ordering, objective, rows, RHS, matrix entries
   and integrality originate in its in-memory `Model`.
2. V2 uses the same columnwise sparse conversion, record order, integer-marker
   transitions and `.17g` number formatting as the frozen writers.
3. The only removed records are `BV` records on fixed binary columns. Their
   existing `FX` records are unchanged. Integer markers are unchanged.
4. Thus v2 bytes are v1 bytes with those exact `BV` lines deleted. Every test
   export checks this full byte-array relation and equality of the complete
   prefix before `BOUNDS`.
5. With no fixed binaries, the entire MPS is byte-identical. This is verified
   on a tiny fixture and was separately verified on the February PG1354 source
   export. It is not a claim that every conceivable source is supported.

The failed tiny's old hash is reproduced from the bundled source. Its only
loaded-model differences are the three lower bounds on `u_offset_0`,
`u_offset_1`, `u_offset_2`: intended [1,1] becomes [0,1]. The generator name
`offset` is a unit identifier; it is not the objective offset. A separate mixed
fixture demonstrates the fixed-zero case. The corrected tiny removes exactly
three `BV` lines and passes every field comparison.

## Actual-library verification

Readback uses the documented C API and the supplied shared library, with no
solve or presolve call. `Highs_getLp` provides the complete LP/MIP data, and
every row/column name is retrieved. The API copies `num_col` starts; the final
CSC endpoint is restored from the returned nonzero count. Integrality storage
is initialized to zero for pure LPs. Name tokens are bounded before calling
the C name getters, whose API has no buffer-length argument.

Acceptance checks all names, numerical fields and sparse storage element by
element; it does not substitute objective agreement for model agreement.
Finite values use equality without a tolerance, with ordinary numeric signed
zero equality. Infinities use the library's `Highs_getInfinity` value. Each
field has its own comparison and diagnostic hashes. Mutation tests confirm
that changing any expected field causes rejection. Any non-OK loader status,
warning/error/ignored/dropped diagnostic, or nonempty Hessian is fatal.

The dropped-coefficient fixture retains a `1e-12` source coefficient in its
MPS and confirms that the default reader's removal of it fails the gate.
The bound fix therefore cannot conceal numerical changes by the reader.

## Limits

This establishes serialization and loading fidelity for accepted tested
models. It does not establish independent physical correctness of the custom
SCUC formulation, solver dual-bound correctness, presolve equivalence, basis
transfer correctness or performance. The historical audit compares matrix
and row data with frozen MPS bytes, with a separate source projection for
column definitions; it does not independently reconstruct network physics.

The full-static February PG89 N-1 model has no binary-bound collision but
loses 33,840 roundoff-scale coefficients on default loading. V2 does not fix
that discrepancy. An exact gate must reject it unless a separately justified
representation/loading change restores equality. See
[LOADER_FIDELITY.md](../LOADER_FIDELITY.md) for its already disclosed historical
status and the conditional interpretation of bounds from a relaxation.
