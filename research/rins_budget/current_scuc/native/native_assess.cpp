// Assessment-only bridge. No optimization, presolve, crossover or repair entry.
#include "Highs.h"
#include <cstdint>
#include <iostream>
#include <dlfcn.h>
extern "C" const char* Highs_version(void);
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>

template<class T> void scalar(std::ofstream& o, const T& v) {
  o.write(reinterpret_cast<const char*>(&v), sizeof(v));
}
template<class T> void array(std::ofstream& o, const std::vector<T>& v) {
  o.write(reinterpret_cast<const char*>(v.data()), sizeof(T)*v.size());
}
void names(std::ofstream& o, const std::vector<std::string>& v) {
  for (const auto& s : v) { uint32_t n=s.size(); scalar(o,n); o.write(s.data(),n); }
}
void ok(HighsStatus s, const char* action) {
  if(s != HighsStatus::kOk) throw std::runtime_error(action);
}
int main(int argc, char** argv) {
  try {
    if(argc!=5) throw std::runtime_error("usage: native_assess model.mps point.sol dump.bin log.txt");
    static_assert(sizeof(HighsInt)==4, "32-bit ABI required");
    static_assert(sizeof(double)==8, "binary64 required");
    uint32_t endian=1;
    if(*reinterpret_cast<char*>(&endian)!=1) throw std::runtime_error("little endian required");
    Highs h;
    ok(h.setOptionValue("log_to_console",false),"log_to_console");
    ok(h.setOptionValue("log_file",std::string(argv[4])),"log_file");
    // Read defaults, never relax tolerances.
    double mip_tol=0, primal_tol=0;
    ok(h.getOptionValue("mip_feasibility_tolerance",mip_tol),"get mip tolerance");
    ok(h.getOptionValue("primal_feasibility_tolerance",primal_tol),"get primal tolerance");
    if(mip_tol!=1e-6 || primal_tol!=1e-7) throw std::runtime_error("unexpected native defaults");
    ok(h.readModel(argv[1]),"readModel");
    ok(h.ensureColwise(),"ensureColwise");
    if(h.getModel().hessian_.dim_!=0) throw std::runtime_error("unexpected Hessian");
    ok(h.readSolution(argv[2]),"readSolution");
    bool valid=false,integral=false,feasible=false;
    auto assessed=h.assessPrimalSolution(valid,integral,feasible);
    const auto& lp=h.getLp(); const auto& s=h.getSolution();
    if(lp.col_names_.size()!=size_t(lp.num_col_) || lp.row_names_.size()!=size_t(lp.num_row_) ||
       s.col_value.size()!=size_t(lp.num_col_) || s.row_value.size()!=size_t(lp.num_row_))
      throw std::runtime_error("incomplete names/solution");
    std::vector<int32_t> types(lp.num_col_,0);
    if(!lp.integrality_.empty()) {
      if(lp.integrality_.size()!=size_t(lp.num_col_)) throw std::runtime_error("incomplete types");
      for(int32_t j=0;j<lp.num_col_;j++) types[j]=int32_t(lp.integrality_[j]);
    }
    std::ofstream o(argv[3],std::ios::binary);
    if(!o) throw std::runtime_error("open dump");
    o.write("HSCONT01",8);
    Dl_info origin{};
    if(!dladdr(reinterpret_cast<void*>(Highs_version), &origin) || !origin.dli_fname) throw std::runtime_error("library provenance");
    std::string dso(origin.dli_fname); uint32_t dso_size=dso.size(); scalar(o,dso_size);o.write(dso.data(),dso_size);
    for(int32_t v : {lp.num_col_,lp.num_row_,int32_t(lp.a_matrix_.value_.size()),int32_t(lp.sense_),
        int32_t(assessed),int32_t(valid),int32_t(integral),int32_t(feasible),int32_t(s.value_valid)}) scalar(o,v);
    for(double v : {lp.offset_,mip_tol,primal_tol,h.getInfinity()}) scalar(o,v);
    array(o,lp.col_lower_);array(o,lp.col_upper_);array(o,lp.col_cost_);
    array(o,lp.row_lower_);array(o,lp.row_upper_);array(o,types);
    array(o,lp.a_matrix_.start_);array(o,lp.a_matrix_.index_);array(o,lp.a_matrix_.value_);
    names(o,lp.col_names_);names(o,lp.row_names_);
    array(o,s.col_value);array(o,s.row_value);o.close();
    if(!o) throw std::runtime_error("write dump");
    return 0; // Assessment rejection is data, not a crashed helper.
  } catch(const std::exception& e) { std::cerr << e.what() << "\n"; return 2; }
}
