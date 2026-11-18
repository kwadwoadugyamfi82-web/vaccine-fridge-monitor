"""
Compares three detectors on the REFIT traces, leave-one-house-out: the ratio rule in the firmware, an EWMA
version of it, and an Isolation Forest on window features.

  ratio    smoothed ON/OFF ratio over the last 5 phases of each kind, relative to the baseline (the firmware rule)
  ewma     exponentially weighted log durations (weight 0.1), the same ratio idea with a longer memory
  iforest  Isolation Forest on five window features: log ON change, log OFF change, log drift, and the
           coefficient of variation of the ON and OFF durations in the window

All three use 24 calibration phases, persistence 6 and the same injected faults as refit_sweep.py. For a fair
comparison each detector gets one alarm threshold, chosen on the two training houses so that the healthy
false-alarm rate there is at or below a target (2 or 5 episodes per 30 days). The held-out house then shows
healthy false alarms per 30 days and how often and how fast a 3x and a 5x fault is found. The forest is fitted
on the training houses only; its training-house scores are in-sample, so its threshold choice is slightly
optimistic, while the held-out numbers are not.

Run:  python refit_detectors.py   Results are saved to ../results/refit_detectors_results.md.
"""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

import refit_replay as rr
import refit_sweep as sw

L, W, P = 24, 5, 6
EWMA_ALPHA = 0.1
TARGETS = [2.0, 5.0]                      # false-alarm targets, episodes per 30 days
MS = [3.0, 5.0]                           # injected fault sizes (final ON/OFF ratio multiplier)
N_TREES, MAX_SAMPLES, SEED = 50, 128, 42
RATIO_GRID = np.round(np.arange(1.10, 4.01, 0.05), 2)


def features(on, dur):
    """Per-phase features after calibration. Returns (index of phase, feature matrix) or (None, None)."""
    on_c, off_c = np.cumsum(on), np.cumsum(~on)
    on_d, off_d = dur[on], dur[~on]
    if len(on_d) < L or len(off_d) < L:
        return None, None
    b_on, b_off = on_d[:L].mean(), off_d[:L].mean()
    s_on, s_off = pd.Series(on_d).rolling(W, min_periods=2), pd.Series(off_d).rolling(W, min_periods=2)
    m_on, m_off = s_on.mean().values, s_off.mean().values
    cv_on, cv_off = (s_on.std().values / m_on), (s_off.std().values / m_off)
    e_on = pd.Series(np.log(on_d / b_on)).ewm(alpha=EWMA_ALPHA, adjust=False).mean().values
    e_off = pd.Series(np.log(off_d / b_off)).ewm(alpha=EWMA_ALPHA, adjust=False).mean().values
    ical = int(np.argmax((on_c >= L) & (off_c >= L)))
    i = np.arange(ical + 1, len(on))
    if len(i) == 0:
        return None, None
    a, b = on_c[i] - 1, off_c[i] - 1
    lo, lf = np.log(m_on[a] / b_on), np.log(m_off[b] / b_off)
    X = np.column_stack([lo, lf, lo - lf, cv_on[a], cv_off[b], e_on[a] - e_off[b]])
    return i, X


COLS = slice(0, 5)            # features the Isolation Forest sees (the EWMA column is not one of them)


def score(det, X, model):
    if det == "ratio":
        return np.exp(X[:, 2])
    if det == "ewma":
        return np.exp(X[:, 5])
    return -model.score_samples(X[:, COLS])


def collect(runs):
    """Feature matrices for healthy blocks and for the injected-fault slices of one appliance."""
    days = max(runs.dur.sum() / 86400, 1)
    healthy = []
    for _, g in runs.groupby("block"):
        i, X = features(g.on.values, g.dur.values)
        if i is not None:
            healthy.append(X)
    inj = {M: [] for M in MS}
    for s0, g in sw.get_slices(runs):
        onset = s0 + rr.ONSET_DAY * 86400
        for M in MS:
            m = 1 + (M - 1) * np.clip((g.start.values - onset) / (rr.RAMP_DAYS * 86400), 0, 1)
            dur = np.where(g.on.values, g.dur.values * np.sqrt(m), g.dur.values / np.sqrt(m))
            i, X = features(g.on.values, dur)
            if i is not None:
                t = g.start.values[i] + dur[i]
                inj[M].append((t, X, onset))
    return dict(days=days, healthy=healthy, inj=inj)


def healthy_rate(c, det, model, thr):
    n = 0
    for X in c["healthy"]:
        flag = sw.persistent(score(det, X, model) > thr, P)
        n += sw.rising(flag)
    return n / c["days"] * 30


def detect(c, det, model, thr, M):
    delays = []
    for t, X, onset in c["inj"][M]:
        fl = sw.persistent(score(det, X, model) > thr, P) & (t >= onset)
        delays.append((t[fl][0] - onset) / 86400 if fl.any() else None)
    return sw.det_stats(delays)


def thresholds(det, model, train):
    if det != "iforest":
        return RATIO_GRID
    s = np.concatenate([score(det, X, model) for a in train for X in a["healthy"]])
    q = 1 - np.logspace(-4, -0.3, 70)
    return np.unique(np.quantile(s, q))


def pick(det, model, train, target):
    """Lowest threshold whose mean healthy false-alarm rate on the training appliances is within the target."""
    grid = thresholds(det, model, train)
    for thr in grid:
        if np.mean([healthy_rate(a, det, model, thr) for a in train]) <= target:
            return thr
    return grid[-1]


def fmt(rate, d3, d5):
    return (f"{rate:.1f} | {d3[0] * 100:.0f}% ({d3[1]:.1f} d) | {d5[0] * 100:.0f}% ({d5[1]:.1f} d)")


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
            data[f"{house}, {col}"] = (house, collect(runs))
    houses = sorted({v[0] for v in data.values()})
    if len(houses) < 2:
        print("Need at least two houses.")
        return

    out = ["# Detector comparison on REFIT traces (leave-one-house-out)", "",
           f"Calibration {L} phases of each kind, persistence {P}, injected faults as in refit_sweep.py. "
           "Each detector has one alarm threshold, chosen on the two training houses to meet a false-alarm target, "
           "then applied unchanged to the held-out house.", ""]
    totals = {}
    for target in TARGETS:
        out += [f"## Target: at most {target:g} false-alarm episodes per 30 days on the training houses", "",
                "| Held-out appliance | Detector | Healthy episodes per 30 d | 3x fault found (median delay) | 5x fault found (median delay) |",
                "|---|---|---|---|---|"]
        for held in houses:
            train = [v[1] for a, v in data.items() if v[0] != held]
            test = {a: v[1] for a, v in data.items() if v[0] == held}
            X_train = np.vstack([X for c in train for X in c["healthy"]])
            rng = np.random.default_rng(SEED)
            sub = X_train[rng.choice(len(X_train), min(len(X_train), 40000), replace=False)]
            model = IsolationForest(n_estimators=N_TREES, max_samples=MAX_SAMPLES, random_state=SEED).fit(sub[:, COLS])
            for det in ["ratio", "ewma", "iforest"]:
                thr = pick(det, model, train, target)
                for a, c in test.items():
                    r = healthy_rate(c, det, model, thr)
                    d3, d5 = detect(c, det, model, thr, 3.0), detect(c, det, model, thr, 5.0)
                    out.append(f"| {a} | {det} (threshold {thr:.2f}) | {fmt(r, d3, d5)} |")
                    totals.setdefault((target, det), []).append((r, d3[0], d3[1], d5[0]))
        out.append("")
    out += ["## Averages over the four held-out appliances", "",
            "| Target | Detector | Mean healthy episodes per 30 d | Mean 3x found | Mean 3x median delay (d) | Mean 5x found |",
            "|---|---|---|---|---|---|"]
    for (target, det), v in totals.items():
        v = np.array(v, float)
        out.append(f"| {target:g} | {det} | {v[:, 0].mean():.1f} | {v[:, 1].mean() * 100:.0f}% | {np.nanmean(v[:, 2]):.1f} | {v[:, 3].mean() * 100:.0f}% |")
    text = "\n".join(out)
    rr.RESULTS.mkdir(exist_ok=True)
    path = rr.RESULTS / "refit_detectors_results.md"
    path.write_text(text, encoding="utf-8")
    print("\n" + "=" * 70 + "\nFULL RESULTS (also saved to " + str(path) + ")\n" + "=" * 70 + "\n" + text)


if __name__ == "__main__":
    main()
