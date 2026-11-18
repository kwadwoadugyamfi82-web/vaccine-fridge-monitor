# Offline / latency test results

Measured on a real ESP32-S3 on 14 Nov 2026 with `offline_latency_test.ino`.

## Setup

| Item | Value |
|---|---|
| Board and toolchain | As in `RESULTS.md` (ESP32-S3 rev v0.2, Arduino-ESP32 3.3.12, Arduino IDE 2.3.11) |
| Network | iPhone Personal Hotspot (2.4 GHz, "Maximize Compatibility" on), public broker `broker.emqx.io` |
| Inputs | Synthetic temperature. No sensors, buzzer or RTC. |
| Loop | Same structure as the first version of the firmware: network work each pass, then `delay(2000)` |
| Metric | Time between the starts of consecutive loop passes (`period_ms`). Its maximum is the worst-case time before the loop can notice anything. |

## Results

Numbers come from the complete raw log (`offline_test_runs_2026-11-14.txt`). Each row is one test condition. The log prints the `USE_NETWORK_TASK` and `MIMIC_ORIGINAL_SETSERVER` settings at every boot. The broker address is not printed in the log, so the unreachable-broker rows rely on my record of which address was in the sketch at the time. Conditions were run once or a few times each, not repeated many times.

| Condition | Settings | Loops (duration) | Max loop period | Loops over 2500 ms | Notes |
|---|---|---|---|---|---|
| No Wi-Fi | task off | 182 (373 s) | 2000 ms | 0 | Core loop unaffected when Wi-Fi is absent |
| Wi-Fi up, `setServer()` skipped (as in the first version of the firmware) | `MIMIC_ORIGINAL_SETSERVER 1`, task off | 192 (534 s) | 5003 ms | 47 | MQTT never started: 0 messages published |
| Wi-Fi up, broker reachable | `MIMIC_ORIGINAL_SETSERVER 0`, task off | 235 (472 s) | 3001 ms | 1 | One stall of 1.0 s at connect, then 2002 ms loops, 231 messages. Three shorter boots: connect stalls 0.95 to 1.5 s |
| Wi-Fi up, broker unreachable (192.0.2.1) | task off | 149 (509 s) | 17,127 ms | 42 | Repeated stalls: 35 of about 3 s, 7 of about 15 s |
| Wi-Fi up, broker unreachable (192.0.2.1) | `USE_NETWORK_TASK 1` | 231 (463 s) | **2000 ms** | **0** | The task still blocks about 3 s per retry, the main loop does not |
| Wi-Fi up, broker reachable | `USE_NETWORK_TASK 1` | 101 (211 s) | **2000 ms** | **0** | MQTT up at t = 15 s, 99 messages published |

## Notes and limits

- Wi-Fi sometimes took 1.5 s to over 30 s to connect after reset. While the iPhone screen was off, the hotspot was not found for several minutes. This was a test-bench effect, not a firmware result.
- The task version was tested only with synthetic data. The final firmware shares a status snapshot between the main loop and the network task under a lock. That was exercised in Wokwi. On the board it ran without Wi-Fi (`board_scenario_log_2026-11-17.txt`), so publishing from the snapshot was not exercised there. The final firmware also runs the network task at priority 0 and sets a 3 s MQTT socket timeout, after a watchdog reset in Wokwi with priority 1. The tests in this file used priority 1.
- Wi-Fi loss in the middle of a run (hotspot switched off while running) has not been tested.

## Raw logs

`offline_test_runs_2026-11-14.txt` contains the full Serial Monitor output of all runs.
