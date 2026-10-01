#include "Highs.h"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

static std::string number(double x) {
  if (!std::isfinite(x)) return "null";
  std::ostringstream s; s << std::setprecision(17) << x; return s.str();
}
static std::string quoted(const std::string& x) {
  std::ostringstream s;
  s << '"';
  for (unsigned char c : x) {
    if (c == '\\' || c == '"') s << '\\' << c;
    else if (c < 0x20) s << "\\u" << std::hex << std::setw(4)
                            << std::setfill('0') << int(c) << std::dec;
    else s << c;
  }
  s << '"';
  return s.str();
}
static void requireOk(HighsStatus s, const char* action) {
  if (s == HighsStatus::kError) { std::cerr << action << " failed\n"; std::exit(2); }
}
struct Incumbent { double time, objective, dual, gap; int64_t nodes; };

// Read-only instrumentation through the official public C++ API. The independent
// checker below supports linear models with ordinary continuous/integer variables.
int main(int argc, char** argv) {
  if (argc < 5 || argc > 7) {
    std::cerr << "Usage: milp_probe MODEL OPTIONS SEED TIME_LIMIT [REL_GAP [ABS_GAP]]\n";
    return 2;
  }
  int seed;
  double time_limit, relative_gap = 0, absolute_gap = 0;
  try {
    size_t used = 0;
    seed = std::stoi(argv[3], &used);
    if (used != std::string(argv[3]).size() || seed < 0)
      throw std::invalid_argument("seed");
    auto parse = [](const char* text) {
      size_t used = 0;
      double value = std::stod(text, &used);
      if (used != std::string(text).size() || !std::isfinite(value) || value < 0)
        throw std::invalid_argument("nonnegative finite number required");
      return value;
    };
    time_limit = parse(argv[4]);
    if (time_limit == 0) throw std::invalid_argument("positive time limit required");
    if (argc >= 6) relative_gap = parse(argv[5]);
    if (argc >= 7) absolute_gap = parse(argv[6]);
  } catch (const std::exception& e) {
    std::cerr << "Invalid argument: " << e.what() << '\n';
    return 2;
  }
  Highs h;
  requireOk(h.setOptionValue("output_flag", false), "quiet output");
  requireOk(h.readOptions(argv[2]), "read options");
  requireOk(h.setOptionValue("output_flag", false), "quiet output");
  requireOk(h.setOptionValue("threads", 1), "threads");
  requireOk(h.setOptionValue("parallel", "off"), "parallel");
  requireOk(h.setOptionValue("random_seed", seed), "seed");
  requireOk(h.setOptionValue("time_limit", time_limit), "time limit");
  requireOk(h.setOptionValue("mip_rel_gap", relative_gap), "relative gap");
  requireOk(h.setOptionValue("mip_abs_gap", absolute_gap), "absolute gap");
  requireOk(h.setOptionValue("mip_feasibility_tolerance", 1e-6), "MIP feasibility tolerance");
  requireOk(h.readModel(argv[1]), "read model");
  if (h.getModel().hessian_.dim_) { std::cerr << "Quadratic models unsupported\n"; return 2; }
  // Snapshot the original model before solve, independent of internal mutation.
  const auto lp = h.getLp();
  for (auto t : lp.integrality_) {
    if (t != HighsVarType::kContinuous && t != HighsVarType::kInteger) {
      std::cerr << "Semi/implicit variables unsupported by this checker\n"; return 2;
    }
  }
  std::vector<Incumbent> incumbents;
  requireOk(h.setCallback([&](int type, const std::string&, const HighsCallbackOutput* out,
                    HighsCallbackInput*, void*) {
    if (type == kCallbackMipImprovingSolution)
      incumbents.push_back({out->running_time, out->objective_function_value,
                            out->mip_dual_bound, out->mip_gap, out->mip_node_count});
  }, nullptr), "set callback");
  requireOk(h.startCallback(kCallbackMipImprovingSolution), "callback");
  HighsProfiling profile;
  const bool profiling = std::getenv("HIGHS_PROBE_PROFILE") != nullptr;
  if (profiling) {
    requireOk(h.setOptionValue("log_dev_level", 1), "profiling log level");
    requireOk(h.setOptionValue("highs_analysis_level", int(kHighsAnalysisLevelMipTime)), "profiling level");
    h.initializeSingleThreadedProfiling(&profile);
  }
  auto start = std::chrono::steady_clock::now();
  auto run_status = h.run();
  double wall = std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
  const auto& info = h.getInfo();
  const auto& sol = h.getSolution();
  double max_bound = 0, max_row = 0, max_integer = 0, objective_error = 0;
  bool checked = sol.value_valid && sol.col_value.size() == size_t(lp.num_col_);
  bool finite = true;
  if (checked) {
    std::vector<long double> rows(lp.num_row_, 0);
    long double objective = lp.offset_;
    for (HighsInt c = 0; c < lp.num_col_; ++c) {
      double x = sol.col_value[c]; finite &= std::isfinite(x);
      max_bound = std::max({max_bound, lp.col_lower_[c]-x, x-lp.col_upper_[c]});
      if (!lp.integrality_.empty() && lp.integrality_[c] == HighsVarType::kInteger)
        max_integer = std::max(max_integer, std::abs(x-std::round(x)));
      objective += static_cast<long double>(lp.col_cost_[c])*x;
    }
    const auto& a = lp.a_matrix_;
    if (a.isColwise()) {
      for (HighsInt c = 0; c < lp.num_col_; ++c)
        for (HighsInt k = a.start_[c]; k < a.start_[c+1]; ++k)
          rows[a.index_[k]] += static_cast<long double>(a.value_[k])*sol.col_value[c];
    } else if (a.isRowwise()) {
      for (HighsInt r = 0; r < lp.num_row_; ++r)
        for (HighsInt k = a.start_[r]; k < a.start_[r+1]; ++k)
          rows[r] += static_cast<long double>(a.value_[k])*sol.col_value[a.index_[k]];
    } else { std::cerr << "Unsupported matrix layout\n"; return 2; }
    for (HighsInt r = 0; r < lp.num_row_; ++r) {
      finite &= std::isfinite(rows[r]);
      max_row = std::max({max_row, double(lp.row_lower_[r]-rows[r]), double(rows[r]-lp.row_upper_[r])});
    }
    objective_error = std::abs(double(objective)-info.objective_function_value);
    finite &= std::isfinite(objective) && std::isfinite(info.objective_function_value)
              && std::isfinite(objective_error);
  }
  bool valid = checked && finite && max_bound <= 1e-6 && max_row <= 1e-6 &&
               max_integer <= 1e-6 && objective_error <= 1e-8*(1+std::abs(info.objective_function_value));
  std::cout << "{\"model\":" << quoted(argv[1]) << ",\"options\":" << quoted(argv[2])
    << ",\"seed\":" << seed << ",\"version\":" << quoted(h.version())
    << ",\"time_limit\":" << number(time_limit)
    << ",\"mip_rel_gap\":" << number(relative_gap)
    << ",\"mip_abs_gap\":" << number(absolute_gap)
    << ",\"rows\":" << lp.num_row_ << ",\"cols\":" << lp.num_col_
    << ",\"nonzeros\":" << lp.a_matrix_.numNz()
    << ",\"run_status\":" << int(run_status)
    << ",\"status\":" << quoted(h.modelStatusToString(h.getModelStatus()))
    << ",\"wall_seconds\":" << number(wall) << ",\"solver_seconds\":" << number(h.getRunTime())
    << ",\"objective\":" << number(info.objective_function_value)
    << ",\"dual_bound\":" << number(info.mip_dual_bound) << ",\"gap\":" << number(info.mip_gap)
    << ",\"nodes\":" << info.mip_node_count << ",\"simplex_iterations\":" << info.simplex_iteration_count
    << ",\"primal_dual_integral\":" << number(info.primal_dual_integral)
    << ",\"independent_feasibility_checked\":" << (checked?"true":"false")
    << ",\"independent_feasibility_valid\":" << (valid?"true":"false")
    << ",\"max_bound_violation\":" << number(max_bound) << ",\"max_row_violation\":" << number(max_row)
    << ",\"max_integrality_violation\":" << number(max_integer)
    << ",\"objective_recalculation_error\":" << number(objective_error)
    << ",\"incumbents\":[";
  for (size_t i=0; i<incumbents.size(); ++i) {
    const auto& p=incumbents[i]; if(i) std::cout << ',';
    std::cout << "{\"time\":" << number(p.time) << ",\"objective\":" << number(p.objective)
      << ",\"dual\":" << number(p.dual) << ",\"gap\":" << number(p.gap) << ",\"nodes\":" << p.nodes << '}';
  }
  std::cout << "],\"profiling\":[";
  if (profiling) {
    for (HighsInt c=0; c<profile.num_profiling_clock_; ++c) {
      if(c) std::cout << ',';
      std::cout << "{\"name\":" << quoted(profile.name[c])
        << ",\"main_seconds\":" << number(profile.read(c, kMipRecord))
        << ",\"submip_seconds\":" << number(profile.read(c, kSubMipRecord))
        << ",\"main_calls\":" << profile.numCall(c, kMipRecord)
        << ",\"submip_calls\":" << profile.numCall(c, kSubMipRecord) << '}';
    }
    h.clearProfiling();
  }
  std::cout << "]}\n";
  return run_status == HighsStatus::kError || (checked && !valid) ? 1 : 0;
}
