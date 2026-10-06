#include "Highs.h"
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
static void scalar(std::ostream& out,double v) {
 if(std::isfinite(v))out<<std::setprecision(17)<<v;
 else out<<std::quoted(v>0?"inf":"-inf");
}
template<class T> static void writeVector(std::ostream& out,const std::vector<T>& v) {
 out<<'[';bool first=true;for(auto x:v){if(!first)out<<',';first=false;scalar(out,double(x));}out<<']';
}
int main(int argc,char**argv){
 if(argc!=3)return 64;Highs h;h.setOptionValue("output_flag",false);
 if(h.readModel(argv[1])!=HighsStatus::kOk)return 65;
 HighsLp lp=h.getLp();lp.ensureColwise();if(lp.col_names_.size()!=size_t(lp.num_col_))return 66;
 std::ofstream o(argv[2]);if(!o)return 67;
 o<<"{\"names\":[";bool first=true;for(auto&n:lp.col_names_){if(!first)o<<',';first=false;o<<std::quoted(n);}o<<']';
 #define FIELD(name,v) o<<",\"" name "\":";writeVector(o,v)
 FIELD("cost",lp.col_cost_);FIELD("lower",lp.col_lower_);FIELD("upper",lp.col_upper_);
 FIELD("row_lower",lp.row_lower_);FIELD("row_upper",lp.row_upper_);FIELD("integer",lp.integrality_);
 FIELD("start",lp.a_matrix_.start_);FIELD("index",lp.a_matrix_.index_);FIELD("value",lp.a_matrix_.value_);
 o<<",\"offset\":";scalar(o,lp.offset_);o<<",\"sense\":"<<int(lp.sense_)<<"}\n";
}
