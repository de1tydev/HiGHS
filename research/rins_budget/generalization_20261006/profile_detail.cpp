// Read existing native clocks without changing the official library.
#include "Highs.h"
#include "parallel/HighsParallel.h"
#include <fstream>
#include <iomanip>
#include <string>
int main(int argc, char** argv) {
  if (argc != 4) return 64;
  HighsProfiling profile;
  Highs h;
  if (h.setOptionValue("threads",2) != HighsStatus::kOk ||
      h.setOptionValue("parallel","off") != HighsStatus::kOk ||
      h.setOptionValue("random_seed",std::stoi(argv[2])) != HighsStatus::kOk ||
      h.setOptionValue("time_limit",60.0) != HighsStatus::kOk ||
      h.setOptionValue("mip_rel_gap",0.0001) != HighsStatus::kOk ||
      h.setOptionValue("log_dev_level",1) != HighsStatus::kOk ||
      h.setOptionValue("highs_analysis_level",128) != HighsStatus::kOk ||
      h.readModel(argv[1]) != HighsStatus::kOk) return 65;
  highs::parallel::initialize_scheduler(2);
  h.initializeProfiling(&profile);
  auto status=h.run();
  std::ofstream out(argv[3]);
  if (!out) return 66;
  out << "scope\tthread\tclock\tcalls\tseconds\n" << std::setprecision(17);
  for (int scope=0;scope<2;scope++) {
    const auto& records=scope ? profile.submip_record : profile.record;
    for (size_t thread=0;thread<records.size();thread++)
      for (size_t clock=0;clock<profile.name.size();clock++)
        if (records[thread].num_call[clock])
          out << (scope ? "submip" : "mip") << '\t' << thread << '\t' << profile.name[clock] << '\t'
              << records[thread].num_call[clock] << '\t' << records[thread].run_time[clock] << '\n';
  }
  h.clearProfiling();
  return status==HighsStatus::kError ? 67 : (h.getModelStatus()==HighsModelStatus::kOptimal ? 0 : 2);
}
