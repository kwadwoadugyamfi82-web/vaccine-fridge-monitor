# REFIT sweep results (leave-one-house-out)

Thresholds fixed at Warning 1.8, Critical 3.5. Injected fault: 30-day slices, calibrated at the start of each slice, fault starts on day 15 and ramps over 7 days. Eligible = Critical found for a 3x fault in at least 80% of slices with median delay at most 7 days on every training appliance. Cost = Warning + 3 x Critical episodes per 30 days.

## Firmware setting on each appliance

| Setting | Healthy Warning / Critical episodes per 30 d | 3x fault: Warning found, median delay | 3x fault: Critical found, median delay | 5x fault: Critical found, median delay |
|---|---|---|---|---|
| House 2, Appliance1 | 13.3 / 1.7 | 100% 1.4 d | 67% 2.9 d | 100% 2.8 d |
| House 15, Appliance1 | 4.8 / 0.5 | 100% 2.8 d | 83% 4.9 d | 100% 4.1 d |
| House 20, Appliance1 | 27.5 / 5.5 | 100% 1.6 d | 100% 4.1 d | 100% 2.7 d |
| House 20, Appliance2 | 5.5 / 0.3 | 100% 1.5 d | 83% 3.5 d | 100% 2.9 d |

## Held-out house: House 15

Training appliances: House 2, Appliance1, House 20, Appliance1, House 20, Appliance2

Chosen on the training houses: **L=24, W=5, mean, P=6** (training cost 22.0; firmware setting 68.8). 14 of 48 settings were eligible.

Scored on the held-out House 15:

| Setting | Healthy Warning / Critical episodes per 30 d | 3x fault: Warning found, median delay | 3x fault: Critical found, median delay | 5x fault: Critical found, median delay |
|---|---|---|---|---|
| House 15, Appliance1 - firmware | 4.8 / 0.5 | 100% 2.8 d | 83% 4.9 d | 100% 4.1 d |
| House 15, Appliance1 - chosen | 1.4 / 0.1 | 100% 2.8 d | 100% 5.7 d | 100% 3.6 d |

## Held-out house: House 2

Training appliances: House 15, Appliance1, House 20, Appliance1, House 20, Appliance2

Chosen on the training houses: **L=6, W=5, median, P=3** (training cost 17.8; firmware setting 56.6). 15 of 48 settings were eligible.

Scored on the held-out House 2:

| Setting | Healthy Warning / Critical episodes per 30 d | 3x fault: Warning found, median delay | 3x fault: Critical found, median delay | 5x fault: Critical found, median delay |
|---|---|---|---|---|
| House 2, Appliance1 - firmware | 13.3 / 1.7 | 100% 1.4 d | 67% 2.9 d | 100% 2.8 d |
| House 2, Appliance1 - chosen | 6.1 / 0.6 | 100% 2.7 d | 100% 5.5 d | 100% 3.8 d |

## Held-out house: House 20

Training appliances: House 2, Appliance1, House 15, Appliance1

Chosen on the training houses: **L=24, W=5, mean, P=6** (training cost 7.7; firmware setting 24.8). 13 of 48 settings were eligible.

Scored on the held-out House 20:

| Setting | Healthy Warning / Critical episodes per 30 d | 3x fault: Warning found, median delay | 3x fault: Critical found, median delay | 5x fault: Critical found, median delay |
|---|---|---|---|---|
| House 20, Appliance1 - firmware | 27.5 / 5.5 | 100% 1.6 d | 100% 4.1 d | 100% 2.7 d |
| House 20, Appliance1 - chosen | 10.3 / 0.7 | 100% 1.6 d | 100% 5.2 d | 100% 2.9 d |
| House 20, Appliance2 - firmware | 5.5 / 0.3 | 100% 1.5 d | 83% 3.5 d | 100% 2.9 d |
| House 20, Appliance2 - chosen | 3.8 / 0.0 | 100% 2.4 d | 100% 6.3 d | 100% 3.4 d |

## All houses together (descriptive only, not a test)

Top five eligible settings by total cost (12 eligible of 48):

| Setting | Total cost | Firmware total cost |
|---|---|---|
| L=24, W=5, mean, P=6 | 23.8 | 75.1 |
| L=6, W=5, median, P=3 | 25.7 | 75.1 |
| L=12, W=5, mean, P=6 | 26.5 | 75.1 |
| L=12, W=5, median, P=3 | 30.4 | 75.1 |
| L=24, W=5, mean, P=3 | 32.3 | 75.1 |

Best setting with all houses: **L=24, W=5, mean, P=6**.

Same comparison with Issues-flagged phases dropped (robustness check):

| Setting | Healthy Warning / Critical episodes per 30 d | 3x fault: Warning found, median delay | 3x fault: Critical found, median delay | 5x fault: Critical found, median delay |
|---|---|---|---|---|
| House 2, Appliance1 - firmware, Issues dropped | 11.2 / 0.5 | 80% 0.6 d | 80% 4.5 d | 80% 3.0 d |
| House 2, Appliance1 - best, Issues dropped | 2.9 / 0.1 | 100% 2.3 d | 100% 6.5 d | 100% 4.4 d |
| House 15, Appliance1 - firmware, Issues dropped | 4.3 / 0.4 | 100% 2.8 d | 83% 8.9 d | 100% 4.1 d |
| House 15, Appliance1 - best, Issues dropped | 1.2 / 0.0 | 100% 2.9 d | 100% 9.5 d | 100% 3.7 d |
| House 20, Appliance1 - firmware, Issues dropped | 12.0 / 1.3 | 100% 2.5 d | 83% 4.4 d | 100% 3.2 d |
| House 20, Appliance1 - best, Issues dropped | 6.2 / 0.1 | 100% 2.7 d | 100% 4.9 d | 100% 3.2 d |
| House 20, Appliance2 - firmware, Issues dropped | 1.8 / 0.0 | 100% 2.5 d | 100% 6.3 d | 100% 3.8 d |
| House 20, Appliance2 - best, Issues dropped | 1.2 / 0.0 | 100% 3.2 d | 100% 6.5 d | 100% 4.0 d |


