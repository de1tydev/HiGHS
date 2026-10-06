# Serial rating preparation: useful saving, failed advancement gate

Preparing emergency ratings once per checker invocation reduced contained wall by **14.4753%** and subtree CPU by **14.4748%** in this fixed checker-only pair. Scientific equality passed, but the wall saving was below the predeclared **20%** advancement threshold. This version is not promoted; the threshold was not changed, no whole-CLI trial followed, and further checker optimization stopped.

## Result

One exposed October saved SCUC point, 36 hours, fresh serial A followed by B on the same qualified runtime. The physical worker and independent source checker remained unchanged and sequential; native thread pools were verified at one thread.

| Measurement | A: original | B: prepared ratings |
| --- | ---: | ---: |
| Contained physical-process wall (s) | 169.115933 | 144.635836 |
| Aggregate subtree CPU (s) | 169.074605 | 144.601456 |
| Direct separator internal wall (s) | 93.558160 | 71.068994 |
| Independent source checker internal wall (s) | 61.926511 | 60.732358 |

The fixed gate required at least 20% contained-wall reduction and at most 20% aggregate CPU increase. The CPU condition passed; the wall condition failed. Both full arms stayed within 300 seconds and the full phase within 660 seconds. This is a real partial saving in one fixed-order observation, not a general speed estimate or a whole-CLI gain.

Contained wall includes startup, binding/imports, preparation of tuples, validation, serialization/readback and cleanup. Internal clocks are nested. CPU uses exactly one fresh `wait4` subtree user-plus-system result per arm; no earlier arm, child or phase CPU is added again. Sampled tree RSS was 433,729,536 bytes for A and 428,290,048 for B; this is sampled summed RSS, not proven unique memory or an unsampled peak. Archival administration is separate.

## Engineering change and exactness

The [single-file source patch](SOURCE_DELTA.patch) ports the earlier PEGASE89 rating-preparation engineering to `current_scuc/core/driver/fractional_separator.py`. It retains already validated emergency-rating values in independent immutable tuples for the current invocation, then reads those values in the existing outage/line/hour loop. It avoids repeated parsing/validation work; it introduces no new kernel, mathematical algorithm, network formulation or factorization method.

The cache is rebuilt on every invocation and does not alias source lists. Validation order, exception text, finite checks, scalar arithmetic, loop/witness order, coverage and public scope descriptor are preserved. The original independent source-checker code and sequential physical orchestration are byte-identical. No parallel-overlap helper is included. Source review identifies the earlier engineering anchors in [RESULTS.public.json](RESULTS.public.json).

Both full arms checked **1,288 listed outages over 36 hours**, covering 66,360,168 eligible pair-hours and 1,289 topologies per checker. All **2,673 floating-point fields matched bit-for-bit**, together with 9,133 other scalar fields and all ordered outage records. Original point, mapping pairs, witness records, violated-pair bytes and SQLite spill bytes matched exactly. The existing timing/path exceptions remain explicit; the only additional identity difference is the direct-separator source hash, authenticated independently to each frozen implementation. No numerical difference was waived and no unrecorded dense-array parity is claimed. Both retained checked upper 11,738,459.752050288 and zero violated pair or line-hour. This checks an existing witness and establishes no new optimum or physical-DC lower certificate.

Qualification passed 22 predeclared rating cases per arm and three fresh-call states, including finite/error behavior, signed zero/infinity bits, exact validation order, list mutation, immutable prior values and renewed NaN rejection. Tiny/subset scientific and artifact comparisons also passed. All actual checker paths remained sequential and all owned processes were reaped. These are retained results; none was rerun for publication.

## Unpromoted checkpoint

This four-file package contains a concise result, compact authenticated evidence and the exact frozen A/B source delta. The existing patch already matched a newly generated diff of the verified source files and was copied unchanged. The reference source manifest is `97a94cbd0ef8e3289bf584c9c5edac8bb65c304c1a9fca5a6163c2597d67efd5`.

It is not a standalone replay bundle, portable runtime or production-default change. Machine-local runner/configuration, saved inputs and raw archives are omitted. No runtime source, threshold or default was changed for publication; there was no rerun, sweep, whole-CLI trial or further checker optimization.
