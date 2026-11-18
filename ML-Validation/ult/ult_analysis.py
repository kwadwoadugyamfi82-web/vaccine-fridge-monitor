"""
Runs the firmware's drift rule on real ultra-low-temperature freezer records and writes one report.

Data: Revco freezers of the labelled ULT freezer dataset (Huang et al., Scientific Data 2023, CC0 data).
Put every <id>_temp.parquet (and <id>_events.parquet when you have it) in a folder called data next to this
script, then run:  python ult_analysis.py
Needs pandas, numpy, pyarrow, matplotlib. It writes ult_report.md and ult_drift_all.png.

Method, fixed before looking at the extra freezers
  - Compressor on = State bit 1 or 2 (either stage). Door-open readings (bit 16) are skipped like the firmware
    skips the first cycle after a door event.
  - The record is cut into steady blocks (gap over 5 min, or chamber warmer than -65 C, ends a block). The first
    and last phase of each block are dropped.
  - Rule as in the firmware: baseline from the first 24 ON and 24 OFF phases of a block, mean of the last 5
    phases of each kind, drift = (ON mean / OFF mean) / baseline, alarm after 6 evaluations in a row above the
    threshold. Warning 1.8, Critical 3.5. Alarms less than 3 days apart count as one episode.
  - Faults come from the main_fault column (service-report date). Compressor and refrigerant faults are the
    primary test; other labels (door, wiring, battery, setpoint) are listed but kept apart.
  - Healthy time leaves out 90 days before to 30 days after every labelled fault.
  - 1.5 and 2.0 are shown next to 1.8 only to see how sensitive the result is. They were not chosen from the
    results.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
READ = pd.read_parquet

DAY = 86400.0
L, W, P = 24, 5, 6
WARN, CRIT = 1.8, 3.5
THRESHOLDS = [1.5, 1.8, 2.0]
GAP_S, WARM_C = 300, -65.0
ON_MASK, DOOR_BIT = 3, 16
BEFORE, AFTER = 90, 30                  # days around a fault that do not count as healthy
NEAR = 30                               # the short warning window, in days
MIN_EVALS = 500                         # fewer evaluations in the long window: no data for that fault
LONG_DAYS = 14


def load(path):
    try:
        df = READ(path, columns=["Datetime", "RTD", "State", "main_fault"])
    except Exception:
        df = READ(path, columns=["Datetime", "RTD", "State"])
    return df.sort_values("Datetime").drop_duplicates("Datetime").reset_index(drop=True)


def phases(df):
    """ON and OFF phases inside steady blocks: start (s), duration (min), on, block."""
    t = df["Datetime"].values.astype("datetime64[s]").astype(np.int64)
    st = df["State"].values.astype(np.int64)
    valid = df["RTD"].values <= WARM_C
    blk = np.cumsum((np.diff(t, prepend=t[0]) > GAP_S) | (valid != np.r_[valid[0], valid[:-1]]))
    on, door = (st & ON_MASK) != 0, (st & DOOR_BIT) != 0
    t, blk, on, door = t[valid], blk[valid], on[valid], door[valid]
    if len(t) == 0:
        return pd.DataFrame(columns=["start", "dur", "on", "blk"])
    change = np.r_[True, (blk[1:] != blk[:-1]) | (on[1:] != on[:-1])]
    p = pd.DataFrame({"pid": np.cumsum(change) - 1, "t": t, "blk": blk, "on": on, "door": door})
    g = p.groupby("pid").agg(start=("t", "first"), blk=("blk", "first"), on=("on", "first"), door=("door", "max"))
    g["next_start"], g["next_blk"], g["prev_blk"] = g["start"].shift(-1), g["blk"].shift(-1), g["blk"].shift(1)
    g = g[(g["next_blk"] == g["blk"]) & (g["prev_blk"] == g["blk"])].copy()
    g["dur"] = (g["next_start"] - g["start"]) / 60.0
    bad = g["door"] | (g["door"].shift(1, fill_value=False) & (g["blk"] == g["blk"].shift(1)))
    g = g[~bad & (g["dur"] > 0)]
    return g[["start", "dur", "on", "blk"]].reset_index(drop=True)


def block_drift(on, dur, start):
    on_c, off_c = np.cumsum(on), np.cumsum(~on)
    on_d, off_d = dur[on], dur[~on]
    if len(on_d) < L or len(off_d) < L:
        return np.array([]), np.array([])
    base = on_d[:L].mean() / off_d[:L].mean()
    r_on = pd.Series(on_d).rolling(W, min_periods=2).mean().values
    r_off = pd.Series(off_d).rolling(W, min_periods=2).mean().values
    i = np.arange(int(np.argmax((on_c >= L) & (off_c >= L))) + 1, len(on))
    if len(i) == 0:
        return np.array([]), np.array([])
    return start[i] + dur[i] * 60, (r_on[on_c[i] - 1] / r_off[off_c[i] - 1]) / base


def drift_series(ph):
    out = [(block_drift(g["on"].values, g["dur"].values, g["start"].values.astype(float)), b)
           for b, g in ph.groupby("blk")]
    out = [(t, d, np.full(len(t), b)) for (t, d), b in out if len(t)]
    if not out:
        return np.array([]), np.array([]), np.array([])
    return tuple(np.concatenate(x) for x in zip(*out))


def episodes(t, d, blk, thr):
    """(start, end, max drift) of runs of P evaluations above thr in one block, merged when under 3 days apart."""
    f, runs, i, n = d > thr, [], 0, len(d)
    while i < n:
        if not f[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and f[j + 1] and blk[j + 1] == blk[i]:
            j += 1
        if j - i + 1 >= P:
            runs.append((t[i], t[j], float(d[i:j + 1].max())))
        i = j + 1
    merged = []
    for e in runs:
        if merged and e[0] - merged[-1][1] < 3 * DAY:
            merged[-1] = (merged[-1][0], e[1], max(merged[-1][2], e[2]))
        else:
            merged.append(e)
    return merged


def overlaps(eps, lo, hi):
    return any(a <= hi and b >= lo for a, b, _ in eps)


def is_cooling(label):
    s = str(label).lower()
    return "compressor" in s or "refrigerant" in s


def quiet_events(ev, lo, hi):
    e = ev[(ev["Datetime"] >= pd.Timestamp(lo, unit="s")) & (ev["Datetime"] <= pd.Timestamp(hi, unit="s"))]
    e = e[~e["Event"].astype(str).str.startswith("Door")]
    return [f"  - {r.Datetime:%Y-%m-%d %H:%M} {str(r.Event)[:70]}" for r in e.itertuples()][:20] or ["  - nothing logged"]


def analyse(path):
    fid = path.name.split("_")[0]
    df = load(path)
    faults = []
    if "main_fault" in df.columns:
        g = df[df["main_fault"].notna()]
        faults = [(pd.Timestamp(a).timestamp(), str(b)) for a, b in zip(g["Datetime"], g["main_fault"])]
    ph = phases(df)
    t, d, blk = drift_series(ph)
    res = {"id": fid, "t": t, "d": d, "faults": faults, "n_read": len(df),
           "first": df["Datetime"].min(), "last": df["Datetime"].max(), "steady_days": ph["dur"].sum() / 1440}
    zones = [(f0 - BEFORE * DAY, f0 + AFTER * DAY) for f0, _ in faults]
    in_zone = np.zeros(len(t), bool)
    for lo, hi in zones:
        in_zone |= (t >= lo) & (t < hi)
    res["healthy_days"] = res["steady_days"] * (~in_zone).mean() if len(t) else 0.0
    res["eps"] = {thr: episodes(t, d, blk, thr) for thr in THRESHOLDS + [CRIT]}
    res["healthy_eps"] = {thr: sum(not any(lo <= e[0] < hi for lo, hi in zones) for e in res["eps"][thr])
                          for thr in res["eps"]}
    ev_path = path.with_name(f"{fid}_events.parquet")
    res["events"] = READ(ev_path) if ev_path.exists() else None
    return res


def fault_rows(results):
    rows = []
    for r in results:
        for f0, label in r["faults"]:
            m = (r["t"] >= f0 - BEFORE * DAY) & (r["t"] < f0)
            n = int(m.sum())
            row = {"id": r["id"], "date": pd.Timestamp(f0, unit="s").date(), "label": label,
                   "cooling": is_cooling(label), "evals": n, "ok": n >= MIN_EVALS,
                   "max": float(r["d"][m].max()) if n else float("nan")}
            for thr in THRESHOLDS + [CRIT]:
                row[("n", thr)] = overlaps(r["eps"][thr], f0 - NEAR * DAY, f0)
                row[("l", thr)] = overlaps(r["eps"][thr], f0 - BEFORE * DAY, f0)
            rows.append(row)
    return rows


def write_report(results):
    rows = fault_rows(results)
    md = ["# Drift rule on real ULT freezer records", "",
          "Rule: compressor on = either stage, 24 calibration phases, window 5, 6 evaluations in a row. "
          "Warning 1.8, Critical 3.5. Fault dates are service-report dates, not the start of the fault. "
          "These are -80 C biobank freezers, not vaccine fridges.", ""]
    md += ["## Freezers", "", "| Freezer | Readings | Period | Steady days | Healthy days | Labelled faults |", "|---|---|---|---|---|---|"]
    for r in results:
        md.append(f"| {r['id']} | {r['n_read']:,} | {r['first']:%Y-%m-%d} to {r['last']:%Y-%m-%d} | "
                  f"{r['steady_days']:.0f} | {r['healthy_days']:.0f} | {len(r['faults'])} |")
    hd = sum(r["healthy_days"] for r in results)
    md += ["", "## Summary", "",
           f"Healthy time pooled over all freezers: {hd:.0f} days.", "",
           "| Threshold | Healthy episodes per 30 days | Cooling faults with an alarm in the last 30 days | "
           "Cooling faults with an alarm in the last 90 days | Other faults, last 90 days |", "|---|---|---|---|---|"]
    cool = [x for x in rows if x["cooling"] and x["ok"]]
    other = [x for x in rows if not x["cooling"] and x["ok"]]
    for thr in THRESHOLDS + [CRIT]:
        eps = sum(r["healthy_eps"][thr] for r in results)
        md.append(f"| {thr}{' (Critical)' if thr == CRIT else ''} | {eps / hd * 30 if hd else 0:.2f} ({eps} episodes) | "
                  f"{sum(x[('n', thr)] for x in cool)} of {len(cool)} | {sum(x[('l', thr)] for x in cool)} of {len(cool)} | "
                  f"{sum(x[('l', thr)] for x in other)} of {len(other)} |")
    skipped = [x for x in rows if not x["ok"]]
    md += ["", f"Faults with fewer than {MIN_EVALS} evaluations in the 90 days before the date are left out of the counts "
           f"({len(skipped)} of {len(rows)}).", "",
           "## Every labelled fault (threshold 1.8)", "",
           "| Freezer | Service date | Label | Kind | Evaluations (90 d) | Max drift | Warning last 30 d | Warning last 90 d | Critical last 90 d |",
           "|---|---|---|---|---|---|---|---|---|"]
    yn = lambda b: "yes" if b else "no"
    for x in rows:
        md.append(f"| {x['id']} | {x['date']} | {x['label'][:38]} | {'cooling' if x['cooling'] else 'other'} | "
                  f"{x['evals']} | {x['max']:.2f} | {yn(x[('n', WARN)]) if x['ok'] else 'no data'} | "
                  f"{yn(x[('l', WARN)]) if x['ok'] else 'no data'} | {yn(x[('l', CRIT)]) if x['ok'] else 'no data'} |")
    md += ["", "## Healthy false alarms per freezer (threshold 1.8)", "", "| Freezer | Healthy days | Warning episodes | Per 30 days | Critical episodes |", "|---|---|---|---|---|"]
    for r in results:
        n = r["healthy_eps"][WARN]
        md.append(f"| {r['id']} | {r['healthy_days']:.0f} | {n} | {n / r['healthy_days'] * 30 if r['healthy_days'] else 0:.2f} | {r['healthy_eps'][CRIT]} |")
    md += ["", f"## Long Warning episodes ({LONG_DAYS} days or more)", "",
           "Events logged in the 10 days before the start and after the end, door events left out.", ""]
    for r in results:
        for a, b, mx in r["eps"][WARN]:
            if b - a < LONG_DAYS * DAY:
                continue
            near = [str(lab)[:30] + f" ({pd.Timestamp(f, unit='s'):%Y-%m-%d})" for f, lab in r["faults"] if a - 120 * DAY <= f <= b + 30 * DAY]
            md.append(f"**{r['id']}: {pd.Timestamp(a, unit='s'):%Y-%m-%d} to {pd.Timestamp(b, unit='s'):%Y-%m-%d}** "
                      f"({(b - a) / DAY:.0f} days, max drift {mx:.1f}). Labelled fault nearby: {'; '.join(near) or 'none'}.")
            if r["events"] is None:
                md.append("  - no events file")
            else:
                md += ["  Before:"] + quiet_events(r["events"], a - 10 * DAY, a) + ["  After:"] + quiet_events(r["events"], b, b + 10 * DAY)
            md.append("")
    (HERE / "ult_report.md").write_text("\n".join(md), encoding="utf-8")


def picture(results):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed, skipping the picture")
        return
    fig, axes = plt.subplots(len(results), 1, figsize=(13, 2.3 * len(results)), squeeze=False)
    for ax, r in zip(axes[:, 0], results):
        ax.scatter(pd.to_datetime(r["t"], unit="s"), np.clip(r["d"], 0, 6), s=1, alpha=0.4)
        ax.axhline(WARN, color="orange", lw=1)
        ax.axhline(CRIT, color="red", lw=1)
        for f0, label in r["faults"]:
            ax.axvline(pd.Timestamp(f0, unit="s"), color="k" if is_cooling(label) else "grey", ls="--", lw=0.8)
        ax.set_ylim(0, 6)
        ax.set_ylabel(r["id"], fontsize=8)
    fig.suptitle("Drift (dashed lines: labelled faults, black = compressor or refrigerant)", fontsize=9)
    fig.tight_layout()
    fig.savefig(HERE / "ult_drift_all.png", dpi=100)
    plt.close(fig)


def main():
    files = sorted(DATA.glob("*_temp.parquet"))
    if not files:
        sys.exit(f"No *_temp.parquet files in {DATA}")
    results = []
    for f in files:
        print("reading", f.name, flush=True)
        results.append(analyse(f))
    write_report(results)
    picture(results)
    print("Saved ult_report.md and ult_drift_all.png")


if __name__ == "__main__":
    main()
