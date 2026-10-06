// Source-only research adapter: invoke probe and final in separate fresh processes.
// CLI: MODEL INPUT_OR_DASH OUTPUT_POINT OUTPUT_METADATA SECONDS probe|final
// Outputs must not exist. Point rows are NAME VALUE; costs are unchecked diagnostics.
#include "Highs.h"
#include "interfaces/highs_c_api.h"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <dlfcn.h>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <unistd.h>
#include <vector>

namespace {
void require(bool ok, const std::string& why) {
  if (!ok) throw std::runtime_error(why);
}
bool printableAscii(const std::string& name) {
  return std::all_of(name.begin(), name.end(),
                     [](unsigned char c) { return c >= 32 && c < 127; });
}
std::string quote(const std::string& s) {
  std::ostringstream o; o << '"';
  for (unsigned char c : s) {
    if (c == '"' || c == '\\') o << '\\' << c;
    else if (c < 32 || c >= 127) o << "\\u00" << std::hex << std::setw(2)
                        << std::setfill('0') << int(c) << std::dec;
    else o << c;
  }
  return o.str() + '"';
}
double number(const std::string& token) {
  size_t end = 0; double value = std::stod(token, &end);
  require(end == token.size() && std::isfinite(value), "invalid finite number");
  return value;
}
std::string jsonNumber(double x) {
  if (!std::isfinite(x)) return "null";
  std::ostringstream o;
  o << std::setprecision(std::numeric_limits<double>::max_digits10) << x;
  return o.str();
}
struct FreshFile {
  FILE* file;
  explicit FreshFile(const char* path) : file(std::fopen(path, "wx")) {
    require(file != nullptr, "cannot exclusively create output: " + std::string(path));
  }
  ~FreshFile() { if (file) std::fclose(file); }
  void write(const std::string& text) {
    require(std::fwrite(text.data(), 1, text.size(), file) == text.size() &&
            std::fflush(file) == 0, "output write failed");
  }
};
HighsLp canonical(const HighsLp& source) {
  HighsLp lp = source; auto& a = lp.a_matrix_;
  require(a.formatOk() && a.num_col_ == lp.num_col_ &&
          a.num_row_ == lp.num_row_, "invalid external matrix dimensions/format");
  lp.ensureColwise();
  require(a.start_.size() >= size_t(lp.num_col_ + 1) && a.start_[0] == 0,
          "invalid external matrix starts");
  const HighsInt nz = a.start_[lp.num_col_];
  require(nz >= 0 && a.index_.size() >= size_t(nz) && a.value_.size() >= size_t(nz),
          "invalid external matrix lengths");
  for (HighsInt j = 0; j < lp.num_col_; ++j) {
    require(a.start_[j] >= 0 && a.start_[j] <= a.start_[j+1] && a.start_[j+1] <= nz,
            "invalid external matrix column");
    std::vector<std::pair<HighsInt, double>> entries;
    for (HighsInt p = a.start_[j]; p < a.start_[j+1]; ++p) {
      require(a.index_[p] >= 0 && a.index_[p] < lp.num_row_ && std::isfinite(a.value_[p]),
              "invalid external matrix entry");
      entries.emplace_back(a.index_[p], a.value_[p]);
    }
    std::sort(entries.begin(), entries.end());
    for (size_t k = 0; k < entries.size(); ++k) {
      require(k == 0 || entries[k-1].first != entries[k].first,
              "duplicate external matrix entry");
      a.index_[a.start_[j]+k] = entries[k].first;
      a.value_[a.start_[j]+k] = entries[k].second;
    }
  }
  a.exactResize(); return lp;
}
bool same16(const HighsLp& a, const HighsLp& b) {
  return a.num_col_ == b.num_col_ && a.num_row_ == b.num_row_ &&
    a.a_matrix_.numNz() == b.a_matrix_.numNz() && a.sense_ == b.sense_ &&
    a.offset_ == b.offset_ && a.col_names_ == b.col_names_ &&
    a.row_names_ == b.row_names_ && a.col_lower_ == b.col_lower_ &&
    a.col_upper_ == b.col_upper_ && a.col_cost_ == b.col_cost_ &&
    a.row_lower_ == b.row_lower_ && a.row_upper_ == b.row_upper_ &&
    a.integrality_ == b.integrality_ && a.a_matrix_.start_ == b.a_matrix_.start_ &&
    a.a_matrix_.index_ == b.a_matrix_.index_ && a.a_matrix_.value_ == b.a_matrix_.value_;
}
void verifyOptions(const Highs& h, double seconds) {
  HighsInt threads = 0, seed = 0; std::string parallel; double limit = 0, gap = 1, absolute = 1;
  require(h.getOptionValue("threads", threads) == HighsStatus::kOk && threads == 2 &&
    h.getOptionValue("parallel", parallel) == HighsStatus::kOk && parallel == "off" &&
    h.getOptionValue("random_seed", seed) == HighsStatus::kOk && seed == 1 &&
    h.getOptionValue("time_limit", limit) == HighsStatus::kOk && limit == seconds &&
    h.getOptionValue("mip_rel_gap", gap) == HighsStatus::kOk && gap == 0 &&
    h.getOptionValue("mip_abs_gap", absolute) == HighsStatus::kOk && absolute == 0,
    "option readback mismatch");
}
}  // namespace

int main(int argc, char** argv) {
  if (argc != 7) {
    std::cerr << "usage: sparse_probe MODEL INPUT_OR_DASH OUTPUT_POINT OUTPUT_METADATA SECONDS probe|final\n";
    return 64;
  }
  Highs h; HighsLp original; std::unique_ptr<FreshFile> meta, point;
  std::string mode = argv[6], outcome = "error", error, loaded_library_path;
  bool ran = false, verified = false, options_verified = false, complete = false;
  HighsStatus run_status = HighsStatus::kError;
  double seconds = 0, objective = std::numeric_limits<double>::quiet_NaN();
  double native_objective = objective; int exit_code = 1;
  try {
    meta.reset(new FreshFile(argv[4])); point.reset(new FreshFile(argv[3]));
    Dl_info library = {};
    require(dladdr(reinterpret_cast<const void*>(&Highs_version), &library) != 0 &&
            library.dli_fname && library.dli_fname[0], "cannot identify loaded HiGHS library");
    loaded_library_path = library.dli_fname;
    require(mode == "probe" || mode == "final", "mode must be probe or final");
    seconds = number(argv[5]);
    require(seconds > 0 && seconds <= 600, "seconds must be in (0,600]");
    require(h.setOptionValue("threads", HighsInt(2)) == HighsStatus::kOk &&
      h.setOptionValue("parallel", "off") == HighsStatus::kOk &&
      h.setOptionValue("random_seed", HighsInt(1)) == HighsStatus::kOk &&
      h.setOptionValue("time_limit", seconds) == HighsStatus::kOk &&
      h.setOptionValue("mip_rel_gap", 0.0) == HighsStatus::kOk &&
      h.setOptionValue("mip_abs_gap", 0.0) == HighsStatus::kOk, "setOptionValue failed");
    verifyOptions(h, seconds); options_verified = true;
    require(h.readModel(argv[1]) == HighsStatus::kOk, "readModel failed or warned");
    require(!h.getModel().isQp() && h.getLp().isMip(), "expected original linear MILP");
    original = canonical(h.getLp());
    const HighsInt n = original.num_col_;
    require(n > 0 && original.col_names_.size() == size_t(n) &&
      original.col_lower_.size() == size_t(n) && original.col_upper_.size() == size_t(n) &&
      original.col_cost_.size() == size_t(n) && original.integrality_.size() == size_t(n),
      "incomplete original column fields");
    for (const auto& name : original.row_names_)
      require(printableAscii(name), "unsupported non-ASCII/control row name");
    std::map<std::string, HighsInt> names;
    for (HighsInt j = 0; j < n; ++j) {
      const auto& name = original.col_names_[j];
      require(printableAscii(name), "unsupported non-ASCII/control column name");
      require(!name.empty() && name.find_first_of(" \t\r\n\v\f") == std::string::npos &&
              names.emplace(name, j).second, "nonunique or unserializable column name");
    }
    std::vector<HighsInt> index; std::vector<double> values, full(n, 0);
    std::vector<bool> seen(n, false);
    if (std::string(argv[2]) != "-") {
      std::ifstream input(argv[2]); require(bool(input), "cannot open input point");
      std::string line;
      while (std::getline(input, line)) {
        std::istringstream row(line); std::string name, token, extra;
        if (!(row >> name)) continue;
        require(bool(row >> token) && !(row >> extra), "expected exactly NAME VALUE per row");
        const double value = number(token); const auto found = names.find(name);
        require(found != names.end(), "unknown input column: " + name);
        const HighsInt j = found->second;
        require(!seen[j], "duplicate input column: " + name); seen[j] = true;
        if (mode == "probe")
          require((token == "0" || token == "1") && (value == 0 || value == 1) &&
            original.integrality_[j] == HighsVarType::kInteger &&
            original.col_lower_[j] == 0 && original.col_upper_[j] == 1,
            "proposal must be a literal 0/1 on a free binary column: " + name);
        index.push_back(j); values.push_back(value); full[j] = value;
      }
      require(input.eof() && !input.bad(), "input point read failed");
    }
    if (mode == "final" && std::string(argv[2]) != "-") {
      require(index.size() == size_t(n), "final requires every original column exactly once");
      HighsSolution start; start.value_valid = true; start.col_value = std::move(full);
      require(h.setSolution(start) == HighsStatus::kOk, "complete setSolution failed or warned");
    } else if (!index.empty()) {
      require(h.setSolution(HighsInt(index.size()), index.data(), values.data()) == HighsStatus::kOk,
              "sparse setSolution failed or warned");
    }
    require(same16(original, canonical(h.getLp())), "original model changed before run");
    verifyOptions(h, seconds);
    // Sparse completion happens privately inside this supported run, followed by ordinary search.
    ran = true; run_status = h.run();
    require(same16(original, canonical(h.getLp())), "original model changed after run");
    verified = true; options_verified = false;
    verifyOptions(h, seconds); options_verified = true;
    require(run_status == HighsStatus::kOk || run_status == HighsStatus::kWarning,
            "invalid run API status");
    const auto status = h.getModelStatus();
    require(status >= HighsModelStatus::kModelEmpty && status <= HighsModelStatus::kMax,
            "invalid native model status");
    const auto& solution = h.getSolution();
    complete = solution.value_valid && solution.col_value.size() == size_t(n) &&
      std::all_of(solution.col_value.begin(), solution.col_value.end(),
                  [](double x) { return std::isfinite(x); });
    if (complete) {
      long double cost = original.offset_;
      std::ostringstream rows;
      rows << std::setprecision(std::numeric_limits<double>::max_digits10);
      for (HighsInt j = 0; j < n; ++j) {
        cost += static_cast<long double>(original.col_cost_[j]) * solution.col_value[j];
        rows << original.col_names_[j] << ' ' << solution.col_value[j] << '\n';
      }
      objective = static_cast<double>(cost);
      require(std::isfinite(objective), "nonfinite recomputed candidate objective");
      point->write(rows.str()); outcome = "point"; exit_code = 0;
    } else { outcome = "no_point"; exit_code = 2; }
    if (h.getInfo().valid) native_objective = h.getInfo().objective_function_value;
  } catch (const std::exception& e) {
    error = e.what(); outcome = "error"; exit_code = 1;
  }
  if (meta) {
    try {
      std::ostringstream out;
      out << "{\"schema_version\":1,\"mode\":" << quote(mode)
          << ",\"process_id\":" << static_cast<long long>(getpid())
          << ",\"outcome\":" << quote(outcome) << ",\"error\":" << quote(error)
          << ",\"loaded_library_path\":" << quote(loaded_library_path)
          << ",\"run_api_status\":" << (ran ? std::to_string(int(run_status)) : "null")
          << ",\"native_model_status\":" << int(h.getModelStatus())
          << ",\"native_model_status_name\":" << quote(h.modelStatusToString(h.getModelStatus()))
          << ",\"complete_primal_present\":" << (complete ? "true" : "false")
          << ",\"model_fields_verified\":" << (verified ? "true" : "false")
          << ",\"num_col\":" << original.num_col_ << ",\"num_row\":" << original.num_row_
          << ",\"num_nz\":" << original.a_matrix_.numNz()
          << ",\"point_objective\":" << jsonNumber(objective)
          << ",\"solver_reported_objective\":" << jsonNumber(native_objective)
          << ",\"options_verified\":" << (options_verified ? "true" : "false")
          << ",\"options\":{\"threads\":2,\"parallel\":\"off\",\"random_seed\":1,\"time_limit\":"
          << jsonNumber(seconds) << ",\"mip_rel_gap\":0,\"mip_abs_gap\":0}}\n";
      meta->write(out.str());
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
  }
  if (!error.empty()) std::cerr << error << '\n';
  return exit_code;
}
