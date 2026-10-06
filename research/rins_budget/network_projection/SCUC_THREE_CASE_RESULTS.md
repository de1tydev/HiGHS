# Three-case SCUC completion comparison

The recorded projected workflow reaches the declared 1% hard-zero SCUC target
on June, October and December PEGASE1354, each for 36 hours and seed 0.
Each conventional ordinary-proof run returns a master point that fails the
complete literal security check and admits no full-target upper within its
600-second contained-process budget. These are three descriptive completion
records with different exposure histories, not evidence of stable acceleration
or a timeout-derived speed ratio.

All listed terminal evidence and archive audits passed. A passing evidence
audit verifies the recorded outcome; it does
not imply that the scientific target was reached.

| Case and exposure | Candidate checked upper | Fresh exact-LP lower | Candidate interval | Contained process, candidate / reference | Conventional full-target result |
| --- | ---: | ---: | ---: | ---: | --- |
| [June 1](SCUC_REFERENCE_RESULTS.md): exposed development | 13,779,019.591303479 | 13,736,286.327225514 | 0.3101328349% | 143.402847636 / 597.608062564 s | No admitted upper; two new violated pairs |
| [October 1](SCUC_OCTOBER_RESULTS.md): case-exposed validation | 11,736,221.140286218 | 11,732,175.309109941 | 0.0344730312% | 97.685884136 / 597.846746922 s | No admitted upper; one new violated pair |
| [December 1](SCUC_DECEMBER_RESULTS.md): first preselected numerical validation in this release | 12,019,778.55028609 | 12,015,900.154340627 | 0.0322667837% | 85.001169514 / 597.666292956 s | No admitted upper; one new violated pair |

Every displayed candidate interval is `(upper - exact LP lower) / upper`.
June also has a separately admitted numerical MIP lower of
13,741,689.973312583, giving 0.2709163576%; it is not mixed with exact-LP
intervals in the table. A conventional master's printed objective and gap do
not become a full-target upper or interval when its returned point fails
complete security checking. No successful conventional completion time is
available, so no speedup ratio, mean, median or pooled timing statistic is
reported.

## Timing boundaries must stay visible

| Case | Candidate whole invocation | Reference whole invocation | Archive boundary |
| --- | ---: | ---: | --- |
| June | 555.937916431 s | 695.883742347 s | In-run stage archives and remote acknowledgements included |
| October | 328.407928192 s | 648.999994709 s | Local checkpoints included; post-exit remote archive administration separate |
| December | 314.687321048 s | 649.582069442 s | Local checkpoints included; post-exit remote archive administration separate |

All arms have a 600-second aggregate contained-process cap and an
1,800-second whole cap. Contained ledgers include charged subprocess work
and are not native solver-only time. The whole clocks include fresh
run-specific transformation/factors, export/readback, numerical/physical
checks and cleanup from pinned serialized original MPS and source data.
Acquisition, original-model generation, setup/build and later independent
audit are outside the arm clocks. June and the later local-checkpoint runs
must not be pooled as a common end-to-end timing series.

## What these cases establish

All three candidate uppers pass original-source, literal-network and
independent direct-DC checks for the 1,288 source-listed outages and all
66,360,168 eligible pair-hours. All 28,080 original binaries are checked
without rounding. Load shedding and reserve shortfall are exactly zero;
positive shared overflow remains small and priced, below the frozen 1e-5 MWh
per-category guard. The exact lower concerns the stored binary64 literal
LODF hard-zero integer subset, whereas the physical upper is a numerical
witness. It is not an exact physical-DC lower or a bound for the former
soft-shedding objective domain.

All cases use unmodified official HiGHS commit
[`d547a3ad8af5399651187fb0e133cf0e42615b82`](https://github.com/ERGO-Code/HiGHS/commit/d547a3ad8af5399651187fb0e133cf0e42615b82).
The tested change is an application/formulation and allocation-policy bundle:
network projection, complete source-valid first-start cuts, fresh seed LPs
and network-value cuts, with the admitted discovery/proof policy. The
conventional arm uses cold ordinary original-DC proof. Historical points,
bounds, cuts, starts and search state are not loaded. The comparison does not
isolate a HiGHS internal patch or a single technique.

June informed development and exercised one same-master discovery-to-proof
transition. October was preselected but became exposed after an earlier
remote-acknowledgement failure and saved-point diagnosis; both remain in its
history. December is the first preselected numerical validation evidenced by
the frozen release, with earlier source-only metadata and preparation exposure
disclosed. This classification does not claim proof that no unrecorded outside
exposure occurred. October and December ended after their first MIP, leaving
their carry paths untested. Each case uses only seed 0. No multiseed,
repeatability or broad MILP conclusion follows.

## Portable implementation evidence is separate

The [published portable validation](https://github.com/de1tydev/HiGHS/blob/cf0fc39cf63bf382f91e0ac0530e512b32223df5/research/rins_budget/current_scuc/VALIDATION.md)
records independent code-parity review, 52 pure tests and
a relocated tiny test that reaches an unchanged-master transition, admits the
current-run start and verifies process reaping. The tiny candidate itself
does not meet the hard-zero/slack target because shared overflow is
2.25 MWh; the test pass covers the stated transition and checker behavior.
The first changed-master coverage attempt fails before carry because no
materially violated new support is found, and is not counted as changed-master
coverage. Cancellation/kill paths are covered only by mocked tests, and the
native prefix/runtime was reused rather than independently rebuilt.

No production-size execution through the portable CLI is established, and
the three full-case records above must not be attributed to it. The historical
public aggregate replay, prior negative outcomes, interrupted attempts and
correctness advisories remain preserved. [Compact three-case evidence](evidence/scuc_three_case_v1.json)
maps this summary to the published June/October evidence and the new
[December evidence](evidence/scuc_december_v1.json), without private paths or
archive account identifiers.
