# Larger SCUC transfer: no completed target

The combined screening method did not transfer successfully to this larger case under the fixed budgets. Neither seed-0 arm produced a full-security 1% certificate. Both returned the same master-feasible point, which violated two source-listed contingency pairs. **There is no valid speedup ratio.** Seeds 1 and 2 were left unrun under the prespecified stop rule, not replaced with easier observations.

## Case and fixed comparison

The public input is [UnitCommitment.jl 0.3 PEGASE1354, 2017-05-01](https://axavier.org/UnitCommitment.jl/0.3/instances/matpower/case1354pegase/2017-05-01.json.gz), using all 36 hours: 1,354 buses, 260 units, 1,991 lines, 1,432 finite-rated lines and 1,288 explicitly listed line outages. The custom preventive DC model has 1,843,338 eligible security pairs and 66,360,168 finite pair-hours. This is not a claim about all line outages, AC feasibility, generator contingencies, or parity with the default UC.jl formulation.

A starts with no security pairs and solves integer masters before checking all listed outages. B adds the existing cold LP screening policy (at most three 10-second calls, 30 seconds total), the optional near-target root-child credit rule and the validated ratings-preparation optimization. Both use the same executable, two solver threads, parallel search off, the common outer-gap return enabled, initial-root IPX disabled, no inherited point/basis, unchanged costs/slacks and the same 1% final target. Each helper process starts fresh.

The reserved order was seed 0 A/B, seed 1 B/A, seed 2 A/B. Each arm allowed 600 aggregate solver-process seconds, 600 seconds per helper, 1,800 seconds for the complete arm and 7 GiB per process. The common helper limit was prospectively changed from 120 to 600 seconds before any May optimization outcome; all other solver policies stayed fixed. Cumulative storage and live free-space checks retained 2 GiB of disk headroom. All setup, generation, checking and cleanup count in end-to-end time. Actual solver overshoot is charged.

## Observed seed-0 result

| Observation | A: cold integer control | B: combined method |
|---|---:|---:|
| Actual aggregate solver-process seconds | 603.354794 | 602.513816 |
| Complete-process standalone-equivalent E2E seconds | 787.349532 | 802.744750 |
| Generation and API-readback seconds | 24.927062 | 49.769703 |
| Complete integer-check seconds | 155.427953 | 145.246132 |
| Eligible full-security upper bound | None | None |
| Full-security 1% certificate | No | No |
| Violating contingency pairs / line-hours | 2 / 21 | 2 / 21 |

These are consumed-work observations for incomplete arms, not times to the target. The E2E endpoint includes the complete arm process plus the common setup allocation; separately stored in-program values are 787.326490 and 802.722047 seconds. They are not substituted for the complete-process endpoint.

A's MIP returned normally at its time limit, with 3.354794 seconds of charged solver overshoot. B's initial LP was watchdog-reaped at 10.061425 seconds and supplied no accepted witness or cuts. Its 0.061425-second overshoot invalidated the strict LP-cap flag. B then solved a fresh integer master with 589.938575 seconds allocated; it returned normally after 592.452392 seconds. Both arms exhausted the aggregate solver budget. No follow-up security master was solved after the missing pairs were discovered.

The final points are byte-identical. Both pass the loaded master and every nonsecurity source check, with zero load shedding, reserve-shortfall cost, shared overflow and base-network overload. Full checking of all 1,288 listed outages finds maximum emergency-limit excess of 447.816864 MW over 21 line-hours. The source linear cost, 14,409,325.059158, is therefore **not** an eligible full-security upper bound. Both retain the same conservative solver-provided integer-master lower bound, 13,816,961.375212. The logged 4.11% gap concerns the master without the missing security pairs; it is not a full-model certificate gap.

The root-credit rule applied zero caps and zero skips. Its recorded decision was outside the activation band. The short LP provided no pairs. This trial consequently establishes neither successful acceleration nor an activated-cap performance comparison.

## Fidelity, scope and evidence

The measured empty master has 313,776 columns, 381,268 rows and 1,232,507 nonzeros. Four source units have one-point production curves; the additive adapter preserves their exact fixed-output relation, on-cost and zero reserve headroom, together with the original ramp and transition constraints. No marginal cost is invented. Pair storage is compact and shared symmetrically by A/B; every final point still receives the original full-source check.

Before timing, 19 synthetic cases and 23 actual-library readbacks passed all 16 model fields, supported multi-segment models retained byte equality, and a real tiny A/B loop reached checked objective 660 in both arms. All-field equality is numerical; normalizing signed zero in row bounds changes no bound. The actual May model/API preflight also passed without optimization: 817,644 KiB measured peak RSS and 26.002084 seconds through the checked wrapper result. Those are separate construction observations; each timed arm rebuilt its own model and inherited no preflight model or numerical state.

The terminal audit verified all 2,723 runtime pins, the three timed model/API reports, solver/check/selector hashes, pair/witness artifacts and complete process accounting. Both complete arm envelopes exited normally within 1,800 seconds, with no resource or cleanup failure. The final campaign exit code 1 denotes the failed completion gate. These are floating-point checks and a solver-reported bound, not an exact rational proof.

[Machine-readable result and provenance](result.json) retain the scalar observations and immutable hashes. The full local run artifacts remain archived; this compact result publication does not add a larger-case replay command to the existing [portable PEGASE89 package](../portable_combined_replay/README.md). The earlier [nine-pair PEGASE89 results](../combined_results/COMBINED_SCUC_RESULTS.md) remain unchanged.
