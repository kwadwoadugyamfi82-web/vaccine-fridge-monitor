import random
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest

# =====================================================
# PART 1: SIMULATE THE FRIDGE (healthy -> degrading)
# =====================================================

SAFE_MIN = 2.0
SAFE_MAX = 8.0

COOLING_RATE = 0.1
WARMING_RATE = 0.05

DOOR_EVENTS_PER_DAY = 5
MAX_DOOR_OPEN_MINUTES = 5

SIMULATION_DAYS = 30
DEGRADATION_START_DAY = 20
MAX_WEAR_EFFECT = 0.6

random.seed(42)

temperature = 4.0
compressor = False
door_open = False
door_open_minutes = 0

rows = []
total_minutes = SIMULATION_DAYS * 24 * 60
start_time = pd.Timestamp("2026-01-01 00:00:00")

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
        "timestamp": start_time + pd.Timedelta(minutes=minute),
        "temperature": temperature,
        "compressor": compressor,
        "door_open": door_open,
        "wear": wear,
    })

sim_df = pd.DataFrame(rows)
sim_df["hour_block"] = sim_df["timestamp"].dt.floor("h")
sim_df["day"] = sim_df["timestamp"].dt.floor("D")

print("Simulation rows:", len(sim_df))

# =====================================================
# PART 2: EXTRACT PER-HOUR FEATURES (using TRUE compressor state,
# since this is simulated data we control -- no hysteresis needed)
# =====================================================

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

# Label: is this hour on/after the degradation start day?
hourly["day_index"] = (hourly["hour_block"] - start_time).dt.days
hourly["is_degrading_hour"] = hourly["day_index"] >= DEGRADATION_START_DAY

print("Total hours:", len(hourly))
print("Degrading hours:", hourly["is_degrading_hour"].sum())

# =====================================================
# PART 3: TRAIN ISOLATION FOREST ON HEALTHY HOURS ONLY
# =====================================================

feature_columns = ["avg_on_time", "avg_off_time", "std_temp", "peak", "low", "num_cycles", "rolling_cycles_3h"]

healthy_hours = hourly[~hourly["is_degrading_hour"]]

model = IsolationForest(contamination=0.05, random_state=42)
model.fit(healthy_hours[feature_columns])

hourly["anomaly_score"] = model.decision_function(hourly[feature_columns])
hourly["predicted_anomaly"] = model.predict(hourly[feature_columns]) == -1

print("\nAverage anomaly score -- healthy hours:",
      round(hourly[~hourly['is_degrading_hour']]['anomaly_score'].mean(), 4))
print("Average anomaly score -- degrading hours:",
      round(hourly[hourly['is_degrading_hour']]['anomaly_score'].mean(), 4))

flagged = hourly[hourly['is_degrading_hour']]['predicted_anomaly'].sum()
total_degrading = hourly['is_degrading_hour'].sum()
print(f"Degrading hours correctly flagged: {flagged} out of {total_degrading}")

false_positives = hourly[~hourly['is_degrading_hour']]['predicted_anomaly'].sum()
total_healthy = (~hourly['is_degrading_hour']).sum()
print(f"Healthy hours incorrectly flagged: {false_positives} out of {total_healthy}")

# When did the FIRST correctly-flagged anomaly happen, relative to degradation start?
first_flag = hourly[hourly['is_degrading_hour'] & hourly['predicted_anomaly']].head(1)
if len(first_flag):
    print("\nFirst correctly flagged degrading hour:", first_flag['hour_block'].values[0])
    print("(Degradation physically started at day", DEGRADATION_START_DAY, ")")

hourly.to_csv("/home/claude/fridge_hourly_features.csv", index=False)
print("\nSaved fridge_hourly_features.csv")

# =====================================================
# PART 4: TREND CHART -- anomaly score over the whole simulation
# =====================================================

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(12, 5))
colors = hourly["is_degrading_hour"].map({True: "red", False: "steelblue"})
ax.scatter(hourly["hour_block"], hourly["anomaly_score"], c=colors, s=8)
ax.axvline(start_time + pd.Timedelta(days=DEGRADATION_START_DAY), color="black", linestyle="--",
           label="Wear begins (Day 20)")
ax.axhline(0, color="gray", linestyle=":", label="Flag threshold (0)")
ax.set_title("Anomaly Score Over Time (blue = healthy, red = degrading)")
ax.set_ylabel("Anomaly score (lower = more abnormal)")
ax.legend()
plt.tight_layout()
plt.savefig("/home/claude/fridge_anomaly_trend.png", dpi=110)
print("Saved fridge_anomaly_trend.png")

# =====================================================
# PART 5: TEST A SECOND, MORE SENSITIVE THRESHOLD
# (specifically to see how much earlier we'd catch it with looser contamination)
# =====================================================

model_sensitive = IsolationForest(contamination=0.15, random_state=42)
model_sensitive.fit(healthy_hours[feature_columns])
hourly["predicted_anomaly_sensitive"] = model_sensitive.predict(hourly[feature_columns]) == -1

flagged_sensitive = hourly[hourly['is_degrading_hour']]['predicted_anomaly_sensitive'].sum()
fp_sensitive = hourly[~hourly['is_degrading_hour']]['predicted_anomaly_sensitive'].sum()
print(f"\n[More sensitive model, contamination=0.15]")
print(f"Degrading hours flagged: {flagged_sensitive} out of {total_degrading}")
print(f"Healthy hours false-flagged: {fp_sensitive} out of {total_healthy}")

first_flag_sensitive = hourly[hourly['is_degrading_hour'] & hourly['predicted_anomaly_sensitive']].head(1)
if len(first_flag_sensitive):
    print("First correctly flagged (sensitive model):", first_flag_sensitive['hour_block'].values[0])
