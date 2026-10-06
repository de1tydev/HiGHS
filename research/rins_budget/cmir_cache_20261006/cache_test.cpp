#include "mip/HighsCmirCoefficientCache.h"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <random>
static bool same(double a, double b) { return std::memcmp(&a,&b,8)==0; }
int main() {
  std::mt19937_64 random(20261006);
  size_t comparisons=0;
  for (double scale : {0.125,0.3,1.0,3.0,8.0,1000000.0}) {
    HighsCmirCoefficientCache cache(32,scale);
    for (int n=0;n<20000;n++) {
      double coefficient = (int64_t(random()%2000001)-1000000)/16.0;
      if (n%8==0) coefficient=std::nextafter(coefficient,INFINITY);
      if (n%8==1) coefficient=std::nextafter(coefficient,-INFINITY);
      if (n%8==2) coefficient=0.0;
      if (n%8==3) coefficient=-0.0;
      const size_t index=n%32;
      for (double x : {coefficient,coefficient,-coefficient,coefficient}) {
        double scaled=x*scale;
        double down=(int64_t)(scaled+kHighsTiny)-((scaled+kHighsTiny)<(int64_t)(scaled+kHighsTiny));
        double fraction=scaled-down;
        auto value=cache.get(index,x);
        assert(same(value.source,x));assert(same(value.scaled,scaled));
        assert(same(value.down,down));assert(same(value.fractional,fraction));
        ++comparisons;
      }
    }
  }
  printf("passed: %zu tuple comparisons, signed-zero and reversal included\n",comparisons);
}
