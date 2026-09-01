# Edge-AI Predictive Monitoring for Vaccine Refrigeration in Rural Ghanaian Health Clinics

A combined edge-AI, embedded systems, and IoT prototype for predicting vaccine refrigerator faults before they cause vaccine spoilage — motivated by documented cold-chain challenges in rural Ghanaian health clinics.

Full write-up: see [`Docs/vaccine-fridge-research-paper.pdf`](Docs/vaccine-fridge-research-paper.pdf)

## What this project does

- **Predicts compressor failure before it happens**, using a detection method validated against a real, publicly available industrial failure dataset (95.3% recall), then applied to a domain-specific vaccine-fridge simulation.
- **Detects likely misuse** (e.g. drinks/food stored in the unit) using a gas sensor.
- **Tracks cumulative vaccine-exposure risk**, not just instantaneous temperature breaches, using a real-time clock.
- **Reports live status over IoT (MQTT)** to a web dashboard — as a convenience layer only; all core safety functions run fully offline.

## Repository structure

```
├── Embedded/             ESP32-S3 firmware + Wokwi circuit (C++)
│   ├── sketch.ino
│   ├── diagram.json
│   └── libraries.txt
├── ML-Validation/        Python: model validation + fridge simulation
│   └── fridge_pipeline.py
├── IoT-dashboard/        Python: live Streamlit dashboard
│   └── dashboard.py
└── Docs/
    ├── vaccine-fridge-research-paper.pdf
    └── vaccine-fridge-research-paper.docx
```

## Running the embedded simulation

1. Open [Wokwi](https://wokwi.com), create a new ESP32-S3 project.
2. Replace `sketch.ino` and `diagram.json` with the files in `Embedded/`.
3. In the Library Manager, add: **DHT sensor library**, **RTClib**, **PubSubClient**.
4. Click Run. Watch the Serial Monitor.

## Running the ML validation script

```bash
pip install pandas numpy scikit-learn matplotlib
python ML-Validation/fridge_pipeline.py
```

## Running the live dashboard

```bash
pip install streamlit paho-mqtt
streamlit run IoT-dashboard/dashboard.py
```
Run this alongside the Wokwi simulation (with Wi-Fi/MQTT connected) to see live data.

## Status

This is a validated, simulation-stage prototype — not yet tested on physical hardware. See the full document for a complete discussion of scope and limitations.

## Author

Adu-Gyamfi Kwadwo — B.Sc. Electrical/Electronic Engineering, Kwame Nkrumah University of Science and Technology
