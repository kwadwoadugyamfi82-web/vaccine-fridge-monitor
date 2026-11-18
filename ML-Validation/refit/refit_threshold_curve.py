"""
Shows how the Warning threshold of the ratio rule trades false alarms against fault size on the REFIT traces.

For each appliance and each threshold (24 calibration phases, window 5, persistence 6) it prints the healthy
false-alarm episodes per 30 days and how often and how fast injected faults of 1.5x, 2x and 3x are found. It
is a descriptive curve over all three homes, not a held-out test, so it shows the trade-off without choosing
a threshold.

Run:  python refit_threshold_curve.py   Results are saved to ../results/refit_threshold_curve_results.md.
"""
from pathlib import Path

import numpy as np
import pandas as pd

import refit_replay as rr
import refit_detectors as dt

dt.MS = [1.5, 2.0, 3.0]
THRESHOLDS = [1.3, 1.4, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.6]


def main():
    data = {}
    for path, house, cols in rr.FILES:
        if not Path(path).exists():
            print("File not found:", path)
            continue
        print(f"reading {house} ...", flush=True)
        df = pd.read_csv(path, usecols=["Unix", "Issues"] + cols)
        t = df["Unix"].values.astype(np.int64)
        order = np.argsort(t, kind="stable")
        t, issue = t[order], df["Issues"].values[order] == 1
        for col in cols:
            p = df[col].values[order].astype(float)
            runs, _, _ = rr.filter_runs(rr.extract_runs(t, p, issue, rr.MIN_RUN_S), False, rr.MIN_RUN_S)
            data[f"{house}, {col}"] = dt.collect(runs)
    out = ["# Warning threshold of the ratio rule: false alarms against fault size", "",
           f"Calibration {dt.L} phases, window {dt.W}, persistence {dt.P}. Descriptive over all three homes. "
           "Each cell after the first is the share of injected faults found and the median delay in days.", ""]
    for a, c in data.items():
        out += [f"## {a}", "", "| Threshold | Healthy episodes per 30 d | 1.5x fault | 2x fault | 3x fault |", "|---|---|---|---|---|"]
        for thr in THRESHOLDS:
            r = dt.healthy_rate(c, "ratio", None, thr)
            cells = []
            for M in dt.MS:
                frac, med = dt.detect(c, "ratio", None, thr, M)
                cells.append(f"{frac * 100:.0f}% ({med:.1f} d)")
            mark = "  (current Warning)" if thr == 1.8 else ""
            out.append(f"| {thr}{mark} | {r:.1f} | " + " | ".join(cells) + " |")
        out.append("")
    text = "\n".join(out)
    rr.RESULTS.mkdir(exist_ok=True)
    path = rr.RESULTS / "refit_threshold_curve_results.md"
    path.write_text(text, encoding="utf-8")
    print("\n" + text)


if __name__ == "__main__":
    main()
