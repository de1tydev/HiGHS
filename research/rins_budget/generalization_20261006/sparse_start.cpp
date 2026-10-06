// Standalone research adapter: a partial solution never changes model bounds.
#include "Highs.h"
#include <cmath>
#include <fstream>
#include <iostream>
#include <set>
#include <string>
#include <vector>
int main(int argc, char** argv) {
  if (argc != 5) return 64; // model, name/value proposals or '-', solution, seconds
  Highs h;
  double seconds = std::stod(argv[4]);
  if (!std::isfinite(seconds) || seconds <= 0 || seconds > 600) return 64;
  if (h.setOptionValue("threads", 2) != HighsStatus::kOk ||
      h.setOptionValue("parallel", "off") != HighsStatus::kOk ||
      h.setOptionValue("random_seed", 1) != HighsStatus::kOk ||
      h.setOptionValue("time_limit", seconds) != HighsStatus::kOk ||
      h.setOptionValue("mip_rel_gap", 0.0) != HighsStatus::kOk ||
      h.readModel(argv[1]) != HighsStatus::kOk) return 65;
  const auto lower = h.getLp().col_lower_, upper = h.getLp().col_upper_;
  const auto integer = h.getLp().integrality_;
  if (std::string(argv[2]) != "-") {
    std::ifstream input(argv[2]); if (!input) return 66;
    std::string name; double value; std::set<HighsInt> seen;
    std::vector<HighsInt> index; std::vector<double> values;
    while (input >> name) {
      if (!(input >> value) || !std::isfinite(value) || (value != 0 && value != 1)) return 67;
      HighsInt col;
      if (h.getColByName(name, col) != HighsStatus::kOk || !seen.insert(col).second ||
          integer.empty() || integer[col] != HighsVarType::kInteger ||
          lower[col] != 0 || upper[col] != 1) return 68;
      index.push_back(col); values.push_back(value);
    }
    if (!input.eof()) return 67;
    if (!index.empty() && h.setSolution(HighsInt(index.size()), index.data(), values.data()) == HighsStatus::kError) return 69;
  }
  if (h.getLp().col_lower_ != lower || h.getLp().col_upper_ != upper || h.getLp().integrality_ != integer) return 70;
  const auto run = h.run();
  if (h.getLp().col_lower_ != lower || h.getLp().col_upper_ != upper || h.getLp().integrality_ != integer) return 71;
  if (run == HighsStatus::kError) return 72;
  if (h.writeSolution(argv[3]) != HighsStatus::kOk) return 73;
  std::cout << "UNRESTRICTED_MODEL_BOUNDS_PRESERVED\n";
  return h.getModelStatus() == HighsModelStatus::kOptimal ? 0 : 2;
}
