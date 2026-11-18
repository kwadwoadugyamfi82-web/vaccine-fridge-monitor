"""
Replays recorded fridge power traces from the REFIT dataset through the drift rule in the firmware.

It turns the compressor power of a fridge or fridge-freezer into ON and OFF phases (ON at 30 W or more, OFF
at 10 W or less) and applies the original rule: baseline from the first 3 ON and 3 OFF phases, a rolling
window of 5 phases, drift = (mean ON / mean OFF over the window) / baseline ratio, Warning above 1.8,
Critical above 3.5.

It reports how often the rule raises a Warning or Critical on healthy appliances, how that changes with
preprocessing choices (Issues rows kept or dropped, minimum phase length), and how long the rule takes to
notice an artificial fault (ON time grows, OFF time shrinks) injected into the real trace.

Limits: these are household fridges and freezers from UK homes, not vaccine fridges, so the test says
something about the rule on real compressor behaviour and nothing about temperature sensing or MQTT. The
injected fault tests the detector, not a real failure. REFIT does not mark door openings, so no cycles are
excluded for doors and the false-alarm counts are pessimistic next to the firmware.

Put the cleaned REFIT files (CLEAN_House2.csv, CLEAN_House15.csv, CLEAN_House20.csv) in the data folder next
to this script and run  python refit_replay.py
Results are printed and saved to ../results/refit_replay_results.md.
"""
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"                      # the REFIT csv files go here (not stored in the repo)
RESULTS = HERE.parent / "results"

FILES = [
    (str(DATA / "CLEAN_House2.csv"), "House 2", ["Appliance1"]),                   # fridge-freezer
    (str(DATA / "CLEAN_House15.csv"), "House 15", ["Appliance1"]),                 # fridge-freezer
    (str(DATA / "CLEAN_House20.csv"), "House 20", ["Appliance1", "Appliance2"]),   # fridge, freezer
]

# ---- settings ------------------------------------------------------------------------------------
ON_W, OFF_W = 30.0, 10.0        # compressor ON at or above, OFF at or below (hysteresis)
GAP_S = 120                     # a timestamp jump above this is a data gap; cycles never cross a gap
MIN_RUN_S = 120                 # phases shorter than this are treated as noise and merged into their neighbours
MIN_RUN_ALT_S = 300             # used only in the sensitivity table
MAX_RUN_S = 6 * 3600            # phases longer than this are treated as unplugged or a dead sensor
DEFROST_FACTOR = 2.0            # ON phases with mean power above this x the median ON power are defrost, dropped
RECAL_GAP_S = 3600              # after a break longer than this, the device is assumed to reboot and recalibrate
DROP_ISSUE_CYCLES = False       # True drops phases containing Issues == 1 rows. Off by default: see README note
PERIOD_DAYS = 30                # third calibration mode: recalibrate every 30 days as well as after outages
WINDOW, CALIBRATION = 5, 3
WARNING, CRITICAL = 1.8, 3.5
INJECT_RATIOS = [1.0, 1.5, 2.0, 3.0, 4.0, 5.0]   # final ON/OFF ratio multiplier; 1.0 is the no-fault control
SLICE_DAYS, MAX_SLICES = 30, 6  # injection test: 30-day slices, calibrated at the start of each slice
ONSET_DAY, RAMP_DAYS = 15, 7


def extract_runs(t, p, issue, min_run_s):
    """Run-length encode ON/OFF state. Returns one row per complete phase."""
    dt = np.diff(t)
    brk = np.r_[False, dt > GAP_S]
    seg = np.cumsum(brk)
    seg_start = np.flatnonzero(np.r_[True, dt > GAP_S])[seg]       # first row index of each row's segment

    raw = np.where(p >= ON_W, 1, np.where(p <= OFF_W, 0, -1)).astype(np.int8)
    idx = np.where(raw != -1, np.arange(len(raw)), 0)
    idx = np.maximum.accumulate(idx)
    state = raw[idx]
    state[idx < seg_start] = -1                                    # never carry a state across a gap

    def runs_of(state):
        key = seg.astype(np.int64) * 4 + (state + 1)
        cut = np.flatnonzero(np.diff(key) != 0) + 1
        return np.r_[0, cut], np.r_[cut, len(key)]

    # Merge short interior phases into their neighbours (a 1-2 minute dip inside an ON phase is not a new cycle)
    merged = 0
    for _ in range(8):
        a, b = runs_of(state)
        st, sg = state[a], seg[a]
        d = t[np.minimum(b, len(t) - 1)] - t[a]
        interior = np.zeros(len(a), bool)
        interior[1:-1] = (sg[:-2] == sg[1:-1]) & (sg[2:] == sg[1:-1]) & (st[:-2] >= 0) & (st[2:] >= 0)
        short = (st >= 0) & interior & (d < min_run_s)
        short &= ~np.r_[False, short[:-1]]                         # never flip two neighbours at once
        if not short.any():
            break
        for ai, bi in zip(a[short], b[short]):
            state[ai:bi] = 1 - state[ai]
        merged += int(short.sum())

    a, b = runs_of(state)
    st, sg = state[a], seg[a]
    n = len(a)
    nxt_same_seg = np.zeros(n, bool)
    nxt_same_seg[:-1] = sg[1:] == sg[:-1]
    prv_ok = np.zeros(n, bool)
    prv_ok[1:] = (sg[1:] == sg[:-1]) & (st[:-1] >= 0)
    complete = (st >= 0) & nxt_same_seg & prv_ok

    t_end = np.where(b < len(t), t[np.minimum(b, len(t) - 1)], np.nan)
    dur = t_end - t[a]
    csum = np.r_[0.0, np.cumsum(p, dtype=np.float64)]
    meanp = (csum[b] - csum[a]) / (b - a)
    isum = np.r_[0, np.cumsum(issue.astype(np.int64))]
    has_issue = (isum[b] - isum[a]) > 0
    outage_block = np.r_[0, np.cumsum(dt > RECAL_GAP_S)][a]        # real outages only, not dropped phases

    df = pd.DataFrame({"on": st == 1, "start": t[a].astype(float), "dur": dur, "meanp": meanp,
                       "issue": has_issue, "block": outage_block})[complete].reset_index(drop=True)
    df.attrs["merged"] = merged
    return df


def filter_runs(df, drop_issues, min_run_s):
    """Drop unusable phases; return the kept ones and a count per reason."""
    why = {"short dips merged into neighbours": df.attrs.get("merged", 0)}
    keep = np.ones(len(df), bool)
    for name, bad in [
        ("too short (< %d s)" % min_run_s, df.dur < min_run_s),
        ("too long (> %d h)" % (MAX_RUN_S // 3600), df.dur > MAX_RUN_S),
        ("sub-meters above aggregate (Issues = 1)", df.issue.values if drop_issues else np.zeros(len(df), bool)),
    ]:
        hit = keep & np.asarray(bad)
        why[name] = int(hit.sum())
        keep &= ~hit
    med_on = df.loc[keep & df.on.values, "meanp"].median()
    bad = df.on.values & (df.meanp.values > DEFROST_FACTOR * med_on)
    hit = keep & bad
    why["ON phase above %.0fx median power (defrost)" % DEFROST_FACTOR] = int(hit.sum())
    keep &= ~bad
    out = df[keep].reset_index(drop=True)
    first = out.groupby("block").start.transform("min")
    out["period"] = out.block * 100000 + ((out.start - first) // (PERIOD_DAYS * 86400)).astype(int)
    return out, why, med_on


def drift_series(runs, group=None):
    """Firmware rule applied to the phase sequence. group = column that triggers recalibration (None = never)."""
    out = []
    groups = [g for _, g in runs.groupby(group, sort=True)] if group else [runs]
    for g in groups:
        on_h, off_h, base = [], [], None
        for on, start, dur in zip(g.on.values, g.start.values, g.dur.values):
            (on_h if on else off_h).append(dur)
            if base is None:
                if len(on_h) >= CALIBRATION and len(off_h) >= CALIBRATION:
                    base = np.mean(on_h[:CALIBRATION]) / np.mean(off_h[:CALIBRATION])
                continue
            if len(on_h) >= 2 and len(off_h) >= 2:
                ratio = np.mean(on_h[-WINDOW:]) / np.mean(off_h[-WINDOW:])
                out.append((start + dur, ratio / base))
    return pd.DataFrame(out, columns=["t", "drift"])


def episodes(flag):
    f = np.asarray(flag, bool)
    return int((f & ~np.r_[False, f[:-1]]).sum())


MODES = [("Never recalibrated", None),
         ("Recalibrated after outages > 1 h", "block"),
         (f"Recalibrated after outages and every {PERIOD_DAYS} days", "period")]


def summary_row(label, d, days):
    if d.empty:
        return f"| {label} | 0 | - | - | - | - | - | - |"
    w = d.drift.values > WARNING
    c = d.drift.values > CRITICAL
    return (f"| {label} | {len(d)} | {np.median(d.drift):.2f} | {np.percentile(d.drift, 99):.2f} | {d.drift.max():.2f} | "
            f"{w.mean() * 100:.1f}% | {c.mean() * 100:.2f}% | {episodes(w) / days * 30:.1f} / {episodes(c) / days * 30:.1f} |")


def short_cell(d, days):
    if d.empty:
        return "-"
    w, c = d.drift.values > WARNING, d.drift.values > CRITICAL
    return f"{w.mean() * 100:.1f}% / {c.mean() * 100:.2f}% ({episodes(w) / days * 30:.1f} / {episodes(c) / days * 30:.1f})"


def injection(runs):
    """Inject a growing ON/OFF ratio into 30-day slices (calibrated at the slice start) and time the detection."""
    slices = []
    for _, g in runs.groupby("block"):
        g = g.reset_index(drop=True)
        t0 = g.start.iloc[0]
        t_last = g.start.iloc[-1] + g.dur.iloc[-1]
        k = 0
        while t0 + (k + 1) * SLICE_DAYS * 86400 <= t_last:
            s0, s1 = t0 + k * SLICE_DAYS * 86400, t0 + (k + 1) * SLICE_DAYS * 86400
            piece = g[(g.start >= s0) & (g.start < s1)].reset_index(drop=True)
            if len(piece) >= 150:
                slices.append((len(piece), s0, piece))
            k += 1
    if not slices:
        return None, 0
    slices = sorted(slices, key=lambda x: -x[0])[:MAX_SLICES]
    res = {M: {"before": 0, "win": 0, "w": [], "c": []} for M in INJECT_RATIOS}
    for _, s0, g in slices:
        onset = s0 + ONSET_DAY * 86400
        ramp = RAMP_DAYS * 86400
        for M in INJECT_RATIOS:
            m = 1 + (M - 1) * np.clip((g.start.values - onset) / ramp, 0, 1)
            h = g.copy()
            h["dur"] = np.where(h.on.values, g.dur.values * np.sqrt(m), g.dur.values / np.sqrt(m))
            d = drift_series(h)
            before, after = d[d.t < onset], d[d.t >= onset]
            res[M]["before"] += int((before.drift > WARNING).sum())
            res[M]["win"] += len(before)
            fw, fc = after[after.drift > WARNING], after[after.drift > CRITICAL]
            res[M]["w"].append((fw.t.iloc[0] - onset) / 86400 if len(fw) else None)
            res[M]["c"].append((fc.t.iloc[0] - onset) / 86400 if len(fc) else None)
    return res, len(slices)


def delay_cell(vals):
    got = [v for v in vals if v is not None]
    if not got:
        return f"never (0/{len(vals)})"
    return f"{np.median(got):.1f} d median, range {min(got):.1f}-{max(got):.1f} ({len(got)}/{len(vals)})"


def main():
    lines = ["# REFIT replay results", "",
             f"Rule: ON >= {ON_W:.0f} W, OFF <= {OFF_W:.0f} W, baseline = first {CALIBRATION} ON + {CALIBRATION} OFF, "
             f"window {WINDOW}, Warning > {WARNING}, Critical > {CRITICAL}. Gaps > {GAP_S} s break cycles. "
             f"Main settings: Issues rows {'dropped' if DROP_ISSUE_CYCLES else 'kept'}, minimum phase {MIN_RUN_S} s.", ""]
    for path, house, cols in FILES:
        if not Path(path).exists():
            lines += [f"## {house}", f"File not found: {path}", ""]
            print(lines[-2:])
            continue
        print(f"reading {house} ...", flush=True)
        df = pd.read_csv(path, usecols=["Unix", "Issues"] + cols)
        t = df["Unix"].values.astype(np.int64)
        order = np.argsort(t, kind="stable")
        t = t[order]
        issue = df["Issues"].values[order] == 1
        for col in cols:
            p = df[col].values[order].astype(float)
            variants = {}
            for name, drop, mr in [("main", DROP_ISSUE_CYCLES, MIN_RUN_S),
                                   ("Issues rows dropped", True, MIN_RUN_S),
                                   (f"minimum phase {MIN_RUN_ALT_S} s", DROP_ISSUE_CYCLES, MIN_RUN_ALT_S)]:
                if name != "main" and drop == DROP_ISSUE_CYCLES and mr == MIN_RUN_S:
                    continue
                raw = extract_runs(t, p, issue, mr)
                variants[name] = filter_runs(raw, drop, mr) + (len(raw),)
            runs, why, med_on, n_all = variants["main"]
            lines += [f"## {house}, {col}", ""]
            if len(runs) < 20:
                lines += [f"Only {len(runs)} usable phases, skipped.", ""]
                continue
            days = max(runs.dur.sum() / 86400, 1)
            on, off = runs[runs.on], runs[~runs.on]
            blk = runs.groupby("block").agg(s=("start", "min"), e=("start", "max"))
            blk_days = (blk.e - blk.s) / 86400
            lines += [
                f"- Rows {len(df):,}; span {(t[-1] - t[0]) / 86400:.0f} days; data gaps > {GAP_S} s: {int((np.diff(t) > GAP_S).sum())}; "
                f"outages > 1 h: {int((np.diff(t) > RECAL_GAP_S).sum())}",
                f"- Complete phases found {n_all:,}; kept {len(runs):,} ({int(runs.on.sum()):,} ON, {int((~runs.on).sum()):,} OFF) "
                f"covering {days:.0f} days",
                f"- Unbroken stretches between outages: {len(blk)}; longest {blk_days.max():.0f} days, median {blk_days.median():.1f} days",
                "- Handling: " + "; ".join(f"{k}: {v}" for k, v in why.items()),
                f"- ON phase: median {on.dur.median() / 60:.1f} min (5th-95th pct {np.percentile(on.dur, 5) / 60:.1f}-{np.percentile(on.dur, 95) / 60:.1f}), "
                f"median power {med_on:.0f} W (5th-95th pct {np.percentile(on.meanp, 5):.0f}-{np.percentile(on.meanp, 95):.0f})",
                f"- OFF phase: median {off.dur.median() / 60:.1f} min (5th-95th pct {np.percentile(off.dur, 5) / 60:.1f}-{np.percentile(off.dur, 95) / 60:.1f})",
                "", "False alarms on healthy data (episodes are per 30 days, Warning / Critical):", "",
                "| Calibration | Windows | Median drift | 99th pct | Max | Above 1.8 | Above 3.5 | Episodes per 30 d |",
                "|---|---|---|---|---|---|---|---|"]
            for label, grp in MODES:
                lines.append(summary_row(label, drift_series(runs, grp), days))
            lines += ["", "Sensitivity to preprocessing (share of windows above 1.8 / above 3.5, with episodes per 30 days in brackets):", "",
                      "| Variant | Phases kept | " + " | ".join(m[0] for m in MODES) + " |", "|---|---|" + "---|" * len(MODES)]
            for name, (r, _, _, _) in variants.items():
                dd = max(r.dur.sum() / 86400, 1)
                lines.append(f"| {name} | {len(r):,} | " + " | ".join(short_cell(drift_series(r, g), dd) for _, g in MODES) + " |")
            lines.append("")
            res, ns = injection(runs)
            if res is None:
                lines += ["Injection test skipped: no 30-day stretch with enough phases.", ""]
            else:
                lines += [f"Injected fault ({ns} slices of {SLICE_DAYS} days, calibrated at the start of each slice; fault starts on day {ONSET_DAY} "
                          f"and grows linearly over {RAMP_DAYS} days). Delay is measured from fault onset:", "",
                          "| Final ON/OFF ratio multiplier | Warnings before onset (windows) | Warning raised after | Critical raised after |",
                          "|---|---|---|---|"]
                for M in INJECT_RATIOS:
                    r = res[M]
                    lines.append(f"| {M:.1f}x | {r['before']} ({r['win']}) | {delay_cell(r['w'])} | {delay_cell(r['c'])} |")
                lines.append("")
            print("\n".join(lines[-30:]), flush=True)
    text = "\n".join(lines)
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / "refit_replay_results.md"
    out.write_text(text, encoding="utf-8")
    print("\n" + "=" * 70 + "\nFULL RESULTS (also saved to " + str(out) + ")\n" + "=" * 70 + "\n" + text)


if __name__ == "__main__":
    main()
