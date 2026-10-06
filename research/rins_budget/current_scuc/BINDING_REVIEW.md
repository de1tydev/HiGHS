# Extraction and binding review scope

The original baseline extraction review is preserved byte-for-byte at
[provenance/BASE_BINDING_REVIEW.md](provenance/BASE_BINDING_REVIEW.md).
[SOURCE_PROVENANCE.json](SOURCE_PROVENANCE.json) retains its baseline source,
segment and AST attribution. Its old hashes and counts apply only where those
bytes remain unchanged; they do not identify the later resource or seed edits.

The historical six-file resource delta remains in
[RESOURCE_REVISION.md](RESOURCE_REVISION.md) and
[RESOURCE_REVISION.json](RESOURCE_REVISION.json). The current approved seed
change spans ten runtime Python files and PROTOCOL.json, documented in
[SEED_REVISION.md](SEED_REVISION.md), [SEED_REVISION.json](SEED_REVISION.json), and
[evidence/seed-source-review.json](evidence/seed-source-review.json).

The current runtime source manifest verifies 70 members, with 59 identical to resource
v2. Scientific bodies and all nonseed policies remain unchanged as documented
by that independent review. Publication itself changes no executable, test,
native-build, license or runtime-manifest bytes. Historical extraction claims
are not new execution coverage or production-readiness claims.
