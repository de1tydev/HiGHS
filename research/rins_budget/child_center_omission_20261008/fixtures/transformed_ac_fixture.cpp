#include <cassert>
#include <cmath>
#include <cstdio>
#include <string>
#include "Highs.h"
int main(int argc,char**argv){
 assert(argc==4);bool omit=std::stoi(argv[1]),maximize=std::stoi(argv[2]);Highs h;
 h.setOptionValue("output_flag",false);h.setOptionValue("threads",2);h.setOptionValue("parallel","off");h.setOptionValue("presolve","on");h.setOptionValue("time_limit",10.0);h.setOptionValue("mip_rel_gap",0.0);h.setOptionValue("random_seed",211);h.setOptionValue("mip_heuristic_run_shifting",true);h.setOptionValue("mip_heuristic_run_zi_round",true);
#ifdef ABLATION_OPTIONS
 assert(h.setOptionValue("mip_omit_child_analytic_center",omit)==HighsStatus::kOk);assert(h.setOptionValue("mip_analytic_center_diagnostics",true)==HighsStatus::kOk);
#else
 assert(!omit);
#endif
 assert(h.readModel(argv[3])==HighsStatus::kOk);HighsLp lp=h.getLp();lp.offset_=17.25;if(maximize){lp.sense_=ObjSense::kMaximize;for(double& c:lp.col_cost_)c=-c;}assert(h.passModel(lp)==HighsStatus::kOk);
 for(int repetition=0;repetition<2;++repetition){
  if(repetition)assert(h.clearSolver()==HighsStatus::kOk);
  assert(h.run()==HighsStatus::kOk);assert(h.getModelStatus()==HighsModelStatus::kOptimal);double expected=(maximize?-1201500:1201500)+17.25;double obj=h.getInfo().objective_function_value,bound=h.getInfo().mip_dual_bound;assert(std::abs(obj-expected)<1e-5);assert(maximize?bound>=expected-1e-5:bound<=expected+1e-5);
  bool valid,integral,feasible;assert(h.assessPrimalSolution(valid,integral,feasible)==HighsStatus::kOk && valid && integral && feasible);
  double recomputed=lp.offset_;std::vector<double> rows(lp.num_row_,0.0);const auto& x=h.getSolution().col_value;
  for(int j=0;j<lp.num_col_;++j){assert(x[j]>=lp.col_lower_[j]-1e-6 && x[j]<=lp.col_upper_[j]+1e-6);if(lp.integrality_[j]!=HighsVarType::kContinuous)assert(std::abs(x[j]-std::round(x[j]))<=1e-6);recomputed+=lp.col_cost_[j]*x[j];for(int k=lp.a_matrix_.start_[j];k<lp.a_matrix_.start_[j+1];++k)rows[lp.a_matrix_.index_[k]]+=lp.a_matrix_.value_[k]*x[j];}
  for(int i=0;i<lp.num_row_;++i)assert(rows[i]>=lp.row_lower_[i]-1e-6 && rows[i]<=lp.row_upper_[i]+1e-6);assert(std::abs(recomputed-expected)<1e-5);
  printf("PASS repetition=%d omit=%d maximize=%d objective=%.17g bound=%.17g original_primal_checked=true\n",repetition,omit,maximize,obj,bound);
 }
 h.resetGlobalScheduler(true);
}
