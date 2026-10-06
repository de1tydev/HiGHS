# Native provenance and limitations

This package preserves the exact assessment-only v3 helper source:
`native_assess.cpp`, SHA-256
`b7cd24d5852080cde20e2d0e269783090bfc004fa2f82fb30f92c9b3ecc73d4a`.
The local `current_scuc/native_source_guards.json` inventory binds 16 required
upstream source files to official HiGHS commit
`d547a3ad8af5399651187fb0e133cf0e42615b82`. Runtime consumers check the actual
local guarded bytes before trusting the source-dependent option and diagnostic
rules. The full official tree is
`788b41e141fa455509c71593e1718b7b71168320`.

A source-only check of the recovered upstream directory on 2026-10-06 hashed
all 1,006 files (19,901,776 bytes), including file modes, and independently
reconstructed this exact Git tree. No native operation was performed by that
check. A compact runtime prefix only needs the complete source inventory plus
the exact guarded files after this verification; the prefix's partial source
folder is not represented as a complete buildable source tree.

Two provenance modes are intentionally distinct:

1. `locally_rebuilt_official_source`: a fresh official checkout/build with
   locally measured native hashes and an actual prospective v3 helper compiler
   receipt. Compiler paths, compiler CMake descriptions, cache options, HConfig
   and the helper command are retained
2. `recovered_current_v3`: exact recovered current native binary identities,
   explicitly labeled reused rather than rebuilt. The old helper-build receipt
   naming v1 is not used as v3 proof. Fresh actual helper execution and loaded
   DSO qualification are still required

No runtime manifest claims machine-independent binary reproducibility. A copied
or rebuilt prefix does not make the historical timing observations portable.
Manifest verification is a necessary source/file identity check, not a successful
SCUC run. Scientific functions retain their own effective option, native ABI,
DSO, matrix, numerical, resource, carry and physical admission checks.

The MIT project notice and UC.jl source notice were retrieved read-only from
public repository `de1tydev/HiGHS` at commit
`38c9d7ff0260136db4f86542714f5ea4df7c5ad1` on 2026-10-06. The HiGHS and bundled
third-party notices came from the exact recovered upstream source tree. See
`THIRD_PARTY_NOTICES.md` for direct source links. No dataset license is inferred
from a code license or from a README description.
