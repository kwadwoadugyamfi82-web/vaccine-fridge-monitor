// The same test on a computer:  g++ -O2 -I. host_if.cpp -o host_if && ./host_if
#include <cstdio>
#include <cmath>
#include <cstdint>
#include "if_model.h"
#include "if_testdata.h"
#include "if_score.h"
int main() {
  double maxErr = 0; int diff = 0;
  for (int k = 0; k < IF_TEST_N; k++) {
    double s = ifScore(&IF_TEST[k * IF_FEATURES]);
    maxErr = fmax(maxErr, fabs(s - IF_EXPECT[k]));
    if ((s > IF_ALARM_THRESHOLD) != ((double)IF_EXPECT[k] > IF_ALARM_THRESHOLD) && fabs(IF_EXPECT[k] - IF_ALARM_THRESHOLD) > 1e-5) diff++;
  }
  printf("max_abs_error=%.3e alarm_decisions_differing=%d\n", maxErr, diff);
}
