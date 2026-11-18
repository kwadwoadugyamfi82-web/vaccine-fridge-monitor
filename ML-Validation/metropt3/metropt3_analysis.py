#!/usr/bin/env python3
"""
MetroPT-3 check of the hourly-features + Isolation Forest method.

The original script was lost in a disk failure, so this is a rebuild from the paper's description (seven
per-hour features, a model fitted on normal hours only) and from fridge_pipeline.py. The paper does not say
which signal defines "compressor on", how normal hours were chosen or whether the evaluation was held out, so
this script runs three defensible ON definitions and reports all of them. Its numbers differ from the first
version of the paper (82/86 and 201/4,327); report what it prints.

The evaluation is held out: the model is fitted on the earliest 60% of normal hours and scored on the later
normal hours and the failure hours.

Data: MetroPT-3, UCI Machine Learning Repository (CC BY 4.0), DOI 10.24432/C5VW3R,
https://archive.ics.uci.edu/dataset/791/metropt+3+dataset . The file is "MetroPT3(AirCompressor).csv"
(about 208 MB, 1,516,948 rows at a 10 s interval, Feb to Aug 2020; the dataset page says 1 Hz). The script reads
the interval from the timestamps. The dataset has no labels. The four failure windows below are the company
failure reports listed on the UCI page (all air leaks); the page says its report numbering is inconsistent, so
treat the windows as published, not verified.

Run:  python metropt3_analysis.py --csv "MetroPT3(AirCompressor).csv" --out metropt3_out
Outputs: metropt3_results.md, metropt3_results.json, hourly_features_<definition>.csv, and a plot if
matplotlib is installed.
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score, roc_auc_score

FAILURE_WINDOWS = [
    ("2020-04-18 00:00:00", "2020-04-18 23:59:59", "event 1 (18 Apr)"),
    ("2020-05-29 23:30:00", "2020-05-30 06:00:00", "event 2 (29-30 May)"),
    ("2020-06-05 10:00:00", "2020-06-07 14:30:00", "event 3 (5-7 Jun)"),
    ("2020-07-15 14:30:00", "2020-07-15 19:00:00", "event 4 (15 Jul)"),
]

FEATURES = ["avg_on_time", "avg_off_time", "std_signal", "peak", "low", "num_cycles", "rolling_cycles_3h"]

ON_DEFINITIONS = {
    "motor_running": "compressor ON = Motor_current above the running threshold (motor turning, loaded or offloaded)",
    "loaded_current": "compressor ON = Motor_current above the loaded threshold (under load)",
    "loaded_valve": "compressor ON = DV_eletric active (outlet valve command, under load)",
}


# ---------------------------------------------------------------- loading
def load_data(path, signal):
    header = pd.read_csv(path, nrows=0).columns.tolist()
    lower = {c.lower(): c for c in header}
    time_col = next((lower[k] for k in ("timestamp", "time", "datetime", "date") if k in lower), None)
    if time_col is None:
        sys.exit("No timestamp column found. Columns in the file: %s" % header)
    if signal not in header:
        sys.exit("Signal column '%s' not found. Columns in the file: %s" % (signal, header))
    valve_col = next((c for c in header if c.lower().replace(" ", "_") in ("dv_eletric", "dv_electric")), None)

    use = [time_col, signal] + ([valve_col] if valve_col else [])
    df = pd.read_csv(path, usecols=use)
    df = df.rename(columns={time_col: "timestamp", signal: "signal"})
    if valve_col:
        df = df.rename(columns={valve_col: "valve"})
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp").drop_duplicates("timestamp").reset_index(drop=True)
    return df, valve_col is not None


def data_checks(df):
    dt = df["timestamp"].diff().dt.total_seconds().dropna()
    median_dt = float(dt.median())
    span_s = (df["timestamp"].iloc[-1] - df["timestamp"].iloc[0]).total_seconds()
    expected_rows_if_continuous = span_s / median_dt if median_dt > 0 else float("nan")
    return {
        "rows": int(len(df)),
        "first_timestamp": str(df["timestamp"].iloc[0]),
        "last_timestamp": str(df["timestamp"].iloc[-1]),
        "median_sample_interval_s": median_dt,
        "share_of_gaps_over_5x_median": float((dt > 5 * median_dt).mean()),
        "rows_if_continuous_at_median_interval": float(expected_rows_if_continuous),
        "signal_quantiles": {str(q): float(df["signal"].quantile(q)) for q in (0.01, 0.25, 0.5, 0.75, 0.99)},
    }


# ---------------------------------------------------------------- features
def make_state(df, definition, args):
    if definition == "motor_running":
        return df["signal"] > args.running_threshold
    if definition == "loaded_current":
        return df["signal"] > args.loaded_threshold
    if definition == "loaded_valve":
        return df["valve"] > 0.5
    raise ValueError(definition)


def hourly_features(df, state, median_dt, coverage):
    """Same features as fridge_pipeline.py: runs are counted inside each hour (a run cut by the hour boundary
    counts as its own run), durations are in samples. Isolation Forest splits are scale-invariant per feature,
    so samples versus seconds does not change the model."""
    d = pd.DataFrame({"hour": df["timestamp"].dt.floor("h"), "state": state.values, "signal": df["signal"].values})
    change = (d["state"] != d["state"].shift()) | (d["hour"] != d["hour"].shift())
    run_id = change.cumsum()
    runs = d.groupby(run_id).agg(hour=("hour", "first"), state=("state", "first"), n=("state", "size"))

    on = runs[runs["state"]].groupby("hour")["n"].agg(avg_on_time="mean", num_cycles="count")
    off = runs[~runs["state"]].groupby("hour")["n"].mean().rename("avg_off_time")
    sig = d.groupby("hour")["signal"].agg(std_signal=lambda x: x.std(ddof=0), peak="max", low="min")
    cnt = d.groupby("hour").size().rename("n_samples")

    h = pd.concat([on, off, sig, cnt], axis=1, sort=True).fillna({"avg_on_time": 0, "avg_off_time": 0, "num_cycles": 0})
    h = h.sort_index()

    expected = 3600.0 / median_dt
    h = h[h["n_samples"] >= coverage * expected].copy()

    # time-based window so a data gap is not silently bridged (fridge_pipeline.py used a row-based window)
    h["rolling_cycles_3h"] = h["num_cycles"].rolling("3h").mean()
    h = h.reset_index().rename(columns={"index": "hour"})
    if "hour" not in h.columns:
        h = h.rename(columns={h.columns[0]: "hour"})
    return h


def label_hours(h):
    overlaps = np.zeros((len(h), len(FAILURE_WINDOWS)))
    for j, (s, e, _) in enumerate(FAILURE_WINDOWS):
        s, e = pd.Timestamp(s), pd.Timestamp(e)
        for i, hr in enumerate(h["hour"]):
            lo = max(hr, s)
            hi = min(hr + pd.Timedelta(hours=1), e)
            overlaps[i, j] = max(0.0, (hi - lo).total_seconds())
    best = overlaps.argmax(axis=1)
    total = overlaps.sum(axis=1)
    h = h.copy()
    h["is_failure"] = total >= 1800  # at least half of the hour inside a documented failure window
    h["event"] = [FAILURE_WINDOWS[b][2] if f else "" for b, f in zip(best, h["is_failure"])]
    return h


# ---------------------------------------------------------------- evaluation
def evaluate(h, contamination, train_frac, seed):
    normal = h[~h["is_failure"]].sort_values("hour")
    fail = h[h["is_failure"]]
    out = {"normal_hours": int(len(normal)), "failure_hours": int(len(fail))}
    if len(normal) < 50 or len(fail) == 0:
        out["error"] = "not enough normal or failure hours to evaluate"
        return out

    # A. Replication of the paper's setup as far as it can be inferred: fit on all normal hours, score everything.
    mA = IsolationForest(contamination=contamination, random_state=seed).fit(normal[FEATURES])
    predA = pd.Series(mA.predict(h[FEATURES]) == -1, index=h.index)
    out["A_replication"] = {
        "failure_flagged": int(predA[fail.index].sum()),
        "failure_total": int(len(fail)),
        "normal_flagged": int(predA[normal.index].sum()),
        "normal_total": int(len(normal)),
        "note": "normal_flagged is measured on the same hours the model was fitted on, so it is close to the "
                "contamination setting by construction. It is not an independent false-alarm estimate.",
    }

    # B. Held-out: train on the earliest part of the normal hours, test on later normal hours plus all failure hours.
    n_train = int(len(normal) * train_frac)
    train, test_normal = normal.iloc[:n_train], normal.iloc[n_train:]
    mB = IsolationForest(contamination=contamination, random_state=seed).fit(train[FEATURES])
    test = pd.concat([test_normal, fail]).sort_values("hour")
    y = test["is_failure"].astype(int).values
    score = -mB.decision_function(test[FEATURES])
    pred = mB.predict(test[FEATURES]) == -1
    per_event = {}
    for ev in sorted(set(fail["event"])):
        mask = (test["event"] == ev).values
        per_event[ev] = {"flagged": int(pred[mask].sum()), "hours": int(mask.sum())}
    out["B_heldout"] = {
        "train_normal_hours": int(len(train)),
        "test_normal_hours": int(len(test_normal)),
        "failure_flagged": int(pred[y == 1].sum()),
        "failure_total": int((y == 1).sum()),
        "test_normal_flagged": int(pred[y == 0].sum()),
        "test_normal_total": int((y == 0).sum()),
        "roc_auc": float(roc_auc_score(y, score)),
        "average_precision": float(average_precision_score(y, score)),
        "per_event": per_event,
        "train_period": "%s to %s" % (train["hour"].iloc[0], train["hour"].iloc[-1]),
        "test_normal_period": "%s to %s" % (test_normal["hour"].iloc[0], test_normal["hour"].iloc[-1]),
    }
    out["_model_B"] = mB
    return out


def maybe_plot(h, model, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return False
    score = model.decision_function(h[FEATURES])
    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.scatter(h["hour"], score, s=5, c=h["is_failure"].map({True: "red", False: "steelblue"}))
    for s, e, _ in FAILURE_WINDOWS:
        ax.axvspan(pd.Timestamp(s), pd.Timestamp(e), color="red", alpha=0.12)
    ax.axhline(0, color="gray", linestyle=":")
    ax.set_ylabel("anomaly score (lower = more abnormal)")
    ax.set_title("MetroPT-3 hourly anomaly score (held-out model, red = documented failure hours)")
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return True


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", required=True, help="path to MetroPT3(AirCompressor).csv")
    ap.add_argument("--out", default="metropt3_out")
    ap.add_argument("--signal", default="Motor_current", help="signal used for std/peak/min features")
    ap.add_argument("--only", choices=list(ON_DEFINITIONS), help="run a single ON definition")
    ap.add_argument("--running-threshold", type=float, default=1.0)
    ap.add_argument("--loaded-threshold", type=float, default=5.5)
    ap.add_argument("--coverage", type=float, default=0.5, help="min share of expected samples per hour")
    ap.add_argument("--contamination", type=float, default=0.05)
    ap.add_argument("--train-frac", type=float, default=0.6)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    df, has_valve = load_data(args.csv, args.signal)
    checks = data_checks(df)
    print("Data checks:")
    for k, v in checks.items():
        print("  %s: %s" % (k, v))

    defs = [args.only] if args.only else list(ON_DEFINITIONS)
    if not has_valve and "loaded_valve" in defs:
        print("DV_eletric column not found: skipping loaded_valve")
        defs.remove("loaded_valve")

    results, plotted = {}, False
    for name in defs:
        state = make_state(df, name, args)
        h = label_hours(hourly_features(df, state, checks["median_sample_interval_s"], args.coverage))
        h.to_csv(os.path.join(args.out, "hourly_features_%s.csv" % name), index=False)
        res = evaluate(h, args.contamination, args.train_frac, args.seed)
        model = res.pop("_model_B", None)
        if model is not None and not plotted:
            plotted = maybe_plot(h, model, os.path.join(args.out, "anomaly_score_%s.png" % name))
        res["definition"] = ON_DEFINITIONS[name]
        res["hours_after_coverage_filter"] = int(len(h))
        results[name] = res
        print("\n== %s: %s" % (name, ON_DEFINITIONS[name]))
        print(json.dumps(res, indent=2, default=str))

    with open(os.path.join(args.out, "metropt3_results.json"), "w") as f:
        json.dump({"data_checks": checks, "settings": vars(args), "results": results}, f, indent=2, default=str)

    md = ["# MetroPT-3 reconstruction results", "",
          "Produced by `metropt3_analysis.py` (a reconstruction, see its header). Settings: contamination %.2f, "
          "train fraction %.2f, seed %d, signal %s." % (args.contamination, args.train_frac, args.seed, args.signal), "",
          "## Data checks", "",
          "- rows: %d, from %s to %s" % (checks["rows"], checks["first_timestamp"], checks["last_timestamp"]),
          "- median sample interval: %.1f s (continuous coverage at this interval would be %.0f rows)"
          % (checks["median_sample_interval_s"], checks["rows_if_continuous_at_median_interval"]),
          "- share of gaps longer than 5x the median interval: %.4f" % checks["share_of_gaps_over_5x_median"], "",
          "## Results by definition of compressor ON", "",
          "| definition | hours kept | A: failure hours flagged | A: normal hours flagged (in-sample) | "
          "B: failure hours flagged | B: held-out normal flagged | B: ROC AUC |", "|---|---|---|---|---|---|---|"]
    for name, r in results.items():
        if "error" in r:
            md.append("| %s | %d | %s | | | | |" % (name, r["hours_after_coverage_filter"], r["error"]))
            continue
        A, B = r["A_replication"], r["B_heldout"]
        md.append("| %s | %d | %d / %d | %d / %d | %d / %d | %d / %d | %.3f |" % (
            name, r["hours_after_coverage_filter"],
            A["failure_flagged"], A["failure_total"], A["normal_flagged"], A["normal_total"],
            B["failure_flagged"], B["failure_total"], B["test_normal_flagged"], B["test_normal_total"], B["roc_auc"]))
    md += ["", "A = fit on all normal hours and score everything (closest to the paper's described setup; its normal-hour "
           "flag rate is in-sample). B = fit on the earliest %.0f%% of normal hours, test on the later normal hours plus "
           "all failure hours (an honest false-alarm estimate)." % (args.train_frac * 100),
           "", "Failure windows are the four company reports as listed on the UCI page (air leaks), unverified."]
    with open(os.path.join(args.out, "metropt3_results.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    print("\nWrote results to", args.out)


if __name__ == "__main__":
    main()
