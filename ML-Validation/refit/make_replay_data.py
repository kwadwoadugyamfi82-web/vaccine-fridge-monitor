"""
Builds the data for the on-board REFIT replay and the results the board has to reproduce.

It uses the same phase extraction as refit_replay.py (Issues rows kept, short dips merged, defrost phases and
phases over 6 hours dropped, outages over 1 hour mark a restart) and writes two files:

  Embedded/tests/refit_replay_board/replay_data.h   the phases as uint16 arrays for the board sketch
  ML-Validation/results/replay_expected.txt         what the board must print, for both rule settings

The expected results come from two separate Python implementations (a plain loop that mirrors the C++ and the
pandas version in refit_sweep.py), which must agree. check_replay_log.py compares a board log with the file.

Run (after the REFIT files are in the data folder):  python make_replay_data.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

import refit_replay as rr
import refit_sweep as sw

SETTINGS = [(3, 5, 1), (24, 5, 6)]          # (calibration phases, window, persistence): original, proposed
WARN, CRIT = rr.WARNING, rr.CRITICAL
BOARD_DIR = rr.HERE.parents[1] / "Embedded" / "tests" / "refit_replay_board"


def encode(runs):
    out, prev = [], None
    for on, dur, block in zip(runs.on.values, runs.dur.values, runs.block.values):
        if prev is not None and block != prev:
            out.append(0xFFFF)                           # outage: device restarts
        prev = block
        d = int(round(dur))
        assert abs(dur - d) < 1e-6 and 1 <= d < 0x8000, dur
        out.append((0x8000 if on else 0) | d)
    return out


def levels_plain(codes, cal, win, pers):
    """Plain-loop version mirroring fridge_logic.h."""
    levels = []
    def fresh():
        return dict(on=[], off=[], con=0, coff=0, son=0.0, soff=0.0, cal=False, wr=0, cr=0, bon=0.0, boff=0.0)
    s = fresh()
    for v in codes:
        if v == 0xFFFF:
            s = fresh()
            continue
        on, d = bool(v & 0x8000), float(v & 0x7FFF)
        buf = s["on"] if on else s["off"]
        buf.append(d)
        if len(buf) > win:
            buf.pop(0)
        if not s["cal"]:
            if on and s["con"] < cal:
                s["son"] += d; s["con"] += 1
            if (not on) and s["coff"] < cal:
                s["soff"] += d; s["coff"] += 1
            if s["con"] >= cal and s["coff"] >= cal:
                s["bon"], s["boff"] = s["son"] / cal, s["soff"] / cal
                s["cal"] = True
            continue
        if len(s["on"]) < 2 or len(s["off"]) < 2:
            continue
        mon = sum(s["on"]) / len(s["on"])
        moff = sum(s["off"]) / len(s["off"])
        drift = (mon / moff) / (s["bon"] / s["boff"])
        s["wr"] = s["wr"] + 1 if drift > WARN else 0
        s["cr"] = s["cr"] + 1 if drift > CRIT else 0
        levels.append(2 if s["cr"] >= pers else 1 if s["wr"] >= pers else 0)
    return np.array(levels, dtype=np.uint8)


def levels_pandas(runs, cal, win, pers):
    out = []
    for _, g in runs.groupby("block", sort=True):
        t, d = sw.block_drift(g.on.values, g.dur.values, g.start.values, cal, win, "mean")
        if len(d):
            wp, cp = sw.persistent(d > WARN, pers), sw.persistent(d > CRIT, pers)
            out.append(np.where(cp, 2, np.where(wp, 1, 0)).astype(np.uint8))
    return np.concatenate(out) if out else np.array([], np.uint8)


def result_line(name, cal, win, pers, lv):
    h = 2166136261
    for x in lv:
        h = ((h ^ int(x)) * 16777619) & 0xFFFFFFFF
    n = [int((lv == k).sum()) for k in (0, 1, 2)]
    return (f"RESULT|{name}|CAL={cal} WIN={win} P={pers}|evals={len(lv)}|lvl0={n[0]}|lvl1={n[1]}|lvl2={n[2]}|hash={h:08X}")


def main():
    series = []                      # (name, codes, runs)
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
            series.append((f"{house}, {col}", encode(runs), runs))
    if not series:
        return

    lines, ok = [], True
    for cal, win, pers in SETTINGS:
        for name, codes, runs in series:
            a = levels_plain(codes, cal, win, pers)
            b = levels_pandas(runs, cal, win, pers)
            same = len(a) == len(b) and bool((a == b).all())
            ok &= same
            print(f"  {name} CAL={cal} P={pers}: plain loop and pandas versions agree: {same}")
            lines.append(result_line(name, cal, win, pers, a))
    print("All Python implementations agree." if ok else "WARNING: the two Python implementations differ, do not use these results.")

    rr.RESULTS.mkdir(exist_ok=True)
    (rr.RESULTS / "replay_expected.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    parts = ["// Generated by make_replay_data.py from REFIT (cleaned), CC BY 4.0. Do not edit.", "#pragma once", "#include <stdint.h>",
             "struct Series { const char* name; const uint16_t* data; uint32_t n; };"]
    total = 0
    for k, (name, codes, _) in enumerate(series):
        parts.append(f"const uint16_t SERIES_{k}[] = {{" + ",".join(str(c) for c in codes) + "};")
        total += len(codes)
    parts.append("const Series SERIES[] = {" + ",".join(f'{{"{n}",SERIES_{k},{len(c)}}}' for k, (n, c, _) in enumerate(series)) + "};")
    parts.append(f"const int N_SERIES = {len(series)};")
    (BOARD_DIR / "replay_data.h").write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(f"\nWrote replay_data.h ({total:,} entries, about {total * 2 / 1024:.0f} KB of flash) and replay_expected.txt")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
