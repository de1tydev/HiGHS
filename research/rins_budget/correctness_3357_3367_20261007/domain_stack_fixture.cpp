// Narrow regression for the cumulative official HiGHS PR #3357 change.
// Uses public internal classes exactly as check/TestMipSolver.cpp fixtures do.
// No Highs::run(), HighsMipSolver::run(), LP solve, or symmetry detection.
#include <exception>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <vector>

#include "Highs.h"
#include "mip/HighsMipSolver.h"
#include "mip/HighsMipSolverData.h"
#include "presolve/HighsSymmetry.h"

namespace {
void require(bool value, const char* message) {
  if (!value) throw std::runtime_error(message);
}

bool exercise(bool lower, bool symmetry) {
  // Two interchangeable pairs: x=2*y and z=2*w. x,z are general integer;
  // y,w are binary. Swapping (x,y) with (z,w) preserves this whole model.
  HighsLp lp;
  lp.num_col_ = 4;
  lp.num_row_ = 2;
  lp.col_cost_.assign(4, 0.0);
  lp.col_lower_.assign(4, 0.0);
  lp.col_upper_ = {2.0, 1.0, 2.0, 1.0};
  lp.integrality_.assign(4, HighsVarType::kInteger);
  lp.row_lower_.assign(2, 0.0);
  lp.row_upper_.assign(2, 0.0);
  lp.a_matrix_.format_ = MatrixFormat::kColwise;
  lp.a_matrix_.num_col_ = 4;
  lp.a_matrix_.num_row_ = 2;
  lp.a_matrix_.start_ = {0, 1, 2, 3, 4};
  lp.a_matrix_.index_ = {0, 0, 1, 1};
  lp.a_matrix_.value_ = {1.0, -2.0, 1.0, -2.0};

  Highs highs;
  require(highs.setOptionValue("output_flag", false) == HighsStatus::kOk,
          "output option setup failed");
  require(highs.setOptionValue("threads", 1) == HighsStatus::kOk,
          "thread option setup failed");
  require(highs.passModel(lp) == HighsStatus::kOk, "model setup failed");
  HighsCallback callback(&highs);
  HighsSolution solution;
  HighsMipSolver mip(callback, highs.getOptions(), highs.getLp(), solution);
  mip.mipdata_.reset(new HighsMipSolverData(mip));
  auto& data = *mip.mipdata_;
  data.feastol = highs.getOptions().mip_feasibility_tolerance;
  data.epsilon = highs.getOptions().small_matrix_value;
  data.setupDomainPropagation();
  data.detectSymmetries = symmetry;

  HighsDomain original(data.getDomain());
  original.propagate();
  require(original.getDomainChangeStack().empty(),
          "fixture unexpectedly tightens before branching");
  const auto direction = lower ? HighsBoundType::kLower : HighsBoundType::kUpper;
  original.changeBound(direction, 0, 1.0, HighsDomain::Reason::branching());
  original.propagate();
  require(!original.infeasible(), "fixture became infeasible");
  require((lower ? original.col_lower_[0] : original.col_upper_[0]) ==
              (lower ? 2.0 : 0.0),
          "real propagation did not tighten x");

  std::vector<HighsInt> saved_branches;
  const auto saved = original.getReducedDomainChangeStack(saved_branches);
  // Real compression must yield y>=1, branch x>=2 (or the upper mirror).
  require(saved.size() == 2 && saved_branches.size() == 1 &&
              saved_branches[0] == 1 && saved[0].column == 1 &&
              saved[1].column == 0 && saved[0].boundtype == direction &&
              saved[1].boundtype == direction,
          "compression did not create the targeted reload order");

  // Use a fresh copy of the unchanged global domain, as node installation does.
  HighsDomain reloaded(data.getDomain());
  reloaded.setDomainChangeStack(saved, saved_branches);
  const auto& branch_positions = reloaded.getBranchingPositions();
  const auto& stack = reloaded.getDomainChangeStack();
  bool retained_x = false;
  for (HighsInt pos : branch_positions)
    retained_x = retained_x || (stack[pos].column == 0 &&
                               stack[pos].boundtype == direction);
  const bool unchanged = !reloaded.infeasible() &&
                         reloaded.col_lower_ == original.col_lower_ &&
                         reloaded.col_upper_ == original.col_upper_;

  // Feed the known valid global pair-swap directly to the real stabilizer.
  // This tests stabilizer consumption, without running symmetry detection.
  HighsSymmetries group;
  group.permutationColumns = {0, 1, 2, 3};
  group.columnPosition = {0, 1, 2, 3};
  group.permutations = {2, 3, 0, 1};
  group.numPerms = 1;
  group.numGenerators = 1;
  StabilizerOrbitWorkspace workspace;
  const auto orbits = group.computeStabilizerOrbits(reloaded, workspace);
  const bool stabilized_x = orbits->isStabilized(0);
  // In the symmetry-off control, computation above is diagnostic only.
  // Production would not use an active symmetry group in that arm.
  const bool passed = unchanged && retained_x == symmetry &&
                      branch_positions.size() == (symmetry ? 1u : 0u) &&
                      stabilized_x == symmetry;
  std::cout << "{\"case\":\"" << (lower ? "lower" : "upper")
            << (symmetry ? "_symmetry_on" : "_symmetry_off")
            << "\",\"retained_x\":" << retained_x
            << ",\"branch_count\":" << branch_positions.size()
            << ",\"stabilized_x\":" << stabilized_x
            << ",\"bounds_unchanged\":" << unchanged
            << ",\"passed\":" << passed << "}\n";
  return passed;
}
}  // namespace

int main() {
  std::cout << std::boolalpha;
  int failures = 0;
  try {
    for (bool lower : {true, false})
      for (bool symmetry : {true, false})
        if (!exercise(lower, symmetry)) ++failures;
  } catch (const std::exception& error) {
    std::cerr << "Fixture setup failure: " << error.what() << '\n';
    return 2;
  }
  std::cout << "{\"cases\":4,\"failures\":" << failures << "}\n";
  return failures ? 1 : 0;
}
