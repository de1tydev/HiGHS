// Source-only diagnostic prepared for HiGHS d547a3ad8af5399651187fb0e133cf0e42615b82.
// Model: check/TestMipSolver.cpp MIP-nmck, with reversed objective costs.
// Callback pattern: check/TestCallbacks.cpp userkMipUserSetSolution.
// Build/run only with separate authorization; see the frozen README.
#include "Highs.h"

#include <chrono>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <limits>
#include <string>
#include <vector>

namespace {
constexpr const char* kPinnedCommit =
    "d547a3ad8af5399651187fb0e133cf0e42615b82";
constexpr const char* kPinnedBuildHash = "d547a3ad8a";
constexpr double kTolerance = 1e-7;
const double kMissing = std::numeric_limits<double>::quiet_NaN();

bool close(double actual, double expected) {
  return std::isfinite(actual) && std::abs(actual - expected) <= kTolerance;
}

// Independently check this fixed three-variable model; no solver calls.
bool feasible(const std::vector<double>& v) {
  return v.size() == 3 && std::isfinite(v[0]) && std::isfinite(v[1]) &&
         std::isfinite(v[2]) && v[0] >= -kTolerance &&
         v[1] >= -kTolerance && v[2] >= -kTolerance &&
         v[2] <= 1 + kTolerance && close(v[2], std::round(v[2])) &&
         v[0] + v[1] + v[2] <= 7 + kTolerance &&
         close(4 * v[0] + 2 * v[1] + v[2], 12);
}

double objective(const std::vector<double>& v, double offset) {
  return v.size() == 3 ? 3 * v[0] + 2 * v[1] + v[2] + offset : kMissing;
}

struct Trace {
  int user_callback_count = 0;
  int after_setup_count = 0;
  int root0_count = 0;
  int submission_count = 0;
  double initial_bound = kMissing;
  double root0_bound = kMissing;
  int64_t initial_lp_iterations = -1;
  int64_t root0_lp_iterations = -1;
  int64_t root0_nodes = -1;
  HighsStatus submission_status = HighsStatus::kError;
  bool bad_order = false;
};

// Returns 0 = pass, 1 = diagnostic failure, 2 = inconclusive.
int runCase(ObjSense sense, double offset) {
  const bool minimize = sense == ObjSense::kMinimize;
  const std::string name = std::string(minimize ? "min_" : "max_") +
                           (offset == 0 ? "offset0" : "offset100");
  const std::vector<double> initial = {2, 2, 0};
  const std::vector<double> candidate =
      minimize ? std::vector<double>{3, 0, 0} : std::vector<double>{0, 6, 0};
  const double expected_initial = 10 + offset;
  const double expected_optimum = (minimize ? 9 : 12) + offset;
  Trace trace;
  Highs highs;
  std::string setup_error;
  auto check = [&](HighsStatus status, const char* operation) {
    if (status != HighsStatus::kOk && setup_error.empty()) setup_error = operation;
  };

  check(highs.setOptionValue("output_flag", false), "output_flag");
  check(highs.setOptionValue("presolve", "off"), "presolve");
  check(highs.setOptionValue("mip_heuristic_run_feasibility_jump", false),
        "mip_heuristic_run_feasibility_jump");
  check(highs.setOptionValue("threads", 1), "threads");
  check(highs.setOptionValue("mip_rel_gap", 0.0), "mip_rel_gap");
  check(highs.setOptionValue("time_limit", 1.0), "time_limit");

  HighsLp lp;
  lp.num_col_ = 3;
  lp.num_row_ = 2;
  lp.sense_ = sense;
  lp.offset_ = offset;
  lp.col_cost_ = {3, 2, 1};
  lp.col_lower_ = {0, 0, 0};
  lp.col_upper_ = {kHighsInf, kHighsInf, 1};
  lp.row_lower_ = {-kHighsInf, 12};
  lp.row_upper_ = {7, 12};
  lp.a_matrix_.format_ = MatrixFormat::kColwise;
  lp.a_matrix_.start_ = {0, 2, 4, 6};
  lp.a_matrix_.index_ = {0, 1, 0, 1, 0, 1};
  lp.a_matrix_.value_ = {1, 4, 1, 2, 1, 1};
  lp.integrality_ = {HighsVarType::kContinuous, HighsVarType::kContinuous,
                     HighsVarType::kInteger};
  check(highs.passModel(lp), "passModel");
  HighsSolution start;
  start.value_valid = true;
  start.col_value = initial;
  check(highs.setSolution(start), "initial_setSolution");

  // Only the callback input is changed while run() is active. There is no
  // reentrant Highs::setSolution(), model edit, repair, or solver-state access.
  HighsCallbackFunctionType callback =
      [&](int type, const std::string&, const HighsCallbackOutput* out,
          HighsCallbackInput* in, void*) {
        if (type != kCallbackMipUserSolution) return;
        ++trace.user_callback_count;
        if (out->external_solution_query_origin ==
            kExternalMipSolutionQueryOriginAfterSetup) {
          ++trace.after_setup_count;
          if (trace.after_setup_count != 1) return;
          trace.initial_bound = out->mip_primal_bound;
          trace.initial_lp_iterations = out->mip_total_lp_iterations;
          if (trace.root0_count != 0) trace.bad_order = true;
          if (in && close(trace.initial_bound, expected_initial)) {
            ++trace.submission_count;
            trace.submission_status = in->setSolution(
                static_cast<HighsInt>(candidate.size()), candidate.data());
          }
        } else if (out->external_solution_query_origin ==
                   kExternalMipSolutionQueryOriginEvaluateRootNode0) {
          ++trace.root0_count;
          if (trace.root0_count != 1) return;
          trace.root0_bound = out->mip_primal_bound;
          trace.root0_lp_iterations = out->mip_total_lp_iterations;
          trace.root0_nodes = out->mip_node_count;
          if (trace.submission_count != 1) trace.bad_order = true;
        }
      };
  check(highs.setCallback(callback), "setCallback");
  check(highs.startCallback(kCallbackMipUserSolution), "startCallback");

  if (!feasible(initial) || !feasible(candidate) ||
      !close(objective(initial, offset), expected_initial) ||
      !close(objective(candidate, offset), expected_optimum)) {
    setup_error = "fixed_fixture_invalid";
  }

  const auto begin = std::chrono::steady_clock::now();
  const HighsStatus run_status =
      setup_error.empty() ? highs.run() : HighsStatus::kError;
  const double elapsed = std::chrono::duration<double>(
                             std::chrono::steady_clock::now() - begin)
                             .count();
  const HighsModelStatus model_status = highs.getModelStatus();
  const auto& info = highs.getInfo();
  const auto& final_solution = highs.getSolution();
  const double final_objective =
      info.valid ? info.objective_function_value : kMissing;
  const bool final_feasible =
      final_solution.value_valid && feasible(final_solution.col_value);
  const double final_recomputed = objective(final_solution.col_value, offset);
  std::string outcome = "PASS";
  std::string reason = "admitted_before_root_lp_and_final_optimum_valid";
  int result = 0;
  auto inconclusive = [&](const std::string& why) {
    result = 2;
    outcome = "INCONCLUSIVE";
    reason = why;
  };
  if (!setup_error.empty()) {
    inconclusive("setup_" + setup_error);
  } else if (trace.after_setup_count == 0 || trace.root0_count == 0) {
    inconclusive("missing_expected_hook");
  } else if (trace.after_setup_count != 1 || trace.bad_order ||
             trace.initial_lp_iterations != 0 || trace.root0_lp_iterations != 0 ||
             trace.root0_nodes != 0) {
    inconclusive("unexpected_event_sequence_or_lp_work");
  } else if (!close(trace.initial_bound, expected_initial) ||
             trace.submission_count != 1 ||
             trace.submission_status != HighsStatus::kOk ||
             !std::isfinite(trace.root0_bound)) {
    inconclusive("initial_bound_or_submission_precondition");
  } else if (run_status != HighsStatus::kOk ||
             model_status != HighsModelStatus::kOptimal) {
    inconclusive("run_did_not_finish_normally_optimal");
  } else if (!final_feasible || !close(final_objective, expected_optimum) ||
             !close(final_recomputed, expected_optimum)) {
    result = 1;
    outcome = "FAIL_FINAL_VALIDATION";
    reason = "final_solution_requires_separate_diagnosis";
  } else if (!close(trace.root0_bound, expected_optimum)) {
    result = 1;
    outcome = "FAIL_ADMISSION";
    reason = close(trace.root0_bound, expected_initial)
                 ? "finite_incumbent_unchanged_before_root_lp"
                 : "unexpected_primal_bound_before_root_lp";
  }

  std::cout << name << '\t' << (minimize ? "min" : "max") << '\t' << offset
            << '\t' << expected_initial << '\t' << expected_optimum << '\t'
            << trace.initial_bound << '\t' << trace.root0_bound << '\t'
            << trace.user_callback_count << '\t' << trace.after_setup_count
            << '\t' << trace.root0_count << '\t' << trace.submission_count
            << '\t' << static_cast<int>(trace.submission_status) << '\t'
            << trace.initial_lp_iterations << '\t' << trace.root0_lp_iterations
            << '\t' << trace.root0_nodes << '\t' << static_cast<int>(run_status)
            << '\t' << static_cast<int>(model_status) << '\t'
            << highs.modelStatusToString(model_status) << '\t' << final_objective
            << '\t' << final_recomputed << '\t' << final_feasible << '\t'
            << elapsed << '\t' << outcome << '\t' << reason << '\n';
  return result;
}
}  // namespace

int main() {
  std::cout << std::setprecision(17) << std::unitbuf;
  Highs identity;
  std::cout << "# pinned_commit=" << kPinnedCommit << "\n# runtime_version="
            << identity.version() << "\n# runtime_githash=" << identity.githash()
            << '\n';
  if (identity.githash() != kPinnedBuildHash) {
    std::cout << "# result=INCONCLUSIVE reason=runtime_githash_mismatch\n";
    return 2;
  }
  std::cout << "case\tsense\toffset\texpected_initial\texpected_optimum"
               "\tinitial_bound\troot0_bound\tuser_callback_count"
               "\tafter_setup_count\troot0_count\tsubmission_count"
               "\tsubmission_status\tinitial_lp_iterations\troot0_lp_iterations"
               "\troot0_nodes\trun_status\tmodel_status\tmodel_status_name"
               "\tfinal_objective\tfinal_recomputed\tfinal_feasible"
               "\trun_seconds\toutcome\treason\n";
  int failures = 0;
  int inconclusive = 0;
  for (ObjSense sense : {ObjSense::kMinimize, ObjSense::kMaximize}) {
    for (double offset : {0.0, 100.0}) {
      const int result = runCase(sense, offset);
      failures += result == 1;
      inconclusive += result == 2;
    }
  }
  std::cout << "# failures=" << failures << " inconclusive=" << inconclusive
            << " cases=4\n";
  // Incomplete coverage takes precedence in the overall exit code; per-case
  // failures remain in the TSV. No retry or model/parameter substitution.
  return inconclusive ? 2 : failures ? 1 : 0;
}
