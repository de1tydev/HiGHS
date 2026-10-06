# SCUC continuation: restored runtime, blocked held-out data, working CPU starts

2026-10-06 checkpoint. **No new large-SCUC generalization or acceleration result
is established.** The frozen algorithm was not edited. The predeclared three
inputs could not be downloaded through this environment's network proxy.
Independent restoration, small tests, CPU proposal/repair-interface development
and official-kernel profiling nevertheless completed.

## Restoration and frozen panel

Research baseline `6b2fee0d4c3f5a2b2d595ed6526c3f9e6e9e0eec`; plan registered in
`47d0029bc` before input downloads or solves. Native source is pristine official
`d547a3ad8af5399651187fb0e133cf0e42615b82`, tree
`788b41e141fa455509c71593e1718b7b71168320`, identifying itself as 1.15.1. It is an
exact development commit, not an assertion of equality to every published
1.15.1 benchmark executable. Rebuilt with GCC 14.2.0, two build jobs, prescribed
options and locally generated runtime/helper manifests. Python 3.12.14, NumPy
2.3.5, SciPy 1.17.0, threadpoolctl 3.6.0. Recovered venv initially lacked numerical
packages. Its setuptools startup hook was removed to meet the unmodified clean
startup gate. No `.agents/skills` instructions were present.

Available envelope: 4 CPU cores, 16GiB cgroup memory, approximately 30GiB free
disk at admission. No NVIDIA executable was available; experiments use CPU.
Runtime hashes and compiler identity: [environment.json](evidence/environment.json).
The full runtime manifest/build and all raw tiny artifacts remain in
`/workspace/scuc-native-build` and `/workspace/scuc-campaign`; binaries and public
SCUC datasets are not committed.

- Pure package tests: 90 total across the two suites, 2 skipped, no failures.
- Fixed seed-1 transition tiny: component PASS, 17.189754 seconds reported by
  launcher; original expected candidate NONPASS with 2.25 MWh shared overflow.
  Actual native assessment, carry/proof admission and both physical checks ran.
  See [tiny result](evidence/tiny-test.json) and
  [scientific result](evidence/tiny-scientific-result.json).
- Dedicated SIGTERM check: exact child reaped with return -15; no adopted
  children remained to kill. The wrapper deliberately returns failure on
  interruption. This is a small wrapper test, not SCUC crash/OOM qualification.

| Fixed date, seed 1 | Input status | Large solver calls | Cost/gap/full SCUC QA |
|---|---|---:|---|
| 2017-01-15 | proxy denied CONNECT, HTTP 403 | 0 | unavailable |
| 2017-04-15 | proxy denied CONNECT, HTTP 403 | 0 | unavailable |
| 2017-07-15 | proxy denied CONNECT, HTTP 403 | 0 | unavailable |

Exact URLs and final permitted retry errors are in
[download-receipts.json](evidence/download-receipts.json). Initial urllib reads,
a direct curl check, a www-host check and an approved network retry all received
403; none obtained data. The approved retry did not change access. No access
restriction was bypassed. Official UC.jl v0.3 repository inspection found no
bundled matching input. Downloads stopped. These are **3 input-access blockers,
not 3 solver failures**; solver failure rate is unmeasured, not zero. No dates
were replaced and no large native run started. This input gap also prevents
checked production training-label generation, production warm-start comparison
and SCUC-side kernel profiling.

The registered production policy remains 600 seconds cumulative LP/MIP/carry
process wall, 600 preparation, 1800 candidate, 2460 outer. New learning phases
must debit prediction/repair and related work from the agreed process envelope
and report complete elapsed time separately. No 600-second end-to-end claim.
No new large-case modeling/solve/check timers exist to report.

## CPU learning interface actually implemented

[history_start.py](history_start.py) implements previous-completed-window,
nearest feature vector, and fixed-k unanimous commitment proposals. Future or
overlapping window labels, late-available labels, incompatible column ordering
or topology, and unchecked history are excluded. Integer labels are never
rounded. A consensus with fewer than k eligible neighbors abstains. Features
must be constructed/scaled in a frozen order using training history only.
Vote fractions are not calibrated probabilities. The `checked` input marker
is caller-supplied; this proposal layer does **not** itself verify a production
label receipt. Production adoption must bind labels to the full checker output.

[sparse_start.cpp](sparse_start.cpp) offers named binary suggestions through the
official sparse-solution API. It checks original lower/upper bounds and
integrality before and after the unrestricted solve; it never exposes a repair
subproblem bound as a global bound. This is a standalone client, not a modified
solver kernel or integration into frozen current_scuc. HiGHS' start completion
shares its time limit; a separately reserved repair/fallback wall allocation is
still required before production adoption. No runtime option was loosened in
the frozen package.

[smoke_history.py](smoke_history.py) exercised cold, previous, nearest,
consensus-partial and deliberately infeasible starts on a two-period synthetic
binary model. Every arm returned independently enumerated objective **13** and
passed every original constraint and literal binary value. The 2/4-variable
consensus exercised actual native MIP completion. Nearest and all-zero starts
were infeasible; the unrestricted solver recovered the correct answer. Five
leakage/abstention tests also passed. A second smoke invocation added explicit
label-enumeration accounting; both original and updated raw runs are preserved.
There was no outcome-driven retry or parameter change. This synthetic model
has no transmission network and is **not** evidence of N-1 SCUC feasibility,
generalization, production speedup or an annual rolling result.

Next learning experiment, once permitted source data and checked labels exist:
previous-window/nearest/3-neighbor-consensus comparison with a short separately
bounded completion stage, then an unrestricted original problem using remaining
budget. Freeze a past-only split before this comparison. For 36h windows require
both the entire label window and its computation to finish by cutoff. The old
June/October/December dates must never become future labels for January/April.
First compare identical initial conditions; closed-loop annual operation is a
separate experiment. Charge all label solves, training, inference, failed repair,
fallback and checks when reporting break-even windows and total annual runtime.
No annual number can be inferred from this checkpoint.

## Kernel research remains active, separately scored

[profile.py](profile.py) ran pristine official HiGHS serially at two scheduler
threads, `parallel=off`, 60 native seconds / 75 outer per call. Egout/flugpl
seed-1 diagnostics completed; p0033 was absent and remains a missing slot.
Dcmulti and gesa2 each used seeds 1,2 with profile off/on in opposite seed order.
All ten available invocations returned native Optimal status at the specified
0.01% MIP tolerance. These are native numerical statuses, not independent exact
global-bound certificates. General-MILP endpoints here were not independently
certified; no patched solver or correctness claim depends on these diagnostics.
The initial generic profile wrapper enforced 7GiB address space and disk/memory
headroom but did not separately sample the 6GiB process-tree RSS policy; the
subsequent bounded detailed-profile wrapper did. This monitoring limitation is
retained and these runs do not establish full SCUC resource-envelope compliance.
All raw logs, solutions, options and process receipts are under [profile/](evidence/profile/).

| Model | Seed | Profile off outer s | Profile on outer s | Primal bound (both) | Dual bound (both) |
|---|---:|---:|---:|---:|---:|
| dcmulti | 1 | 3.182358 | 3.159516 | 188182 | 188165.733226 |
| dcmulti | 2 | 1.842882 | 1.947185 | 188182 | 188163.677836 |
| gesa2 | 1 | 0.709186 | 0.705647 | 25779856.3717 | 25778989.9633 |
| gesa2 | 2 | 0.726329 | 0.646230 | 25779856.3717 | 25779678.3345 |

No speed ratio is attributed to an optimization: both arms are the same
library; profiling adds diagnostics and host variation is unquantified.

The four follow-up [profile_detail.cpp](profile_detail.cpp) invocations exposed
existing clocks without rebuilding/modifying the library. All completed:

| Model/seed | Main MIP s | Parent sub-MIP s | Root separation s | Main observations |
|---|---:|---:|---:|---|
| dcmulti/1 | 4.117462 | 3.148786 | 0.771410 | RENS 1.782660s; dive RINS 0.79315s |
| dcmulti/2 | 2.214920 | 1.801980 | see raw TSV | RENS 0.77383s; dive RINS 0.75420s |
| gesa2/1 | 0.75085 | 0.42644 | 0.27890 | root reduced-cost heuristic 0.42911s |
| gesa2/2 | 0.69080 | 0.28485 | 0.36622 | root reduced-cost heuristic 0.28732s |

These clocks overlap and must not be summed. Native clock names include a blank
name and duplicate root-LP names; raw TSV is preserved rather than merged by
name. Sub-MIP records currently do not expose all nested heuristic/separator
clocks. Fourteen actual generic solver invocations completed, plus one missing
input; no timeouts/failures were discarded. This tiny bundled diagnostic set is
neither representative MIPLIB2017 nor the missing SCUC pairing.

Concrete next kernel experiment: in an isolated default-off diagnostic patch,
measure each existing separator's elapsed time and generated/accepted cut count
(main and sub-MIP separately), plus root LP reoptimization cost, on this full
fixed development panel. Current source uses dummy 990/991 clocks for implied
bounds/cliques, so aggregate separation cannot identify the expensive algorithm.
Only after that attribution choose a cut-generation redundancy shortcut or
cost-aware selection change, with mathematical/numerical validation and paired
multi-seed regression. Review the existing CMIR integer-complement checkpoint
before reimplementing it; its older custom-corrected baseline and incomplete
SCUC bridge do not qualify a port automatically. The observed nested heuristics
also justify future bounded neighborhood work, but do not justify repeating the
failed RINS switches/root-IPX/root-credit experiments. **No new core acceleration
patch or speedup is claimed in this checkpoint.**

## Reproduction and remote status

[reproduce.sh](reproduce.sh) gives fresh-build commands and serial tests using
this unchanged package. It requires Python 3.12, GCC/G++, zlib headers, enough
space for the original tiny admission, and permitted Git/PyPI access. The script
was syntax-checked; its constituent commands were executed in this workspace.
The complete fresh script was not rerun as a duplicate build. Individual logs
are portable evidence; paths in raw receipts identify this execution and are
not silently rewritten. Use fresh output directories. `bounded.py` records
start-through-exact-reap wall and checks cancellation/RSS/headroom.

First two research commits were successfully pushed and remote HEAD confirmed
as e260fd8a593d89c7e400d241851091ff756ea4b3. GitHub connector returned no workflow
runs for that commit. The shell gh token failed auth, but git push and the
connected GitHub read worked. No master edit, force-push, merge, deployment,
upstream issue, external benchmark submission or customer-data upload occurred.
Final checkpoint remote/CI evidence is recorded separately after publication.
