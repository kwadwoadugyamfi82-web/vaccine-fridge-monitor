# Hardware measurements: decision-logic benchmark

Measured on a real ESP32-S3 on 13 Nov 2026. These results cover the decision logic only (not the full vaccine-fridge system, and not energy).

## Setup

| Item | Value |
|---|---|
| Chip | ESP32-S3 (QFN56), revision v0.2, 240 MHz. Checked with a separate sketch: 8,388,608 B (8 MB) PSRAM present (found with Tools > PSRAM set to OPI) and 16,777,216 B (16 MB) flash. The benchmark itself ran with the Tools > PSRAM option Disabled and the default 4 MB flash/partition settings, so it used internal RAM only. |
| Board / module | Dual USB-C ESP32-S3 development board (CH343P UART port). Module marking on the metal shield: ESP32-S3-N16R8 (16 MB flash, 8 MB octal PSRAM), matching the sizes measured below. The board's listing name was not recorded. |
| Toolchain | Arduino IDE 2.3.11, Arduino-ESP32 core 3.3.12, esptool v5.3.1 |
| Board setting | ESP32S3 Dev Module, USB CDC On Boot: Disabled, flashed and read over the UART (CH343P) port |
| Program | `decision_logic_bench.ino` (decision logic taken from the first version of the firmware, with the rolling-window helper corrected). The later change to the calibration step affects only the first few cycles and was not re-measured. The replay test in `ML-Validation/results/board_replay_log.txt` times the later `fridge_logic.h` at 16 to 18 us per phase including its replay loop, which is a different measurement. |
| Inputs | 20,000 synthetic on/off cycle durations (deterministic: healthy, then degrading) |
| Timing method | `ESP.getCycleCount()` around each call to `evaluateCycle()`, converted to microseconds at 240 MHz |

## Results (three runs, identical)

| Metric | Value |
|---|---|
| Per-call time, min | 0.22 us |
| Per-call time, mean | 2.03 us |
| Per-call time, max | 6.81 us |
| Alert levels produced | normal 12,769, warning 5,834, critical 1,388 |
| Benchmark sketch size | 275,808 B (21% of the 1,310,720 B app partition of the default 4 MB scheme selected in the IDE; the chip has 16 MB flash) |
| Global variables | 21,664 B (6% of 327,680 B) |
| Free heap at start | 359,048 B |

The alert counts are identical to those from running the same logic on a laptop, which checks that the logic behaves the same on the chip.

## What this does and does not show

- It shows the cost of evaluating one completed compressor cycle: microseconds, so negligible next to cycles that last tens of seconds.
- It uses synthetic inputs. It does not include sensor reading, the buzzer, Wi-Fi or MQTT.
- It does not measure end-to-end alert latency. The first firmware version's loop was dominated by `delay(2000)` and blocking buzzer routines; the final sketch no longer has them, and its latency was not measured.
- It does not measure energy. That would need a USB power meter or a series multimeter.
- The timer call itself adds a small overhead to each measurement.

## Raw output

```
=== decision-logic benchmark ===
CPU MHz: 240 | free heap: 359048 B | sketch size: 275808 B | chip: ESP32-S3 rev 2
calls: 20000
per-call time  min: 0.22 us | mean: 2.03 us | max: 6.81 us
alert levels produced  normal: 12769 | warning: 5834 | critical: 1388  (sanity check)
```
