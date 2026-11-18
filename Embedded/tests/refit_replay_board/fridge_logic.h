// fridge_logic.h
// Compressor-cycle decision logic with no Arduino calls, so it builds on the board, in Wokwi and on a computer.
//
// Phases are completed ON or OFF durations in seconds. The first CAL ON phases and the first CAL OFF phases
// set the baseline ON/OFF ratio. After that, the mean of the last WIN ON phases over the mean of the last WIN
// OFF phases, divided by the baseline ratio, is the drift. Warning above 1.8 and Critical above 3.5, each only
// after PERSIST evaluations in a row.
//
// Settings in use: CAL 3, WIN 5, PERSIST 1 (original firmware) and CAL 24, WIN 5, PERSIST 6 (chosen by
// leave-one-house-out testing on recorded household-fridge traces, see the README).
#pragma once
#include <stdint.h>

#ifndef WARNING_DRIFT_FACTOR
#define WARNING_DRIFT_FACTOR 1.8
#endif
#ifndef CRITICAL_DRIFT_FACTOR
#define CRITICAL_DRIFT_FACTOR 3.5
#endif

template <int CAL, int WIN, int PERSIST>
class DriftDetector {
 public:
  DriftDetector() { reset(); }

  void reset() {
    calOn = calOff = 0;
    calOnSum = calOffSum = 0.0;
    calibrated = false;
    nOn = nOff = 0;
    warnRun = critRun = 0;
    drift = 0.0;
  }

  // Feed one completed phase. Returns -1 while calibrating or gathering, otherwise the alert level
  // (0 normal, 1 warning, 2 critical).
  int addPhase(bool wasOn, double seconds) {
    push(wasOn ? recOn : recOff, wasOn ? nOn : nOff, seconds);

    if (!calibrated) {
      if (wasOn) {
        if (calOn < CAL) { calOnSum += seconds; calOn++; }
      } else {
        if (calOff < CAL) { calOffSum += seconds; calOff++; }
      }
      if (calOn >= CAL && calOff >= CAL) {
        baselineOn = calOnSum / CAL;
        baselineOff = calOffSum / CAL;
        calibrated = true;
      }
      return -1;
    }

    if (nOn < 2 || nOff < 2) return -1;
    double smoothedOn = mean(recOn, nOn);
    double smoothedOff = mean(recOff, nOff);
    if (baselineOff <= 0 || smoothedOff <= 0) return -1;
    double baselineRatio = baselineOn / baselineOff;
    if (baselineRatio <= 0) return -1;
    drift = (smoothedOn / smoothedOff) / baselineRatio;

    warnRun = (drift > WARNING_DRIFT_FACTOR) ? warnRun + 1 : 0;
    critRun = (drift > CRITICAL_DRIFT_FACTOR) ? critRun + 1 : 0;
    if (critRun >= PERSIST) return 2;
    if (warnRun >= PERSIST) return 1;
    return 0;
  }

  bool isCalibrated() const { return calibrated; }
  int onPhasesCalibrated() const { return calOn; }
  int offPhasesCalibrated() const { return calOff; }
  double baselineOnSeconds() const { return baselineOn; }
  double baselineOffSeconds() const { return baselineOff; }
  double lastDrift() const { return drift; }
  int warningRun() const { return warnRun; }
  int criticalRun() const { return critRun; }

 private:
  static void push(double* arr, int& count, double v) {
    if (count < WIN) {
      arr[count++] = v;                       // window still filling: append
    } else {
      for (int i = 0; i < WIN - 1; i++) arr[i] = arr[i + 1];
      arr[WIN - 1] = v;                       // window full: slide left
    }
  }
  static double mean(const double* arr, int count) {
    double s = 0.0;
    for (int i = 0; i < count; i++) s += arr[i];
    return s / count;
  }

  double recOn[WIN], recOff[WIN];
  int nOn, nOff;
  int calOn, calOff;
  double calOnSum, calOffSum;
  double baselineOn = 0.0, baselineOff = 0.0;
  bool calibrated;
  int warnRun, critRun;
  double drift;
};
