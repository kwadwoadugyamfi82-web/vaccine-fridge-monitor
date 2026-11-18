// decision_logic_bench.ino
// Times the decision logic per completed cycle on an ESP32-S3. No sensors or Wi-Fi needed.
// The logic is the one from the first version of the firmware (3 calibration phases, no persistence) with
// the Serial, LED and buzzer code removed and the rolling-window fill bug fixed. The later 24/6 settings
// are not included, so this measures the original rule. The replay test times fridge_logic.h itself.

#define ROLLING_WINDOW_SIZE 5
#define WARNING_DRIFT_FACTOR 1.8f
#define CRITICAL_DRIFT_FACTOR 3.5f
#define CALIBRATION_CYCLES 3
#define N_ITER 20000

float baselineOnTime = 0, baselineOffTime = 0;
int completedCalibrationCycles = 0;
bool calibrated = false;
float recentOn[ROLLING_WINDOW_SIZE], recentOff[ROLLING_WINDOW_SIZE];
int onCount = 0, offCount = 0;

void addToWindow(float *arr, int &count, float v) {
  if (count < ROLLING_WINDOW_SIZE) {
    arr[count++] = v;                      // append while filling
  } else {
    for (int i = 0; i < ROLLING_WINDOW_SIZE - 1; i++) arr[i] = arr[i + 1];
    arr[ROLLING_WINDOW_SIZE - 1] = v;      // slide when full
  }
}

float avg(float *arr, int count) {
  float s = 0;
  for (int i = 0; i < count; i++) s += arr[i];
  return count ? s / count : 0;
}

// returns alert level 0/1/2, or -1 if still calibrating / gathering
int evaluateCycle(bool wasOn, float durationSeconds) {
  if (!calibrated) {
    if (wasOn) {
      baselineOnTime = ((baselineOnTime * completedCalibrationCycles) + durationSeconds) / (completedCalibrationCycles + 1);
    } else {
      baselineOffTime = ((baselineOffTime * completedCalibrationCycles) + durationSeconds) / (completedCalibrationCycles + 1);
      completedCalibrationCycles++;
    }
    if (completedCalibrationCycles >= CALIBRATION_CYCLES) calibrated = true;
    return -1;
  }
  if (wasOn) addToWindow(recentOn, onCount, durationSeconds);
  else addToWindow(recentOff, offCount, durationSeconds);
  if (onCount < 2 || offCount < 2) return -1;

  float drift = (avg(recentOn, onCount) / avg(recentOff, offCount)) / (baselineOnTime / baselineOffTime);
  if (drift > CRITICAL_DRIFT_FACTOR) return 2;
  if (drift > WARNING_DRIFT_FACTOR) return 1;
  return 0;
}

// deterministic synthetic cycles: healthy (19s on / 41s off) then degrading (on grows)
float synthDuration(int i, bool on) {
  float base = on ? 19.0f : 41.0f;
  if (on && i > N_ITER / 2) base *= 1.0f + 3.0f * (float)(i - N_ITER / 2) / (N_ITER / 2);
  return base + (float)((i * 7) % 5) * 0.2f;
}

void setup() {
  Serial.begin(115200);
  delay(1500);
  Serial.println("\n=== decision-logic benchmark ===");
  Serial.printf("CPU MHz: %d | free heap: %u B | sketch size: %u B | chip: %s rev %d\n",
                getCpuFrequencyMhz(), ESP.getFreeHeap(), ESP.getSketchSize(), ESP.getChipModel(), ESP.getChipRevision());

  uint32_t minC = 0xFFFFFFFF, maxC = 0;
  uint64_t sumC = 0;
  int lvl[3] = {0, 0, 0};
  volatile int sink = 0;

  for (int i = 0; i < N_ITER; i++) {
    bool on = (i % 2 == 0);
    float d = synthDuration(i, on);
    uint32_t t0 = ESP.getCycleCount();
    int r = evaluateCycle(on, d);
    uint32_t t1 = ESP.getCycleCount();
    sink += r;
    if (r >= 0) lvl[r]++;
    uint32_t c = t1 - t0;
    if (c < minC) minC = c;
    if (c > maxC) maxC = c;
    sumC += c;
  }
  float us_per_cycle = 1.0f / getCpuFrequencyMhz();   // microseconds per CPU cycle
  Serial.printf("calls: %d\n", N_ITER);
  Serial.printf("per-call time  min: %.2f us | mean: %.2f us | max: %.2f us\n",
                minC * us_per_cycle, (float)sumC / N_ITER * us_per_cycle, maxC * us_per_cycle);
  Serial.printf("alert levels produced  normal: %d | warning: %d | critical: %d  (sanity check)\n", lvl[0], lvl[1], lvl[2]);
  Serial.println("Note: max includes occasional interrupt/Wi-Fi-stack jitter; report min/mean/max, not just mean.");
}

void loop() {}
