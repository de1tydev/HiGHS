# Reconstructing the conditionally admitted research reference

This index reconstructs source and identifies the tested binaries. It does not promise that a rebuild in a different environment has identical binary bytes. Any materially different source/build/runtime must be qualified separately before scientific comparisons.

1. Use a separate clean source tree at d547a3ad8af5399651187fb0e133cf0e42615b82.
2. From this directory at immutable research commit 15245e434f07e0974d0406606457fbe3a9e196d6, verify and apply reference-3357-3367.patch, then upstream3332.patch. Use SHA256 values in REFERENCE_IDENTITY.json. Do not apply unrelated experimental patches.
3. Verify all 1,006 source files against REFERENCE_SOURCE_HASHES.json. This is the corrected source; older baseline receipts remain associated with their original source/runtime.
4. Configure separate assertion and Release build directories using REFERENCE_IDENTITY.json and the preceding README's build details. Enable BUILD_TESTING and ALL_TESTS for native qualification. Serialize builds with two jobs. Restore the normal libhighs.so -> libhighs.so.1 -> libhighs.so.1.15.1 symlinks if recovering saved binary files.
5. Match the exact DSO and native-unit-test hashes for reuse of the tested binary cohort. Otherwise treat the build as a new runtime and rerun appropriate qualification. Clear ambient LD_PRELOAD/LD_AUDIT/LD_LIBRARY_PATH, select the intended library explicitly and verify actual loader resolution.
6. For every future explicitly scoped research solve, set the native HiGHS threads option explicitly. Environment-level OMP limits alone do not satisfy this requirement. Native unit-test results here have no global-thread-pin claim.
7. Preserve the original 168/169 CTest result and the separate 400-case exact-affinity-exclusion aggregate. The latter does not repair the failed affinity test or turn the original suite green.

The complete source/runtime identities, compact reconstruction patches, standalone #3332 driver and independent mathematical proof remain in this directory. QUALIFICATION.md records the additional native coverage and limitations. This admission permits no automatic SCUC/performance campaign and does not enable the rejected child analytic-center omission experiment.
