# Edge-AI predictive monitoring for vaccine refrigeration

A vaccine-fridge monitor that decides locally, on an ESP32-S3, whether something is going wrong. It does not need an internet connection for that. The decision rule comes from an offline machine-learning analysis of how a compressor cycles on and off.

I have tested it in simulation and on recorded data, not on a physical fridge. The firmware runs in the Wokwi simulator and, with the sketch generating its own test signals, on a real ESP32-S3 board. The method was tried on a public industrial dataset, on a Python fridge simulation and on recorded power traces of household fridges and on the labelled records of ten real ultra-low-temperature laboratory freezers. On the board I measured how long the decision logic takes, replayed the recorded fridge phases through it, ran an Isolation Forest, and played a full test scenario through the firmware. All of that used recorded or generated inputs. The system has not been run with physical sensors on a real fridge, and the project holds no real vaccine-fridge data.

The household-fridge replay showed that the thresholds from my simulation raise too many false alarms on real compressor cycling. A longer calibration and a persistence requirement reduced them, and those settings (24 calibration phases, persistence 6) are now the firmware default. On the real freezer records the rule rarely raised alarms, but it flagged only 4 of 14 compressor or refrigerant faults in the 90 days before their service dates, so I do not call it validated for real faults. See [Replay on household fridge traces](#replay-on-household-fridge-traces-refit), [Labelled freezer records](#labelled-freezer-records-ult), [Limitations](#limitations-and-known-issues) and the [Embedded README](Embedded/README.md).

Preprint: [10.31224/8149](https://doi.org/10.31224/8149) (EngrXiv). Paper: [`Docs/vaccine-fridge-research-paper.pdf`](Docs/vaccine-fridge-research-paper.pdf)

## Motivation

Vaccine cold-chain failures cause a lot of vaccine wastage, and rural clinics often have unreliable power and connectivity. Most low-cost monitors only react. They alarm once the temperature has already left the 2 to 8 °C range, and many need a cloud connection. I wanted to see whether a cheap microcontroller could give an earlier warning by watching how the compressor cycles, and keep working when the network is down.

## What the system does

| Layer | What it does | Basis |
|---|---|---|
| Predictive fault detection | Warns of likely compressor degradation before a temperature excursion | On/off cycle ratio compared with the unit's own baseline, smoothed over 5 cycles |
| Misuse detection | Flags combustible vapours in the unit, such as alcohol-based drinks | MQ2 sensor with a fixed threshold. It does not detect food in general. |
| Cumulative exposure | Counts the time spent at or above 8 °C each day, so many short excursions add up | Warm-time counter that resets daily, alert at 30 minutes |
| Local alerts | Green, yellow and red LEDs, a compressor LED and distinct buzzer tones | Works without Wi-Fi |
| IoT reporting (optional) | Publishes status as JSON over MQTT to a Streamlit dashboard | Runs in its own task, so a failed connection does not stop local alerts |

## How the analysis relates to the firmware

The Isolation Forest does not run the alerts. I used it offline, on a computer, to look for a signal that predicts failure. What came out of it was the ratio of compressor on-time to off-time, and the firmware turns that into simple threshold rules:

1. Learn a baseline on/off ratio from the first 24 ON and 24 OFF phases after power-up. The first version used 3, and `DEMO_SHORT_SETTINGS` brings that back for quick demos.
2. Keep a rolling average of the last 5 ON and 5 OFF durations.
3. Compute `drift = (smoothed on/off ratio) / (baseline on/off ratio)`.
4. Raise Warning if `drift > 1.8` and Critical if `drift > 3.5`, but only after 6 evaluations in a row above the threshold. The first version alerted on the first one.

Cycles right after a door-open event are ignored. The thresholds are relative to each unit's own baseline, so they do not depend on how long a particular fridge's cycle is.

The values 1.8 and 3.5 are design choices that I checked against the simulation ([threshold check](#threshold-check-on-the-simulated-fridge)). They were not measured on a vaccine fridge, and on recorded household-fridge traces the rule raised many false alarms. "Edge AI" here means the decisions are made on the device, using logic that came out of machine-learning analysis. I also ran an Isolation Forest on the chip to see whether it could replace the rule. It runs, but it did not detect better ([detector comparison](#detector-comparison)).

## Repository layout

```
Embedded/
  fridge_monitor/        The firmware (open this folder in the Arduino IDE): fridge_monitor.ino and fridge_logic.h
  wokwi/                 Circuit (diagram.json) and library list for the Wokwi simulator
  tests/                 Sketches for a real board: decision-logic timing, offline latency,
                         REFIT replay, Isolation Forest parity test
  logs/                  Raw logs and short result notes from the board and Wokwi runs
ML-Validation/
  simulation/            Fridge simulation and threshold check
  metropt3/              MetroPT-3 analysis
  refit/                 REFIT replay, sweep, detector comparison and threshold curve, plus the
                         scripts that make the data and the model for the board
  ult/                   The rule on ten labelled ULT freezers: one script and its saved report
  results/               Saved output of those scripts and the board replay
IoT-dashboard/           Streamlit dashboard that subscribes to the MQTT topic
Docs/                    Research paper (PDF and DOCX)
```

## Results

### MetroPT-3 (metro-train air compressor)

I first tried the method on the public MetroPT-3 dataset (UCI, DOI 10.24432/C5VW3R). It holds sensor data from a real air compressor, with four documented air-leak failure windows. I trained an Isolation Forest on normal hours only, using seven per-hour features: average on-time, average off-time, signal variability, peak, minimum, cycle count and a 3-hour rolling cycle count. The script is `ML-Validation/metropt3/metropt3_analysis.py`.

- The CSV I used has 1,516,948 rows with a median sampling interval of 10 s, from 2020-02-01 to 2020-09-01. The dataset description says 1 Hz and 15,169,480 rows, so this file holds every tenth sample.
- An hour counts as a failure hour if at least 30 minutes of it fall inside a documented failure window. After a coverage filter that leaves 83 failure hours and 4,131 normal hours.
- The model is fitted on the earliest 60% of normal hours (up to 2020-06-10) and tested on the later normal hours and all failure hours. Contamination is 0.05 and the random seed is 42.

How "compressor ON" is defined changes the result a lot, so here are all three definitions I tried.

| Definition of ON | Failure hours flagged | Later normal hours flagged | ROC AUC | Average precision |
|---|---|---|---|---|
| Motor current above 1.0 A (motor running) | 22 / 83 | 107 / 1,653 (6.5%) | 0.935 | 0.26 |
| Motor current above 5.5 A (under load) | 81 / 83 | 77 / 1,653 (4.7%) | 0.977 | 0.70 |
| `DV_eletric` valve signal active | 24 / 83 | 105 / 1,653 (6.4%) | 0.937 | 0.26 |

With the under-load definition every failure event is caught (23 of 24, 6 of 7, 47 of 47 and 5 of 5 failure hours). The dataset documentation gives roughly 0 A when off, 4 A offloaded, 7 A under load and 9 A at start-up, so 5.5 A separates loaded from offloaded running. I set it from those documented levels and not from the failure labels, but it was still the best of the three definitions, so treat the number with that in mind.

A few things to keep in mind when reading these numbers.

- About half of the flags in the held-out test are false (81 failure hours against 77 normal hours), because normal hours outnumber failure hours roughly 20 to 1.
- Flags are per hour, so they say nothing about how early a failure is found.
- The failure windows come from the dataset documentation and I did not verify them independently. The third window spans about 53 hours, of which 47 remain after the coverage filter.
- A train compressor switching between loaded and offloaded has no direct counterpart in a fridge. A fridge's on/off cycling is closer to the "motor running" definition, which did poorly. This stage tests the method on a different machine and is not evidence about vaccine fridges.

### Simulated fridge

`ML-Validation/simulation/fridge_pipeline.py` simulates 30 days of a 2 to 8 °C fridge with door-open events and gradual compressor wear starting on day 20. The model is fitted on the earliest 60% of healthy hours (288 hours) and tested on the later 192 healthy hours and the 240 degrading hours.

| Model | Later healthy hours flagged | Degrading hours flagged | Hours with wear of 0.3 or more flagged | ROC AUC |
|---|---|---|---|---|
| Strict (contamination 0.05) | 6 / 192 | 30 / 240 | 29 / 168 | 0.638 |
| Sensitive (contamination 0.15) | 33 / 192 | 88 / 240 | 81 / 168 | 0.638 |

Healthy and degrading hours are only weakly separated (AUC 0.64) with this feature set. That is one reason the device uses the simple cycle-ratio rule and not this model. The simulation itself is simple, so these results say little about real fridges.

#### Threshold check on the simulated fridge

`ML-Validation/simulation/threshold_analysis.py` computes the firmware's drift value cycle by cycle on the same simulation, leaving out cycles with a door event. Durations are in simulated minutes. Healthy cycles average about 63 min ON and 120 min OFF, a ratio of 0.52. In the last three days of wear the ratio reaches about 1.7, around 3.3 times the healthy value.

| Days | Windows | Mean drift | Max drift | Above 1.8 | Above 3.5 |
|---|---|---|---|---|---|
| 0 to 20 (healthy) | 242 | 1.00 | 1.17 | 0% | 0% |
| 20 to 23 | 43 | 1.12 | 1.28 | 0% | 0% |
| 23 to 26 | 35 | 1.57 | 2.24 | 26% | 0% |
| 26 to 30 | 45 | 2.55 | 3.04 | 100% | 0% |

Door events make single cycles noisy. On healthy days one ON/OFF pair exceeded 1.8 times the baseline in 18% of cases (maximum 10 times), a five-cycle average did so in 2% of windows (maximum 2.0 times), and no window exceeded 1.17 times once door-affected cycles were left out. That is why the firmware uses both the five-cycle average and the door-event exclusion.

The table above uses the mean of all healthy cycles as the baseline. With a baseline from the first 3 ON and 3 OFF cycles, as the first version of the firmware did, the maximum drift is 1.06 while healthy and 2.76 in the last days. The Warning threshold of 1.8 gave no warnings in 20 healthy days and was crossed consistently as wear progressed. The Critical threshold of 3.5 was never reached. It sits above anything this simulation produces, so it is a margin for more severe degradation and not a value taken from data.

### Replay on household fridge traces (REFIT)

To see how the rule behaves on real compressor cycling, `ML-Validation/refit/refit_replay.py` replays recorded power traces from the REFIT Electrical Load Measurements dataset (cleaned version, University of Strathclyde, CC BY 4.0) through the firmware's drift rule. I used four appliance plugs from three UK homes: the fridge-freezers in House 2 and House 15, and the separate fridge and freezer in House 20. The traces cover 460 to 617 days at a median interval of about 7 s, and the metadata does not give the appliance models. These are domestic units, so the test shows how the rule copes with doors, food loading, defrost and seasons. It says nothing about temperature sensing and it is not vaccine-fridge data.

How it was run:

- ON is 30 W or more and OFF is 10 W or less. Cycles never cross a timestamp gap of more than 2 minutes, dips shorter than 2 minutes are merged into the surrounding phase, phases over 6 hours are dropped, and ON phases with mean power above twice the median are dropped as defrost.
- REFIT does not mark door openings, so no cycles are excluded for doors the way the firmware would. The false-alarm counts are therefore pessimistic.
- The cleaned files carry an `Issues` flag, set when the sub-meters add up to more than the household aggregate. That flag is about the aggregate and not the timing of one plug, so I kept those phases in the main analysis and show the version with them dropped as a check.
- The baseline is recalibrated after any outage longer than one hour, as a rebooted device would do. Episodes are counted per 30 days, because overlapping windows make percentages overstate the number of independent events.

Here is the original firmware rule on healthy traces (3-phase calibration, 5-phase mean window, Warning 1.8, Critical 3.5).

| Appliance | Phases kept (days) | Windows above 1.8, recalibrated after outages | Warning / Critical episodes per 30 days | Windows above 1.8, never recalibrated |
|---|---|---|---|---|
| House 2 fridge-freezer | 14,074 (450) | 8.4% | 13.3 / 1.7 | 31.0% |
| House 15 fridge-freezer | 17,635 (478) | 2.7% | 4.8 / 0.5 | 0.9% |
| House 20 fridge | 19,923 (412) | 14.0% | 27.5 / 5.5 | 15.9% |
| House 20 freezer | 14,859 (412) | 3.4% | 5.5 / 0.3 | 15.3% |

Warning episodes came every 1 to 6 days, and Critical episodes ranged from 0.3 to 5.5 per 30 days. The simulation had suggested almost none. With the `Issues` phases dropped the counts were lower (11.2 / 0.5, 4.3 / 0.4, 12.0 / 1.3 and 1.8 / 0.0 Warning / Critical episodes per 30 days, in the same order). The result also depends heavily on the three cycles used for the baseline. In House 15 the never-recalibrated baseline happened to be a good one.

For the injected-fault test I took 30-day slices, calibrated at the start of each slice. From day 15, ON durations were multiplied and OFF durations divided by the square root of a factor that grew from 1 to a final ON/OFF ratio multiplier over 7 days. This tests the detector and not a physical failure. The full tables are in [`ML-Validation/results/refit_replay_results.md`](ML-Validation/results/refit_replay_results.md).

#### Calibration and persistence sweep

I then asked whether a small change could help. `refit_sweep.py` compares 48 variations of the rule: calibration over 3, 6, 12 or 24 phases of each kind, a window of 5 or 10, mean or median, and persistence (alert only after 1, 3 or 6 consecutive windows above the threshold). The thresholds stay at 1.8 and 3.5. I wrote the selection rule down before running the sweep. For each house in turn, the best variation was chosen using only the other two houses and then scored on the held-out house. A variation was eligible only if a 3x fault reached Critical in at least 80% of slices with a median delay of 7 days or less on every training appliance, and the best of those had the fewest healthy false alarms (Warning episodes plus three times Critical episodes). House 20's fridge and freezer share a home, so they were held out together.

| Held-out appliance (setting chosen without it) | Warning / Critical episodes per 30 days: firmware, then chosen | Critical found for a 3x fault: firmware, then chosen (median delay) |
|---|---|---|
| House 15 fridge-freezer (24 phases, window 5, mean, persistence 6) | 4.8 / 0.5, then 1.4 / 0.1 | 83% (4.9 d), then 100% (5.7 d) |
| House 2 fridge-freezer (6 phases, window 5, median, persistence 3) | 13.3 / 1.7, then 6.1 / 0.6 | 67% (2.9 d), then 100% (5.5 d) |
| House 20 fridge (24 phases, window 5, mean, persistence 6) | 27.5 / 5.5, then 10.3 / 0.7 | 100% (4.1 d), then 100% (5.2 d) |
| House 20 freezer (24 phases, window 5, mean, persistence 6) | 5.5 / 0.3, then 3.8 / 0.0 | 83% (3.5 d), then 100% (6.3 d) |

In every held-out house the chosen setting had fewer false alarms and still reached Critical on a 3x fault in every slice, at the cost of a delay about 1 to 3 days longer. Warning detection was unchanged in two cases and about a day slower in the other two. The same pattern held with the `Issues` phases dropped. Across all three houses the setting that did best was a calibration of 24 phases, a window of 5, a mean and persistence 6. That is a description of the sweep and not a separate test. Full output: [`ML-Validation/results/refit_sweep_results.md`](ML-Validation/results/refit_sweep_results.md).

The improvement is only partial. The House 20 fridge still raised about 10 Warning episodes per 30 days and House 2 about 6, so on these domestic appliances the rule is still noisy. A longer calibration also has a cost, because a fault that is already present during calibration gets absorbed into the baseline. The injected faults are artificial, the sweep covers only three homes, and the chosen setting was picked on recorded traces. It is the firmware default but has not been tried on a real fridge.

#### Detector comparison

The rule is still noisy, so I checked whether anything detects better. `refit_detectors.py` compares three detectors with the same calibration (24 phases), the same persistence (6) and the same injected faults: the ratio rule in the firmware, an exponentially weighted version of it, and an Isolation Forest on five window features (log ON change, log OFF change, log drift, and the spread of the ON and OFF durations in the window). To make the comparison fair, each detector gets one alarm threshold, chosen on the two training houses so that the healthy false-alarm rate there is at or below 2 or 5 episodes per 30 days. That threshold is then applied unchanged to the held-out house. The forest is fitted on the training houses only.

Averages over the four held-out appliances:

| Target on the training houses | Detector | Healthy episodes per 30 days | 3x fault found | Median delay for 3x (days) | 5x fault found |
|---|---|---|---|---|---|
| 2 per 30 days | ratio rule | 2.7 | 100% | 3.1 | 100% |
| 2 per 30 days | exponentially weighted | 2.6 | 100% | 3.0 | 100% |
| 2 per 30 days | Isolation Forest | 6.4 | 96% | 3.4 | 100% |
| 5 per 30 days | ratio rule | 6.6 | 100% | 2.1 | 100% |
| 5 per 30 days | exponentially weighted | 3.9 | 100% | 2.0 | 100% |
| 5 per 30 days | Isolation Forest | 12.5 | 100% | 2.0 | 100% |

All three find the injected faults almost every time, so the difference is in the false alarms. The forest raised about twice as many as the ratio rule at both targets (6.4 against 2.7, and 12.5 against 6.6). It is not a better detector for this signal, and it needs 50 stored trees where the rule needs a few lines, so the firmware keeps the ratio rule. The exponentially weighted version was close to the ratio rule on average but not on every appliance (on House 2 it gave 8.3 healthy episodes against 1.9 at the first target), and with three homes I cannot say it is better. The thresholds chosen on the training houses also did not hold the target on the held-out ones (the ratio rule gave 6.1 episodes on the House 20 fridge at the first target), which shows how much the right threshold depends on the particular fridge. Full output: [`ML-Validation/results/refit_detectors_results.md`](ML-Validation/results/refit_detectors_results.md).

#### Warning threshold

`refit_threshold_curve.py` shows what moving the Warning threshold does with the settings the firmware now uses (24 phases, window 5, persistence 6). It is descriptive over all three homes and not a held-out test. Simple averages over the four appliances, from the saved output:

| Warning threshold | Healthy episodes per 30 days | 1.5x fault found (median delay) | 2x fault found (median delay) | 3x fault found (median delay) |
|---|---|---|---|---|
| 1.5 | 9.2 | 100% (2.6 d) | 100% (1.9 d) | 100% (1.6 d) |
| 1.8 (firmware) | 5.1 | 96% (3.5 d) | 100% (2.8 d) | 100% (2.1 d) |
| 2.0 | 3.4 | 87% (4.7 d) | 100% (3.5 d) | 100% (2.5 d) |
| 2.4 | 1.8 | 71% (6.6 d) | 96% (5.3 d) | 100% (3.4 d) |

Raising the threshold cuts false alarms but misses small faults and finds the rest later. Nothing in the table removes the noise. I kept 1.8 because it is the highest value in the table that still finds a 1.5x fault in nearly every slice, but 2.0 is a reasonable alternative if false alarms matter more than catching small drifts. The real choice needs data from the actual fridge. Full output: [`ML-Validation/results/refit_threshold_curve_results.md`](ML-Validation/results/refit_threshold_curve_results.md).

### Labelled freezer records (ULT)

The household tests use artificial faults. To see the rule on real compressor faults I ran it on the labelled ultra-low-temperature freezer dataset (Huang, Nøstvik, Bacher, Jensen, Markussen and Møller, Scientific Data 2023, [10.1038/s41597-023-02808-6](https://doi.org/10.1038/s41597-023-02808-6); the data are released under CC0). I used ten Revco freezers from a biobank, held at -80 °C. They were logged once a minute for 6 to 11 years each, and the dataset lists 22 faults with the date of the service report. `ML-Validation/ult/ult_analysis.py` is the only script for this part.

How it works:

- The compressor counts as ON when either cascade stage is running, taken from the controller's State code. Readings with the door-open bit set are skipped.
- Steady blocks end at a gap over 5 minutes or when the chamber is warmer than -65 °C. The firmware rule is applied with its default settings (24 calibration phases, window 5, persistence 6, Warning 1.8, Critical 3.5). Alarms less than 3 days apart count as one episode.
- Healthy time leaves out 90 days before to 30 days after each fault date. I wrote the method down before running the extra freezers. The thresholds 1.5 and 2.0 are shown to see how sensitive the result is and were not picked from the results.
- Compressor and refrigerant-leak faults (14 with enough data) are the main test. The other 7 labels (door, wiring, battery, setpoint, condensation, filter) are kept apart, and one label had no data.

| Threshold | Healthy episodes per 30 days | Compressor or refrigerant faults with an alarm in the last 30 days | Same, last 90 days | Other faults with an alarm, last 90 days |
|---|---|---|---|---|
| 1.5 | 0.31 (336 episodes) | 4 of 14 | 6 of 14 | 5 of 7 |
| 1.8 (firmware) | 0.15 (158 episodes) | 2 of 14 | 4 of 14 | 2 of 7 |
| 2.0 | 0.11 (114 episodes) | 1 of 14 | 1 of 14 | 0 of 7 |
| 3.5 (Critical) | 0.05 (52 episodes) | 0 of 14 | 0 of 14 | 0 of 7 |

What I take from it:

- **It alarms rarely.** There were 158 Warning episodes in about 89 freezer-years of healthy time, roughly 1.8 per freezer per year. This is an upper bound, because the unlabelled time is not clean: one freezer (806026) accounts for 31 of the 52 Critical episodes, and its log shows repeated failures to reach the setpoint and several power interruptions.
- **It matches the labelled faults poorly.** At 1.8, 4 of 14 compressor and refrigerant faults had a Warning in the 90 days before the service date, and none reached Critical. For several stage 2 compressor services (freezers 806024, 806026 and 806033) the highest drift in those 90 days was only 1.02 to 1.21. It is also not specific: 2 of 7 other faults (a door adjustment and a condensation fault) had a Warning too. At 1.5 it caught 6 of 14 and doubled the false alarms. The dates are service-report dates, so the fault may have started much earlier or may not affect the cycling.
- **Long drifts often ended in the freezer's own alarm.** There were 19 Warning episodes of 14 days or more that had no label. For the 18 with an events file, the freezer logged a warm alarm, a shutdown, a warm interstage warning or a failure to reach the setpoint within 10 days after the episode in 12 cases, and nothing in 6. For example, freezer 806016 sat above 1.8 for 81 days (peak 5.5) until a warm alarm and shutdown on 16 August 2018. These events are not fault labels, and an episode also ends when the chamber warms and the block restarts, so I do not count them as detections. They suggest the ratio rose for weeks before the alarm in several freezers, which is worth testing properly.
- **It differs from the firmware.** The compressor state came from the controller, not from the 8 °C and 2 °C rule, so this does not test the temperature-based state inference. ULT cascade freezers are not vaccine refrigerators.

Full output: [`ML-Validation/ult/results/ult_report.md`](ML-Validation/ult/results/ult_report.md) and the drift plot [`ult_drift_all.png`](ML-Validation/ult/results/ult_drift_all.png).

### Replay on the board

`ML-Validation/refit/make_replay_data.py` turns the same recorded phases into a data file (`replay_data.h`, 66,568 entries, about 130 KB). It also works out in Python, with two independent implementations that agree with each other, what the decision logic should output for the original settings (3 calibration phases, window 5, persistence 1) and the new ones (24, 5, 6). `Embedded/tests/refit_replay_board` then runs `fridge_logic.h`, the same code the firmware uses, over that data on an ESP32-S3. For each appliance it prints the number of evaluations, the number at each alert level, and a hash of the whole alert-level sequence. No sensors or network are involved.

All eight lines (four appliances, two settings) matched the Python result exactly, hash included, so the board produced the same alert sequence as the analysis on about 66,000 recorded phases. The board output is in [`ML-Validation/results/board_replay_log.txt`](ML-Validation/results/board_replay_log.txt) and the expected output in [`ML-Validation/results/replay_expected.txt`](ML-Validation/results/replay_expected.txt).

| Appliance | Evaluations (original / new) | Hash match |
|---|---|---|
| House 2 fridge-freezer | 13,885 / 12,718 | yes |
| House 15 fridge-freezer | 17,506 / 16,676 | yes |
| House 20 fridge | 19,845 / 19,299 | yes |
| House 20 freezer | 14,781 / 14,233 | yes |

The board was an ESP32-S3 (QFN56, revision 2) at 240 MHz, and the replay sketch used 410,016 bytes of program memory. Each phase took 16 to 18 µs, including the replay loop, the hash and the flash reads. That cannot be compared with the 2.03 µs figure further down, which timed different code. The shared logic uses double-precision arithmetic (done in software on this chip) so that it matches the Python results exactly. Either way it is far below the minutes a compressor phase lasts.

This shows that the firmware logic reproduces the analysis. It is a replay of recorded household-fridge phases and not a test with a real fridge.

### Isolation Forest on the board

To see whether the forest could run on the chip at all, `ML-Validation/refit/make_if_model.py` trains one on the healthy REFIT windows (50 trees, 128 samples per tree, the five features above) and exports the trees as C arrays. `Embedded/tests/if_board_test` scores a few thousand stored feature vectors on the ESP32-S3 and compares each score with the one scikit-learn gave on the computer. I ran it first with a model trained on synthetic phases, to test the chip before the REFIT model was ready. The board scores matched scikit-learn to within 3.2e-8, no alarm decision differed, and one score took about 100 µs. Those figures are for the synthetic-trained model. They check that the export and the chip work and say nothing about detection quality, which the [detector comparison](#detector-comparison) covers.

### Firmware in Wokwi

I first ran the sketch with the temperature driven by hand through the DHT22 slider. Calibration finished after 3 ON and 3 OFF cycles (baseline ON 38.44 s, OFF 44.91 s). With ON periods stretched relative to OFF, the smoothed drift rose from about 1.5 to 4.3. The sketch printed WARNING at 1.82 and CRITICAL at 4.07, and stepped back down to WARNING when the drift fell to 3.34. Because of the 5-cycle smoothing, a few abnormal cycles are needed before an alert appears. The thresholds are relative to each calibration, so Critical needs the smoothed ratio to exceed 3.5 times the baseline ratio printed at calibration.

In later runs the published MQTT messages carried `alertLevel` 1 (Warning) and `alertLevel` 2 (Critical, drift 3.65 at the point it escalated). During recovery, normal-length cycles brought the drift down through 2.48, 2.58, 2.22, 2.29, 2.01, 2.04 and 1.82 (still Warning) to 1.51, and the published message then carried `alertLevel` 0 (Normal). The Streamlit dashboard showed "Critical" and later "Normal" to match, and a stale-data banner appears when no message has arrived for 30 s.

After the settings change I ran the revised sketch (using `fridge_logic.h`) in Wokwi with `DEMO_SHORT_SETTINGS 1`, so that calibration takes 3 phases and an alert needs one evaluation. The saved log ([`Embedded/logs/wokwi_short_mode_log.txt`](Embedded/logs/wokwi_short_mode_log.txt)) shows a smoothed drift of 1.66 with no alert, then 1.94 with `WARNING: Early sign of abnormal cycling detected (sustained).`, and the published MQTT messages then carry `alertLevel` 1. That log does not include the calibration messages or the Critical text.

Wokwi runs slower than real time (roughly 40 to 80% in my runs, and it stops when the browser tab is in the background), and it does not model real power draw or sensor noise. For a hands-off run I added the test mode described next, which the sketch can also run inside Wokwi. A run in Wokwi with the short settings ([`Embedded/logs/wokwi_test_signal_log_2026-11-16.txt`](Embedded/logs/wokwi_test_signal_log_2026-11-16.txt)) reached WARNING at a drift of 1.81 and CRITICAL at 3.71, and the door opened and closed during Critical. That log came from an earlier version of the test mode that stopped at the fault peak and never returned to Normal, so recovery is covered by the board run below.

With the original version of the sketch I also checked door-event exclusion, the distinct alert tones, MQ2 threshold behaviour, the daily-reset exposure counter and MQTT delivery to the dashboard. The main loop kept a steady cycle of about 2 s during repeated failed MQTT connection attempts.

### Full scenario on the board

Setting `SIMULATED_TEMPERATURE` to 1 in `fridge_monitor.ino` makes the sketch generate its own temperature, door, gas reading and clock, so the firmware runs on a bare ESP32-S3 with nothing attached. It plays one scenario: healthy cycling, a growing fault, recovery, a gas reading above the threshold, then the door open with the temperature held at 9 °C. I ran it on the real board with the full settings (24 calibration phases, persistence 6, `DEMO_SHORT_SETTINGS 0`) and saved the Serial output in [`Embedded/logs/board_scenario_log_2026-11-17.txt`](Embedded/logs/board_scenario_log_2026-11-17.txt). Times are the sketch's own clock, which starts at 12:00:00.

| Event | Clock | What the log shows |
|---|---|---|
| Calibration complete | 12:09:24 | Baseline ON 10.92 s, OFF 12.58 s |
| Warning | 12:16:14 | Drift 2.58 |
| Critical | 12:21:12 | Drift 4.21 |
| Back to Normal | 12:25:50 | Drift 1.71, "Cycling is back within normal limits." |
| Gas alert, then cleared | 12:27:46 to 12:28:16 | Reading 3000, then 1100 |
| Door opened | 12:28:34 | Temperature held at 9 °C |
| Exposure alert | 12:28:44 | Raised at 2 minutes of warm time, the test threshold (the real one is 30) |
| Door closed | 12:31:30 | "Cycle ignored (right after door event)." No alert follows |

The log has one boot line at the top and no watchdog message or restart in about 36 minutes of sketch time. This covers the full 24/6 settings, recovery from Critical, the exposure counter, the gas alert and the door handling. It does not cover real sensors, LEDs or the buzzer (none were attached), or MQTT (no Wi-Fi network was available, so the sketch only logged that it was starting Wi-Fi in the background). Every input is a generated test signal, so this tests the decision logic and the alert paths and is not a fridge test.

An earlier version of this run reset the chip with a task watchdog error. The Wi-Fi/MQTT task ran at priority 1 on core 0 and starved the idle task while it waited on the broker. It now runs at priority 0 with a 3 s socket timeout.

### Measurements on a real ESP32-S3

I ran two tests on an ESP32-S3-N16R8 board (16 MB flash, 8 MB octal PSRAM; the timing benchmark ran with PSRAM disabled), both with synthetic inputs.

- Decision-logic timing (`Embedded/tests/decision_logic_bench`). The cycle evaluation with the rolling window was timed at 240 MHz over 20,000 synthetic cycles. The mean was 2.03 µs per call, the minimum 0.22 µs and the maximum 6.81 µs. The benchmark sketch used 275,808 bytes of program memory. This covers the decision logic of the first firmware version only, without sensors, buzzer, Wi-Fi or MQTT, and I did not measure energy. See [`Embedded/logs/decision_logic_bench_results.md`](Embedded/logs/RESULTS.md).
- Network behaviour (`Embedded/tests/offline_latency_test`, phone hotspot, public MQTT broker). With the MQTT connect call in the main loop, an unreachable broker stalled the loop repeatedly (usually about 3 s, sometimes about 15 s), and the longest loop period reached 17,127 ms against 2000 ms nominal. With a reachable broker the loop stalled once, for about 1 to 1.5 s. With the network work moved to its own task the loop stayed at 2000 ms in both cases. I also found that calling `setServer()` only when Wi-Fi was already up at boot meant MQTT never started if Wi-Fi came up later (0 messages in about 530 s). Calling it unconditionally fixed that. See [`Embedded/logs/offline_latency_results.md`](Embedded/logs/OFFLINE_RESULTS.md).

The firmware uses the network-task structure, and `loop()` no longer calls `delay(2000)` or blocks on the buzzer: sensing runs every 2 s from `millis()` and sounds are played in steps. I did not re-measure the loop timing or the sensor-to-alert latency after that change, and I did not measure energy.

## Running it

Each part has its own instructions. The short version:

Fridge simulation:

```
cd ML-Validation/simulation
pip install pandas numpy scikit-learn matplotlib
python fridge_pipeline.py
python threshold_analysis.py
```

The first script prints held-out flag counts and ROC AUC and saves `fridge_anomaly_trend.png` and `fridge_hourly_features.csv` in the current folder. The second prints the threshold table above.

MetroPT-3. Download the dataset from the UCI repository, put the CSV in `ML-Validation/metropt3/` and run the command below. It prints data checks, including the sampling interval, writes `metropt3_results.md` and takes a few minutes.

```
cd ML-Validation/metropt3
python metropt3_analysis.py --csv "MetroPT3(AirCompressor).csv" --out metropt3_out
```

REFIT scripts. Download the cleaned REFIT data ([Strathclyde dataset page](https://pureportal.strath.ac.uk/en/datasets/refit-electrical-load-measurements-cleaned/), file `CLEAN_REFIT_081116.7z`, about 490 MB), extract the house files `CLEAN_House2.csv`, `CLEAN_House15.csv` and `CLEAN_House20.csv` into `ML-Validation/refit/data/` and run the commands below. Do not open the CSVs in Excel. Each script reads three files of 300 to 350 MB and takes a few minutes, and the results are written to `ML-Validation/results/`.

```
cd ML-Validation/refit
pip install pandas numpy scikit-learn
python refit_replay.py
python refit_sweep.py
python refit_detectors.py
python refit_threshold_curve.py
```

ULT freezer records. Download the `*_temp.parquet` files (and the matching `*_events.parquet` files if you want the event log in the report) of the Revco freezers from the dataset's GitLab repository linked in the paper, put them in `ML-Validation/ult/data/` and run:

```
cd ML-Validation/ult
pip install pandas numpy pyarrow matplotlib
python ult_analysis.py
```

Each temperature file is about 175 MB. The script writes `ult_report.md` and `ult_drift_all.png` next to itself.

Board tests and the firmware: see [`Embedded/README.md`](Embedded/README.md).

Dashboard:

```
cd IoT-dashboard
pip install streamlit paho-mqtt
streamlit run dashboard.py
```

Then start the Wokwi simulation. The device and the dashboard share one public MQTT topic.

## Limitations and known issues

- The thresholds were checked against a simulation and not against real vaccine-fridge logs. I did not find a public dataset of real vaccine-fridge failures. The Critical threshold of 3.5 is above anything the simulation produces.
- On recorded household-fridge traces the original rule raised Warning episodes every 1 to 6 days on healthy appliances. The longer calibration with persistence cut that by about a third to 70% in leave-one-house-out testing but did not remove it, and the traces are from domestic appliances with no door information. The new default has not been tried on a real fridge.
- The full firmware has not been run on a physical fridge or with physical sensors. The board runs used recorded or generated inputs.
- On the ULT freezer records the rule flagged 4 of 14 compressor or refrigerant faults in the 90 days before their service dates at the default threshold, and it also alarmed before 2 of 7 other faults. The fault dates are service-report dates, the compressor state came from the controller, and the freezers are -80 °C laboratory units, not vaccine fridges. The events behind the long unlabelled drifts were not confirmed as faults.
- The injected faults in the REFIT tests are artificial, so detection rates and delays show how the rule behaves on a simulated drift and not how it would perform on real failures.
- The test mode shortens the exposure alert to 2 minutes. The 30-minute value has not been run on the board.
- The MetroPT-3 result depends on how "compressor ON" is defined and on the failure windows in the dataset documentation. It also comes from a different machine, a train compressor.
- On the simulation the Isolation Forest separates healthy from degrading hours only weakly, and on the REFIT traces it raised more false alarms than the ratio rule.
- The firmware infers "compressor on" from the 8 °C and 2 °C thresholds. A real fridge cycles on its own thermostat, so a real build would need a compressor current sensor or a temperature-slope detector.
- The MQ2 sensor detects combustible vapours only. Exposure tracking resets daily and does not follow a vaccine's whole storage life.
- The public MQTT broker (`broker.emqx.io`) has no authentication and is for demonstration only. MQTT has not been exercised on the board with the current firmware.
- I have not measured sensor-to-alert latency of the full firmware, or its energy use.

### Corrections made during testing

Testing on the board and in the simulator turned up several problems. They are fixed in the current sketch.

- The rolling window shifted its array while it was still filling, which put zeros into early averages and made the drift too low.
- Calibration counted the partial period from power-up to the first transition as a full cycle, and divided the ON total by one count too many. In a simulated healthy fridge that gave a baseline ratio of 0.345 against a true 0.462, so drift read about 1.3 times too high.
- MQTT connect was called from the main loop and blocked it, and `setServer()` was skipped when Wi-Fi was not up at boot.
- Warm time added a fixed 2 s per loop, which underestimates the time because each loop takes longer than that.
- My first fridge-simulation and MetroPT-3 evaluations reported false-flag rates on the same hours the model was trained on, which only reproduces the contamination setting. I replaced them with held-out evaluations.
- The first version of the REFIT replay dropped every phase containing an `Issues` row. That removed 27 to 32% of the phases, cut the data into hundreds of short fragments (so the fault-injection test could not run), and flattered the recalibrate-after-breaks row, because it recalibrated every few hours. The replay now keeps those phases, recalibrates only after real outages, and reports the dropped-`Issues` version as a check. I made this change after seeing the first results.
- Moving the decision logic into `fridge_logic.h` changed one behaviour on purpose. The rolling window now includes the calibration phases, as in the Python analysis, so drift is evaluated from the first phase after calibration and does not wait for the window to refill. The sketch also gained a persistence counter and the 24-phase default.
- The main loop blocked on `delay(2000)` and the buzzer routines (the critical siren took about 1.25 s). Both are gone: sampling runs from `millis()` and the buzzer plays in steps.
- Running the full firmware on the board showed a task watchdog reset caused by the network task's priority. It is fixed as described above.

## Planned work

- Test the firmware on the board with real sensors, and report energy only if I measure it with a power meter.
- Collect real fridge temperature data, replace the thresholds that came from the simulation, and test compressor-state sensing. Trying the new settings (24 calibration phases, persistence 6) on a real fridge is the biggest remaining gap.
- Test the on/off-cycle rule on the ORNL supermarket refrigeration fault dataset (Sun et al., Scientific Data 2021, figshare 10.6084/m9.figshare.13232627), which pairs fault-free baseline tests with six imposed faults, including an open display-case door.
- Move the dashboard to a private, authenticated MQTT broker.

## Data and credits

MetroPT-3: Veloso, B., Ribeiro, R.P., Pereira, P.M., Gama, J., "The MetroPT dataset for predictive maintenance", Scientific Data 9, 764 (2022), DOI 10.1038/s41597-022-01877-3. Dataset on UCI, DOI 10.24432/C5VW3R (CC BY 4.0).

REFIT: Murray, D., Stankovic, L., Stankovic, V., "An electrical load measurements dataset of United Kingdom households from a two-year longitudinal study", Scientific Data 4, 160122 (2017), DOI 10.1038/sdata.2016.122. Cleaned dataset: University of Strathclyde, DOI 10.15129/9ab14b0e-19ac-4279-938f-27f643078cec (CC BY 4.0). As the dataset ReadMe asks, also cite Murray, D., Liao, J., Stankovic, L., et al., "A data management platform for personalised real-time energy feedback", Proceedings of the 8th International Conference on Energy Efficiency in Domestic Appliances and Lighting (EEDAL), 2015.

Author: Adu-Gyamfi Kwadwo, B.Sc. Electrical/Electronic Engineering, KNUST, Ghana.
