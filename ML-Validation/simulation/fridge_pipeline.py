"""
Simulated fridge (30 days, wear from day 20) with an Isolation Forest on hourly features.

Held out: the model is fitted on the earliest 60% of healthy hours and scored on the later healthy hours and
on the degrading hours. This is simulation only, not fridge data.

Run:  python fridge_pipeline.py
Outputs: fridge_anomaly_trend.png and fridge_hourly_features.csv, in the current folder.
"""
import random
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
import matplotlib.pyplot as plt

# ---- Part 1: simulate the fridge (healthy, then degrading) ----

SAFE_MIN = 2.0
SAFE_MAX = 8.0
COOLING_RATE = 0.1
WARMING_RATE = 0.05
DOOR_EVENTS_PER_DAY = 5
MAX_DOOR_OPEN_MINUTES = 5
SIMULATION_DAYS = 30
DEGRADATION_START_DAY = 20
MAX_WEAR_EFFECT = 0.6

START_TIME = pd.Timestamp("2026-01-01 00:00:00")


def simulate():
    """Run the 30-day fridge simulation and return one row per minute."""
    random.seed(42)

    temperature = 4.0
    compressor = False
    door_open = False
    door_open_minutes = 0

    rows = []
    total_minutes = SIMULATION_DAYS * 24 * 60

    for minute in range(total_minutes):
        current_day = minute // (24 * 60)

        if current_day < DEGRADATION_START_DAY:
            wear = 0.0
        else:
            wear = (current_day - DEGRADATION_START_DAY) / (SIMULATION_DAYS - DEGRADATION_START_DAY)
            wear = min(wear, 1.0)

        effective_cooling_rate = COOLING_RATE * (1 - MAX_WEAR_EFFECT * wear)
        effective_warming_rate = WARMING_RATE * (1 + MAX_WEAR_EFFECT * wear)

        if not door_open and random.random() < (DOOR_EVENTS_PER_DAY / (24 * 60)):
            door_open = True
            door_open_minutes = 0

        if door_open:
            temperature += 0.8
            door_open_minutes += 1
            if random.random() < 0.25 or door_open_minutes >= MAX_DOOR_OPEN_MINUTES:
                door_open = False
        else:
            if temperature >= SAFE_MAX:
                compressor = True
            elif temperature <= SAFE_MIN:
                compressor = False

            if compressor:
                temperature -= effective_cooling_rate
            else:
                temperature += effective_warming_rate

        temperature += random.uniform(-0.05, 0.05)

        rows.append({
            "timestamp": START_TIME + pd.Timedelta(minutes=minute),
            "temperature": temperature,
            "compressor": compressor,
            "door_open": door_open,
            "wear": wear,
        })

    sim_df = pd.DataFrame(rows)
    return sim_df


def main():
    start_time = START_TIME
    sim_df = simulate()
    print("Simulation rows:", len(sim_df))
    sim_df["hour_block"] = sim_df["timestamp"].dt.floor("h")


    # ---- Part 2: per-hour features (true compressor state) ----

    def extract_hour_features(group):
        comp = group["compressor"].values
        temp = group["temperature"].values

        runs = []
        state = comp[0]
        run_length = 1
        for s in comp[1:]:
            if s == state:
                run_length += 1
            else:
                runs.append((state, run_length))
                state = s
                run_length = 1
        runs.append((state, run_length))

        on_times = [r[1] for r in runs if r[0] == True]
        off_times = [r[1] for r in runs if r[0] == False]

        return pd.Series({
            "avg_on_time": np.mean(on_times) if on_times else 0,
            "avg_off_time": np.mean(off_times) if off_times else 0,
            "std_temp": temp.std(),
            "peak": temp.max(),
            "low": temp.min(),
            "num_cycles": len(on_times),
        })

    hourly = sim_df.groupby("hour_block").apply(extract_hour_features, include_groups=False).reset_index()
    hourly = hourly.sort_values("hour_block").reset_index(drop=True)
    hourly["rolling_cycles_3h"] = hourly["num_cycles"].rolling(3, min_periods=1).mean()

    hourly["day_index"] = (hourly["hour_block"] - start_time).dt.days
    hourly["is_degrading_hour"] = hourly["day_index"] >= DEGRADATION_START_DAY

    print("Total hours:", len(hourly))
    print("Degrading hours:", hourly["is_degrading_hour"].sum())

    # ---- Part 3: train isolation forest, held-out evaluation ----
    # The model is trained on the earliest 60% of healthy hours only.
    # It is then scored on (a) the later, unseen healthy hours and (b) the degrading hours.
    # Scoring the training hours themselves would only reproduce the contamination
    # setting (5% or 15%) by construction, so that number is not reported as a false-alarm rate.
    from sklearn.metrics import roc_auc_score

    feature_columns = ["avg_on_time", "avg_off_time", "std_temp", "peak", "low", "num_cycles", "rolling_cycles_3h"]
    hourly["mean_wear"] = hourly["day_index"].map(
        lambda d: 0.0 if d < DEGRADATION_START_DAY else min((d - DEGRADATION_START_DAY) / (SIMULATION_DAYS - DEGRADATION_START_DAY), 1.0))

    healthy_hours = hourly[~hourly["is_degrading_hour"]].sort_values("hour_block")
    cut = int(len(healthy_hours) * 0.6)
    train = healthy_hours.iloc[:cut]
    heldout_healthy = healthy_hours.iloc[cut:]
    degrading = hourly[hourly["is_degrading_hour"]]
    clearly_degraded = hourly[hourly["mean_wear"] >= 0.3]   # excludes the first days, where wear is still tiny

    print("Train healthy hours:", len(train), "| held-out healthy:", len(heldout_healthy), "| degrading:", len(degrading))

    for name, contamination in [("Strict", 0.05), ("Sensitive", 0.15)]:
        m = IsolationForest(contamination=contamination, random_state=42)
        m.fit(train[feature_columns])
        for df in (hourly,):
            df["anomaly_score_" + name] = m.decision_function(df[feature_columns])
            df["predicted_" + name] = m.predict(df[feature_columns]) == -1
        ho = hourly.loc[heldout_healthy.index, "predicted_" + name]
        dg = hourly.loc[degrading.index, "predicted_" + name]
        cd = hourly.loc[clearly_degraded.index, "predicted_" + name]
        y = np.r_[np.zeros(len(heldout_healthy)), np.ones(len(degrading))]
        sc = -np.r_[hourly.loc[heldout_healthy.index, "anomaly_score_" + name], hourly.loc[degrading.index, "anomaly_score_" + name]]
        print(f"\n[{name}, contamination={contamination}]")
        print("Held-out healthy hours flagged:", int(ho.sum()), "/", len(ho))
        print("All degrading hours flagged:", int(dg.sum()), "/", len(dg))
        print("Clearly degraded hours (wear >= 0.3) flagged:", int(cd.sum()), "/", len(cd))
        print("ROC AUC (held-out healthy vs degrading):", round(roc_auc_score(y, sc), 3))

    hourly["anomaly_score"] = hourly["anomaly_score_Strict"]
    hourly["predicted_anomaly"] = hourly["predicted_Strict"]

    # ---- Part 4: trend chart ----

    fig, ax = plt.subplots(figsize=(12, 5))
    colors = hourly["is_degrading_hour"].map({True: "red", False: "steelblue"})
    ax.scatter(hourly["hour_block"], hourly["anomaly_score"], c=colors, s=8)
    ax.axvline(start_time + pd.Timedelta(days=DEGRADATION_START_DAY), color="black", linestyle="--", label="Wear begins (Day 20)")
    ax.axvline(train["hour_block"].iloc[-1], color="green", linestyle="--", label="End of training data")
    ax.axhline(0, color="gray", linestyle=":", label="Flag threshold (0)")
    ax.set_title("Anomaly Score Over Time (blue = healthy, red = degrading)")
    ax.set_ylabel("Anomaly score (lower = more abnormal)")
    ax.legend()
    plt.tight_layout()
    plt.savefig("fridge_anomaly_trend.png", dpi=110)
    plt.close()

    hourly.to_csv("fridge_hourly_features.csv", index=False)
    print("\nSaved fridge_anomaly_trend.png and fridge_hourly_features.csv")


if __name__ == "__main__":
    main()
