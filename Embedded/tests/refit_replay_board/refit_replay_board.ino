// refit_replay_board.ino
// Runs the decision logic on the ESP32-S3 over recorded REFIT compressor phases. No sensors or Wi-Fi needed.
// The board prints one RESULT line per appliance and setting; they should match
// ML-Validation/results/replay_expected.txt.
//
// replay_data.h is not in the repo. Generate it with ML-Validation/refit/make_replay_data.py (it lands in this
// folder). This is a replay of recorded traces, not a test with physical sensors.

#include "replay_data.h"
#include "replay_runner.h"

// A macro rather than a template function, so the Arduino build does not need a prototype for it.
#define RUN_ALL(CAL, WIN, PERSIST, LABEL)                                                          \
  for (int s = 0; s < N_SERIES; s++) {                                                             \
    uint32_t t0 = ESP.getCycleCount();                                                             \
    ReplayResult r = replaySeries<CAL, WIN, PERSIST>(SERIES[s].data, SERIES[s].n);                 \
    uint32_t cycles = ESP.getCycleCount() - t0;  /* wraps after about 17 s; each call is shorter */ \
    Serial.printf("RESULT|%s|CAL=%d WIN=%d P=%d|evals=%lu|lvl0=%lu|lvl1=%lu|lvl2=%lu|hash=%08lX\n", \
                  SERIES[s].name, CAL, WIN, PERSIST,                                               \
                  (unsigned long)r.evals, (unsigned long)r.lvl0, (unsigned long)r.lvl1,            \
                  (unsigned long)r.lvl2, (unsigned long)r.hash);                                   \
    Serial.printf("TIMING|%s|%s|phases=%lu|%.3f us per phase (replay loop included)\n",            \
                  SERIES[s].name, LABEL, (unsigned long)SERIES[s].n,                               \
                  (double)cycles / (double)getCpuFrequencyMhz() / (double)SERIES[s].n);            \
  }

void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.printf("\n=== REFIT replay on ESP32-S3 | chip %s rev %d | %d MHz | sketch %u B ===\n",
                ESP.getChipModel(), (int)ESP.getChipRevision(), (int)getCpuFrequencyMhz(), (unsigned)ESP.getSketchSize());
  RUN_ALL(3, 5, 1, "original settings");
  RUN_ALL(24, 5, 6, "proposed settings");
  Serial.println("DONE");
}

void loop() {}
