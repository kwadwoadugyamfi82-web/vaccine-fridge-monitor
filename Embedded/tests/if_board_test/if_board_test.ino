// Isolation Forest on the ESP32-S3: parity and timing test. No sensors needed.
//
// Scores IF_TEST_N feature vectors with the exported trees and compares each score with the one scikit-learn
// gave on the computer. Prints the largest difference, the alarm decisions that differ, the time per score
// and the memory used. Serial Monitor at 115200 baud.
//
// if_model.h and if_testdata.h are not in the repo. ML-Validation/refit/make_if_model.py writes them into
// this folder.

#include <Arduino.h>
#include "if_model.h"
#include "if_testdata.h"
#include "if_score.h"

void setup() {
  Serial.begin(115200);
  delay(3000);
  Serial.printf("\n=== Isolation Forest on ESP32-S3 | chip %s rev %d | %d MHz | sketch %u B ===\n",
                ESP.getChipModel(), ESP.getChipRevision(), (int)ESP.getCpuFreqMHz(), (unsigned)ESP.getSketchSize());
  Serial.printf("MODEL|trees=%d|features=%d|nodes=%d|threshold=%.6f\n", IF_TREES, IF_FEATURES, IF_NODES, IF_ALARM_THRESHOLD);

  double maxErr = 0.0, sumErr = 0.0;
  int alarms = 0, healthyAlarms = 0, faultAlarms = 0, flagDiff = 0, borderline = 0;
  for (int k = 0; k < IF_TEST_N; k++) {
    double s = ifScore(&IF_TEST[k * IF_FEATURES]);
    double e = fabs(s - (double)IF_EXPECT[k]);
    if (e > maxErr) maxErr = e;
    sumErr += e;
    bool a = s > IF_ALARM_THRESHOLD;
    bool b = (double)IF_EXPECT[k] > IF_ALARM_THRESHOLD;
    if (a) { alarms++; if (k < IF_TEST_HEALTHY) healthyAlarms++; else faultAlarms++; }
    if (a != b) { if (fabs((double)IF_EXPECT[k] - IF_ALARM_THRESHOLD) < 1e-5) borderline++; else flagDiff++; }
  }
  Serial.printf("PARITY|vectors=%d|max_abs_error=%.3e|mean_abs_error=%.3e|alarm_decisions_differing=%d|borderline_differing=%d\n",
                IF_TEST_N, maxErr, sumErr / IF_TEST_N, flagDiff, borderline);
  Serial.printf("ALARMS|total=%d|among_healthy_windows=%d of %d|among_fault_windows=%d of %d\n",
                alarms, healthyAlarms, IF_TEST_HEALTHY, faultAlarms, IF_TEST_N - IF_TEST_HEALTHY);

  volatile double sink = 0.0;
  for (int rep = 0; rep < 3; rep++) {
    uint32_t t0 = micros();
    for (int k = 0; k < IF_TEST_N; k++) sink += ifScore(&IF_TEST[k * IF_FEATURES]);
    uint32_t dt = micros() - t0;
    Serial.printf("TIMING|run=%d|%.2f us per score|%d scores in %lu us\n", rep + 1, (double)dt / IF_TEST_N, IF_TEST_N, (unsigned long)dt);
  }
  Serial.printf("MEMORY|free heap %u B|model arrays in flash about %u B\n", (unsigned)ESP.getFreeHeap(),
                (unsigned)(IF_NODES * (1 + 4 + 2 + 2) + IF_TREES * 2));
  Serial.println(flagDiff == 0 && maxErr < 1e-4 ? "RESULT|PASS" : "RESULT|CHECK");
  Serial.println("DONE");
}

void loop() {}
