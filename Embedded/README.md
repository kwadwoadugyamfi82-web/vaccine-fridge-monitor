# Embedded

Firmware and board tests for an ESP32-S3 (developed on an ESP32-S3-N16R8). The Arduino IDE needs each sketch in a folder with the same name as the `.ino` file, which is why the folders are laid out this way.

```
fridge_monitor/   The firmware. fridge_monitor.ino and fridge_logic.h (the decision logic, no Arduino calls)
wokwi/            diagram.json and libraries.txt for the Wokwi simulator
tests/            Sketches for a real board (below)
logs/             Raw logs and result notes from the board and Wokwi runs
```

`tests/refit_replay_board/` keeps its own copy of `fridge_logic.h` because the Arduino IDE builds each sketch folder on its own. If you change `fridge_monitor/fridge_logic.h`, copy it there too.

## Libraries

Install from the Library Manager in the Arduino IDE:

- DHT sensor library, by Adafruit (accept the extra libraries it asks for)
- RTClib, by Adafruit
- PubSubClient, by Nick O'Leary

Board: ESP32S3 Dev Module. Wi-Fi and the file system come with the ESP32 board package.

## Run the firmware on a board with nothing attached

1. Open `fridge_monitor/fridge_monitor.ino`.
2. Change `#define SIMULATED_TEMPERATURE 0` to `1`. The sketch then makes up its own temperature, door, gas reading and clock.
3. Upload, open the Serial Monitor at 115200 and leave it for about 30 minutes.

It plays one scenario: healthy cycling, a growing fault (Warning, then Critical), recovery to Normal, a gas reading above the threshold, then the door open with the temperature at 9 °C, which triggers the exposure alert. The exposure alert is cut to 2 minutes in this mode. With the default `DEMO_SHORT_SETTINGS 0` (24 calibration phases, persistence 6) the run takes about 36 minutes of sketch time. With `DEMO_SHORT_SETTINGS 1` (3 phases, persistence 1) it is shorter. A saved run is in `logs/board_scenario_log_2026-11-17.txt`.

Wi-Fi is optional. Without it the sketch prints a line about starting Wi-Fi in the background and carries on. To use MQTT, put your own hotspot name and password in the sketch on your computer, and never commit them.

## Run it with real sensors

Set `SIMULATED_TEMPERATURE` back to 0. The pins are at the top of `fridge_monitor.ino` and match the circuit in `wokwi/diagram.json`: a DHT22 for temperature, an MQ2 for gas, a DS1307 clock, a door switch, LEDs and a buzzer. The firmware has not been run with real sensors on a real fridge.

## Run it in Wokwi

Create an ESP32-S3 DevKitC-1 project, paste `fridge_monitor.ino` as `sketch.ino`, add `fridge_logic.h` as a second file, and paste in `wokwi/diagram.json` and `wokwi/libraries.txt`. In Wokwi the temperature comes from the DHT22 slider unless you turn on `SIMULATED_TEMPERATURE`. Wokwi runs slower than real time and pauses when the browser tab is in the background, so keep the tab in front.

## Board tests (`tests/`)

| Folder | What it does | Needs |
|---|---|---|
| `decision_logic_bench` | Times the first version of the decision logic over 20,000 synthetic cycles | Nothing |
| `offline_latency_test` | Measures main-loop stalls when Wi-Fi or the MQTT broker is slow or missing | Phone hotspot, PubSubClient |
| `refit_replay_board` | Runs `fridge_logic.h` over recorded REFIT phases and prints one result line per appliance and setting | `replay_data.h` from `ML-Validation/refit/make_replay_data.py` |
| `if_board_test` | Scores stored feature vectors with an exported Isolation Forest and compares with scikit-learn | `if_model.h` and `if_testdata.h` from `ML-Validation/refit/make_if_model.py` |

The generated headers are large and are not committed. The two scripts write them straight into the right folders. Both tests have a `host_*.cpp` file that does the same work on a computer with g++. To check a replay log, run `python ML-Validation/refit/check_replay_log.py board_log.txt ML-Validation/results/replay_expected.txt`.
