"""
Leave-one-house-out sweep of calibration length, window and persistence on the REFIT traces.

The original rule (3 ON + 3 OFF calibration phases, a 5-phase window, alert on a single window) raises many
false alarms on real household fridges, as refit_replay.py shows. This asks whether a small change cuts that
without making real faults much slower to find. It tries 48 combinations of

  calibration length L   3, 6, 12 or 24 phases of each kind
  window size W          5 or 10 phases of each kind
  window statistic       mean or median
  persistence P          alert after 1, 3 or 6 windows in a row above the threshold

with the thresholds fixed at Warning 1.8 and Critical 3.5.

The selection rule was fixed before looking at any result. For each house in turn the best setting is chosen
on the other two houses and scored on the held-out one. House 20's fridge and freezer share a home and are
always held out together. A setting is eligible only if, on every training appliance, an injected 3x ON/OFF
fault reaches Critical in at least 80% of slices with a median delay of 7 days or less. Among the eligible
settings the lowest cost wins (Warning episodes + 3 x Critical episodes per 30 days of healthy running);
ties go to the smaller P, then W, then L.

Same limits as refit_replay.py: household fridges, injected faults, no door information, recorded traces.

Run after refit_replay.py's data files are in place:  python refit_sweep.py
Results are printed and saved to ../results/refit_sweep_results.md.
"""
import itertools
from pathlib import Path

import numpy as np
import pandas as pd

import refit_replay as rr

WARNING, CRITICAL = rr.WARNING, rr.CRITICAL
GRID = list(itertools.product([3, 6, 12, 24], [5, 10], ["mean", "median"], [1, 3, 6]))   # L, W, stat, P
FIRMWARE = (3, 5, "mean", 1)
MAX_DELAY_DAYS, MIN_DETECT_FRAC, COST_CRIT_WEIGHT = 7.0, 0.8, 3.0


def block_drift(on, dur, start, L, W, stat):
    """Drift after each phase once calibrated. Same rule as the firmware, with swept settings."""
    on_c, off_c = np.cumsum(on), np.cumsum(~on)
    on_d, off_d = dur[on], dur[~on]
    if len(on_d) < L or len(off_d) < L:
        return np.array([]), np.array([])
    f = np.mean if stat == "mean" else np.median
    base = f(on_d[:L]) / f(off_d[:L])
    s_on, s_off = pd.Series(on_d).rolling(W, min_periods=2), pd.Series(off_d).rolling(W, min_periods=2)
    r_on = (s_on.mean() if stat == "mean" else s_on.median()).values
    r_off = (s_off.mean() if stat == "mean" else s_off.median()).values
    ical = int(np.argmax((on_c >= L) & (off_c >= L)))
    i = np.arange(ical + 1, len(on))
    if len(i) == 0:
        return np.array([]), np.array([])
    drift = (r_on[on_c[i] - 1] / r_off[off_c[i] - 1]) / base
    return start[i] + dur[i], drift


def persistent(flag, P):
    if P == 1 or len(flag) == 0:
        return flag
    return pd.Series(flag.astype(int)).rolling(P).sum().values == P


def rising(flag):
    f = np.asarray(flag, bool)
    return int((f & ~np.r_[False, f[:-1]]).sum())


def healthy_metrics(runs, cfg):
    L, W, stat, P = cfg
    days = max(runs.dur.sum() / 86400, 1)
    w = c = 0
    for _, g in runs.groupby("block"):
        t, d = block_drift(g.on.values, g.dur.values, g.start.values, L, W, stat)
        if len(d):
            w += rising(persistent(d > WARNING, P))
            c += rising(persistent(d > CRITICAL, P))
    return w / days * 30, c / days * 30


def get_slices(runs):
    out = []
    for _, g in runs.groupby("block"):
        g = g.reset_index(drop=True)
        t0, t_last = g.start.iloc[0], g.start.iloc[-1] + g.dur.iloc[-1]
        k = 0
        while t0 + (k + 1) * rr.SLICE_DAYS * 86400 <= t_last:
            s0, s1 = t0 + k * rr.SLICE_DAYS * 86400, t0 + (k + 1) * rr.SLICE_DAYS * 86400
            piece = g[(g.start >= s0) & (g.start < s1)].reset_index(drop=True)
            if len(piece) >= 150:
                out.append((len(piece), s0, piece))
            k += 1
    return [(s0, g) for _, s0, g in sorted(out, key=lambda x: -x[0])[:rr.MAX_SLICES]]


def detection(slices, cfg, M):
    """Return (Warning delays, Critical delays) in days, None where never raised."""
    L, W, stat, P = cfg
    dw, dc = [], []
    for s0, g in slices:
        onset = s0 + rr.ONSET_DAY * 86400
        m = 1 + (M - 1) * np.clip((g.start.values - onset) / (rr.RAMP_DAYS * 86400), 0, 1)
        dur = np.where(g.on.values, g.dur.values * np.sqrt(m), g.dur.values / np.sqrt(m))
        t, d = block_drift(g.on.values, dur, g.start.values, L, W, stat)
        late = t >= onset
        for thr, store in ((WARNING, dw), (CRITICAL, dc)):
            fl = persistent(d > thr, P) & late if len(d) else np.array([], bool)
            store.append((t[fl][0] - onset) / 86400 if fl.any() else None)
    return dw, dc


def det_stats(vals):
    got = [v for v in vals if v is not None]
    return (len(got) / len(vals) if vals else 0.0), (float(np.median(got)) if got else float("nan"))


def evaluate(runs, cfg, slices):
    w, c = healthy_metrics(runs, cfg)
    w3, c3 = detection(slices, cfg, 3.0)
    w5, c5 = detection(slices, cfg, 5.0)
    return dict(warn=w, crit=c, cost=w + COST_CRIT_WEIGHT * c,
                c3=det_stats(c3), w3=det_stats(w3), c5=det_stats(c5), n=len(slices))


def eligible(m):
    frac, med = m["c3"]
    return frac >= MIN_DETECT_FRAC and med <= MAX_DELAY_DAYS


def name(cfg):
    L, W, stat, P = cfg
    return f"L={L}, W={W}, {stat}, P={P}" + ("  (firmware)" if cfg == FIRMWARE else "")


def cell(m):
    return (f"{m['warn']:.1f} / {m['crit']:.1f} | {m['w3'][0] * 100:.0f}% {m['w3'][1]:.1f} d | "
            f"{m['c3'][0] * 100:.0f}% {m['c3'][1]:.1f} d | {m['c5'][0] * 100:.0f}% {m['c5'][1]:.1f} d")


HEAD = ("| Setting | Healthy Warning / Critical episodes per 30 d | 3x fault: Warning found, median delay | "
        "3x fault: Critical found, median delay | 5x fault: Critical found, median delay |\n|---|---|---|---|---|")


def row(label, m):
    parts = cell(m).split(" | ")
    return f"| {label} | " + " | ".join(parts) + " |"


def main():
    data = {}      # appliance label -> (house, runs, runs_noissues)
    for path, house, cols in rr.FILES:
        if not Path(path).exists():
            print("File not found:", path)
            continue
        print(f"reading {house} ...", flush=True)
        df = pd.read_csv(path, usecols=["Unix", "Issues"] + cols)
        t = df["Unix"].values.astype(np.int64)
        order = np.argsort(t, kind="stable")
        t = t[order]
        issue = df["Issues"].values[order] == 1
        for col in cols:
            p = df[col].values[order].astype(float)
            raw = rr.extract_runs(t, p, issue, rr.MIN_RUN_S)
            runs, _, _ = rr.filter_runs(raw, False, rr.MIN_RUN_S)
            runs2, _, _ = rr.filter_runs(raw, True, rr.MIN_RUN_S)
            data[f"{house}, {col}"] = (house, runs, runs2)
    if len(data) < 3:
        print("Need at least two houses to cross-validate.")
        return

    print("sweeping ...", flush=True)
    grid = {}
    slices = {a: get_slices(v[1]) for a, v in data.items()}
    for a, (house, runs, _) in data.items():
        for cfg in GRID:
            grid[(a, cfg)] = evaluate(runs, cfg, slices[a])
        print("  done", a, flush=True)

    houses = sorted({v[0] for v in data.values()})
    lines = ["# REFIT sweep results (leave-one-house-out)", "",
             f"Thresholds fixed at Warning {WARNING}, Critical {CRITICAL}. Injected fault: {rr.SLICE_DAYS}-day slices, calibrated at the "
             f"start of each slice, fault starts on day {rr.ONSET_DAY} and ramps over {rr.RAMP_DAYS} days. "
             f"Eligible = Critical found for a 3x fault in at least {MIN_DETECT_FRAC * 100:.0f}% of slices with median delay at most {MAX_DELAY_DAYS:.0f} days "
             f"on every training appliance. Cost = Warning + {COST_CRIT_WEIGHT:.0f} x Critical episodes per 30 days.", ""]

    # The firmware setting on every appliance, for reference
    lines += ["## Firmware setting on each appliance", "", HEAD]
    for a in data:
        lines.append(row(a, grid[(a, FIRMWARE)]))
    lines.append("")

    chosen = {}
    for held in houses:
        train = [a for a, v in data.items() if v[0] != held]
        test = [a for a, v in data.items() if v[0] == held]
        ok = []
        for cfg in GRID:
            if all(eligible(grid[(a, cfg)]) for a in train):
                cost = sum(grid[(a, cfg)]["cost"] for a in train)
                ok.append((cost, cfg[3], cfg[1], cfg[0], cfg))
        ok.sort()
        lines += [f"## Held-out house: {held}", "", f"Training appliances: {', '.join(train)}", ""]
        if not ok:
            lines += ["No setting met the detection requirement on every training appliance.", ""]
            continue
        best = ok[0][-1]
        chosen[held] = best
        fw_cost = sum(grid[(a, FIRMWARE)]["cost"] for a in train)
        lines += [f"Chosen on the training houses: **{name(best)}** (training cost {ok[0][0]:.1f}; firmware setting {fw_cost:.1f}). "
                  f"{len(ok)} of {len(GRID)} settings were eligible.", "",
                  f"Scored on the held-out {held}:", "", HEAD]
        for a in test:
            lines.append(row(f"{a} - firmware", grid[(a, FIRMWARE)]))
            lines.append(row(f"{a} - chosen", grid[(a, best)]))
        lines.append("")

    # Setting chosen with all houses, for the write-up, plus the Issues-dropped robustness check
    ok = []
    for cfg in GRID:
        if all(eligible(grid[(a, cfg)]) for a in data):
            ok.append((sum(grid[(a, cfg)]["cost"] for a in data), cfg[3], cfg[1], cfg[0], cfg))
    ok.sort()
    lines += ["## All houses together (descriptive only, not a test)", ""]
    if not ok:
        lines += ["No setting met the detection requirement on every appliance.", ""]
    else:
        lines += [f"Top five eligible settings by total cost ({len(ok)} eligible of {len(GRID)}):", "", "| Setting | Total cost | Firmware total cost |", "|---|---|---|"]
        fw_total = sum(grid[(a, FIRMWARE)]["cost"] for a in data)
        for cost, _, _, _, cfg in ok[:5]:
            lines.append(f"| {name(cfg)} | {cost:.1f} | {fw_total:.1f} |")
        lines.append("")
        best = ok[0][-1]
        lines += [f"Best setting with all houses: **{name(best)}**.", "",
                  "Same comparison with Issues-flagged phases dropped (robustness check):", "", HEAD]
        for a, (house, runs, runs2) in data.items():
            sl = get_slices(runs2)
            lines.append(row(f"{a} - firmware, Issues dropped", evaluate(runs2, FIRMWARE, sl)))
            lines.append(row(f"{a} - best, Issues dropped", evaluate(runs2, best, sl)))
        lines.append("")

    text = "\n".join(lines)
    rr.RESULTS.mkdir(exist_ok=True)
    out = rr.RESULTS / "refit_sweep_results.md"
    out.write_text(text, encoding="utf-8")
    print("\n" + "=" * 70 + "\nFULL RESULTS (also saved to " + str(out) + ")\n" + "=" * 70 + "\n" + text)


if __name__ == "__main__":
    main()
