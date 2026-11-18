// offline_latency_test.ino
// Measures how long the main loop stalls when the network is slow or gone. Needs a phone hotspot and the
// PubSubClient library; the temperature is synthetic.
//
// The loop copies the first version of the firmware: Wi-Fi in setup, then tryConnectMQTT() and
// publishStatus() on every pass and delay(2000) at the end. The longest loop period printed is the
// worst-case time before this structure can notice anything.
//
// Edit the hotspot name and password on your computer only. Do not commit them.

#include <WiFi.h>
#include <PubSubClient.h>

// ---------- settings you change ----------
#define WIFI_SSID     "YOUR_HOTSPOT_NAME"
#define WIFI_PASSWORD "YOUR_HOTSPOT_PASSWORD"

#define USE_NETWORK_TASK 0              // 0 = same structure as the first version of the firmware, 1 = network work moved to its own task
#define SIMULATE_BLOCKING_ALERT_SOUND 0 // 1 = every 15 s block for 1248 ms, like the old criticalSiren()
#define MIMIC_ORIGINAL_SETSERVER 1      // 1 = setServer() only if Wi-Fi was connected at boot (as in the first version of the firmware)
// -----------------------------------------

#define LOOP_DELAY_MS 2000
#define MQTT_RETRY_INTERVAL_MS 10000
#define ALERT_REPEAT_INTERVAL_MS 15000

const char* MQTT_BROKER = "broker.emqx.io";
const int MQTT_PORT = 1883;
const char* MQTT_TOPIC = "kwadwo-fridge-offline-test-2026/status";   // test topic, not the dashboard topic

WiFiClient espClient;
PubSubClient mqttClient(espClient);

unsigned long lastMqttAttempt = 0;
volatile float lastTemperature = 4.0f;
volatile unsigned long netMsLastLoop = 0;
volatile unsigned long publishCount = 0;

void tryConnectMQTT() {
  if (mqttClient.connected()) return;
  if (millis() - lastMqttAttempt < MQTT_RETRY_INTERVAL_MS) return;
  lastMqttAttempt = millis();
  String clientId = "esp32-test-" + String(random(0xffff), HEX);
  mqttClient.connect(clientId.c_str());
}

void publishStatus() {
  if (!mqttClient.connected()) return;
  mqttClient.loop();
  char payload[120];
  snprintf(payload, sizeof(payload), "{\"temperature\":%.1f,\"n\":%lu}", (double)lastTemperature, (unsigned long)publishCount);
  if (mqttClient.publish(MQTT_TOPIC, payload)) publishCount++;
}

#if USE_NETWORK_TASK
void networkTask(void*) {
  for (;;) {
    unsigned long n0 = millis();
    if (WiFi.status() == WL_CONNECTED) {
      tryConnectMQTT();
      publishStatus();
    }
    netMsLastLoop = millis() - n0;
    vTaskDelay(pdMS_TO_TICKS(LOOP_DELAY_MS));
  }
}
#endif

void setup() {
  Serial.begin(115200);
  delay(1500);
  Serial.println("\n=== offline / latency test ===");
  Serial.printf("USE_NETWORK_TASK=%d SIMULATE_BLOCKING_ALERT_SOUND=%d MIMIC_ORIGINAL_SETSERVER=%d\n",
                USE_NETWORK_TASK, SIMULATE_BLOCKING_ALERT_SOUND, MIMIC_ORIGINAL_SETSERVER);
  Serial.printf("broker=%s\n", MQTT_BROKER);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {   // same as the first version of the firmware: up to 10 s
    delay(500);
    Serial.print(".");
    attempts++;
  }
  Serial.println();
  Serial.printf("Wi-Fi at boot: %s\n", WiFi.status() == WL_CONNECTED ? "connected" : "NOT connected");

#if MIMIC_ORIGINAL_SETSERVER
  if (WiFi.status() == WL_CONNECTED) mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
#else
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
#endif

#if USE_NETWORK_TASK
  xTaskCreatePinnedToCore(networkTask, "net", 8192, NULL, 1, NULL, 0);
#endif
  Serial.println("columns: t_s | period_ms | net_ms | wifi | mqtt | published");
}

void loop() {
  static unsigned long prevStart = 0;
  static unsigned long maxPeriod = 0;
  static unsigned long stalled = 0;      // loops whose period exceeded 2500 ms
  static unsigned long iterations = 0;
  static unsigned long lastSound = 0;

  unsigned long start = millis();
  unsigned long period = (prevStart == 0) ? LOOP_DELAY_MS : (start - prevStart);
  prevStart = start;

  // synthetic temperature (stands in for the sensor read)
  lastTemperature = 4.0f + 0.5f * (float)((start / 1000) % 5);

#if !USE_NETWORK_TASK
  unsigned long n0 = millis();
  if (WiFi.status() == WL_CONNECTED) {
    tryConnectMQTT();
    publishStatus();
  }
  netMsLastLoop = millis() - n0;
#endif

#if SIMULATE_BLOCKING_ALERT_SOUND
  if (millis() - lastSound >= ALERT_REPEAT_INTERVAL_MS) {
    delay(1248);          // 3 x (26 up + 26 down) x 8 ms, as in criticalSiren()
    lastSound = millis();
  }
#endif

  iterations++;
  if (period > maxPeriod) maxPeriod = period;
  if (period > 2500) stalled++;

  Serial.printf("%lu | %lu | %lu | %s | %s | %lu\n",
                start / 1000, period, (unsigned long)netMsLastLoop,
                WiFi.status() == WL_CONNECTED ? "UP" : "DOWN",
                mqttClient.connected() ? "UP" : "DOWN",
                (unsigned long)publishCount);

  if (iterations % 15 == 0) {
    Serial.printf("SUMMARY after %lu loops: max period %lu ms, loops over 2500 ms: %lu\n", iterations, maxPeriod, stalled);
  }

  delay(LOOP_DELAY_MS);
}
