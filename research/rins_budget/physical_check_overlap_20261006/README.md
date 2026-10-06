# Physical-check overlap: faster wall, failed CPU gate

This checker-only experiment preserved scientific results but **failed its predeclared advancement threshold**. Overlapping the independent source checker with the direct-DC separator reduced contained physical-stage wall by **23.66%**, while aggregate process-tree CPU rose **27.91%**, above the fixed 20% ceiling. This version is not promoted. No production defaults changed, no whole-CLI trial was run, and no parameter sweep followed.

## Fixed observation

One exposed October saved SCUC point, 36 hours, sequential A then B on the same qualified runtime. A ran the two checks serially. B ran the unchanged source-checker computation in a contained child while the unchanged direct-DC separator ran in its parent; native thread pools were verified at one thread. No optimizer was used to produce a new point.

| Measurement | A: serial | B: overlap |
| --- | ---: | ---: |
| Contained physical-process wall (s) | 166.879450 | 127.401192 |
| Total subtree CPU, user + system (s) | 166.860601 | 213.434954 |
| Direct separator internal wall (s) | 90.819287 | 114.387545 |
| Source checker internal wall (s) | 62.148479 | 84.948918 |

Actual checker overlap was **84.948836 seconds**. Each internal check took longer in the overlapping arm. Shared-resource contention is a possible explanation, but this one fixed-order observation does not establish the cause. It supports no general performance or whole-CLI speed claim.

The fixed gate required at least 20% contained-wall reduction **and** at most 20% aggregate subtree-CPU increase. The wall criterion passed; the CPU criterion failed. Both full arms stayed within their 300-second caps and the full phase within its 660-second cap. Contained wall includes startup, binding, imports, result output/readback and cleanup; checker-internal clocks are nested and must not be summed as elapsed wall. CPU comes from one fresh `wait4` subtree result per arm. B already includes its source child; adding that child's diagnostic CPU again would double-count it.

## Scientific equality and limits

The two numerical checker source files were byte-identical between A and B. Both arms checked all **1,288 listed outages over 36 hours**, covering 66,360,168 eligible pair-hours and 1,289 topologies per checker. All source residual categories and ordered outage records matched; **2,673 floating-point fields matched bit-for-bit**, along with 9,134 other scalar fields. Only the explicitly listed timing/path fields were excluded. Serialized original point, mapping pairs, witness records, violated-pair bytes and SQLite spill bytes also matched. No dense-array equivalence beyond those recorded outputs is claimed.

Both retained checked upper 11,738,459.752050288 with no violated pair or line-hour. This rechecks a saved physical witness; it creates neither a new optimization result nor a physical-DC lower certificate. The preceding tiny/subset equivalence checks and error/cancellation/deadline cleanup controls passed. All owned processes were reaped.

Sampled summed tree RSS rose from 477,306,880 to 523,743,232 bytes. Summed RSS is not unique physical memory and does not prove an unsampled peak. Individual process high-water sums need not be simultaneous; no stronger memory-efficiency claim is made.

See [RESULTS.public.json](RESULTS.public.json) for exact measurements, fixed thresholds, comparison exceptions, source identities and raw evidence hashes. Original evidence archival/readback is separate administration, not checker timing.

## Inspectable, unpromoted source delta

[SOURCE_DELTA.patch](SOURCE_DELTA.patch) is the exact two-file delta between the verified A/B packages: the orchestration edits in `current_scuc/physical.py` and new `current_scuc/physical_overlap.py`. Its bytes were checked against a freshly generated diff of those frozen source files and already matched; neither candidate nor reference was edited for publication. The numerical checker bodies, tolerances, outage scope and arithmetic remain unchanged. The opt-in overlap argument defaults off.

The reference is the published current-SCUC package with source manifest `97a94cbd0ef8e3289bf584c9c5edac8bb65c304c1a9fca5a6163c2597d67efd5`. This four-file checkpoint is an inspectable research result, not a portable runtime, complete replay bundle or default CLI integration. It omits machine-local runner/configuration, saved input payloads and raw archives. No tests, builds, checkers or optimizer calls were rerun to prepare it. The fixed CPU failure is retained, and this version ends here.
