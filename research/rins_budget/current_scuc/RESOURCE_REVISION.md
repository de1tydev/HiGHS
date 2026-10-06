# Portable resource revision v2

Base publication commit: cf0fc39cf63bf382f91e0ac0530e512b32223df5.
Base package source manifest: b2bcc4dc84d77eb1e5f5491bfbc1e15947f886720c439ee7595ec0ba0b6aa164.
The published/tested directory was copied, then left untouched. Its source and
artifact manifests and validation description are preserved under provenance/.

The adopted four-file patch has SHA256
cd5fc24522a156f1a9841b942489bb3a42ee056e8f9f9290f0967c81d50bd1bb, from proposal
27a414f489d4b3eb9eca08887243824756f0c166df02fe2eb771f9f4265e40aa. It adds qualified
SQLite MEMORY/readbacks, CORE 0/readbacks and the earliest CLI limit call.
The additional thin resource delta fixes candidate storage admission to 11 GiB,
adds fixed 16 GiB admission before runtime discovery/preparation, and updates
the formerly unused phase constant and protocol metadata consistently.
No caller can select an arbitrary lower threshold. Existing filesystem, active
writer and phase reservations remain; 4 KiB allocation is mandatory.

The accepted writer proof maxima are 10,995 MiB candidate and 16,243 MiB complete
CLI, including the unchanged 2 GiB free floor and 1 GiB launch margin. The full
CLI bound includes preparation, four root JSON files, one 512 MiB outer log and
one 128 MiB outer receipt. The owner must inherit CORE 0, AS 7 GiB and FSIZE
512 MiB before CLI interpreter startup. Qualified startup directories contain
no startup hooks; bytecode is disabled. Other owner files/archives need another
proof and are not part of the planned run. This does not prove RAM sufficiency.

Every scientific source file, solver/native option pin, clock and mathematical
threshold is byte-identical to baseline. Existing witness helpers/methods except initialization,
all SQL schema/INSERT/SELECT text, record format, ordering and caps are unchanged.
The reviewed single June invocation accepts no historical prepared model, cuts,
point, factor, bound, basis or solver state as runtime input.

The reviewed run preserves preparation 600 seconds / worker 300 seconds,
candidate 1800 seconds, actual seed/MIP/carry start-through-reap ledger 600 seconds
and an outer allocation of 2460 seconds including cleanup. There is no comparator,
ratio, retry, tuning, alternate case or forced carry coverage. The single full June CLI
invocation completed and reported a pass; a read-only independent terminal audit
verified the saved QA evidence and byte bindings.
See VALIDATION.md and evidence/june-cli-result.json for its scoped result.

RESOURCE_REVISION.json preserves a labeled prelaunch record with private receipt
locations removed and receipt sizes/hashes retained. Its historical status flags
remain unchanged. The original prelaunch narrative is preserved under provenance/.
The runtime SOURCE_MANIFEST.json identifies the tested resource source; the
ARTIFACT_MANIFEST.json identifies these public distribution bytes. The original
resource artifact manifest and baseline projection/binding records are retained
under provenance/. Historical attribution is conditional on the relevant source
bytes remaining identical; it does not claim edited files retain old hashes.
