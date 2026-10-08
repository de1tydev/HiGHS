#include <cassert>
#include <cmath>
#include <cstdio>
#include <string>
#include "Highs.h"
#include "mip/HighsMipSolver.h"
#include "mip/HighsMipSolverData.h"
#include "parallel/HighsParallel.h"
int main(int argc,char**argv) {
 assert(argc==5);bool child=std::stoi(argv[1]),omit=std::stoi(argv[2]);std::string presolve=argv[3];
 Highs h;h.setOptionValue("output_flag",false);h.setOptionValue("threads",2);h.setOptionValue("parallel","off");h.setOptionValue("presolve",presolve);h.setOptionValue("time_limit",10.0);h.setOptionValue("mip_rel_gap",0.0);h.setOptionValue("random_seed",211);h.setOptionValue("mip_heuristic_run_shifting",true);h.setOptionValue("mip_heuristic_run_zi_round",true);
#ifdef ABLATION_OPTIONS
 assert(h.setOptionValue("mip_omit_child_analytic_center",omit)==HighsStatus::kOk);assert(h.setOptionValue("mip_analytic_center_diagnostics",true)==HighsStatus::kOk);
#else
 assert(!omit);
#endif
 assert(h.readModel(argv[4])==HighsStatus::kOk);HighsLp lp=h.getLp();
 highs::parallel::initialize_scheduler(2);HighsTimer timer;HighsProfiling profiling;profiling.initialize(timer,false,false);HighsCallback callback(&h);HighsSolution sol;
 for(int repetition=0;repetition<2;++repetition){
  // Internal HighsMipSolver is single-use: each repetition owns fresh state.
  HighsMipSolver m(callback,h.getOptions(),lp,sol,child,child?1:0);m.setProfiling(&profiling);
  m.run();assert(m.modelstatus_==HighsModelStatus::kOptimal);assert(std::abs(m.solution_objective_-1201500)<1e-5);assert(m.dual_bound_<=1201500+1e-5);assert(m.solution_.size()==size_t(lp.num_col_));
  std::vector<double> rows(lp.num_row_,0.0);double obj=lp.offset_;
  for(int j=0;j<lp.num_col_;++j){double x=m.solution_[j];assert(x>=lp.col_lower_[j]-1e-6 && x<=lp.col_upper_[j]+1e-6);if(lp.integrality_[j]!=HighsVarType::kContinuous)assert(std::abs(x-std::round(x))<=1e-6);obj+=lp.col_cost_[j]*x;for(int k=lp.a_matrix_.start_[j];k<lp.a_matrix_.start_[j+1];++k)rows[lp.a_matrix_.index_[k]]+=lp.a_matrix_.value_[k]*x;}
  for(int i=0;i<lp.num_row_;++i)assert(rows[i]>=lp.row_lower_[i]-1e-6 && rows[i]<=lp.row_upper_[i]+1e-6);assert(std::abs(obj-1201500)<1e-5);
  if(child && omit){assert(m.mipdata_->analyticCenter.empty());assert(!m.mipdata_->analyticCenterComputed);assert(m.mipdata_->analyticCenterStatus==HighsModelStatus::kNotset);}
  printf("PASS repetition=%d child=%d omit=%d presolve=%s objective=%.17g bound=%.17g restarts=%d center_size=%zu computed=%d center_status=%d\n",repetition,child,omit,presolve.c_str(),m.solution_objective_,m.dual_bound_,int(m.mipdata_->numRestarts),m.mipdata_->analyticCenter.size(),int(m.mipdata_->analyticCenterComputed),int(m.mipdata_->analyticCenterStatus));fflush(stdout);
 }
 h.resetGlobalScheduler(true);
}
