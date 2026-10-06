# Selected next experiment: path-mixing scratch workspace reuse

Selected after all six separator diagnostics identify path aggregation as the
largest measured separator component for dcmulti and gesa2, both main and
sub-MIP contexts. This document is a proposal, not an executed result.

Static evidence: HighsPathSeparator.cpp creates inds, solval, upper, isIntegral,
rhs, tmpUpper and tmpSolval inside each path-mixing attempt; four vectors reserve
num_col+num_row entries repeatedly. aggregatedPath also clears nested vectors
between starts. First narrow experiment: move only the scalar/index scratch
vectors to invocation-local reusable workspace and clear/resize them identically
before each path, leaving aggregatedPath and hash-table lifetimes unchanged.
Measure allocation counts/bytes and time in that block before choosing a patch;
whole path time alone does not prove allocation dominates.

Correctness target: capacity reuse only, identical values, insertion order,
iteration order, row aggregation, random stream, cut calculation and admission.
Freshly zero-initialize rhs after clear/resize as the original constructor does.
No row/cut omitted, no feasibility or bound change, no persistent state across
separation calls. Check early-return and partially transformed-path exits for
stale workspace before a default-off implementation.

Use the same full exposed 7-model / 3-seed diagnostic panel first, preserving all
regressions, and add a genuinely independent, preselected affordable general
MILP panel only if the mechanism and development speed gates pass. Do not claim
SCUC transfer without the still-blocked original inputs and full source/N-1/DC
checks. No further cache-parameter tuning is proposed after the two failures.
