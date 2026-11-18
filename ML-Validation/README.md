# ML-Validation

Python analysis behind the firmware rule and the checks on recorded data. The results quoted in the main README are saved in `results/`.

```
simulation/   Simulated fridge with an Isolation Forest, and the threshold check
metropt3/     Hourly-features Isolation Forest on the MetroPT-3 air-compressor dataset
refit/        Replay of recorded household-fridge traces (REFIT) through the firmware rule
ult/          The rule on ten labelled ultra-low-temperature freezers: ult_analysis.py and its saved report
results/      Saved output and the board replay log
```

## REFIT scripts

Put the cleaned REFIT files `CLEAN_House2.csv`, `CLEAN_House15.csv` and `CLEAN_House20.csv` in `refit/data/`. They are about 300 MB each and are not in the repo. Then, from `refit/`:

| Script | What it does | Writes |
|---|---|---|
| `refit_replay.py` | Original rule on healthy traces, plus an injected-fault test | `results/refit_replay_results.md` |
| `refit_sweep.py` | 48 variations of calibration, window and persistence, leave-one-house-out | `results/refit_sweep_results.md` |
| `refit_detectors.py` | Ratio rule, exponentially weighted rule and Isolation Forest at equal false-alarm targets | `results/refit_detectors_results.md` |
| `refit_threshold_curve.py` | Warning threshold against false alarms and fault size | `results/refit_threshold_curve_results.md` |
| `make_replay_data.py` | Data file for the board replay and the results the board must reproduce | `Embedded/tests/refit_replay_board/replay_data.h`, `results/replay_expected.txt` |
| `make_if_model.py` | Trains the Isolation Forest and exports it for the board | `Embedded/tests/if_board_test/` |
| `check_replay_log.py` | Compares a board log with `replay_expected.txt` | Prints a match or the differences |

`refit_sweep.py`, `refit_detectors.py` and `refit_threshold_curve.py` import `refit_replay.py`, so keep them in the same folder. They need pandas, numpy and scikit-learn.

REFIT is not a vaccine-fridge dataset. The faults in these tests are injected into recorded household traces, so the results describe the detector and not real failures.

## ULT freezer script

`ult/ult_analysis.py` runs the firmware rule on the labelled ULT freezer dataset (Huang et al., Scientific Data 2023, CC0 data). Put the `*_temp.parquet` files, and the `*_events.parquet` files if you have them, in `ult/data/` (about 175 MB per temperature file, not in the repo) and run `python ult_analysis.py` from `ult/`. It needs pandas, numpy, pyarrow and matplotlib, and writes `ult_report.md` and `ult_drift_all.png`. The saved output is in `ult/results/`. The faults are dated at the service report and the freezers are not vaccine fridges.
