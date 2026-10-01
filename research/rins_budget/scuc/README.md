# Public UC / DC-SCUC reproduction pack

Prepared 2026-10-01 from public primary sources. This is a **custom MILP formulation using unchanged public input data**, not an export of the official UnitCommitment.jl JuMP formulation and not an operational grid model. No synthetic ratings, loads or unit multipliers were added.

## Cases and honest labels

| Official v0.3 dataset, 2017-02-01 | Hours | Buses | Units | Lines | Explicit finite ratings | Listed line outages | Appropriate use |
|---|---:|---:|---:|---:|---:|---:|---|
| matpower/case57 | 36 | 57 | 7 | 80 | 0 | 79 | Small UC control; not a meaningful network test |
| matpower/case118 | 36 | 118 | 54 | 186 | 0 | 177 | Larger UC control |
| matpower/case300 | 36 | 300 | 69 | 411 | 0 | 320 | UC control only; not pursued |
| matpower/case89pegase | 36 | 89 | 12 | 210 | 77 | 192 | Network UC and preventive DC security test |
| matpower/case1354pegase | 36 | 1354 | 260 | 1991 | 1432 | 1288 | Next larger finite-network input, prep only |

The February and August 1 files for case118 and case89pegase are archived. `data_manifest.json` has source URLs, hashes of compressed and decompressed bytes, sizes/parameters and source attribution. Hosted data may change, so byte hashes are the reproducibility identity. UC.jl v0.3.0 reference code revision is `6573bb7ea2d5da5eff4a190744edc5a392e90c98`; **do not imply the separately hosted data are pinned by that code commit**.

PEGASE89 has 192 LISTED outages, not every possible non-islanding outage. The 18 excluded lines include 16 graph bridges and two additional non-islanding lines, `l65` and `l69`. A passing check covers exactly the supplied 192 line contingencies. There are no listed generator outages. UC.jl describes non-islanding line outages in general, but the actual JSON is authoritative here.

## Reproduce

Python 3 with NumPy and SciPy is required. HiGHS must be built separately from its official source. The measured executable is HiGHS 1.15.1, git `73cac48`, from an unchanged Release build. All timings use one solver thread, parallel search off, seed 0 unless explicitly stated.

Download hash-verified inputs:

```sh
python download_data.py --case case89pegase_2017-02-01
```

Generate network UC, exact all-listed-outage static model, or larger copperplate UC control:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python generate.py data/case89pegase_2017-02-01.json.gz --mode network --output models/network.mps
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python generate.py data/case89pegase_2017-02-01.json.gz --mode n1 --output models/full_n1.mps
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python generate.py data/case118_2017-02-01.json.gz --mode uc --output models/uc.mps
```

The default horizon is all 36 input hours. `--hours 24` is available but is a **truncated derivative**, not the unchanged 36-hour instance. No such truncation was used for reported solves.

The main benchmark target is **1%: `mip_rel_gap = 0.01`**. `smoke.options` is a separately labeled stricter test (`0.0001`, or 0.01%). Never mix these targets in an A/B comparison.

Use exact finite constraint generation with one 300-second TOTAL wall budget, including model generation, solving, and checking:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python screen_and_solve.py data/case89pegase_2017-02-01.json.gz --highs /path/to/highs --output-dir runs/seed0 --budget 300 --gap 0.01 --seed 0
```

For paired solver comparisons, seed BOTH arms with the same archived 12-pair set:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python screen_and_solve.py data/case89pegase_2017-02-01.json.gz --highs /path/to/highs --output-dir runs/armA_seed0 --budget 300 --gap 0.01 --seed 0 --initial-pairs models/case89_screen_pairs.json
```

No primal incumbent is inherited. The initial pairs were selected from a previously computed network-UC solution; this is an explicitly pre-screened-start comparison. It is not a cold-start end-to-end screening result. Run seeds 0,1,2 with alternating arm order, serially. Every arm must recheck all listed contingencies and add newly violated pairs; comparison uses TOTAL loop time, final independently checked incumbent and master bound. The static screened MPS alone is only a relaxation for an arbitrary new incumbent.

The driver terminates with status 2 for partial/failed results; it does not treat an unchecked master incumbent as full SCUC. It rejects nonfinite bounds/invalid parameters and lower bounds above the validated incumbent. A generation/check overrun is reported and cannot claim completion within the budget. Report floating-point numerical feasibility/gap certificates, not exact rational proofs. HiGHS may ignore very small coefficients; inspect solver logs for any dropped-coefficient warnings before interpreting lower bounds as those of the algebraic source model.

Independent check of a HiGHS style-0 solution:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python check_solution.py data/case89pegase_2017-02-01.json.gz solutions/case89_screened_main.sol --mode n1
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m unittest discover -p 'test_*.py' -v
```

The nine portable generator-semantic tests in `test_model_semantics.py` construct tiny synthetic inputs and enumerate commitment schedules. They do not import or test the independent solution checker, and are not public-grid benchmark data. Three additional portable driver-hygiene tests cover output-directory reuse and dropped-coefficient warnings.

Separate earlier mutation checks used locally archived solutions to exercise the independent checker with fractional commitment, perturbed flow, negative shedding, uniform angle translation, and a base-network solution that fails security. Those archived-solution mutation checks are not the portable generator test suite. The checker does not import the generator or use its matrix/LODFs; it reconstructs generator/time logic and costs from source JSON and re-factors every outage topology. Raw datasets, generated MPS files and solution files are excluded from this publication package; reproduce them using the commands above. The portable tests require none of those files.

## Formulation and scope

- Three binaries per generator/hour: on, start, stop; transition equality, exclusive start/stop, minimum up/down windows, and residual initial obligations
- Convex incremental production segments, full dispatch variable, source no-load and incremental costs. Segment caps are multiplied by commitment
- Nonnegative startup-cost epigraph with monotone source downtime categories. It represents the correct integer objective but has a different LP relaxation from UC.jl's startup-category binaries
- Spinning reserve eligibility, source reserve requirement and shortfall penalty. A negative/missing shortfall penalty fixes shortfall to zero, hence hard reserve requirements in these data
- Dispatch plus reserve obeys capacity and startup capability. Ramp-up includes current reserve; ramp-down includes previous reserve. Shutdown capability includes reserve. This convention is present in the downloaded ArrCon2000 source; it can be stronger than a checker that tests only scheduled production on ramp-down. No terminal commitment obligation after the last hour is imposed
- Initial power is enforced in the first ramp transitions; there is no fictitious pre-horizon reserve. Explicitly conflicting must-run/residual downtime inputs are rejected
- Nodal DC balance and `flow = source susceptance × (theta_source − theta_target)`, one fixed reference angle. Uses the supplied susceptance, not silently recomputed `1/reactance`. No AC voltage/reactive power/losses, transformer tap/phase-shift reconstruction or frequency/security dynamics
- Source load curtailment is bounded between zero and the actual load at each bus/hour; source penalty is $1000/MW per hourly step. No surplus-dump variable and no arbitrary injection slack
- Source line overflow is one **shared nonnegative, unbounded slack per monitored line/hour**, charged once ($5000/MW here) across normal and all emergency constraints. The default models are therefore penalized-soft-line-limit formulations, not unconditional hard-feasibility models. Report both relaxed and unrelaxed residuals and actual slack usage. The successful measured solutions use zero shedding and zero overflow
- Preventive dispatch is unchanged after outages; no contingency redispatch or reserve deployment. No generator failures or islanding contingencies are silently approximated. Only listed single-line outages are supported
- Security rows are `±(f_monitored + LODF[monitored,outage] f_outage) − overflow ≤ emergency_rating`. No dense per-contingency variable blocks. No generator-side LODF/PTDF cutoff
- UC.jl documentation says missing flow ratings default to infinity; its v0.3 reader actually substitutes `1e8` MW. This custom code uses infinity. On current positive-susceptance PEGASE89 and IEEE118 data, total generator maximum output is only 11,342.21MW and 9,874.62MW respectively, so the 100-million-MW omitted ratings are physically inactive. Treat this as a documented implementation difference. IEEE300 has negative susceptance and is not used for a network-equivalence claim
- UC.jl normally applies its repair routine and its default formulation applies PTDF/LODF cutoffs (0.005/0.001). This code does neither. It rejects unsupported nonconvex curves, time-varying production curves, non-hourly steps, price-sensitive loads, generator/multiple-line contingencies or reserve products other than spinning. It is deliberately a restricted custom model

## Initial measured results (not A/B evidence)

| Model | Matrix rows / columns / nonzeros | Result |
|---|---|---|
| IEEE118 36h UC | 33,066 / 23,724 / 132,642 | 14.70s, objective 5,767,414.999062, bound 5,763,338.47632, gap 0.0707%, target 1%; source checker passes |
| PEGASE89 network UC | 23,676 / 21,096 / 80,103 | 27.07s, objective 3,203,022.065125, gap 0.00703%, stricter target 0.01%; no slack. Fails 314 line-hours under listed outages, worst 1,204.286MW |
| PEGASE89 full static N-1 | 1,083,588 / 21,096 / 3,100,143 exported | 45.79 solver seconds / 50.94 total seconds, no incumbent at limit; maximum RSS 2,052,092KiB. 149,752,475-byte MPS |
| PEGASE89 12-pair master, all-outage checked | 24,540 / 21,096 / 82,695 | 33.30s, feasible full objective 3,534,678.762427, master bound 3,499,824.901948, numerical gap 0.986055%; target 1%; all 192 listed outages pass, no slack |

The 12-pair master is 4,018,423 bytes, SHA-256 `c3c8dc7c4541bbe8f10808c69661d91866ece69bbe5baa14abdb42c3ac235d8b`. The independent all-outage residual is at most 2.3e-11MW; phase-flow residual is below 7.5e-10MW. The master uses 12 of 14,721 eligible monitored/outage pairs. Active and omitted lists, indexing and hashes are in `models/case89_screen_pair_manifest.json`. Removing inequalities yields a valid lower bound for the full custom model; the independently checked incumbent yields an upper bound. This certificate is for this source data/model/solution, not every solution of the 12-pair relaxation.

The full-static run emitted 33,840 roundoff-scale coefficients of magnitude at most 9.57312e-15 which HiGHS ignored at its default 1e-9 small-matrix threshold. The 12-pair screened matrix contains no coefficient at or below that threshold. The failed full-static run's lower bound is not used for the successful certificate.

The exploratory screening computation reused the earlier 27.07-second strict network solve, then generated/check-separated 12 pairs and ran the 33.30-second 1% master. Sum of solver time is 60.37 seconds; generation/verification add a few seconds. This is a manually coordinated pilot, not a recorded fresh 300-second driver run. The driver enforces the global budget for future comparisons. No speedup claim follows from these initial runs.

## Next case and resource plan

PEGASE1354 has 260 units and 1432 finite-rated lines. Its 1288 listed outages imply exactly 1,843,338 line pairs and **132,720,336 security rows** for a static 36-hour expansion, before unit/network rows. Do not build that full MPS on this machine. Start with the base network and exact separation; profile generation, direct-check time and RSS before any enlarged run. A dense 1991×1991 LODF matrix is only ~32MB, but direct checking all 1288 topologies and MILP memory can dominate. Input preparation alone does not establish a solve-time guarantee.

## Primary sources and attribution / license

- UnitCommitment.jl official source: https://github.com/ANL-CEEESA/UnitCommitment.jl/tree/v0.3.0
- Data catalogue: https://axavier.org/UnitCommitment.jl/0.3/instances/
- Format: https://anl-ceeesa.github.io/UnitCommitment.jl/0.3/format/
- Benchmark construction: https://anl-ceeesa.github.io/UnitCommitment.jl/0.3/instances/
- UC.jl citation: A. S. Xavier, A. M. Kazachkov, O. Yurdakul, F. Qiu, UnitCommitment.jl (v0.3), Zenodo 2022, https://doi.org/10.5281/zenodo.4269874
- MATPOWER: R. D. Zimmerman, C. E. Murillo-Sánchez, R. J. Thomas, IEEE TPWRS 2011, https://doi.org/10.1109/TPWRS.2010.2051168
- PEGASE: C. Josz, S. Fliscounakis, J. Maeght, P. Panciatici, https://arxiv.org/abs/1603.01533; S. Fliscounakis et al., https://doi.org/10.1109/TPWRS.2013.2251015
- Original PEGASE1354 case and license notice: https://github.com/MATPOWER/matpower/blob/7.1/data/case1354pegase.m
- Original PEGASE89 case and license notice: https://github.com/MATPOWER/matpower/blob/7.1/data/case89pegase.m

The source PEGASE data are fictitious research networks, not operational European grid data. The original PEGASE89 and PEGASE1354 headers license these data under Creative Commons Attribution 4.0, https://creativecommons.org/licenses/by/4.0/. UC.jl code's modified BSD notice is preserved in `sources/UCjl_v0.3.0_LICENSE.md`; original source headers and attributions remain in downloaded JSON. MATPOWER explicitly states its software BSD license does not automatically cover all case data; do not apply the code license indiscriminately to datasets. Downloaded data and generated model/solution artifacts are excluded from this source package.

## Publication-time replay guards

The published screening driver requires a new output directory and refuses to certify an original-model bound when HiGHS reports ignored/dropped matrix coefficients. These guards were added after the recorded six-arm experiment. All recorded arms already used fresh directories and had no such warnings, so the observations are unaffected. `SOURCE_MANIFEST.json` at the research-package root retains both the historical measured driver hash and the current published driver hash. Solver-free guard tests are in `scuc/test_driver_hygiene.py`.
