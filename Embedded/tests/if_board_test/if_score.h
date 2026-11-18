// Isolation Forest scoring with the exported trees. No Arduino calls, so it also builds on a computer.
#pragma once
#include <math.h>
#include <stdint.h>

// Anomaly score, higher means more abnormal. x holds IF_FEATURES float values.
static inline double ifScore(const float* x) {
  double total = 0.0;
  for (int t = 0; t < IF_TREES; t++) {
    int n = IF_ROOT[t];
    while (IF_FEAT[n] >= 0) {
      n = (x[IF_FEAT[n]] <= IF_THR[n]) ? IF_LEFT[n] : IF_RIGHT[n];
    }
    total += IF_THR[n];                 // at a leaf this holds depth + average path length of the leaf
  }
  return pow(2.0, -(total / IF_TREES) / IF_C_MAX);
}
