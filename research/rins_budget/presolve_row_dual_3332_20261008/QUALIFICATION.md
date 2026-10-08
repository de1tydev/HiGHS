# Bounded native qualification of the isolated #3332 correction

## Outcome
Focused assertion coverage passes. Release integration has the single known affinity-test exception; the original full-suite failure is retained. A separate fresh-process aggregate excluding only that exact test passes. No new failure was observed in the exercised inventory. After review, this exact corrected source/runtime was conditionally admitted for future explicitly scoped research with explicit native solver thread settings and the affinity exception retained. Historical baselines are unchanged.

### Focused native assertions
- 119 selected cases executed in separate processes: all returned success.
- 918 assertions pass across 118 assertion-bearing cases; the existing get-integrality case has zero assertions.
- The official implied-row-dual-bound-invalidation test contributes 14 passing assertions.
- The inventory is the historical 118-name focused inventory plus this new #3332 case. Historical baseline results were not rerun or represented as new-boot native comparison evidence.
- All three existing standalone regression families (#3357 four cases; #3364 CSC check; #3359 optimum 25 with original-model feasibility) also pass.

### Release CTest inventory
- All 169 configured CTest entries were executed once, individually and serially.
- 168 passed. The sole failed entry is unit_tests_all; its CTest return code is 8.
- Raw aggregate: 401 test cases, 400 passed, one failed; 1,260,063 assertions, 1,260,062 passed, one failed.
- Literal failure: TestHighsParallel.cpp:348, REQUIRE(cores == 1), expansion 5 == 1, in AffinityReducedCoreCount.
- No timeout occurred. The three standalone regression families pass under the same Release DSO after the CTest inventory.
- Verbose output plus output-on-failure prints the failed unit aggregate twice in its log. This is duplicated reporting from one invocation, not two suite executions.

### Fresh-process exact-exclusion aggregate
The affinity test aborts at REQUIRE before its normal restoration/shutdown lines, so later cases in that same failed aggregate may inherit missing cleanup. To separate coverage from that risk, a new unit_tests process was run with exactly ~AffinityReducedCoreCount. Full and filtered inventories were checked: precisely that one case was excluded; all other 400 remained. All 400 cases and 1,260,062 assertions passed. The original CTest result was not changed, and the failed affinity test was not retried or declared passing.

## Provenance and controls
- Exact source: d547 + archived #3357/#3367 minimal patch + official #3332 merge delta 4591d1de08ed2e3bed529ec2c35220a80c4cb9db.
- All 1,006 fixed source files were rehashed before and after qualification and are unchanged.
- Enabling/building native test targets preserved the exact narrow-A/B DSO bytes in both modes.
- Assertions DSO: 1cd1ee2a86caf402e3d4a97fef182feccd07fbeed62387c9b32f8b6babc12651.
- Release DSO: b2c073c6c16f6af5e8c73b232a01fcf230ca0773e1d199c6423c4e7a1dec1aac.
- Compile commands verify no NDEBUG for the assertion build and NDEBUG for Release. Runtime loader traces identify the intended DSO for each solver invocation. The CTest unit-test-build entry is build-only and has no solver-DSO requirement.
- Builds use two jobs and are serialized. Each test process has a wall-time cap, core dumps disabled, and a seven-GiB virtual-address limit.
- Native unit tests retain their own thread settings; there is no supported global HiGHS thread pin in this runner. OMP/BLAS environment limits are not claimed to pin the native scheduler. This qualification does not validate automatic-thread/affinity correctness.
- Previous full-suite results and this boot's results remain separate. No timings are pooled and no speed claim is made.

## Conditional admission boundary
This exact corrected source/runtime is conditionally admitted as a bounded experimental reference for future explicitly scoped research with explicit native solver threads and the retained affinity exception. It is not an unconditional whole-suite pass, production certification, or global promotion. No SCUC data/model, large performance campaign, child analytic-center experiment, or further algorithmic change was run.

An independent read-only review confirmed the inventories, raw outcomes and artifact identities. The affinity exception and conditional-admission boundary remain binding.
