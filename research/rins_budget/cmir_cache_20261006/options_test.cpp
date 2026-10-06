#include "Highs.h"
#include <cassert>
int main(){
 Highs h;h.setOptionValue("output_flag",false);
 for(auto name:{"mip_cmir_cache_coefficients","mip_cmir_cache_log"}){
  bool current=true,defaultValue=true;
  assert(h.getBoolOptionValues(name,&current,&defaultValue)==HighsStatus::kOk);
  assert(!current&&!defaultValue);assert(h.setOptionValue(name,true)==HighsStatus::kOk);
 }
 HighsOptions copy(h.getOptions()),assigned;assigned=copy;Highs receiver;
 assert(receiver.passOptions(assigned)==HighsStatus::kOk);
 for(auto name:{"mip_cmir_cache_coefficients","mip_cmir_cache_log"}){bool value=false;assert(receiver.getOptionValue(name,value)==HighsStatus::kOk);assert(value);}
}
