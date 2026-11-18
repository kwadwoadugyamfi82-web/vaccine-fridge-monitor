// replay_runner.h
// Feeds recorded ON/OFF phases through DriftDetector and counts the alert levels. Plain C++, so the board
// and a computer give identical output for identical input.
//
// Entry format (uint16_t): 0xFFFF is an outage marker (the detector restarts); otherwise bit 15 is set for
// an ON phase and bits 0 to 14 hold the duration in seconds.
#pragma once
#include <stdint.h>
#include "fridge_logic.h"

struct ReplayResult {
  uint32_t evals, lvl0, lvl1, lvl2, hash;
};

template <int CAL, int WIN, int PERSIST>
ReplayResult replaySeries(const uint16_t* data, uint32_t n) {
  DriftDetector<CAL, WIN, PERSIST> det;
  ReplayResult r = {0, 0, 0, 0, 2166136261u};     // FNV-1a offset basis
  for (uint32_t i = 0; i < n; i++) {
    uint16_t v = data[i];
    if (v == 0xFFFF) { det.reset(); continue; }
    int lvl = det.addPhase((v & 0x8000) != 0, (double)(v & 0x7FFF));
    if (lvl < 0) continue;
    r.evals++;
    if (lvl == 0) r.lvl0++; else if (lvl == 1) r.lvl1++; else r.lvl2++;
    r.hash ^= (uint8_t)lvl;
    r.hash *= 16777619u;                          // FNV-1a prime
  }
  return r;
}
