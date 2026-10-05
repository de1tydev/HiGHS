# Fresh hard-zero SCUC target reached on June1354

Recorded 2026-10-05 on the exposed 36-hour PEGASE1354 June 1, 2017 case.
The candidate reached the predefined 1% integer target with a **0.270916%
numerical MIP interval**. A separate exact rational certificate from this same
invocation gives a **0.310133% interval** against the final checked upper.
Independent terminal review passed. This is one development sample, with no
matched speed ratio, repeatability or multiple-case claim.

| Quantity | Result |
| --- | ---: |
| Checked original upper objective | 13,779,019.591303479 |
| Conservative solver-reported MIP lower | 13,741,689.973312583 |
| Fresh exact-certified projected-LP lower | 13,736,286.327225514 |
| Positive load shedding / reserve shortfall | 0 / 0 MWh |
| Positive shared overflow | 9.4836559583e-7 MWh |
| Charged contained-process ledger | 143.402847636 / 600 seconds |
| Whole invocation, including checks and stage archives | 555.937916431 / 1,800 seconds |

## Target and checks

This is a new hard-zero target: only the 22,356 originally positive shedding
upper bounds become zero; 26,388 shedding bounds and all reserve-shortfall
bounds were already zero. Original costs and all other domains and physical
constraints are unchanged. Both lower bounds apply to this hard-zero integer
subset of the specified literal binary64 LODF model. They do not bound the old
soft optimum, the larger negligible-shedding domain or the physical-DC optimum.

All 28,080 original binaries passed without rounding, with zero residual.
Fresh original-source feasibility and cost checks, literal-network checks and
independent direct-DC validation passed over all 1,288 source-listed outages
and 66,360,168 monitored pair-hours, with no violated pairs. This is listed-outage
coverage, not all 1,991 lines as outages. The unchanged positive-sum guard is
1e-5 MWh for each slack category. Feasibility and the physical upper remain
numerical at the inherited tolerances; no exact physical-DC lower certificate
is claimed.

## Method and timing

The application/formulation bundle combines the source-valid complete
[5,148-row first-start family](FIRST_START_RESULTS.md), adaptive per-line
network-value cuts, and one permitted discovery-to-proof transition. The solver
is unmodified official HiGHS development commit
`d547a3ad8af5399651187fb0e133cf0e42615b82`.

Two fresh seed LP solves precede one cold discovery MIP and one ordinary proof
MIP. The discovery lower is discarded. With no new violated support at its
checked point, the sole transition uses the identical current master and a
verified start acquired during this invocation. No third MIP or unchanged
failed-proof retry occurred. The exact LP certificate stays attached to its
actual one-installed-batch seed matrix; it is not relabelled as a certificate
of the later promoted master. The numerical MIP lower is a separately admitted
solver report, not an exact certificate. Both reported gaps use (upper-lower)/upper.

The contained ledger includes the seed worker (73.552803691 s), discovery
process (10.854620914 s), start preparation (17.806557207 s) and proof process
(41.188865824 s). It is not native-solver-only time. Native LP time totals
6.895392179 s; the MIP logs separately report 9.69 s and 39.90 s. The whole
invocation includes fresh projection, all run-specific preparation, checks and
stage archives; final physical validation alone took 158.765812067 s. All caps
passed, all seven stage archives were acknowledged, and no process survived.
Independent terminal review and consolidated checkpoint publication are later
research administration, outside the invocation clock.

Timing begins from pinned serialized original MPS and source data. Earlier
original-model export, environment recovery and build are outside that clock;
a comparator must use the same input boundary. The original MPS contains two
historical May security pairs (144 rows), but projection removes all original
network/security rows and starts with an empty support bank. No historical
solver points, bounds or support bank enter this run.

## History and publication limits

The previous hard-zero policy remains a closed negative: checked upper
14,320,683.423559552, gap 4.080791%, and contained ledger 81.701979355 s. It
stopped through policy exhaustion when no new support was violated; it did
not consume the 600-second budget. This new method prospectively adds the
single discovery-to-proof transition. These observations establish no speed
ratio. Earlier checkpoints and correctness advisories remain unchanged. Raw
solver diagnostics were retained and acceptance tolerances were not relaxed.

[Compact evidence](evidence/scuc_target_v1.json) records values and SHA-256
commitments to the audited result, certificate, source and final archive.
Full matrices, vectors and the current runner are not bundled here. This is an
evidence checkpoint: the current method has no published, validated portable
entrypoint. The existing public source and fixed tiny replay still exercise
their earlier aggregate formulation. A matched conventional hard-zero baseline
and fresh confirmation cases are needed before a stable acceleration claim.
