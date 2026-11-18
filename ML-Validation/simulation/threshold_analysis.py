"""
Checks the Warning 1.8x and Critical 3.5x thresholds against the simulated fridge, cycle by cycle.

It reuses the simulation in fridge_pipeline.py and works on single compressor cycles, as the firmware does:
drift = (mean ON time / mean OFF time over the last 5 cycles) / baseline ON/OFF ratio, in simulated minutes.
Cycles with a door-open minute are left out, which approximates the firmware ignoring the first cycle after
a door event. The baseline is shown two ways: the first 3 ON and 3 OFF cycles (what the firmware does) and
all healthy cycles (an idealised baseline).

Run:  python threshold_analysis.py
"""
import numpy as np
import pandas as pd

from fridge_pipeline import simulate, DEGRADATION_START_DAY, SIMULATION_DAYS

WINDOW = 5
CALIBRATION = 3
WARNING, CRITICAL = 1.8, 3.5


def completed_cycles(sim):
    state = sim["compressor"].values
    door = sim["door_open"].values
    runs, start = [], 0
    for i in range(1, len(state) + 1):
        if i == len(state) or state[i] != state[start]:
            runs.append((bool(state[start]), i - start, start, bool(door[start:i].any())))
            start = i
    # the first run starts at an unknown phase and the last is unfinished
    return pd.DataFrame(runs[1:-1], columns=["on", "minutes", "start", "door"])


def drift_series(cycles, baseline):
    """Rolling 5-cycle drift after each completed cycle, door cycles excluded."""
    on_hist, off_hist, out = [], [], []
    for row in cycles.itertuples():
        if row.door:
            continue
        (on_hist if row.on else off_hist).append(row.minutes)
        if len(on_hist) >= 2 and len(off_hist) >= 2:
            ratio = np.mean(on_hist[-WINDOW:]) / np.mean(off_hist[-WINDOW:])
            out.append((row.start / 1440.0, ratio / baseline))
    return pd.DataFrame(out, columns=["day", "drift"])


def summarise(drift, label):
    print(f"\n{label}")
    print("| Days | Windows | Mean drift | Max drift | Above 1.8 | Above 3.5 |")
    print("|---|---|---|---|---|---|")
    edges = [0, DEGRADATION_START_DAY, 23, 26, SIMULATION_DAYS]
    for lo, hi in zip(edges[:-1], edges[1:]):
        d = drift[(drift.day >= lo) & (drift.day < hi)]
        if d.empty:
            continue
        print(f"| {lo}-{hi} | {len(d)} | {d.drift.mean():.2f} | {d.drift.max():.2f} | "
              f"{(d.drift > WARNING).mean() * 100:.0f}% | {(d.drift > CRITICAL).mean() * 100:.0f}% |")


def noise_check(cycles, baseline):
    """How noisy are healthy cycles, and what do smoothing and door exclusion buy?"""
    healthy = cycles[cycles.start < DEGRADATION_START_DAY * 1440]
    on = healthy[healthy.on].minutes.values
    off = healthy[~healthy.on].minutes.values
    n = min(len(on), len(off))
    single = (on[:n] / off[:n]) / baseline
    with_doors = drift_series(healthy.assign(door=False), baseline).drift
    without_doors = drift_series(healthy, baseline).drift
    print("\nHealthy days only (drift against the idealised baseline)")
    print("| Method | Values | Max drift | Above 1.8 |")
    print("|---|---|---|---|")
    print(f"| One ON/OFF pair, door cycles kept | {n} | {single.max():.2f} | {(single > WARNING).mean() * 100:.0f}% |")
    print(f"| 5-cycle average, door cycles kept | {len(with_doors)} | {with_doors.max():.2f} | {(with_doors > WARNING).mean() * 100:.0f}% |")
    print(f"| 5-cycle average, door cycles left out | {len(without_doors)} | {without_doors.max():.2f} | {(without_doors > WARNING).mean() * 100:.0f}% |")


def main():
    sim = simulate()
    cycles = completed_cycles(sim)
    healthy = cycles[cycles.start < DEGRADATION_START_DAY * 1440]
    clean = healthy[~healthy.door]
    on_all = clean[clean.on].minutes.mean()
    off_all = clean[~clean.on].minutes.mean()
    print(f"Healthy cycles without door events: {int(clean.on.sum())} ON, {int((~clean.on).sum())} OFF")
    print(f"Mean ON {on_all:.1f} min, mean OFF {off_all:.1f} min, ON/OFF ratio {on_all / off_all:.2f}")

    ideal = on_all / off_all
    summarise(drift_series(cycles, ideal), f"Baseline = mean of all healthy cycles (ratio {ideal:.2f})")
    noise_check(cycles, ideal)

    first = cycles[~cycles.door]
    first_on = first[first.on].minutes.iloc[:CALIBRATION].mean()
    first_off = first[~first.on].minutes.iloc[:CALIBRATION].mean()
    fw = first_on / first_off
    summarise(drift_series(cycles, fw), f"Baseline = first {CALIBRATION} ON and OFF cycles, as in the firmware (ratio {fw:.2f})")

    late = cycles[cycles.start >= 27 * 1440]
    lo = late[late.on].minutes.mean() / late[~late.on].minutes.mean()
    print(f"\nLate-stage cycles (days 27-30): ON/OFF ratio {lo:.2f}, which is {lo / ideal:.2f}x the healthy ratio")


if __name__ == "__main__":
    main()
