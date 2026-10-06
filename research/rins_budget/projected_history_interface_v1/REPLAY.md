# Source inspection and bounded replay requirements

This directory is a four-file experimental overlay, not a standalone replacement for HiGHS or `current_scuc`. Keep it beside the published `current_scuc`, `checked_history_interface_v1` and `generalization_20261006` directories. `SOURCE_DELTA_v3.patch` is an inspectable delta from published `current_scuc`; staging uses the byte-identical overlay files directly. The frozen published package is never edited.

## Required identities

- Published base source manifest: `97a94cbd0ef8e3289bf584c9c5edac8bb65c304c1a9fca5a6163c2597d67efd5`
- Official native source commit: `d547a3ad8af5399651187fb0e133cf0e42615b82`
- Qualified probe binary: `64fc588e461c918ead65bd55c9c0dbaa9667f3047d0ba95734e41ea9b48944ca`
- Qualified historical importer review: `d3f28f71864a303c616d1c84e1d41952b966c2f72f0f5c0616d7643bfa70cc9e`
- October raw source: `b64be5dcaec762356291b8ee353ee242869e2a8a0c68859aa477a4431dc1d9d6`

[Source/runtime identities](evidence/SOURCE-IDENTITIES.public.json) preserve the executed manifest and native artifact hashes. The executed staged source manifest also includes machine-local plan paths, so a differently located stage obtains a different manifest. That does not authorize changing any source, adapter or dataset pin.

Build guidance for the underlying runtime remains in [current_scuc/native/BUILD.md](../current_scuc/native/BUILD.md), and the probe source and its bounded build procedure are in [checked_history_interface_v1](../checked_history_interface_v1/). A new build is not automatically the qualified binary: `stage.py` deliberately requires the exact adapter hash above. This publication does not provide a binary distribution or qualify a newly built runtime. Requalification is separate work, not a flag to bypass a hash.

Production history mode additionally requires the complete previously authenticated June recovery capsule accepted by `june_label.py` and its fixed member pins. The public summary, compact label or fabricated `checked` flag cannot replace that capsule. Input data and archive access must be supplied lawfully; no downloader is included.

## Existing commands, conditional on those prerequisites

The following commands describe the qualified interfaces; they were not executed during publication. Set `SCUC_PYTHON` to the qualified clean Python interpreter, `PROBE_BIN` to the exact qualified adapter, `RECOVERY_ROOT` to the authenticated capsule, `RUN_ROOT` to an existing output parent outside the repository, and `NATIVE_ROOT` to the qualified runtime prefix. All stages/work directories must be fresh.

From this directory, stage the tiny profile:

```sh
"$SCUC_PYTHON" -B -s stage.py --out "$RUN_ROOT/tiny-stage" \
  --adapter "$PROBE_BIN" --recovery-root "$RECOVERY_ROOT" --mode tiny_history
PYTHONPATH="$RUN_ROOT/tiny-stage" "$SCUC_PYTHON" -B -s test_seams.py
```

The pure tests use mocks and perform no native solver calls. Staging copies the base into an isolated output, installs only the four overlays, creates an explicit plan and seals its source manifest. `tiny_history` is a synthetic fixture scope; it does not re-admit June under its small admission allowance.

The numerical tiny pair is an explicit separate operation with the existing process limits and a supervising 360-second owner:

```sh
/usr/bin/prlimit --core=0:0 --as=7516192768:7516192768 \
  --fsize=536870912:536870912 \
  "$SCUC_PYTHON" -B -s tiny_pair.py --staged-parent "$RUN_ROOT/tiny-stage" \
  --highs "$NATIVE_ROOT/bin/highs" \
  --runtime-manifest "$NATIVE_ROOT/runtime-manifest.json" \
  --workdir "$RUN_ROOT/tiny-pair"
```

That command alone does not supply the external owner's interpreter-start, exact-reap and publication accounting. Use the same qualified containment/startup workflow as the recorded experiment. Correct tiny success means mechanism PASS and scientific quality NONPASS, preserving the existing overflow fixture; it is not a production-quality gate.

For the recorded production-scope protocol, `stage.py --mode history` creates the experimental package using the same arguments and a separate fresh output. Ordinary cold comparison uses the unmodified published package. Each arm must be invoked once through the qualified outer owner: cold first, then history, seed 1, with fresh preparation and identical runtime, input and resource policy. The ordinary CLI syntax is documented in [current_scuc/README.md](../current_scuc/README.md). Its command alone is not the complete paired supervision protocol.

The limits are unchanged: preparation 600 s; candidate 1,800 s; combined solver/history ledger 600 s; outer supervised CLI 2,460 s; final physical reserve 360 s. The history probe requests at most 25 native seconds within a 30-second process slot, preserving the existing fallback reserve. At most three actual integer processes are allowed. A rejected launched probe leaves two ordinary logical slots; no timer or attempt counter resets. [PROTOCOL_AMENDMENT.md](PROTOCOL_AMENDMENT.md) defines the exact admission/failure and tiny-versus-production boundaries.

This package makes the completed fixed result inspectable. It is not an instruction to rerun, broaden the panel, tune the probe after observing October, or infer portability from source equivalence. Original raw archives and post-exit archival administration remain separate from the compact public evidence.
