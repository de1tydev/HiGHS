# Combined SCUC results

Historical results recorded on 2026-10-02. The experiment's predeclared final performance gate failed; correctness and accounting passed. Publication adds no new performance observations.

## Read the result

- [Result narrative and complete nine-pair table](COMBINED_SCUC_RESULTS.md)
- [Standalone nine-row Markdown table](PAIR_TABLE.md)
- [Nine-row CSV](confirmation_pairs.csv), including exact retained times, certificates, RSS, cap counts and shedding

## Machine-readable evidence

- [Confirmation projection](confirmation_projection.json): summary plus an ordered index of nine compressed pair records covering all 18 final arms, their timings, certificates, intermediate-stage status/check summaries, per-child resources, actual root-credit telemetry and API/selected-module receipts
- [Separate development projection](development_projection.json.gz): familiar February seed 0; explicitly excluded from confirmation statistics
- [Audit projection](audit_projection.json): final independent audit, complete compact audit pair records, date gates, finite-sample tails and source-chain audit
- [Frozen-design projection](frozen_design_projection.json): complete planned sequence, arm definitions, prior exposure and the pre-outcome February seed amendment
- [Raw artifact identities](raw_artifact_hashes.json.gz): exact hashes and sizes of principal original files, plus the retained confirmation-phase artifact inventory
- [Historical runtime/source provenance](historical_runtime_provenance.json.gz): all 395 historical runtime inventory entries, all 983 solver source-file identities, official source base and patch chain, exact measured binary/DSO identities, compiler/build settings and exact option text
- [Source-data provenance](source_data_provenance.json): exact official input URLs, compressed/decompressed byte hashes, source notices and November's recorded selection/acquisition history
- [SHA-256 manifest](SHA256SUMS): identities of these published projections and documents

The projections are new JSON files, not byte-identical copies of the large original records. Original hashes identify the retained original bytes; SHA256SUMS identifies the published-form projections. Absolute machine paths have been replaced by logical archive labels. Those labels are provenance identifiers, not promised download links or runnable paths.

Large repeated eligible-pair/residual arrays and the full primal vector are omitted from projections; their checks, outcomes and exact source/model/solution/check-artifact hashes remain. All observed successes, incomplete intermediate screens, timings and final outcomes are retained. No binary, large MPS, credential or huge raw log is included. Inspecting retained JSON and byte hashes is not a new numerical feasibility check.

The 27 original integer-source check receipts include intermediate cold-screen points that can violate not-yet-added security constraints. The complete security-feasibility claim covers the 18 final confirmation points, not every intermediate point. The 45 API receipts attest the loaded intended model at all 45 stages; they are distinct from optimization and final source feasibility.

## Replay and publication boundary

The [portable Linux replay](../portable_combined_replay/README.md) is available with a separately recorded tiny correctness/equality validation. Its source/runtime-binding refactor has not been performance-measured on the production cases. The historical measured source and runtime identities remain available above.

This result collection is self-contained for reading, but intentionally does not redistribute the approximately 123 MB original confirmation JSON, raw vectors, MPS models or complete logs. Their exact identities are retained for audit traceability. A replay creates new observations under separately identified source/runtime/data bindings and must not replace these historical outcomes.

## Compressed evidence

Larger evidence files use lossless gzip so individual transfers stay bounded. [COMPRESSION.json](COMPRESSION.json) records compressed and uncompressed SHA-256 identities. Use `gzip -dc FILE.json.gz` to inspect a record. The confirmation index lists all nine pair files in the frozen order; JSON-decoding those files reconstructs the original `pairs` array exactly. No numeric values or observed outcomes were removed. The other compressed files reproduce their complete original projection bytes. The narrative, CSV, summary and audit stay directly readable.
