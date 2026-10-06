# Seed revision v3: implementation validation

The package preserves the approved default-zero policy and adds the bounded
`--seed` plumbing described in SEED_REVISION.md. No native qualification, tiny
optimizer or production panel has been executed during this implementation.

- 90 pure tests passed: the 62 inherited tests plus 28 focused seed tests
- The unchanged SQLite resource harness passed all 71 checks, with no numerical,
  model, physical, or native module imported
- All 70 immutable v2 package members were rehashed; exactly ten runtime Python
  files and PROTOCOL.json changed, leaving 59 members byte-identical
- All previous protocol values, nonseed LP/MIP option constants, native source
  and build pins, source-path mapping, fixture bytes and mathematical methods
  outside the approved seed boundaries remain unchanged
- The native-option qualifier and fixed transition-tiny commands are prepared
  for separate owner-scheduled execution after final review

Pure tests ran from the external validation directory with the pinned Python
interpreter, `-B -s`, source `PYTHONPATH`, and
`CURRENT_SCUC_TEST_RUNTIME_MANIFEST` naming the existing native manifest. The
runtime tests inspect source/manifest bytes only. The runner performs one
source-import child check, then forbids native CDLL entry, subprocess launches,
factorization and linear solves throughout the pure suite. Focused LP tests use
fake API functions, including simulated runs; no HiGHS optimizer was called.

The initial external-directory invocation lacked PYTHONPATH and therefore failed
only its import-child check; the runtime fixture was also not selected in that
attempt. Both launch settings were corrected, and the complete final suite
passed without skips. Original logs are retained alongside final logs.

The focused tests cover omitted seed versus explicit 0, seeds 1/2 across CLI,
arm, worker and native-command boundaries, immutable per-instance LP profiles,
two simulated LP runs, post-solve changes and pre-run drift, global-profile
immutability, strict canonical native argv, missing/invalid/mismatched worker
provenance and typed transition readbacks. Production discovery remains cold.

Current identities and external receipt hashes are in SEED_REVISION.json and
ARTIFACT_MANIFEST.json. The prior validation text is retained at
provenance/RESOURCE_V2_VALIDATION.md. The older historical metadata remains an
attribution record and does not imply that v3 native checks have run.
