# Method and benchmark grounding (2026-10-06)

- Xavier, Qiu, Ahmed, *Learning to Solve Large-Scale Security-Constrained Unit
  Commitment Problems*, https://arxiv.org/abs/1902.01697 : historical-instance
  information informs starts, constraint prediction and affine subspaces.
  Practical translation here: first test CPU nearest-history and partial starts;
  all omitted security rows require complete recovery and final checks. Do not
  transfer the paper's reported speedups to this implementation.
- Nair et al., *Solving Mixed Integer Programs Using Neural Networks*,
  https://arxiv.org/abs/2012.13349 : partial assignments followed by sub-MIP
  completion motivate bounded repair, but a restricted-subproblem lower bound
  cannot prove the original problem. Deep model/GPU training is not a prerequisite
  for testing the partial-assignment interface. This is inspiration, not a
  reproduction or assertion of latest state of the art.

The benchmark name “zimmer” remains ambiguous; the likely intended reference is
Hans Mittelmann's https://plato.asu.edu/bench.html . The official MILP page
https://plato.asu.edu/ftp/milp.html dated 2026-07-07 uses 240 MIPLIB2017 v1
instances after SCIP perturbation/presolve, 2h limits, Ryzen 5900X 12 cores,
128GB; unsuccessful runs receive max time in shifted geometric means. Its
serial HiGHS 1.15.0 and parallel 1.15.1 entries are different configurations.
CPLEX/Gurobi no longer appear on that traditional public comparison. No local
commercial licenses or matching hardware/full suite are available here; our
4-core 16GiB diagnostics against exact development commit d547a3ad8a are not
leaderboard results. The separate MIPFEAS primal-integral benchmark is a
different objective and must not be conflated with proven MILP completion.

Read prior NEGATIVE_TRANSFER.md, INITIAL_ROOT_IPX.md and ROOT_CHILD_CREDIT.md:
root-IPX transfers missed targets; additional UC repair time did not improve
the incumbent; root-child credit missed its predefined improvement gate.
No repetition of those switches is justified without new profiling evidence.
