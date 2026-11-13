# Edge-AI Predictive Monitoring for Vaccine Refrigeration

A design for a low-cost vaccine-fridge monitor that makes its safety decisions locally on an ESP32-S3, without needing an internet connection. The decision logic is derived from a machine-learning analysis of compressor cycling behaviour.

**Status: validated in simulation. Not yet tested on physical hardware.** The firmware runs in the Wokwi simulator, and the ML analysis uses a public industrial dataset and a Python fridge simulation. No physical vaccine fridge, real fridge data, or field deployment is involved. See [Limitations](#limitations) and [Known issues](#known-issues).

Preprint: [10.31224/8149](https://doi.org/10.31224/8149) (EngrXiv)
Paper: [`Docs/vaccine-fridge-research-paper.pdf`](Docs/vaccine-fridge-research-paper.pdf)

---

## Motivation

Vaccine cold-chain failures are a major cause of vaccine wastage, and rural clinics often have unreliable power and connectivity. Most low-cost monitors are reactive: they alarm only after the temperature has left the 2 to 8 °C range, and many need a cloud connection to work. This project asks whether a cheap microcontroller can warn earlier, by watching how the compressor cycles, and keep working when the network is down.

## What the system does

| Layer | What it does | Basis |
|---|---|---|
| Predictive fault detection | Warns of likely compressor degradation before a temperature excursion | On/off cycle ratio compared with a per-unit baseline, using a 5-cycle rolling average |
| Misuse detection | Flags combustible vapours (for example alcohol-based drinks) in the unit | MQ2 sensor with a fixed threshold. It is not a general food detector. |
| Cumulative exposure tracking | Counts time at or above 8 °C per day, so many short excursions are caught | Warm-time counter, daily reset, alert at 30 minutes |
| Local alerting | Green, yellow and red LEDs, a compressor LED, and distinct buzzer tones | Independent of Wi-Fi |
| IoT reporting (optional) | Publishes status as JSON over MQTT to a Streamlit dashboard | Non-blocking, so a failed connection does not stop local alerts |

## How the ML and the firmware relate

The Isolation Forest does **not** run on the microcontroller. It is used offline, on a workstation, to find a predictive signal. That signal, the ratio of compressor on-time to off-time, is turned into simple threshold rules that run on the ESP32-S3:

1. Learn a baseline on/off ratio from the first 3 completed cycles.
2. Keep a rolling average of the last 5 on-cycles and 5 off-cycles.
3. Compute `drift = (smoothed on/off ratio) / (baseline on/off ratio)`.
4. Warning if `drift > 1.8`. Critical if `drift > 3.5`.

The 1.8 and 3.5 thresholds were chosen from the simulation output (median-based analysis of healthy versus degrading hours). Cycles right after a door-open event are ignored.

So "edge AI" here means the decisions are made locally with logic derived from ML analysis. It does not mean a trained model is running inference on the device.

## Repository layout

```
Embedded/        ESP32-S3 firmware (Arduino C++) and the Wokwi circuit (diagram.json)
ML-Validation/   Python fridge simulation and Isolation Forest analysis
IoT-dashboard/   Streamlit dashboard that subscribes to the MQTT topic
Docs/            Research paper (PDF and DOCX)
```

## Validation summary

**1. Real industrial data (MetroPT-3, metro-train air compressor).** An Isolation Forest was trained on normal-operation hours only, using seven per-hour features (average on-time, average off-time, signal variability, peak, minimum, cycle count, 3-hour rolling cycle count).

| Result | Value |
|---|---|
| Documented failure hours flagged | 82 / 86 (95.3%) |
| Normal hours false-flagged | 201 / 4,327 (4.6%) |

This tests the *method* on a physically similar system. It is not evidence of vaccine-fridge performance. The MetroPT-3 analysis script is not yet in this repository (see [Known issues](#known-issues)).

**2. Python fridge simulation** (`ML-Validation/fridge_pipeline.py`). A 30-day simulated 2 to 8 °C fridge with door-open events and gradual compressor wear starting on day 20.

| Model | Degrading hours flagged | Healthy hours false-flagged | First correct detection |
|---|---|---|---|
| Strict (contamination 0.05) | 15 / 240 | 24 / 480 | Day 22 |
| Sensitive (contamination 0.15) | 87 / 240 | 72 / 480 | Day 21 |

As binary flags these numbers are modest. The more informative result is the anomaly-score trend (average falling from about 0.10 early in the wear period to about 0.02 by day 30), which shows detection confidence following fault severity. The simulation itself is a simple model, so these results say little about real fridges.

**3. Firmware in Wokwi.** Verified in simulation: calibration, rolling-window drift calculation, door-event exclusion, distinct alert tones, MQ2 threshold behaviour, daily-reset exposure counter, and MQTT delivery to the dashboard. Wokwi does not model real power draw or real sensor noise.

## Running it

**Simulation analysis**
```
cd ML-Validation
pip install pandas numpy scikit-learn matplotlib
python fridge_pipeline.py
```
This prints the flag counts and saves `fridge_anomaly_trend.png` and `fridge_hourly_features.csv`.

**Firmware.** Open `Embedded/` in Wokwi (ESP32-S3 DevKitC-1). Libraries: DHT sensor library, RTClib, PubSubClient. In Wokwi the temperature is driven by the DHT22 slider, so cycles are produced by changing it manually.

**Dashboard**
```
cd IoT-dashboard
pip install streamlit paho-mqtt
streamlit run dashboard.py
```
Then start the Wokwi simulation. The device and the dashboard share one public MQTT topic.

## Limitations

- Thresholds come from a simulation, not from real vaccine-fridge logs. No public dataset of real vaccine-fridge failures was found.
- The MetroPT-3 data comes from a different machine (a train compressor).
- In the firmware, "compressor on" is inferred from the firmware's own 8 °C / 2 °C thresholds. A real fridge cycles on its own thermostat. A real build would need a compressor current sensor or a temperature-slope detector.
- The MQ2 sensor detects combustible vapours only.
- Exposure tracking resets daily and does not follow a vaccine's whole storage life.
- The public MQTT broker (`broker.emqx.io`) is unauthenticated and is for demonstration only.
- No latency, memory, or energy measurements on real hardware have been made yet.

## Known issues

These are open and being worked on.

1. **Rolling-window bug in `Embedded/sketch.ino`.** `addToRollingWindow` shifts the array while it is still filling, which inserts zeros and pulls early averages down. Drift is underestimated until the window has been replaced. Fix: append while filling and shift only when full.
2. **Timing.** `loop()` uses `delay(2000)` and the buzzer routines block (the critical siren takes about 1.25 s). Alert latency is therefore bounded by this blocking design, and the "real-time" claim should be read accordingly. The warm-time counter adds a fixed 2 s per loop, so it underestimates time because each loop takes longer than 2 s.
3. **Reproducibility.** The MetroPT-3 validation script and the threshold-derivation analysis are not yet included in this repository.

## Planned work

- Fix the rolling-window bug and move to non-blocking (`millis()`-based) timing.
- Add the MetroPT-3 validation script and threshold analysis to `ML-Validation/`.
- Run on a physical ESP32-S3 and report measured decision-logic time, end-to-end alert latency, and memory use. Energy will be reported only if measured with a power meter.
- Collect real fridge temperature data, replace simulation-derived thresholds, and test compressor-state sensing.
- Investigate a properly exported, quantised one-class model for on-device inference.
- Move to a private, authenticated MQTT broker.

## Author

Adu-Gyamfi Kwadwo, B.Sc. Electrical/Electronic Engineering, KNUST (2024).
