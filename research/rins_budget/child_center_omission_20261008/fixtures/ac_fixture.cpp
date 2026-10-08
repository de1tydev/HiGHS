#include <cassert>
#include <cmath>
#include <cstdio>
#include <string>
#include "Highs.h"
#include "mip/HighsMipSolver.h"
#include "mip/HighsMipSolverData.h"
#include "parallel/HighsParallel.h"

int main(int argc, char** argv) {
  assert(argc == 6);
  const bool child = std::stoi(argv[1]);
  const bool omit = std::stoi(argv[2]);
  const std::string parallel = argv[3];
  const std::string kind = argv[4];
  const int depth = std::stoi(argv[5]);
  Highs highs;
  assert(highs.setOptionValue("output_flag", false) == HighsStatus::kOk);
  assert(highs.setOptionValue("threads", 2) == HighsStatus::kOk);
  assert(highs.setOptionValue("parallel", parallel) == HighsStatus::kOk);
  assert(highs.setOptionValue("presolve", "off") == HighsStatus::kOk);
  assert(highs.setOptionValue("time_limit", 10.0) == HighsStatus::kOk);
  assert(highs.setOptionValue("random_seed", 211) == HighsStatus::kOk);
  assert(highs.setOptionValue("mip_rel_gap", 0.0) == HighsStatus::kOk);
  assert(highs.setOptionValue("mip_heuristic_run_shifting", true) == HighsStatus::kOk);
  assert(highs.setOptionValue("mip_heuristic_run_zi_round", true) == HighsStatus::kOk);
#ifdef ABLATION_OPTIONS
  bool b = true;
  assert(highs.getOptionValue("mip_omit_child_analytic_center", b) == HighsStatus::kOk && !b);
  assert(highs.getOptionValue("mip_analytic_center_diagnostics", b) == HighsStatus::kOk && !b);
  assert(highs.setOptionValue("mip_omit_child_analytic_center", omit) == HighsStatus::kOk);
  assert(highs.setOptionValue("mip_analytic_center_diagnostics", true) == HighsStatus::kOk);
  HighsOptions copy = highs.getOptions();
  assert(copy.mip_omit_child_analytic_center == omit && copy.mip_analytic_center_diagnostics);
#else
  assert(!omit);
#endif
  HighsLp lp;
  lp.num_col_ = 12; lp.num_row_ = 2;
  lp.col_lower_.assign(12, 0.0); lp.col_upper_.assign(12, 1.0);
  lp.integrality_.assign(12, HighsVarType::kInteger);
  lp.row_lower_ = {-kHighsInf, -kHighsInf}; lp.row_upper_ = {27.5, 25.5};
  lp.a_matrix_.format_ = MatrixFormat::kColwise;
  lp.a_matrix_.num_col_=12; lp.a_matrix_.num_row_=2; lp.a_matrix_.start_.clear();
  const int costs[] = {9, 6, 13, 7, 11, 4, 8, 14, 5, 10, 12, 3};
  const int w1[] = {6, 3, 8, 5, 7, 2, 4, 9, 3, 6, 8, 2};
  const int w2[] = {2, 7, 5, 3, 8, 4, 6, 3, 5, 4, 7, 2};
  for (int j=0;j<12;++j) {
    lp.col_cost_.push_back(-costs[j]); lp.a_matrix_.start_.push_back(2*j);
    lp.a_matrix_.index_.push_back(0);lp.a_matrix_.value_.push_back(w1[j]);
    lp.a_matrix_.index_.push_back(1);lp.a_matrix_.value_.push_back(w2[j]);
  }
  lp.a_matrix_.start_.push_back(24);
  double optimum = 0;
  for (int mask=0;mask<4096;++mask) {
    int a=0,b=0,c=0;
    for(int j=0;j<12;++j) if(mask&(1<<j)){a+=w1[j];b+=w2[j];c-=costs[j];}
    if(a<=27.5 && b<=25.5) optimum=std::min(optimum,double(c));
  }
  if(kind=="infeasible") {
    // Odd cycle: every pair must sum to one, impossible for three binaries.
    lp.num_col_=3;lp.num_row_=3;lp.col_cost_.assign(3,-1.0);
    lp.col_lower_.assign(3,0.0);lp.col_upper_.assign(3,1.0);
    lp.integrality_.assign(3,HighsVarType::kInteger);
    lp.row_lower_.assign(3,1.0);lp.row_upper_.assign(3,1.0);
    lp.a_matrix_.num_col_=3;lp.a_matrix_.num_row_=3;
    lp.a_matrix_.start_={0,2,4,6};lp.a_matrix_.index_={0,2,0,1,1,2};
    lp.a_matrix_.value_.assign(6,1.0);
  }
  if(kind=="unbounded") {lp.col_upper_[0]=kHighsInf;lp.a_matrix_.value_[0]=0;lp.a_matrix_.value_[1]=0;}
  if(kind=="rootlimit") highs.setOptionValue("mip_max_nodes", 0);
  if(kind=="timelimit") highs.setOptionValue("time_limit", 0.0);
  if(kind=="maxoffset") {lp.sense_=ObjSense::kMaximize;for(auto& c:lp.col_cost_)c=-c;lp.offset_=17.25;}
  if(kind=="minoffset") lp.offset_=17.25;
  if(child) {
    assert(kind!="maxoffset" && kind!="minoffset");
    highs::parallel::initialize_scheduler(2);
    HighsTimer timer; HighsProfiling profiling; profiling.initialize(timer, false, false);
    HighsCallback callback(&highs); HighsSolution solution;
    HighsMipSolver mip(callback, highs.getOptions(), lp, solution, true, depth);
    mip.setProfiling(&profiling); mip.run();
    if(omit && parallel=="off") {
      assert(mip.mipdata_->analyticCenter.empty());
      assert(mip.mipdata_->analyticCenterStatus==HighsModelStatus::kNotset);
      assert(!mip.mipdata_->analyticCenterComputed);
    }
    if(kind=="normal") {
      assert(mip.modelstatus_==HighsModelStatus::kOptimal);
      assert(std::abs(mip.solution_objective_-optimum)<1e-7);
      double a=0,b=0,c=0;assert(mip.solution_.size()==12);
      for(int j=0;j<12;++j){double x=mip.solution_[j];assert(x>=-1e-7 && x<=1+1e-7 && std::abs(x-std::round(x))<1e-7);a+=w1[j]*x;b+=w2[j]*x;c-=costs[j]*x;}
      assert(a<=27.5+1e-7 && b<=25.5+1e-7 && std::abs(c-optimum)<1e-7);
      assert(mip.dual_bound_<=optimum+1e-6);
    }
    if(kind=="infeasible") assert(mip.modelstatus_==HighsModelStatus::kInfeasible);
    if(kind=="unbounded") assert(mip.modelstatus_==HighsModelStatus::kUnbounded || mip.modelstatus_==HighsModelStatus::kUnboundedOrInfeasible);
    if(kind=="rootlimit") assert(mip.modelstatus_==HighsModelStatus::kSolutionLimit);
    if(kind=="timelimit") assert(mip.modelstatus_==HighsModelStatus::kTimeLimit);
    printf("PASS child=%d omit=%d parallel=%s kind=%s depth=%d status=%d objective=%.17g bound=%.17g center_size=%zu computed=%d center_status=%d\n",child,omit,parallel.c_str(),kind.c_str(),depth,int(mip.modelstatus_),mip.solution_objective_,mip.dual_bound_,mip.mipdata_->analyticCenter.size(),int(mip.mipdata_->analyticCenterComputed),int(mip.mipdata_->analyticCenterStatus));
  } else {
    assert(highs.passModel(lp)==HighsStatus::kOk);
    HighsStatus status=highs.run();assert(status!=HighsStatus::kError);
    if(kind=="normal" || kind=="maxoffset" || kind=="minoffset") {
      assert(highs.getModelStatus()==HighsModelStatus::kOptimal);
      const double expected=kind=="maxoffset" ? -optimum+17.25 : optimum+(kind=="minoffset"?17.25:0);
      assert(std::abs(highs.getInfo().objective_function_value-expected)<1e-7);
      bool valid,integral,feasible;assert(highs.assessPrimalSolution(valid,integral,feasible)==HighsStatus::kOk && valid && integral && feasible);
      double bound=highs.getInfo().mip_dual_bound;
      assert(kind=="maxoffset" ? bound>=expected-1e-6 : bound<=expected+1e-6);
    }
    if(kind=="infeasible") assert(highs.getModelStatus()==HighsModelStatus::kInfeasible);
    if(kind=="unbounded") assert(highs.getModelStatus()==HighsModelStatus::kUnbounded || highs.getModelStatus()==HighsModelStatus::kUnboundedOrInfeasible);
    if(kind=="rootlimit") assert(highs.getModelStatus()==HighsModelStatus::kSolutionLimit);
    if(kind=="timelimit") assert(highs.getModelStatus()==HighsModelStatus::kTimeLimit);
    printf("PASS child=%d omit=%d parallel=%s kind=%s depth=%d status=%d objective=%.17g bound=%.17g\n",child,omit,parallel.c_str(),kind.c_str(),depth,int(highs.getModelStatus()),highs.getInfo().objective_function_value,highs.getInfo().mip_dual_bound);
  }
  highs.resetGlobalScheduler(true);
}
