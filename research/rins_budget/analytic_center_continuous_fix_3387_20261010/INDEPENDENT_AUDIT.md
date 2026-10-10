# Independent source and terminal evidence review

Reviewer: independent source/evidence reviewer, 2026-10-10.

PASS for the exact three-line candidate scope: the guard skips only kContinuous; analytic-center calculation, central rounding and ordinary propagation remain unchanged. One of 1006 source files differs. Patch and runtime identities remain separate from the previously qualified reference.

PASS for eight main tiny cases and ten unchanged native tests: reviewer rehashed all 18 raw logs, checked ten loader-initialization paths and all eight process-map/DSO hashes, and verified 88 native assertions. Release compile records contain NDEBUG; assertion records do not. Original MPS Git blob matches 22afeec6fe42d56c1cd924a7b76d06601a5f77bc; the MIN fixture differs only in objective sense and sign. Independent exact-Fraction witness checking gives zero residuals with k=4722366482869645/2361183241434822606848 and g=1. Returned candidate primal residuals are zero in off arms and approximately5.05e-15 in on arms; bounds and integrality checks pass.

PASS for all six prior-backport processes: three fixture/data files match their exact published Git blobs; executable hashes, DSO pins, raw summaries and single candidate loader initialization are verified. The four #3357 combinations per build pass; #3364 valid-CSC and #3359 objective/primal checks pass.

The historical candidate runner predicate checked model status/objective and recorded run status; all observed run statuses are0. The portable replay additionally checks run status. Its separate smoke check is not part of the independently reviewed eight-arm matrix.

Limits: no whole-suite rerun, no SCUC/performance result, no reference promotion. Retained integer analytic-center fixing remains unproven. Existing native tests retain original per-test thread settings, not a global one-thread guarantee. The historical qualification's affinity exception is not repaired or retested here. Numerical proximity can no longer remove continuous-column feasible solutions through this particular stage, but this is not a blanket correctness certificate.
