# Portable seed revision v3

This is a separate source copy of resource revision v2, whose source manifest is
3465ac32efaf90225a34178593ea7748a04f4becb2af85e4fddfb74e375c63c0 and published
commit is 63fa6688f2fcccaeae03fd57c52ed40b9039eb81. The base and its production
results are unchanged. This copy implements the approved seed-control proposal,
SHA-256 481e3246fe4572c73bcecfc5264ef5bd9d5e21cad71a59e1fc5d8bf3a04405d1.

The only changed scientific policy is an optional `--seed`, default 0, accepting
canonical decimal integers 0 through 2147483647. Python/JSON boundaries accept
only actual integers, rejecting booleans, floats, missing fields and conflicts.
The selected value is recorded as `solver_random_seed` in the hash-bound arm
manifest, candidate/LP results, MIP trace and carry evidence. The CLI checks the
returned candidate value against its request. Both LP solves use one fresh
handle with an instance-local immutable option profile; setter freezing and
pre-run drift checks use that selected profile. Every discovery/proof MIP uses
the same value in its command and typed reference-handle readback. The MIP
readback remains a separate empty reference handle, not the live solving handle.

No module-global option map is changed. Python hashing stays 0. Private HiGHS
child-seed handling, role option-file bytes, every nonseed option, the algorithm,
physical checks, targets, tolerances and budgets remain unchanged. There is no
environment override or worker seed flag. The existing arm schema remains v1;
this source-manifest revision requires the new seed field and has no missing-field
fallback. The unused legacy `option_probe.validate_invocation` remains zero-only.
No native binary, build, runtime manifest or source-path mapping was changed.

The current release checks are pure/mock tests and independent source review.
Prepared native checks are a single bounded empty-handle setter/getter run for
0/1/2, followed by the existing fixed transition tiny at seed 1. They have not
been executed as part of implementation. The tiny keeps two LP solves and three
MIPs total (cold discovery, unchanged-master proof, existing full reference),
30 original retained columns, all 12 original binaries, and the expected
2.25 MWh overflow nonpass. Its 180-second owner/170-second worker, 20-second
native MIP, 60-second cumulative seed-native and all resource caps are unchanged.
There is no changed-master component in this release gate. The legacy tiny's
explicit seed-0 metadata compatibility is source-only and its v3 native behavior
is untested. No optimizer was launched, and no six-run panel result is claimed.

Current source/member identities are in `SEED_REVISION.json`,
`current_scuc/SOURCE_MANIFEST.json` and `ARTIFACT_MANIFEST.json`. Historical
attribution files remain historical; v2 resource metadata has not been rewritten
to describe this change. Validation logs and the reviewed release launchers are
retained outside the source tree in the corresponding seed-v3 validation directory.
