"""
Trains an Isolation Forest on the healthy REFIT window features and writes it as C arrays for the ESP32-S3.

It writes three files into Embedded/tests/if_board_test/:
  if_model.h       the 50 trees as constant arrays
  if_testdata.h    a few thousand feature vectors (healthy and injected-fault windows) and the scikit-learn
                   scores for them
  if_expected.txt  the same scores and alarm decisions as plain text

if_board_test.ino scores the same vectors on the chip and compares. That is a device test of the same
model, not an evaluation of detection quality (refit_detectors.py does that).

Run (after the REFIT files are in the data folder):  python make_if_model.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

import refit_replay as rr
import refit_detectors as dt

N_TEST_HEALTHY, N_TEST_FAULT = 2000, 1000
OUT = rr.HERE.parents[1] / "Embedded" / "tests" / "if_board_test"
EULER = 0.5772156649015329


def c_factor(n):
    n = np.asarray(n, float)
    return np.where(n <= 1, 0.0, np.where(n == 2, 1.0, 2.0 * (np.log(np.maximum(n - 1, 1)) + EULER) - 2.0 * (n - 1) / np.maximum(n, 1)))


def float32_floor(x):
    """Largest float32 not above x, so that a float32 value v satisfies v <= x exactly when v <= result."""
    f = np.float32(x)
    return f if float(f) <= x else np.nextafter(f, np.float32(-np.inf))


def export_trees(model):
    feat, thr, left, right, roots = [], [], [], [], []
    for est, fidx in zip(model.estimators_, model.estimators_features_):
        assert list(fidx) == list(range(len(fidx))), "feature subsets are not the identity"
        tr = est.tree_
        base = len(feat)
        roots.append(base)
        depth = np.zeros(tr.node_count, int)
        for n in range(tr.node_count):                       # parents come before children
            if tr.children_left[n] != -1:
                depth[tr.children_left[n]] = depth[tr.children_right[n]] = depth[n] + 1
        for n in range(tr.node_count):
            if tr.children_left[n] == -1:
                feat.append(-1)
                thr.append(np.float32(depth[n] + c_factor(tr.n_node_samples[n])))
                left.append(0); right.append(0)
            else:
                feat.append(int(tr.feature[n]))
                thr.append(float32_floor(tr.threshold[n]))
                left.append(base + int(tr.children_left[n]))
                right.append(base + int(tr.children_right[n]))
    return feat, thr, left, right, roots


def python_score(X, tree_arrays, c_max):
    feat, thr, left, right, roots = tree_arrays
    out = np.zeros(len(X))
    for k, x in enumerate(X.astype(np.float32)):
        total = 0.0
        for r in roots:
            n = r
            while feat[n] >= 0:
                n = left[n] if x[feat[n]] <= thr[n] else right[n]
            total += float(thr[n])
        out[k] = 2.0 ** (-(total / len(roots)) / c_max)
    return out                                               # anomaly score, higher = more abnormal


def arr(name, ctype, values, fmt):
    body = ",".join(fmt(v) for v in values)
    return f"const {ctype} {name}[{len(values)}] PROGMEM = {{{body}}};\n"


def main():
    OUT.mkdir(exist_ok=True)
    healthy, faulted = [], []
    from pathlib import Path as P
    for path, house, cols in rr.FILES:
        if not P(path).exists():
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
            c = dt.collect(runs)
            healthy += c["healthy"]
            for tt, X, onset in c["inj"][3.0]:
                faulted.append(X[tt >= onset + 7 * 86400])   # windows after the fault has fully ramped in
    Xh = np.vstack(healthy)[:, dt.COLS]
    Xf = np.vstack([f for f in faulted if len(f)])[:, dt.COLS]
    rng = np.random.default_rng(dt.SEED)
    train = Xh[rng.choice(len(Xh), min(len(Xh), 40000), replace=False)]
    model = IsolationForest(n_estimators=dt.N_TREES, max_samples=dt.MAX_SAMPLES, random_state=dt.SEED).fit(train)
    thr_alarm = float(np.quantile(-model.score_samples(train), 0.995))

    tree_arrays = export_trees(model)
    c_max = float(c_factor(model.max_samples_))
    test = np.vstack([Xh[rng.choice(len(Xh), N_TEST_HEALTHY, replace=False)],
                      Xf[rng.choice(len(Xf), N_TEST_FAULT, replace=len(Xf) < N_TEST_FAULT)]]).astype(np.float32)
    ref = -model.score_samples(test.astype(np.float32))
    mine = python_score(test, tree_arrays, c_max)
    print(f"export check in Python: max |sklearn - exported| = {np.abs(ref - mine).max():.2e}")
    assert np.abs(ref - mine).max() < 1e-6, "exported trees do not reproduce scikit-learn"

    feat, thr, left, right, roots = tree_arrays
    with open(OUT / "if_model.h", "w") as f:
        f.write("// Isolation Forest exported by make_if_model.py. Do not edit.\n#pragma once\n#ifdef ARDUINO\n#include <pgmspace.h>\n#else\n#define PROGMEM\n#endif\n")
        f.write(f"#define IF_TREES {len(roots)}\n#define IF_FEATURES {test.shape[1]}\n#define IF_NODES {len(feat)}\n")
        f.write(f"const double IF_C_MAX = {c_max!r};\nconst double IF_ALARM_THRESHOLD = {thr_alarm!r};\n")
        f.write(arr("IF_ROOT", "int16_t", roots, str))
        f.write(arr("IF_FEAT", "int8_t", feat, str))
        f.write(arr("IF_THR", "float", [float(v) for v in thr], lambda v: repr(float(np.float32(v))) + "f"))
        f.write(arr("IF_LEFT", "int16_t", left, str))
        f.write(arr("IF_RIGHT", "int16_t", right, str))
    with open(OUT / "if_testdata.h", "w") as f:
        f.write("// Test vectors exported by make_if_model.py. Do not edit.\n#pragma once\n#ifdef ARDUINO\n#include <pgmspace.h>\n#else\n#define PROGMEM\n#endif\n")
        f.write(f"#define IF_TEST_N {len(test)}\n#define IF_TEST_HEALTHY {N_TEST_HEALTHY}\n")
        f.write(arr("IF_TEST", "float", test.ravel(), lambda v: repr(float(v)) + "f"))
        f.write(arr("IF_EXPECT", "float", ref, lambda v: repr(float(np.float32(v))) + "f"))
    flags = ref > thr_alarm
    with open(OUT / "if_expected.txt", "w") as f:
        f.write(f"N={len(test)}\nALARMS={int(flags.sum())}\nHEALTHY_ALARMS={int(flags[:N_TEST_HEALTHY].sum())}\n")
        f.write(f"FAULT_ALARMS={int(flags[N_TEST_HEALTHY:].sum())}\nTHRESHOLD={thr_alarm!r}\n")
        f.write("SCORES\n" + "\n".join(repr(float(v)) for v in ref) + "\n")
    margin = np.abs(ref - thr_alarm).min()
    print(f"nodes {len(feat)}, trees {len(roots)}, alarm threshold {thr_alarm:.4f}, closest score to threshold {margin:.2e}")
    print(f"test vectors: {N_TEST_HEALTHY} healthy windows ({int(flags[:N_TEST_HEALTHY].sum())} above threshold), "
          f"{N_TEST_FAULT} windows from a 3x injected fault ({int(flags[N_TEST_HEALTHY:].sum())} above threshold)")
    print("written to", OUT)


if __name__ == "__main__":
    main()
