// MIT-licensed HiGHS test data adapted from official PR #3367,
// head b116e43c9dfce28217cee376d8a207dcf0aaf13c, issue-3364.
// Standalone driver: explicit checks remain active with NDEBUG.
#include <cmath>
#include <exception>
#include <iostream>
#include <string>
#include <vector>
#include "Highs.h"
#include "presolve/HPresolve.h"
#include "presolve/HighsPostsolveStack.h"

namespace {
int fail(const std::string& message, int code = 1) {
  std::cerr << "FAIL " << message << std::endl;
  return code;
}

bool validCsc(const HighsLp& lp) {
  const auto& a = lp.a_matrix_;
  if (lp.num_col_ < 0 || lp.num_row_ < 0 || !a.isColwise() ||
      a.start_.size() != static_cast<size_t>(lp.num_col_) + 1 ||
      a.index_.size() != a.value_.size() || a.start_.front() != 0 ||
      a.start_.back() != static_cast<HighsInt>(a.index_.size()))
    return false;
  for (HighsInt col = 0; col < lp.num_col_; ++col)
    if (a.start_[col] < 0 || a.start_[col] > a.start_[col + 1])
      return false;
  for (size_t nz = 0; nz < a.index_.size(); ++nz) {
    if (a.index_[nz] < 0 || a.index_[nz] >= lp.num_row_ ||
        !std::isfinite(a.value_[nz])) {
      std::cerr << "Invalid CSC entry nz=" << nz
                << " row=" << a.index_[nz]
                << " num_row=" << lp.num_row_ << std::endl;
      return false;
    }
  }
  return true;
}

int rowPositions3364() {
  HighsLp lp;
  lp.num_col_ = 7;
  lp.num_row_ = 5;
  lp.sense_ = ObjSense::kMinimize;
  lp.col_cost_ = {-1, -1, -1, 1, 1, -1, -1};
  lp.col_lower_.assign(lp.num_col_, 0);
  lp.col_upper_.assign(lp.num_col_, 10);
  lp.integrality_ = {
      HighsVarType::kContinuous, HighsVarType::kContinuous,
      HighsVarType::kContinuous, HighsVarType::kInteger,
      HighsVarType::kInteger, HighsVarType::kContinuous,
      HighsVarType::kContinuous};
  // Numeric order A/B/i/D/E is essential: nearly-parallel A precedes B.
  lp.row_lower_ = {-kHighsInf, -kHighsInf, 6, -kHighsInf, -kHighsInf};
  lp.row_upper_ = {13, 8, 6, 7, 7};
  lp.a_matrix_.format_ = MatrixFormat::kColwise;
  lp.a_matrix_.num_col_ = lp.num_col_;
  lp.a_matrix_.num_row_ = lp.num_row_;
  lp.a_matrix_.start_ = {0, 4, 8, 11, 12, 13, 14, 15};
  lp.a_matrix_.index_ = {0, 1, 2, 3, 0, 1, 2, 4, 0, 1, 2, 0, 0, 3, 4};
  lp.a_matrix_.value_ = {1, 1, 1, 1, 2, 2, 2, 1, 3, 3, 3, 2, 3, 1, 1};
  lp.col_names_ = {"x0", "x1", "x3", "s1", "s2", "x4", "x5"};
  lp.row_names_ = {"A", "B", "i", "D", "E"};
  if (!validCsc(lp)) return fail("3364 input CSC", 2);

  HighsOptions options;
  options.presolve_rule_test = kPresolveRuleParallelRowsAndCols;
  options.solver = kIpmString;
  options.run_crossover = kHighsOffString;
  options.output_flag = false;
  HighsTimer timer;
  timer.start();
  if (!timer.running()) return fail("3364 timer setup", 2);
  presolve::HighsPostsolveStack postsolve;
  postsolve.initializeIndexMaps(lp.num_row_, lp.num_col_);
  presolve::HPresolve presolver;
  presolver.setInput(lp, options, -1, &timer);
  if (!presolver.okSetupPresolveDataStructures())
    return fail("3364 presolve setup", 2);
  std::cout << "BEGIN 3364 rule-only" << std::endl;
  const HighsModelStatus status = presolver.run(postsolve);
  if (status != HighsModelStatus::kNotset)
    return fail("3364 unexpected status " +
                std::to_string(static_cast<int>(status)));
  if (!validCsc(lp)) return fail("3364 output CSC");
  std::cout << "PASS 3364 rows=" << lp.num_row_
            << " cols=" << lp.num_col_
            << " nnz=" << lp.a_matrix_.index_.size() << std::endl;
  return 0;
}

int equationSize3359(const std::string& filename) {
  Highs h;
  if (h.setOptionValue("output_flag", false) != HighsStatus::kOk ||
      h.setOptionValue("threads", 1) != HighsStatus::kOk ||
      h.setOptionValue("presolve", "on") != HighsStatus::kOk ||
      h.setOptionValue("time_limit", 30.0) != HighsStatus::kOk)
    return fail("3359 option setup", 2);
  if (h.readModel(filename) != HighsStatus::kOk)
    return fail("3359 readModel", 2);
  if (!validCsc(h.getLp())) return fail("3359 input CSC", 2);
  std::cout << "BEGIN 3359 presolve-on expected=25" << std::endl;
  const HighsStatus run_status = h.run();
  if (h.getModelStatus() == HighsModelStatus::kTimeLimit)
    return fail("3359 time limit; inconclusive", 2);
  if (run_status != HighsStatus::kOk ||
      h.getModelStatus() != HighsModelStatus::kOptimal)
    return fail("3359 run/model status " +
                std::to_string(static_cast<int>(run_status)) + "/" +
                std::to_string(static_cast<int>(h.getModelStatus())));
  const HighsLp& lp = h.getLp();
  const auto& sol = h.getSolution();
  const double tol = 1e-6;
  const double reported = h.getInfo().objective_function_value;
  if (!validCsc(lp) || !sol.value_valid ||
      sol.col_value.size() != static_cast<size_t>(lp.num_col_) ||
      !std::isfinite(reported) || std::abs(reported - 25.0) > tol)
    return fail("3359 objective or solution structure");
  std::vector<double> activities(lp.num_row_, 0.0);
  double objective = lp.offset_;
  for (HighsInt col = 0; col < lp.num_col_; ++col) {
    const double x = sol.col_value[col];
    if (!std::isfinite(x) || x < lp.col_lower_[col] - tol ||
        x > lp.col_upper_[col] + tol ||
        (!lp.integrality_.empty() &&
         lp.integrality_[col] != HighsVarType::kContinuous &&
         std::abs(x - std::round(x)) > tol))
      return fail("3359 column bound/integrality");
    objective += lp.col_cost_[col] * x;
    for (HighsInt nz = lp.a_matrix_.start_[col];
         nz < lp.a_matrix_.start_[col + 1]; ++nz)
      activities[lp.a_matrix_.index_[nz]] += lp.a_matrix_.value_[nz] * x;
  }
  for (HighsInt row = 0; row < lp.num_row_; ++row)
    if (!std::isfinite(activities[row]) ||
        activities[row] < lp.row_lower_[row] - tol ||
        activities[row] > lp.row_upper_[row] + tol)
      return fail("3359 original-model row feasibility");
  if (!std::isfinite(objective) || std::abs(objective - 25.0) > tol)
    return fail("3359 independently computed objective");
  std::cout << "PASS 3359 objective=" << reported
            << " original_model_feasible=true" << std::endl;
  return 0;
}
}  // namespace

int main(int argc, char** argv) {
  try {
    if (argc == 2 && std::string(argv[1]) == "3364")
      return rowPositions3364();
    if (argc == 3 && std::string(argv[1]) == "3359")
      return equationSize3359(argv[2]);
    return fail("usage: pr3367_regression 3364 | 3359 /path/to/3359.mps", 2);
  } catch (const std::exception& e) {
    return fail(std::string("exception: ") + e.what());
  }
}
