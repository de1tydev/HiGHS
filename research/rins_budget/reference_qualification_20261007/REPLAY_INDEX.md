# Replay and source index

This index identifies inputs and existing public source code for the recorded
qualification. **It is not a self-contained replay kit for the patched run.**
The qualification-specific identity adapter, supervisors, assertions-build
harness and full raw evidence are not distributed in this compact addendum.
No portable patched-adapter command is presented as tested.

## Immutable source references

All research links below are pinned to `40d8240a7e834fe86e39509dbf0c91dd69af79d4`.

- [Official HiGHS base](https://github.com/ERGO-Code/HiGHS/commit/d547a3ad8af5399651187fb0e133cf0e42615b82):
  `d547a3ad8af5399651187fb0e133cf0e42615b82`. The candidate checks all 1,006 files and changes exactly
  `highs/mip/HighsDomain.cpp` and `highs/presolve/HPresolve.cpp`.
- [Minimal patch and fixture checkpoint](https://github.com/de1tydev/HiGHS/blob/40d8240a7e834fe86e39509dbf0c91dd69af79d4/research/rins_budget/correctness_3357_3367_20261007/README.md),
  including [combined patch](https://github.com/de1tydev/HiGHS/blob/40d8240a7e834fe86e39509dbf0c91dd69af79d4/research/rins_budget/correctness_3357_3367_20261007/combined-minimal-correctness.patch),
  [domain-stack fixture](https://github.com/de1tydev/HiGHS/blob/40d8240a7e834fe86e39509dbf0c91dd69af79d4/research/rins_budget/correctness_3357_3367_20261007/domain_stack_fixture.cpp),
  [presolve fixture](https://github.com/de1tydev/HiGHS/blob/40d8240a7e834fe86e39509dbf0c91dd69af79d4/research/rins_budget/correctness_3357_3367_20261007/pr3367_regression.cpp),
  and [ordered 3359 MPS](https://github.com/de1tydev/HiGHS/blob/40d8240a7e834fe86e39509dbf0c91dd69af79d4/research/rins_budget/correctness_3357_3367_20261007/3359.mps).
  Patch SHA256: `bdba43930c63ad8c7e86215cf91e745e7fd67a7fcf7787bb9f52dc62a95912a0`.
  The earlier manual commands are Release-fixture instructions. They do not
  replay the subsequent assertions-enabled gate or native suite by themselves.
- [Portable pristine recipe](https://github.com/de1tydev/HiGHS/blob/40d8240a7e834fe86e39509dbf0c91dd69af79d4/research/rins_budget/portable_pristine_reference_replay_v3/README.md)
  and its [source-identity guard](https://github.com/de1tydev/HiGHS/blob/40d8240a7e834fe86e39509dbf0c91dd69af79d4/research/rins_budget/portable_pristine_reference_replay_v3/replay/prepare_replay.py#L35-L53).
  Its complete pristine inventory is authoritative. Applying the minimal patch
  makes that source fail this guard. Do not relabel the patched build pristine,
  bypass a check, or treat the documented pristine commands as a tested replay
  of these results. The published pristine recipe's tiny paired run also differs
  from this single seed-1 full-source tiny qualification.
- Public numerical components retained by the PG89 qualification:
  [generator](https://github.com/de1tydev/HiGHS/blob/40d8240a7e834fe86e39509dbf0c91dd69af79d4/research/rins_budget/portable_pristine_reference_replay_v3/replay/payload/scuc/generate.py),
  [original-source checker](https://github.com/de1tydev/HiGHS/blob/40d8240a7e834fe86e39509dbf0c91dd69af79d4/research/rins_budget/portable_pristine_reference_replay_v3/replay/payload/scuc/check_solution.py),
  [exact export/readback](https://github.com/de1tydev/HiGHS/blob/40d8240a7e834fe86e39509dbf0c91dd69af79d4/research/rins_budget/portable_pristine_reference_replay_v3/replay/payload/canonical_mps_export/readback.py),
  [budget policy](https://github.com/de1tydev/HiGHS/blob/40d8240a7e834fe86e39509dbf0c91dd69af79d4/research/rins_budget/portable_pristine_reference_replay_v3/replay/payload/combined_screening_driver/trial_policy.py),
  [cold-control loop](https://github.com/de1tydev/HiGHS/blob/40d8240a7e834fe86e39509dbf0c91dd69af79d4/research/rins_budget/portable_pristine_reference_replay_v3/replay/payload/combined_screening_driver/cold_screen_pair.py),
  and [offline verifier](https://github.com/de1tydev/HiGHS/blob/40d8240a7e834fe86e39509dbf0c91dd69af79d4/research/rins_budget/portable_pristine_reference_replay_v3/replay/payload/combined_screening_driver/verify_run.py).
  Numerical model/export/readback/checker/separation/proof/budget/containment
  code remained byte-identical; the run used a separate exact patched-identity,
  one-arm adapter. That adapter was exercised in its recorded environment;
  portability is not established here.

## Fixed input identities

- [Tiny triangle source](https://github.com/de1tydev/HiGHS/blob/40d8240a7e834fe86e39509dbf0c91dd69af79d4/research/rins_budget/portable_pristine_reference_replay_v3/replay/payload/combined_screening_driver/tiny_triangle.json):
  SHA256 `dbcc5bc8901542c795dec194d0bb38d63f331c72bfcac75fd93ce64706206f48`.
- Ordered #3359 MPS: SHA256
  `403c72defdc2a3ac365841711353d0a4842ef70a6cf6bfcf1dea6aaa2535178d`.
  Preserve its original row/column order for the regression.
- [PG89 May 1, 2017 input](https://axavier.org/UnitCommitment.jl/0.3/instances/matpower/case89pegase/2017-05-01.json.gz):
  compressed SHA256 `a13b8da591278afec5d14ef7c787bfd7c0c6a3f91c526511bfee051294c9be4c`;
  decompressed SHA256 `1b00f8b3efd27e777e6cf888690ffcc0e9d28f2a6559699b82b3822c890c61eb`.
  The recorded arm uses the full source and seed 211 only; no held-out status
  or all-possible-outage coverage is implied.

## Recorded native identity and reproduction boundary

Release CLI SHA256: `8c5e774e72ef259e183b7b2339ee9332010611f9035b3c543a9dcb50aa49daea`.
Main DSO: `5cf57054b20fdc2dd137dee356f5b184064493f46deb31015d25de713a4544ce`.
Extras DSO: `add1358fa82827a3ead2137b8483956fb8f38ff86f2b0ada974125dcb58b7e0d`.
These identify the observed build, not promised hashes for independent rebuilds.
Actual library initialization was checked in each solver process; version
output alone is insufficient. Matching source headers, ABI, build settings,
library aliases and resolved providers are required.

A future self-contained patched replay must provide and validate its own
explicit candidate-source manifest and identity adapter, preserve the numerical
core and original checks/budgets, retain failure/cleanup evidence, and distinguish
a local rebuild's hashes from this recorded binary identity. It must audit all
161 option records rather than relying on the 114-record public count. It must
also preserve the affinity exception and the limits in [README.md](README.md).
This index does not claim that such a portable package has been validated.

[PUBLICATION_MANIFEST.json](PUBLICATION_MANIFEST.json) records hashes for the
three summary files, the linked source inputs/components and retained evidence
used to prepare the summaries. Evidence digests are provenance anchors, not
public download locations or a claim that the raw records are bundled.

Source licenses/notices remain in the linked packages. HiGHS and replay code
retain their MIT notices. PG89 comes from the UnitCommitment.jl 0.3 catalogue
and [MATPOWER case89pegase](https://github.com/MATPOWER/matpower/blob/7.1/data/case89pegase.m),
under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Original data
attribution: Cédric Josz, Stéphane Fliscounakis, Jean Maeght and Patrick
Panciatici (2015/2016). These are fictitious benchmark data. See
[Josz et al.](https://arxiv.org/abs/1603.01533) and
[Fliscounakis et al.](https://doi.org/10.1109/TPWRS.2013.2251015).
