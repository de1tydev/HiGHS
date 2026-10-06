# Portable seed revision v3

The only new scientific policy is optional `--seed`, default 0, range
0–2147483647. CLI text must be canonical decimal; internal Python/JSON values
must be actual integers. Booleans, floats, missing worker provenance, conflicts
and out-of-range seeds are rejected. The selected `solver_random_seed` is bound
through CLI, arm manifest, worker results, LP/MIP options, native argv, carry
and discovery-to-proof transition checks.

Both LP solves retain one immutable instance-local profile on one fresh handle.
Every top-level discovery/proof MIP receives the selected value. Typed MIP option
readback is performed on a separate empty reference handle, not on the live
solving handle. Module-global option profiles are unchanged, Python hashing
stays 0, and official HiGHS private child-seed handling remains unchanged.

Ten runtime Python files and PROTOCOL.json differ from resource revision v2;
59 of its 70 package members are identical. All nonseed options, mathematical
policies, solver schedules, caps, tolerances, physical checks and budgets remain.
No native code, build, runtime manifest or source-path mapping changed. The
unused legacy zero-only invocation validator remains unchanged. Inspect the
hash-bound delta in [SEED_REVISION.json](SEED_REVISION.json) and its independent
[field-mapped source review](evidence/seed-source-review.json).

The reviewed source manifest is
`97a94cbd0ef8e3289bf584c9c5edac8bb65c304c1a9fca5a6163c2597d67efd5`.
Its resource-v2 parent was published at
`63fa6688f2fcccaeae03fd57c52ed40b9039eb81`, with source manifest
`3465ac32efaf90225a34178593ea7748a04f4becb2af85e4fddfb74e375c63c0`.
The fixed panel proposal SHA-256 is
`481e3246fe4572c73bcecfc5264ef5bd9d5e21cad71a59e1fc5d8bf3a04405d1`.

Completed source and release gates are described in [VALIDATION.md](VALIDATION.md).
The six-run solver-seed sensitivity panel passed its final scientific audit;
results and actual path coverage are in [SEED_PANEL.md](SEED_PANEL.md). The implementation-time source record and native
pending statements are preserved as historical snapshots under
[provenance/](provenance/README.md), not interpreted as current release status.
