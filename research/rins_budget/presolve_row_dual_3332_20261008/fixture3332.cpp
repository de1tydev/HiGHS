#include "Highs.h"
#include <cmath>
#include <iostream>
#include <iomanip>
int main(int argc,char** argv) {
  HighsLp lp;
  lp.num_col_ = 6;
  lp.num_row_ = 2;
  lp.col_cost_ = {0, 0, 0, 0, 4, -2};
  lp.col_lower_ = {-kHighsInf, -5, 0, -5, 0, 0};
  lp.col_upper_ = {-10, kHighsInf, kHighsInf, 5, 7, 2};
  lp.row_lower_ = {-13, 11};
  lp.row_upper_ = {kHighsInf, 11};
  lp.integrality_ = {HighsVarType::kInteger, HighsVarType::kInteger,
                     HighsVarType::kInteger, HighsVarType::kContinuous,
                     HighsVarType::kInteger, HighsVarType::kInteger};
  lp.a_matrix_.format_ = MatrixFormat::kColwise;
  lp.a_matrix_.start_ = {0, 2, 4, 5, 6, 8, 10};
  lp.a_matrix_.index_ = {0, 1, 0, 1, 1, 1, 0, 1, 0, 1};
  lp.a_matrix_.value_ = {-3, 1, -1, -1, -2, -1, -8, 1, -1, 10};


  Highs highs; highs.setOptionValue("threads",1); highs.setOptionValue("output_flag",true); highs.setOptionValue("presolve",std::string(argc>1?argv[1]:"on"));
  if(highs.passModel(lp)!=HighsStatus::kOk) return 2;
  auto run=highs.run(); auto status=highs.getModelStatus(); auto sol=highs.getSolution(); double objective=highs.getObjectiveValue();
  bool feasible=sol.value_valid && sol.col_value.size()==6; double direct=0;
  if(feasible) { for(int j=0;j<6;j++){double x=sol.col_value[j]; feasible=feasible && std::isfinite(x) && x>=lp.col_lower_[j]-1e-7 && x<=lp.col_upper_[j]+1e-7; if(j!=3) feasible=feasible && std::abs(x-std::round(x))<=1e-7; direct+=lp.col_cost_[j]*x;}
    auto x=sol.col_value; double r0=-3*x[0]-x[1]-8*x[4]-x[5], r1=x[0]-x[1]-2*x[2]-x[3]+x[4]+10*x[5]; feasible=feasible && r0>=-13-1e-7 && std::abs(r1-11)<=1e-7; }
  bool ok=run==HighsStatus::kOk && status==HighsModelStatus::kOptimal && feasible && std::abs(objective+4)<=1e-7 && std::abs(direct-objective)<=1e-7;
  std::cout<<std::setprecision(17)<<"RESULT presolve="<<(argc>1?argv[1]:"on")<<" run="<<int(run)<<" model="<<int(status)<<" objective="<<objective<<" direct="<<direct<<" feasible="<<feasible<<" ok="<<ok<<" primal=";
  for(double x:sol.col_value) std::cout<<x<<","; std::cout<<"\\n"; return ok?0:1;
}

