# Third-party notices and data attribution

Project code uses the MIT license in [LICENSE.txt](LICENSE.txt). This exact
notice was retrieved from the public project's
[network_projection/LICENSE.txt at commit 38c9d7ff0260136db4f86542714f5ea4df7c5ad1](https://github.com/de1tydev/HiGHS/blob/38c9d7ff0260136db4f86542714f5ea4df7c5ad1/research/rins_budget/network_projection/LICENSE.txt).
It is an actual repository notice, rather than an inference from a README.

## HiGHS and its dependencies

The native source/build contract uses
[ERGO-Code/HiGHS commit d547a3ad8af5399651187fb0e133cf0e42615b82](https://github.com/ERGO-Code/HiGHS/tree/d547a3ad8af5399651187fb0e133cf0e42615b82).
Preserved notices are:

- [HiGHS MIT license](licenses/HiGHS_LICENSE.txt)
- [Unmodified upstream third-party notice inventory](licenses/HiGHS_THIRD_PARTY_NOTICES.md)
- [CLI11 2.5.0 notice](licenses/CLI11_NOTICE.txt), copied from the actual leading
  license comment in `extern/cli11/CLI11.hpp`. This is the BSD three-clause
  text applicable to the CLI parser
- [pdqsort zlib license](licenses/pdqsort_LICENSE.txt)
- [zstr MIT license](licenses/zstr_LICENSE.txt)

HIPO=OFF excludes the optional AMD/METIS/RCM build path. If distributing a full
upstream checkout or a build that enables these components, retain their own
notices too. This package does not redistribute their source. Upstream's
third-party notice text is preserved verbatim, including its historical CLI11
path wording; the actual notice here was checked in `extern/cli11/CLI11.hpp`.

NumPy, SciPy and threadpoolctl are installed dependencies, not vendored here.
Their installed distribution notices, including bundled BLAS/Fortran notices,
remain applicable. Preserve those notices if redistributing packages or wheels.
HiGHS uses the system zlib and standard C/C++ runtime libraries; a binary bundle
that distributes those libraries must retain their applicable notices.

## UnitCommitment.jl and input data

The project contains source-derived generator/checker work with the preserved
[UnitCommitment.jl 0.3 source notice](licenses/UCjl_v0.3.0_LICENSE.md), retrieved
from the public project's
[scuc/sources directory at the same commit](https://github.com/de1tydev/HiGHS/blob/38c9d7ff0260136db4f86542714f5ea4df7c5ad1/research/rins_budget/scuc/sources/UCjl_v0.3.0_LICENSE.md).
The notice names UChicago Argonne, LLC and the Argonne National Laboratory.

No real-world dataset is included in this package. A project's code MIT license
does not license or relicense user-provided inputs. Users obtaining public
instances should retain the source catalogue and each underlying dataset's
own attribution and terms. The predecessor README attributes PEGASE1354 to
UnitCommitment.jl/MATPOWER and points to CC BY 4.0 for the underlying dataset;
this package does not independently establish a dataset license from that
README. Dataset terms must be verified with the actual downloaded source.
Synthetic test fixtures are identified as synthetic and contain no PEGASE data.
