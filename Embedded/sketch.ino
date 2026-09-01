#include <DHT.h>
#include <Wire.h>
#include <RTClib.h>
#include <WiFi.h>
#include <PubSubClient.h>

// -----------------------------
// PIN DEFINITIONS (ESP32-S3 safe pins)
// -----------------------------

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

// -----------------------------
// FRIDGE PARAMETERS
// -----------------------------

#define SAFE_MIN 2.0
#define SAFE_MAX 8.0
#define CALIBRATION_CYCLES 3
#define ROLLING_WINDOW_SIZE 5       // smooth over last 5 cycles (data-derived: single cycles are too noisy)
#define WARNING_DRIFT_FACTOR 1.8    // derived from real data: degrading hours averaged ~2.55x baseline
#define CRITICAL_DRIFT_FACTOR 3.5   // derived from real data: late-stage degrading averaged ~5x baseline
#define ALERT_REPEAT_INTERVAL_MS 15000
#define GAS_THRESHOLD 2000
#define GAS_CHECK_INTERVAL_MS 5000
#define EXPOSURE_ALERT_MINUTES 30
#define LOOP_INTERVAL_SECONDS 2
#define MQTT_RETRY_INTERVAL_MS 10000

// -----------------------------
// WIFI + MQTT
// -----------------------------

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

bool compressorOn = false;
unsigned long cycleStartTime = 0;

float baselineOnTime = 0;
float baselineOffTime = 0;
int completedCalibrationCycles = 0;
bool calibrated = false;

// Rolling window of recent cycle durations (data-derived fix for single-cycle noise)
float recentOnTimes[ROLLING_WINDOW_SIZE];
float recentOffTimes[ROLLING_WINDOW_SIZE];
int onCount = 0;
int offCount = 0;

bool doorOpen = false;
bool ignoreNextCycle = false;

int currentAlertLevel = 0;
unsigned long lastAlertSoundTime = 0;

unsigned long lastGasCheckTime = 0;
bool gasAlertActive = false;
int lastGasReading = 0;

unsigned long warmSecondsToday = 0;
int lastLoggedDay = -1;
bool exposureAlertActive = false;

float lastTemperature = 0;

// -----------------------------
// ROLLING AVERAGE HELPERS
// -----------------------------

void addToRollingWindow(float arr[], int &count, float value) {
  int limit = min(count, ROLLING_WINDOW_SIZE - 1);
  for (int i = 0; i < limit; i++) {
    arr[i] = arr[i + 1];
  }
  arr[min(count, ROLLING_WINDOW_SIZE - 1)] = value;
  if (count < ROLLING_WINDOW_SIZE) count++;
}

float rollingAverage(float arr[], int count) {
  if (count == 0) return 0;
  float sum = 0;
  for (int i = 0; i < count; i++) sum += arr[i];
  return sum / count;
}

// -----------------------------
// MQTT CONNECTION -- NON-BLOCKING, safety logic never waits on this
// -----------------------------

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

  String alertText = "Normal";
  if (currentAlertLevel == 1) alertText = "Warning";
  if (currentAlertLevel == 2) alertText = "Critical";

  DateTime now = rtc.now();
  char timeStr[9];
  snprintf(timeStr, sizeof(timeStr), "%02d:%02d:%02d", now.hour(), now.minute(), now.second());

  char payload[350];
  snprintf(payload, sizeof(payload),
    "{\"temperature\":%.1f,\"compressor\":\"%s\",\"alertLevel\":%d,\"alertText\":\"%s\",\"gasAlert\":%s,\"gasReading\":%d,\"warmMinutesToday\":%lu,\"door\":\"%s\",\"deviceTime\":\"%s\"}",
    lastTemperature,
    compressorOn ? "ON" : "OFF",
    currentAlertLevel,
    alertText.c_str(),
    gasAlertActive ? "true" : "false",
    lastGasReading,
    warmSecondsToday / 60,
    doorOpen ? "OPEN" : "CLOSED",
    timeStr
  );

  mqttClient.publish(MQTT_TOPIC, payload);
  Serial.print("Published: ");
  Serial.println(payload);
}

// -----------------------------
// SETUP
// -----------------------------

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

  Wire.begin(RTC_SDA, RTC_SCL);
  if (!rtc.begin()) {
    Serial.println("RTC not found -- check wiring.");
  }
  if (!rtc.isrunning()) {
    Serial.println("RTC not running, setting to compile time (demo only).");
    rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
  }

  DateTime now = rtc.now();
  lastLoggedDay = now.day();

  cycleStartTime = millis();

  Serial.println("Connecting to WiFi...");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.print("WiFi connected. IP: ");
    Serial.println(WiFi.localIP());
    mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  } else {
    Serial.println();
    Serial.println("WiFi connection failed -- device continues in local-only mode (core safety features unaffected).");
  }

  Serial.println("System started. Calibrating baseline cycle behavior...");
}

// -----------------------------
// BUZZER SOUNDS
// -----------------------------

void playTone(int frequency, int durationMs) {
  ledcWriteTone(BUZZER_PIN, frequency);
  delay(durationMs);
}

void stopTone() {
  ledcWriteTone(BUZZER_PIN, 0);
}

void warningBeep() {
  playTone(1200, 150);
  stopTone();
  delay(100);
  playTone(1200, 150);
  stopTone();
}

void criticalSiren() {
  for (int repeat = 0; repeat < 3; repeat++) {
    for (int freq = 800; freq <= 1800; freq += 40) {
      ledcWriteTone(BUZZER_PIN, freq);
      delay(8);
    }
    for (int freq = 1800; freq >= 800; freq -= 40) {
      ledcWriteTone(BUZZER_PIN, freq);
      delay(8);
    }
  }
  stopTone();
}

void gasAlertBeep() {
  for (int i = 0; i < 3; i++) {
    playTone(600, 100);
    stopTone();
    delay(80);
  }
}

void exposureAlertChime() {
  int notes[] = {1500, 1100, 700};
  for (int i = 0; i < 3; i++) {
    playTone(notes[i], 250);
    stopTone();
    delay(100);
  }
}

void playAlertForLevel(int level) {
  if (level == 2) {
    criticalSiren();
  } else if (level == 1) {
    warningBeep();
  }
  lastAlertSoundTime = millis();
}

// -----------------------------
// STATUS LEDS
// -----------------------------

void setStatusLEDs(int level) {
  currentAlertLevel = level;
  digitalWrite(LED_GREEN, level == 0 ? HIGH : LOW);
  digitalWrite(LED_YELLOW, level == 1 ? HIGH : LOW);
  digitalWrite(LED_RED, level == 2 ? HIGH : LOW);
}

// -----------------------------
// GAS/MISUSE CHECK
// -----------------------------

void checkGasSensor() {
  int gasLevel = analogRead(MQ2_PIN);
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

// -----------------------------
// CUMULATIVE VACCINE EXPOSURE TRACKING (RTC-based)
// -----------------------------

void updateExposureTracking(float temperature) {
  DateTime now = rtc.now();

  if (now.day() != lastLoggedDay) {
    Serial.println("New day -- resetting cumulative exposure counter.");
    warmSecondsToday = 0;
    exposureAlertActive = false;
    lastLoggedDay = now.day();
  }

  if (temperature >= SAFE_MAX) {
    warmSecondsToday += LOOP_INTERVAL_SECONDS;
  }

  unsigned long warmMinutesToday = warmSecondsToday / 60;

  Serial.print("[");
  Serial.print(now.timestamp(DateTime::TIMESTAMP_TIME));
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

// -----------------------------
// HANDLE A COMPLETED ON/OFF CYCLE
// -----------------------------

void handleCompletedCycle(bool wasOn, float durationSeconds) {
  if (ignoreNextCycle) {
    Serial.println("Cycle ignored (right after door event).");
    ignoreNextCycle = false;
    return;
  }

  if (!calibrated) {
    if (wasOn) {
      baselineOnTime = ((baselineOnTime * completedCalibrationCycles) + durationSeconds) / (completedCalibrationCycles + 1);
    } else {
      baselineOffTime = ((baselineOffTime * completedCalibrationCycles) + durationSeconds) / (completedCalibrationCycles + 1);
      completedCalibrationCycles++;
    }

    Serial.print("Calibrating... cycles learned: ");
    Serial.println(completedCalibrationCycles);

    if (completedCalibrationCycles >= CALIBRATION_CYCLES) {
      calibrated = true;
      Serial.print("Calibration complete. Baseline ON: ");
      Serial.print(baselineOnTime);
      Serial.print("s, Baseline OFF: ");
      Serial.println(baselineOffTime);
    }
    return;
  }

  if (wasOn) {
    addToRollingWindow(recentOnTimes, onCount, durationSeconds);
  } else {
    addToRollingWindow(recentOffTimes, offCount, durationSeconds);
  }

  if (onCount < 2 || offCount < 2) {
    Serial.println("Gathering more cycles before evaluating (rolling window not full yet).");
    return;
  }

  float smoothedOn = rollingAverage(recentOnTimes, onCount);
  float smoothedOff = rollingAverage(recentOffTimes, offCount);

  float baselineRatio = baselineOnTime / baselineOffTime;
  float smoothedRatio = smoothedOn / smoothedOff;
  float driftFactor = smoothedRatio / baselineRatio;

  Serial.print("Smoothed drift factor (rolling avg of last ");
  Serial.print(ROLLING_WINDOW_SIZE);
  Serial.print(" cycles): ");
  Serial.println(driftFactor);

  int newLevel;
  if (driftFactor > CRITICAL_DRIFT_FACTOR) {
    newLevel = 2;
    Serial.println("CRITICAL: Compressor cycling pattern significantly abnormal (sustained).");
  } else if (driftFactor > WARNING_DRIFT_FACTOR) {
    newLevel = 1;
    Serial.println("WARNING: Early sign of abnormal cycling detected (sustained).");
  } else {
    newLevel = 0;
  }

  setStatusLEDs(newLevel);
  if (newLevel > 0) {
    playAlertForLevel(newLevel);
  }
}

// -----------------------------
// MAIN LOOP
// -----------------------------

void loop() {
  float temperature = dht.readTemperature();

  if (isnan(temperature)) {
    Serial.println("Sensor read failed.");
    delay(2000);
    return;
  }

  lastTemperature = temperature;

  bool doorReading = (digitalRead(DOOR_PIN) == LOW);
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

  if (WiFi.status() == WL_CONNECTED) {
    tryConnectMQTT();
    publishStatus();
  }

  Serial.print("Temp: ");
  Serial.print(temperature);
  Serial.print(" C | Compressor: ");
  Serial.println(compressorOn ? "ON" : "OFF");

  delay(2000);
}
