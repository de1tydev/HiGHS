# Constructor-derived security seed v1: development result

The fixed policy failed its predeclared advancement gate on the exposed February 2017 PG89 case (36 hours, solver seed 0, order A/B/C). All three arms completed an original-source numerical 1% certificate. The seed replacement was slower than both comparators. Confirmation and larger-case diagnostics remain unrun.

| Arm | Initial preparation | Actual solver seconds | Complete-process E2E seconds | MIP masters | Final gap |
|---|---|---:|---:|---:|---:|
| A | Original cold integer screening | 36.822558 | 52.269013 | 2 | 0.986055% |
| B | Current bundle: two LP discovery calls | 24.129854 | 44.098132 | 1 | 0.986055% |
| C | Source-derived non-primal cut seed | 66.456904 | 83.464556 | 2 | 0.978493% |

C increased solver time by 80.48% and E2E by 59.68% against A; against B the increases were 175.41% and 89.27%. The gate required at least 20% improvement against A on both endpoints and strictly better E2E than B, with all three certificates valid. It failed. This single exposed development result supports no stable acceleration claim.

The common original objective was approximately 3,534,678.762427. Every final solution had zero shedding, zero shared overflow, and 36 zero reserve-shortfall columns. Every master passed all 16 loaded-model checks; each arm's final solution passed the independent original-source/all-listed-outage checker. Each arm stayed within its 600-second actual solver and 1800-second containing limits; the complete campaign took 179.308 containing seconds, with no watchdog kill, resource failure, or adopted-child cleanup.

## Recorded mechanism

C's seed helper completed in 1.857109 seconds and selected nine original pairs; preparation through the pre-final-checkpoint measurement took 2.169695 seconds. One omitted pair violated the first MIP point, requiring the ordinary second cold master.

| C master | Active pairs | New pairs | Solver seconds | Generation/API seconds | Check seconds | Nested root-child seconds |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 9 | 1 | 30.746298 | 2.408851 | 3.110293 | 26.435795 |
| 2 | 10 | 0 | 35.710606 | 2.559447 | 3.060526 | 31.512564 |

The nested intervals are diagnostic portions of solver process time, not additional budget debits. B's sole MIP recorded 18.069839 nested root-child seconds. Root credit applied one cap in each C master and one in B's MIP. The first C point was not an eligible full-source upper bound. The second solve carried no incumbent, basis, point, or objective cutoff; it was a new cold process with validated original rows.

C's final master had 21,096 columns, 1,296 binaries, 24,396 rows and 82,263 nonzeros. B's had the same columns/binaries, 24,540 rows and 82,695 nonzeros. Their exact MPS hashes differ, as expected for different selected row sets:

- B: c3c8dc7c4541bbe8f10808c69661d91866ece69bbe5baa14abdb42c3ac235d8b
- C: 3a31807da69a0868d5b3f115959bfd52ce6f632dbf5d6769ea4f6b8be2232167

The complete-process E2E endpoint includes the fresh containing arm through reap plus charged common setup. Provisioning is separately recorded. A/C is the complete-bundle comparison; B/C compares initial-preparation replacement. The constructor's non-primal role and original objective, constraints, slacks and certificate rules were unchanged.

## Scope and evidence

The source is the public [UnitCommitment.jl PEGASE89 February case](https://axavier.org/UnitCommitment.jl/0.3/instances/matpower/case89pegase/2017-02-01.json.gz). This is the custom preventive DC formulation used in the earlier work, with 192 explicitly listed outages out of 210 lines and the original soft-constraint semantics. It is not an AC or every-possible-line-outage certificate. Primal feasibility and objective were independently checked; lower bounds come from HiGHS and include the conservative printed-precision allowance.

Both initial screening approaches start without learned pairs. C fixes the source initial commitment only inside a deterministic arithmetic probe, then performs a complete direct outage sweep. The probe can select valid original rows but is never a primal, objective cutoff or lower bound. Every selected pair expands to the original signs and finite hours. Subsequent masters use the ordinary full checker and add all newly violated original rows.

All arms use the same validated experimental binary, two threads with parallel search off, and the same 1% final target. B and C both enable the existing root-child credit and optimized separator; C replaces B's bounded LP discovery. A has those bundle components off. The timing comparison is for this frozen adapter and single exposed seed, not a new confirmation of the earlier nine-pair results.

The [machine-readable projection](result.json) preserves exact timing, certificates, stage/model/source/runtime hashes and method attribution. Its source raw archive contains 197 artifacts totaling 70,066,172 bytes, with manifest SHA256 `1c8c81e627b56a3d15b3f11674c84e351f1182f173d55e30acbf18dfc8bf76ca`. Large raw models and private execution paths are omitted from this checkpoint.

Validation passed before timing: 127 pure tests, 13 synthetic numerical fixtures with eight actual-library model readbacks, and a separate tiny A/B/C route. The terminal result audit verified all seven development model readbacks, final source/security certificates, exact stage and timing projections, and the unchanged runtime. No rerun was used to rescue the failed gate. Reserved May/June/September PG89 confirmations and June1354 diagnostics remain unrun under this policy.

This checkpoint reports a rejected research policy; it does not add a supported replay entrypoint. The previously validated [portable combined replay](../portable_combined_replay/README.md) remains available.
