// Vaccine fridge monitor for an ESP32-S3.
//
// The compressor state is inferred from the temperature (on at 8 C or above, off at 2 C or below). Each
// completed ON or OFF phase is timed and handed to the decision logic in fridge_logic.h. The first
// CALIBRATION_CYCLES phases of each kind set a baseline ON/OFF ratio, and after that the ratio over the last
// five phases is compared with it: Warning above 1.8x, Critical above 3.5x, each only after
// PERSISTENCE_WINDOWS evaluations in a row. The first cycle after a door event is ignored.
//
// Settings: 24 calibration phases and persistence 6 are the values that did best when the rule was replayed
// on recorded household-fridge traces. They have not been tested on a real fridge. DEMO_SHORT_SETTINGS 1
// switches back to 3 phases and no persistence, which is quicker to step through by hand in Wokwi.
//
// SIMULATED_TEMPERATURE 1 makes the sketch produce its own temperature, door, gas and clock values, so it
// runs on a bare board. See the README in this folder.
//
// Structure: the decision logic has no Arduino calls, so the same file builds on the board, in Wokwi and on
// a computer. Wi-Fi and MQTT run in their own task on core 0 and read a status snapshot, so a slow broker
// cannot hold up sensing. Buzzer sounds are played in steps from loop(), so nothing blocks.

#include <DHT.h>
#include <Wire.h>
#include <RTClib.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include "fridge_logic.h"

// ---- Pin definitions (ESP32-S3 safe pins) ----

#define DHT_PIN 18
#define DHT_TYPE DHT22
#define DOOR_PIN 5
#define LED_GREEN 6
#define LED_YELLOW 7
#define LED_RED 15
#define LED_COMPRESSOR 16
#define BUZZER_PIN 17
#define MQ2_PIN 8
#define RTC_SDA 11
#define RTC_SCL 12

// ---- Fridge parameters ----

#define SAFE_MIN 2.0
#define SAFE_MAX 8.0
#define DEMO_SHORT_SETTINGS 0       // 1 = original settings (3 calibration phases, no persistence), for demos in Wokwi
#if DEMO_SHORT_SETTINGS
#define CALIBRATION_CYCLES 3
#define PERSISTENCE_WINDOWS 1
#else
#define CALIBRATION_CYCLES 24       // phases of each kind used for the baseline (proposed after the REFIT replay)
#define PERSISTENCE_WINDOWS 6       // evaluations in a row above a threshold before an alert is raised
#endif
#define ROLLING_WINDOW_SIZE 5       // smooth over last 5 cycles (single cycles are noisy)
#define WARNING_DRIFT_FACTOR 1.8    // chosen from the Python simulation output, not from real fridge data (see README)
#define CRITICAL_DRIFT_FACTOR 3.5   // chosen from the Python simulation output, not from real fridge data (see README)
// Self-running test, no sensors needed. One scenario: healthy cycling, a growing fault (Warning, then
// Critical), recovery, a gas reading above the threshold, then the door open with the temperature held at
// 9 C. It is a test signal, not fridge data, and the exposure alert is cut to 2 minutes in this mode.
#ifndef SIMULATED_TEMPERATURE
#define SIMULATED_TEMPERATURE 0
#endif
#define SIM_ON_SECONDS 10           // healthy ON phase
#define SIM_OFF_SECONDS 12          // healthy OFF phase
#define SIM_FAULT_FACTOR 5.0        // ON phase reaches this multiple of its healthy length
#define SIM_RAMP_PAIRS 12           // ON/OFF pairs over which the fault grows
#define SIM_HOLD_PAIRS 4            // pairs at the full fault size
#define SIM_RECOVERY_PAIRS 8        // healthy pairs after the fault, so the alert can clear
#define SIM_GAS_SECONDS 30          // gas reading above the threshold for this long
#define SIM_WARM_SECONDS 180        // door open and temperature held at 9 C for this long

#define ALERT_REPEAT_INTERVAL_MS 15000
#define GAS_THRESHOLD 2000
#define GAS_CHECK_INTERVAL_MS 5000
#define SAMPLE_INTERVAL_MS 2000    // temperature is read every 2 s (the DHT22 cannot be read faster)
#if SIMULATED_TEMPERATURE
#define EXPOSURE_ALERT_MINUTES 2    // shortened for the self-running test
#else
#define EXPOSURE_ALERT_MINUTES 30
#endif
#define MQTT_RETRY_INTERVAL_MS 10000

// ---- Wi-Fi and MQTT ----

// Wokwi-GUEST works in Wokwi only. On a real board, put your own hotspot here on your computer and
// do not commit it.
const char* WIFI_SSID = "Wokwi-GUEST";
const char* WIFI_PASSWORD = "";

const char* MQTT_BROKER = "broker.emqx.io";
const int MQTT_PORT = 1883;
const char* MQTT_TOPIC = "ghana-vaccine-fridge-AduGyamfiKwadwo-2026/status";

WiFiClient espClient;
PubSubClient mqttClient(espClient);
unsigned long lastMqttAttempt = 0;

DHT dht(DHT_PIN, DHT_TYPE);
RTC_DS1307 rtc;

#if SIMULATED_TEMPERATURE
int simGasValue = 1100;                         // raw MQ2-style reading made up by the test scenario
bool simDoorOpen = false;                       // door state made up by the test scenario
#endif

// Clock, gas and door reads go through these so the test mode can replace them.
struct ClockNow {
  int d, h, m, s;
  int day() const { return d; }
  int hour() const { return h; }
  int minute() const { return m; }
  int second() const { return s; }
};

ClockNow clockNow() {
#if SIMULATED_TEMPERATURE
  unsigned long sec = 12UL * 3600UL + millis() / 1000UL;      // starts at 12:00:00, the day never changes
  ClockNow c = {16, (int)((sec / 3600) % 24), (int)((sec / 60) % 60), (int)(sec % 60)};
  return c;
#else
  DateTime t = rtc.now();
  ClockNow c = {t.day(), t.hour(), t.minute(), t.second()};
  return c;
#endif
}

int readGas() {
#if SIMULATED_TEMPERATURE
  return simGasValue;
#else
  return analogRead(MQ2_PIN);
#endif
}

bool readDoor() {
#if SIMULATED_TEMPERATURE
  return simDoorOpen;
#else
  return digitalRead(DOOR_PIN) == LOW;
#endif
}

bool compressorOn = false;
unsigned long cycleStartTime = 0;

DriftDetector<CALIBRATION_CYCLES, ROLLING_WINDOW_SIZE, PERSISTENCE_WINDOWS> detector;
bool firstTransitionSeen = false;   // the first transition after boot starts from an unknown phase, so it is skipped

bool doorOpen = false;
bool ignoreNextCycle = false;

int currentAlertLevel = 0;
unsigned long lastAlertSoundTime = 0;

unsigned long lastGasCheckTime = 0;
unsigned long lastSampleMs = 0;
bool gasAlertActive = false;
int lastGasReading = 0;

unsigned long warmSecondsToday = 0;
unsigned long warmMsAccum = 0;
unsigned long lastExposureTickMs = 0;
int lastLoggedDay = -1;
bool exposureAlertActive = false;

float lastTemperature = 0;

// ---- Status snapshot (loop() writes it, the network task reads it) ----

struct StatusSnapshot {
  float temperature;
  bool compressorOn;
  int alertLevel;
  bool gasAlert;
  int gasReading;
  unsigned long warmMinutes;
  bool doorOpen;
  char timeStr[9];
  bool valid;
};

StatusSnapshot snapshot;                       // zero-initialised, valid = false until first update
portMUX_TYPE snapshotMux = portMUX_INITIALIZER_UNLOCKED;

// Called from loop() only (it reads the RTC over I2C, which must stay in one task).
void updateSnapshot() {
  ClockNow now = clockNow();

  StatusSnapshot s;
  s.temperature = lastTemperature;
  s.compressorOn = compressorOn;
  s.alertLevel = currentAlertLevel;
  s.gasAlert = gasAlertActive;
  s.gasReading = lastGasReading;
  s.warmMinutes = warmSecondsToday / 60;
  s.doorOpen = doorOpen;
  snprintf(s.timeStr, sizeof(s.timeStr), "%02d:%02d:%02d", now.hour(), now.minute(), now.second());
  s.valid = true;

  portENTER_CRITICAL(&snapshotMux);
  snapshot = s;
  portEXIT_CRITICAL(&snapshotMux);
}

// ---- MQTT (runs in the network task, so a blocking connect can never stall loop()) ----

void tryConnectMQTT() {
  if (mqttClient.connected()) return;
  if (millis() - lastMqttAttempt < MQTT_RETRY_INTERVAL_MS) return;

  lastMqttAttempt = millis();
  Serial.print("Attempting MQTT connection...");
  String clientId = "esp32-fridge-" + String(random(0xffff), HEX);

  if (mqttClient.connect(clientId.c_str())) {
    Serial.println(" connected.");
  } else {
    Serial.print(" failed, rc=");
    Serial.print(mqttClient.state());
    Serial.println(" -- will retry later. Core safety functions unaffected.");
  }
}

void publishStatus() {
  if (!mqttClient.connected()) return;

  mqttClient.loop();

  StatusSnapshot s;
  portENTER_CRITICAL(&snapshotMux);
  s = snapshot;
  portEXIT_CRITICAL(&snapshotMux);
  if (!s.valid) return;                         // nothing measured yet

  const char* alertText = "Normal";
  if (s.alertLevel == 1) alertText = "Warning";
  if (s.alertLevel == 2) alertText = "Critical";

  char payload[350];
  snprintf(payload, sizeof(payload),
    "{\"temperature\":%.1f,\"compressor\":\"%s\",\"alertLevel\":%d,\"alertText\":\"%s\",\"gasAlert\":%s,\"gasReading\":%d,\"warmMinutesToday\":%lu,\"door\":\"%s\",\"deviceTime\":\"%s\"}",
    s.temperature,
    s.compressorOn ? "ON" : "OFF",
    s.alertLevel,
    alertText,
    s.gasAlert ? "true" : "false",
    s.gasReading,
    s.warmMinutes,
    s.doorOpen ? "OPEN" : "CLOSED",
    s.timeStr
  );

  mqttClient.publish(MQTT_TOPIC, payload);
  Serial.print("Published: ");
  Serial.println(payload);
}

void networkTask(void *) {
  bool wifiAnnounced = false;
  for (;;) {
    if (WiFi.status() == WL_CONNECTED) {
      if (!wifiAnnounced) {
        Serial.print("WiFi connected. IP: ");
        Serial.println(WiFi.localIP());
        wifiAnnounced = true;
      }
      tryConnectMQTT();
      publishStatus();
    } else {
      wifiAnnounced = false;
    }
    vTaskDelay(pdMS_TO_TICKS(2000));
  }
}

// ---- Setup ----

void setup() {
  Serial.begin(115200);

  pinMode(DHT_PIN, INPUT_PULLUP);
  dht.begin();
  delay(2000);

  pinMode(DOOR_PIN, INPUT_PULLUP);
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_YELLOW, OUTPUT);
  pinMode(LED_RED, OUTPUT);
  pinMode(LED_COMPRESSOR, OUTPUT);
  pinMode(MQ2_PIN, INPUT);

  ledcAttach(BUZZER_PIN, 2000, 8);

#if !SIMULATED_TEMPERATURE
  Wire.begin(RTC_SDA, RTC_SCL);
  if (!rtc.begin()) {
    Serial.println("RTC not found -- check wiring.");
  }
  if (!rtc.isrunning()) {
    Serial.println("RTC not running, setting to compile time (demo only).");
    rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
  }
#endif

  ClockNow now = clockNow();
  lastLoggedDay = now.day();

  cycleStartTime = millis();

  Serial.println("Starting Wi-Fi in the background (core safety functions never wait for it)...");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);   // always set, even if Wi-Fi is not up yet
  mqttClient.setSocketTimeout(3);                  // give up on a silent broker after 3 s (default 15 s)

  Serial.println("System started. Calibrating baseline cycle behavior...");
#if SIMULATED_TEMPERATURE
  Serial.println("SIMULATED TEMPERATURE MODE: the temperature is generated by the sketch, not read from a sensor.");
#endif

  lastExposureTickMs = millis();
  // Priority 0, the same as the idle task. At priority 1 a long wait on the broker starved the idle task
  // and the watchdog reset the chip.
  xTaskCreatePinnedToCore(networkTask, "net", 8192, NULL, 0, NULL, 0);
}

// ---- Buzzer sounds ----
// A sound is a list of (frequency, length) steps played by buzzerUpdate() from loop(). A new sound replaces
// the current one only if its priority is the same or higher.

struct ToneStep { uint16_t freq; uint16_t ms; };            // freq 0 is silence
#define MAX_TONE_STEPS 170
ToneStep toneSteps[MAX_TONE_STEPS];
int toneCount = 0, toneIndex = 0, tonePriority = 0;
unsigned long toneStepStart = 0;
bool toneActive = false;

void stopTone() {
  ledcWriteTone(BUZZER_PIN, 0);
}

void startTones(int priority, int count) {
  if (toneActive && priority < tonePriority) return;
  toneCount = count;
  toneIndex = 0;
  tonePriority = priority;
  toneActive = count > 0;
  toneStepStart = millis();
  if (toneActive) ledcWriteTone(BUZZER_PIN, toneSteps[0].freq);
}

void buzzerUpdate() {
  if (!toneActive) return;
  if (millis() - toneStepStart < toneSteps[toneIndex].ms) return;
  toneIndex++;
  toneStepStart = millis();
  if (toneIndex >= toneCount) {
    toneActive = false;
    stopTone();
  } else {
    ledcWriteTone(BUZZER_PIN, toneSteps[toneIndex].freq);
  }
}

int addTone(int n, int freq, int ms) {
  toneSteps[n].freq = freq;
  toneSteps[n].ms = ms;
  return n + 1;
}

void warningBeep() {             // two short beeps
  int n = 0;
  n = addTone(n, 1200, 150); n = addTone(n, 0, 100);
  n = addTone(n, 1200, 150);
  startTones(1, n);
}

void criticalSiren() {           // three sweeps up and down, about 1.25 s
  int n = 0;
  for (int repeat = 0; repeat < 3; repeat++) {
    for (int freq = 800; freq <= 1800; freq += 40) n = addTone(n, freq, 8);
    for (int freq = 1800; freq >= 800; freq -= 40) n = addTone(n, freq, 8);
  }
  startTones(3, n);
}

void gasAlertBeep() {            // three short beeps
  int n = 0;
  for (int i = 0; i < 3; i++) { n = addTone(n, 600, 100); n = addTone(n, 0, 80); }
  startTones(2, n);
}

void exposureAlertChime() {      // three falling notes
  int notes[] = {1500, 1100, 700};
  int n = 0;
  for (int i = 0; i < 3; i++) { n = addTone(n, notes[i], 250); n = addTone(n, 0, 100); }
  startTones(2, n);
}

void playAlertForLevel(int level) {
  if (level == 2) {
    criticalSiren();
  } else if (level == 1) {
    warningBeep();
  }
  lastAlertSoundTime = millis();
}

// ---- Status LEDs ----

void setStatusLEDs(int level) {
  currentAlertLevel = level;
  digitalWrite(LED_GREEN, level == 0 ? HIGH : LOW);
  digitalWrite(LED_YELLOW, level == 1 ? HIGH : LOW);
  digitalWrite(LED_RED, level == 2 ? HIGH : LOW);
}

// ---- Gas and misuse check ----

void checkGasSensor() {
  int gasLevel = readGas();
  lastGasReading = gasLevel;

  Serial.print("Gas sensor reading: ");
  Serial.println(gasLevel);

  if (gasLevel > GAS_THRESHOLD) {
    if (!gasAlertActive) {
      Serial.println("MISUSE ALERT: Possible non-vaccine item (combustible vapor source) detected in fridge.");
    }
    gasAlertActive = true;
    digitalWrite(LED_YELLOW, HIGH);
    digitalWrite(LED_RED, HIGH);
    gasAlertBeep();
  } else {
    if (gasAlertActive) {
      Serial.println("Gas/misuse alert cleared.");
    }
    gasAlertActive = false;
    setStatusLEDs(currentAlertLevel);
  }
}

// ---- Cumulative vaccine exposure tracking (RTC-based) ----

void updateExposureTracking(float temperature) {
  ClockNow now = clockNow();

  if (now.day() != lastLoggedDay) {
    Serial.println("New day -- resetting cumulative exposure counter.");
    warmSecondsToday = 0;
    warmMsAccum = 0;
    exposureAlertActive = false;
    lastLoggedDay = now.day();
  }

  unsigned long nowMs = millis();
  unsigned long elapsedMs = nowMs - lastExposureTickMs;
  lastExposureTickMs = nowMs;

  if (temperature >= SAFE_MAX) {
    warmMsAccum += elapsedMs;
    warmSecondsToday = warmMsAccum / 1000;
  }

  unsigned long warmMinutesToday = warmSecondsToday / 60;

  Serial.print("[");
  char clockText[10];
  snprintf(clockText, sizeof(clockText), "%02d:%02d:%02d", now.hour(), now.minute(), now.second());
  Serial.print(clockText);
  Serial.print("] Cumulative warm-time today: ");
  Serial.print(warmMinutesToday);
  Serial.println(" min");

  if (warmMinutesToday >= EXPOSURE_ALERT_MINUTES && !exposureAlertActive) {
    exposureAlertActive = true;
    Serial.print("EXPOSURE RISK ALERT: Cumulative warm-time exceeded ");
    Serial.print(EXPOSURE_ALERT_MINUTES);
    Serial.println(" minutes today. Vaccine potency may be at risk.");
    exposureAlertChime();
  }
}

// ---- Handle a completed ON/OFF cycle ----

void handleCompletedCycle(bool wasOn, float durationSeconds) {
  if (ignoreNextCycle) {
    Serial.println("Cycle ignored (right after door event).");
    ignoreNextCycle = false;
    return;
  }

  if (!firstTransitionSeen) {
    firstTransitionSeen = true;
    Serial.println("First transition after boot skipped (start phase unknown).");
    return;
  }

  bool wasCalibrated = detector.isCalibrated();
  int level = detector.addPhase(wasOn, durationSeconds);

  if (!wasCalibrated) {
    if (detector.isCalibrated()) {
      Serial.print("Calibration complete. Baseline ON: ");
      Serial.print(detector.baselineOnSeconds());
      Serial.print("s, Baseline OFF: ");
      Serial.println(detector.baselineOffSeconds());
    } else {
      Serial.print("Calibrating... ON phases: ");
      Serial.print(detector.onPhasesCalibrated());
      Serial.print(" of ");
      Serial.print(CALIBRATION_CYCLES);
      Serial.print(", OFF phases: ");
      Serial.print(detector.offPhasesCalibrated());
      Serial.print(" of ");
      Serial.println(CALIBRATION_CYCLES);
    }
    return;
  }

  if (level < 0) {
    Serial.println("Gathering more cycles before evaluating (rolling window not full yet).");
    return;
  }

  Serial.print("Smoothed drift factor (rolling avg of last ");
  Serial.print(ROLLING_WINDOW_SIZE);
  Serial.print(" cycles): ");
  Serial.println(detector.lastDrift());

  if (level == 2) {
    Serial.println("CRITICAL: Compressor cycling pattern significantly abnormal (sustained).");
  } else if (level == 1) {
    Serial.println("WARNING: Early sign of abnormal cycling detected (sustained).");
  } else if (detector.warningRun() > 0) {
    Serial.print("Drift above the Warning threshold for ");
    Serial.print(detector.warningRun());
    Serial.print(" of ");
    Serial.print(PERSISTENCE_WINDOWS);
    Serial.println(" evaluations in a row; no alert yet.");
  }

  if (level == 0 && currentAlertLevel > 0) {
    Serial.println("Cycling is back within normal limits.");
  }
  setStatusLEDs(level);
  if (level > 0) {
    playAlertForLevel(level);
  }
}

#if SIMULATED_TEMPERATURE
// Returns 5 C (inside the hysteresis band) except once at the end of a phase, when it returns 9 C or 1 C to
// trigger the next transition. simStage: 0 cycling (healthy, fault, recovery), 1 gas event, 2 wait for the
// next ON phase, 3 warm excursion with the door open, 4 healthy cycling again.
unsigned long simPhaseStartMs = 0, simPhaseMs = 0, simRandom = 12345, simStageStartMs = 0;
bool simInit = false, simCompressorOn = true;
int simPairs = 0, simStage = 0;

float simJitter() {                       // about +/- 4 percent, repeatable
  simRandom = simRandom * 1103515245UL + 12345UL;
  return 0.96f + 0.08f * ((simRandom >> 16) & 0xFF) / 255.0f;
}

unsigned long simPhaseLengthMs(bool compressorOn) {
  float length = (compressorOn ? SIM_ON_SECONDS : SIM_OFF_SECONDS) * 1000.0f * simJitter();
  int healthyPairs = CALIBRATION_CYCLES + 4;
  int faultEnd = healthyPairs + SIM_RAMP_PAIRS + SIM_HOLD_PAIRS;
  if (compressorOn && simStage == 0 && simPairs >= healthyPairs && simPairs < faultEnd) {
    float growth = (float)(simPairs - healthyPairs + 1) / SIM_RAMP_PAIRS;
    if (growth > 1.0f) growth = 1.0f;
    length *= 1.0f + (SIM_FAULT_FACTOR - 1.0f) * growth;
  }
  return (unsigned long)length;
}

float simulatedTemperature() {
  unsigned long now = millis();
  if (!simInit) {
    simInit = true;
    simPhaseStartMs = now;
    simPhaseMs = simPhaseLengthMs(true);
    return 9.0;
  }
  int scenarioEnd = CALIBRATION_CYCLES + 4 + SIM_RAMP_PAIRS + SIM_HOLD_PAIRS + SIM_RECOVERY_PAIRS;
  if (simStage == 0 && simPairs >= scenarioEnd) {
    simStage = 1;
    simStageStartMs = now;
    simGasValue = 3000;
  }
  if (simStage == 1 && now - simStageStartMs >= SIM_GAS_SECONDS * 1000UL) {
    simGasValue = 1100;
    simStage = 2;
  }
  if (simStage == 3) {                                     // warm excursion: door open, held at 9 C
    if (now - simPhaseStartMs >= 4000) simDoorOpen = true;
    if (now - simPhaseStartMs >= simPhaseMs) {
      simDoorOpen = false;
      simStage = 4;
      simCompressorOn = false;
      simPhaseStartMs = now;
      simPhaseMs = simPhaseLengthMs(false);
      return 1.0;
    }
    return 9.0;
  }
  if (now - simPhaseStartMs < simPhaseMs) return 5.0;
  simCompressorOn = !simCompressorOn;
  simPhaseStartMs = now;
  if (simCompressorOn) simPairs++;
  if (simCompressorOn && simStage == 2) {                  // start the warm excursion with this ON phase
    simStage = 3;
    simPhaseMs = SIM_WARM_SECONDS * 1000UL;
    return 9.0;
  }
  simPhaseMs = simPhaseLengthMs(simCompressorOn);
  return simCompressorOn ? 9.0 : 1.0;
}
#endif

// ---- Main loop ----

void loop() {
  buzzerUpdate();
  if (millis() - lastSampleMs < SAMPLE_INTERVAL_MS) {
    delay(1);                    // lets the idle task run; the buzzer is serviced on every pass
    return;
  }
  lastSampleMs = millis();

#if SIMULATED_TEMPERATURE
  float temperature = simulatedTemperature();
#else
  float temperature = dht.readTemperature();
#endif

  if (isnan(temperature)) {
    Serial.println("Sensor read failed.");
    return;
  }

  lastTemperature = temperature;

  bool doorReading = readDoor();
  if (doorReading && !doorOpen) {
    doorOpen = true;
    ignoreNextCycle = true;
    Serial.println("Door opened.");
  } else if (!doorReading && doorOpen) {
    doorOpen = false;
    Serial.println("Door closed.");
  }

  bool shouldBeOn = compressorOn;
  if (temperature >= SAFE_MAX) shouldBeOn = true;
  else if (temperature <= SAFE_MIN) shouldBeOn = false;

  if (shouldBeOn != compressorOn) {
    unsigned long now = millis();
    float durationSeconds = (now - cycleStartTime) / 1000.0;
    handleCompletedCycle(compressorOn, durationSeconds);

    compressorOn = shouldBeOn;
    cycleStartTime = now;
    digitalWrite(LED_COMPRESSOR, compressorOn ? HIGH : LOW);
  }

  if (currentAlertLevel > 0 && (millis() - lastAlertSoundTime >= ALERT_REPEAT_INTERVAL_MS)) {
    Serial.println("Repeating alert -- condition still abnormal.");
    playAlertForLevel(currentAlertLevel);
  }

  if (millis() - lastGasCheckTime >= GAS_CHECK_INTERVAL_MS) {
    checkGasSensor();
    lastGasCheckTime = millis();
  }

  updateExposureTracking(temperature);

  updateSnapshot();

  Serial.print("Temp: ");
  Serial.print(temperature);
  Serial.print(" C | Compressor: ");
  Serial.println(compressorOn ? "ON" : "OFF");
}
