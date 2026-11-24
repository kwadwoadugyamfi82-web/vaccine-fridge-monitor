# Data needed to reproduce the results

None of the datasets are stored in this repository. They are public, large (GitHub rejects files over 100 MB) and belong to their authors, so download them from the sources below and place them exactly where shown. The saved outputs of every script are already in `ML-Validation/results/` and `ML-Validation/ult/results/`, so you can read the results without downloading anything. The fridge simulation scripts need no download because they generate their own data.

| Part | Dataset | Size | Where to put it | Licence |
|---|---|---|---|---|
| MetroPT-3 | MetroPT-3 Dataset, UCI Machine Learning Repository | 208 MB zip (file `MetroPT3(AirCompressor).csv`, 1,516,948 rows) | `ML-Validation/metropt3/` | CC BY 4.0 |
| REFIT replay, sweep, detectors, threshold curve, board replay | REFIT: Electrical Load Measurements (Cleaned), University of Strathclyde | 490 MB archive; three house files of about 300 to 350 MB each | `ML-Validation/refit/data/` | CC BY 4.0 |
| ULT freezers | Labelled dataset for Ultra-Low Temperature Freezers (Huang et al., 2023) | about 175 MB per temperature file; about 1.7 GB for the ten freezers | `ML-Validation/ult/data/` | see the dataset page (CC0 according to the project notes) |

## 1. MetroPT-3

- Page: https://archive.ics.uci.edu/dataset/791/metropt+3+dataset (DOI [10.24432/C5VW3R](https://doi.org/10.24432/C5VW3R))
- Direct download: https://archive.ics.uci.edu/static/public/791/metropt+3+dataset.zip
- Unzip it and put `MetroPT3(AirCompressor).csv` in `ML-Validation/metropt3/`.
- Run:

```
cd ML-Validation/metropt3
python metropt3_analysis.py --csv "MetroPT3(AirCompressor).csv" --out metropt3_out
```

- Check: the file has 1,516,948 rows. The dataset page describes 1 Hz sampling, but this file holds every tenth sample (median interval 10 s). The script reads the interval from the timestamps.
- Citation: Davari, N., Veloso, B., Ribeiro, R., & Gama, J. (2021). MetroPT-3 Dataset. UCI Machine Learning Repository. https://doi.org/10.24432/C5VW3R

## 2. REFIT (household fridges and freezers)

- Page: https://pureportal.strath.ac.uk/en/datasets/refit-electrical-load-measurements-cleaned/ (DOI [10.15129/9ab14b0e-19ac-4279-938f-27f643078cec](https://doi.org/10.15129/9ab14b0e-19ac-4279-938f-27f643078cec))
- Download `CLEAN_REFIT_081116.7z` (about 490 MB) and extract these three files into `ML-Validation/refit/data/`:
  - `CLEAN_House2.csv` (Appliance1, fridge-freezer)
  - `CLEAN_House15.csv` (Appliance1, fridge-freezer)
  - `CLEAN_House20.csv` (Appliance1 fridge, Appliance2 freezer)
- Do not open the CSV files in Excel. Each script reads all three and takes a few minutes.
- Run, from `ML-Validation/refit/`: `python refit_replay.py`, `python refit_sweep.py`, `python refit_detectors.py`, `python refit_threshold_curve.py`.
- `make_replay_data.py` and `make_if_model.py` also need these files. They write the headers used by the board tests in `Embedded/tests/`.
- Citation: Murray, D., Stankovic, L., & Stankovic, V. (2017). An electrical load measurements dataset of United Kingdom households from a two-year longitudinal study. Scientific Data, 4, 160122. https://www.nature.com/articles/sdata2016122

## 3. ULT freezers

- Paper: Huang, Nøstvik, Bacher, Jensen, Markussen and Møller (2023), Scientific Data, DOI [10.1038/s41597-023-02808-6](https://doi.org/10.1038/s41597-023-02808-6). Its Data Records section says the data are stored in figshare and in an open-access GitLab repository; follow the links given there.
- Files are named `<freezer id>_temp.parquet` (temperature data with labels) and `<freezer id>_events.parquet` (event log, optional). The Revco freezers are in the `dataset/Revco` folder of that repository.
- The analysis uses these ten Revco freezers: 806016, 806017, 806024, 806026, 806031, 806033, 806269, 806272, 806276, 806279.
- Put the ten `_temp.parquet` files (and the `_events.parquet` files if you want the event log in the report) in `ML-Validation/ult/data/`.
- Run:

```
cd ML-Validation/ult
python ult_analysis.py
```

It writes `ult_report.md` and `ult_drift_all.png` next to the script.
- Expected: the saved report in `ML-Validation/ult/results/ult_report.md` lists the same ten freezers with their record counts, so you can check that you have the right files.

## Python packages

`pip install -r ML-Validation/requirements.txt` installs pandas, numpy, scikit-learn, matplotlib and pyarrow. The dashboard needs `pip install -r IoT-dashboard/requirements.txt`.
