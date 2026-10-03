# Replay validation

Use the [consumer recipe](../README.md) for exact source, build, preparation and run commands. The [validation record](../VALIDATION.md) describes the completed reference checks and their limits. This package uses pristine official HiGHS commit `d547a3ad8af5399651187fb0e133cf0e42615b82`; do not substitute a moving branch or an older library.

## Reproduce on a new machine

1. Verify the publication manifest, this package's closed inventory and all 1006 source files with the external `verify_files.py` tool. Keep source, build, data, work and kit directories separate.
2. Build the CLI, main library and extras together using the exact Release/FAST_BUILD/shared/int32 recipe: HIPO off, two build jobs and `-flto=2` linker flags. The package binds actual executable, library, alias, compiler and configuration hashes from that build.
3. Run the focused official regressions and complete configured CTest suite, retain their statuses and diagnose every failure. The recorded reference unit suite was 399/400 because of an environment-triggered affinity/default-core-count failure. This remains a failed test; explicit nonzero replay threads bypass that lookup.
4. Prepare a fresh work directory using the three hash-pinned public inputs, then run the separate preflight. Preflight checks scientific and native providers; it does not generate or solve a model. Every actual solve must identify the same main and extras libraries.
5. Run the tiny pair and the offline verifier. Tiny uses two hours, one outage, seed 0, A then early, 10 aggregate actual solver-process seconds per arm, 2-second charged MIP grace and 180-second arm containment. Keep the 7 GiB per-process address-space limit, 4 GiB file-size limit and sampled 2 GiB memory/disk floors. Retain all sixteen model-readback fields, complete saved primal columns, original-source/outage checks and proof-only certificates.
6. Retain run and verifier statuses separately, including a nonzero run result. Inspect incomplete/failure and cleanup records. A tiny result is an integration check; it does not establish a performance result or exact independent dual proof.
7. For a fresh PG89 study, use the explicit pair commands and [reporting instructions](../REPORT_TEMPLATE.md). Preserve all declared outcomes, including failed, censored and unrun rows. Never pool historical and new-runtime timings.

The exact #3270 LP, retained #3179 regression and public #3180/#3181 compatibility outcomes are summarized in the [validation record](../VALIDATION.md). The #3181 fixture retained scaling warnings and did not establish dynamic coverage of the guarded retry. Neither those fixtures nor the tiny pair establish universal solver correctness or production readiness.

## File integrity

The public package differs from the measured package only in this document, `README.md`, `SOURCE_LINEAGE.json` and the resulting package manifest. Every executable, payload, test, source-inventory, data-attribution, dependency and license file remains byte-identical. The [equivalence record](../EXECUTABLE_EQUIVALENCE.json) lists their hashes and the measured/public package identities. Write logs, bindings, work trees and results outside the immutable package, with Python bytecode disabled.
