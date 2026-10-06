# Seed revision v3: observed validation

This public projection reads retained records and hashes only. It does not run
or repeat tests, native calls, model generation, optimization or scientific QA.
Its exact runtime source manifest is
`97a94cbd0ef8e3289bf584c9c5edac8bb65c304c1a9fca5a6163c2597d67efd5`.

## Source and pure checks

The implementation passed 90 pure tests (62 inherited and 28 focused seed
tests) and all 71 unchanged SQLite resource checks. The independent reviewer
separately passed the same 90-test pure suite with zero skips. Tests check
omitted/default versus explicit 0, 1/2 propagation, immutable LP profiles,
two simulated LP solves, native argv and typed option readbacks, drift and
invalid/missing/conflicting seed provenance. They prohibit actual native entry,
subprocess optimization, factorization and scientific solves.

The independent source review verified all 70 package members: ten Python files
and PROTOCOL.json changed from v2, while 59 members stayed identical. All prior
protocol values and nonseed option constants are unchanged. The six launcher
ASTs differ from the reviewed v2 owner only in approved source/input/output
identities and the selected seed. Static call-count checks are not runtime
coverage. The evidence is field-mapped in
[evidence/seed-source-review.json](evidence/seed-source-review.json); the
independent pure log is [retained](evidence/seed-independent-pure-tests.log).
Historical implementation test receipt identities remain in
[SEED_REVISION.json](SEED_REVISION.json).

## Actual native and fixed-tiny release gates

An independent read-only gate audit passed. Fresh empty native handles accepted
and read back seeds 0, 1 and 2, with all three handles destroyed and zero model,
presolve or optimizer calls. Contained wall was 0.182686528 seconds within the
20-second bound; cleanup and limits passed.

The single seed-1 transition tiny passed its component test and correctly failed
candidate quality. Exactly two LP solves and three total MIPs ran: cold
discovery, unchanged-master proof, and the existing tiny full reference. Carry
preserved 30 original retained columns and all 12 binaries; exact/native carry,
proof-start admission, original-matrix, literal-scope and independent direct-DC
checks passed. Carry itself performed no optimizer or factorization call.

The checked upper was 11306.00000000003 against reference objective 11306.0.
The allowance-adjusted numerical MIP lower was 11305.99998995; the separate exact
seed-LP lower was 7557.499999999971. The tiny remained a quality NONPASS with
2.2500000000000058 MWh shared overflow and zero shedding/reserve shortfall.
Contained wall was 12.910000969 seconds; full launcher elapsed was
13.475546288 seconds. All recorded resource and cleanup gates passed. This is
unchanged-master coverage, not changed-master coverage or production success.
The three MIPs include a reference solve; they do not establish coverage of a
third production candidate MIP.

The gate audit rehashed 119 source/evidence files and verified the durable
source archive's 320 members, including 317 regular members, two symlinks and
its manifest. See the field-mapped
[evidence/seed-release-gates.json](evidence/seed-release-gates.json).

## Fixed panel: six audited passes

[SEED_PANEL.md](SEED_PANEL.md) reports the fixed June/1, October/1, December/1,
December/2, October/2, June/2 order. All six terminal scientific and accounting
audits passed the unchanged interval/full-QA/slack/resource/cleanup gate. The
source and policies remained fixed. No outcome was removed or replaced. The
final independent descriptive audit is field-mapped in
[evidence/seed-panel-final-audit-summary.json](evidence/seed-panel-final-audit-summary.json).
All six terminal and closure archives passed actual-byte/member readback
verification. [The separate administration projection](evidence/seed-panel-administration.json)
records measured assembly/readback and explicitly filesystem-derived closure spans.

This is descriptive seed sensitivity on three already exposed dates. It cannot
establish same-seed repeatability, statistical reliability, failure probability,
unseen-case generalization or general production readiness. There is no
conventional comparator, speed ratio, replacement run or outcome-driven tuning.

The interval lower belongs to the hard-zero shedding/reserve integer subset of
the full literal serialized-LODF model. It is not valid for the original soft
optimum or the broader negligible-shedding domain. Numerical MIP lower bounds
remain numerical and allowance-adjusted; exact seed-LP certificates concern
the projected literal-row matrix. Physical U is a numerical witness checked
against the original matrix, all original binaries, full literal scope and both
independent physical/source checks. Physical DC lower-bound certification stays
false. Clock scopes are nested: the CLI field runs from main entry to just before
its final RESULT.json write and stdout output; the outer start-through-reap
clock includes interpreter startup, that final write/output, exit and cleanup.
Both are reported separately from candidate, preparation, physical checks and
the 600-second seed/MIP/carry ledger. Post-exit archive work is external administration.

The panel exercised 12 LP solves, 8 MIPs and two carry preparations. June seed1
used the unchanged-master discovery-to-proof transition. June seed2 exercised
changed-master row growth: three new rows and 2,643 nonzeros, with 141,878 columns,
active lines [1201, 1378] and map unchanged. Exact carry checks covered all columns,
rows and binaries; the native start was admitted feasible. Its carried source
was a target-feasible diagnostic point with material overflow, not a previously
approved physical endpoint. The later selected endpoint passed full production
quality and physical checks. New-line/column-growth carry and third-MIP execution
were not observed; row-growth coverage does not establish either path.
Default seed 0 retains pure/mock
compatibility coverage and actual empty-native option readback; this v3 panel
contains only seeds 1 and 2. The legacy changed-master tiny has source-level
seed-0 compatibility but no v3 native execution coverage. Cancellation, crash
and OOM behavior remain untested.

## Historical evidence

The v2 full June CLI result and earlier extraction/resource checks remain
preserved, outside this six-run panel. See [provenance/README.md](provenance/README.md)
for their scope. [tests/TINY_REPLAY.md](tests/TINY_REPLAY.md) is preserved
byte-for-byte with its historical implementation-time pending statements;
the actual current seed-1 gate observations above supersede those statements.
