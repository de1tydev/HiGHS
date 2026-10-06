#include "mip/HighsCmirCoefficientCache.h"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <random>
static bool same(double a,double b){return std::memcmp(&a,&b,8)==0;}
int main(){
 std::mt19937_64 rng(20261006);size_t comparisons=0;
 for(double scale:{0.125,0.3,1.0,3.0,8.0,1000000.0}){
  HighsCmirCoefficientCache cache(32,scale);double coefficients[32];
  for(int j=0;j<32;j++){
   coefficients[j]=(int64_t(rng()%2000001)-1000000)/16.;
   if(j%8==0)coefficients[j]=std::nextafter(coefficients[j],INFINITY);
   if(j%8==1)coefficients[j]=std::nextafter(coefficients[j],-INFINITY);
   if(j%8==2)coefficients[j]=0.;if(j%8==3)coefficients[j]=-0.;
   cache.refresh(j,coefficients[j]);
  }
  for(int trial=0;trial<20000;trial++){
   int k=rng()%32;coefficients[k]=-coefficients[k];
   if(trial%3==0){ // fractional-rhs rejection: restore without touching cache
    coefficients[k]=-coefficients[k];
   }else{
    cache.refresh(k,coefficients[k]);
    if(trial%3==1){coefficients[k]=-coefficients[k];cache.refresh(k,coefficients[k]);}
   }
   for(int j=0;j<32;j++){
    double scaled=coefficients[j]*scale;double down=(int64_t)(scaled+kHighsTiny)-((scaled+kHighsTiny)<(int64_t)(scaled+kHighsTiny));
    const auto& value=cache.get(j);
    assert(same(value.down,down));assert(same(value.fractional,scaled-down));++comparisons;
   }
  }
 }
 printf("passed: %zu cached tuple comparisons over accepted/restored/skipped flips\n",comparisons);
}
