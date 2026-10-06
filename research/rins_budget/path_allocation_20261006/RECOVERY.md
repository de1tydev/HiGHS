# Recovery protocol

Preserve the exact source, patch, configuration, dependency identities, fixed
schedule, limits, and stop rule before launch. Complete and verify the source
checkpoint before starting numerical work. Keep official and candidate builds
separate, and identify a fresh runtime explicitly when a previous workspace
cannot be recovered; never silently reuse historical timing as its baseline.

After a bounded experiment terminates, immediately preserve every planned slot,
including failed, incomplete, stopped, and unrun outcomes, plus raw options,
logs, points, checker reports, process receipts, summaries, and source/build
hashes. Keep the terminal backup independent of later prose and publication.
An audit or public projection is an additional artifact, not a replacement for
the raw terminal evidence.

For long builds, take lightweight source/configuration/progress snapshots at
roughly five-minute intervals. This is an intended protocol with a maximum
ten-minute loss window, not a guarantee of storage durability or a fixed
workspace-reset cadence. Do not create periodic heavyweight archives during
short work or overlap backup work with timed solver slots.

A stored item or upload receipt alone is insufficient verification. Retrieve
the actual stored bytes, compare the archive SHA-256 with the original, inspect
the archive member list, and verify every manifest-listed member hash. Preserve
the archive and verification-receipt hashes. The five verified capsules for
this checkpoint are identified without account details in PROVENANCE.json.

If recovery fails, report the missing evidence, preserve what remains, and
restore only from verified source and artifacts. Do not infer a fixed reset
schedule from an absent workspace, host uptime, or one observed loss event.
