# Portable resource revision v2 validation

62 pure tests passed (the original 52, one approved CORE readback test, and
nine focused storage/entry-boundary tests), with both bound-runtime source-only
tests enabled. 71 SQLite equivalence checks passed against the actual new
witness implementation, including unchanged queries, bytes, hashes, ordering,
negative compile/readback cases and injected allocation failures.

No HiGHS solve, model generation, physical computation, full June CLI or new
numerical fixture was run for this revision. Earlier numerical coverage is
preserved verbatim in [provenance/BASE_VALIDATION.md](provenance/BASE_VALIDATION.md);
it is historical baseline evidence, not a numerical retest of this revision.

The first pure invocation from outside the source working directory passed all
61 in-process tests but failed the import-only subprocess with ModuleNotFoundError.
The documented source-directory invocation passed all 62 tests without code
changes. Both logs remain in the separate local validation directory.

Run pure tests from this source directory using Python -B -s tools/run_pure_tests.py,
with CURRENT_SCUC_TEST_RUNTIME_MANIFEST naming a verified runtime manifest.
Run tests/sqlite_resource_equivalence.py with --baseline pointing to the preserved
publication, --saved-physical pointing to the retained December physical evidence,
and --out naming a fresh directory outside this source bundle. Its fixed triangle
records test serialization only; the saved December witness dataset is empty.

Full production quality, full-size memory fit, changed-master/new-line carry,
cancellation and crash/OOM behavior remain unexercised by this revision.
