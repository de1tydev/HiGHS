# Next experiment: separator cost attribution after both cache speed failures

V2 finished 21 successful pairs but missed the fixed median improvement gate
(-4.2868% vs required <=-5%; worst +11.3154%). Do not tune a third cache version.

Next bounded experiment: a diagnostic-only patch to the pristine official
commit, enabled only at log_dev_level >=2, times each implied-bound, clique,
tableau, path-aggregation, mod-k and machine-scheduling separator and LP
reoptimization, reporting pool-size deltas and LP iteration deltas. Clock each
call immediately around original code, print afterward, retain parent/sub-MIP
identity. Pool-size delta is not an accepted-global-cut count or validity proof.
Do not sum nested/inclusive categories or compare logged wall as acceleration.
No solver decision/cut selection/parameter heuristic changes are introduced.

Six fixed diagnostic calls: dcmulti and gesa2 seeds 1,2,3, 60 native /75 outer,
same serial resources and original matrix checker. Separate official worktree
and build; both cache versions remain untouched and retained. All outcomes
persist. Stop at resource/process/checker failure. This can identify the next
algorithmic target but cannot itself establish an optimization.
