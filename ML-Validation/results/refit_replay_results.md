# REFIT replay results

Rule: ON >= 30 W, OFF <= 10 W, baseline = first 3 ON + 3 OFF, window 5, Warning > 1.8, Critical > 3.5. Gaps > 120 s break cycles. Main settings: Issues rows kept, minimum phase 120 s.

## House 2, Appliance1

- Rows 5,733,526; span 617 days; data gaps > 120 s: 597; outages > 1 h: 81
- Complete phases found 14,396; kept 14,074 (7,054 ON, 7,020 OFF) covering 450 days
- Unbroken stretches between outages: 32; longest 59 days, median 9.6 days
- Handling: short dips merged into neighbours: 315; too short (< 120 s): 318; too long (> 6 h): 4; sub-meters above aggregate (Issues = 1): 0; ON phase above 2x median power (defrost): 0
- ON phase: median 34.0 min (5th-95th pct 17.5-60.9), median power 86 W (5th-95th pct 84-156)
- OFF phase: median 55.4 min (5th-95th pct 9.0-91.6)

False alarms on healthy data (episodes are per 30 days, Warning / Critical):

| Calibration | Windows | Median drift | 99th pct | Max | Above 1.8 | Above 3.5 | Episodes per 30 d |
|---|---|---|---|---|---|---|---|
| Never recalibrated | 14068 | 1.46 | 4.46 | 9.57 | 31.0% | 2.72% | 32.2 / 6.0 |
| Recalibrated after outages > 1 h | 13885 | 0.86 | 3.25 | 6.16 | 8.4% | 0.73% | 13.3 / 1.7 |
| Recalibrated after outages and every 30 days | 13855 | 0.97 | 3.89 | 6.46 | 15.4% | 1.60% | 16.3 / 3.5 |

Sensitivity to preprocessing (share of windows above 1.8 / above 3.5, with episodes per 30 days in brackets):

| Variant | Phases kept | Never recalibrated | Recalibrated after outages > 1 h | Recalibrated after outages and every 30 days |
|---|---|---|---|---|
| main | 14,074 | 31.0% / 2.72% (32.2 / 6.0) | 8.4% / 0.73% (13.3 / 1.7) | 15.4% / 1.60% (16.3 / 3.5) |
| Issues rows dropped | 9,278 | 25.5% / 1.18% (33.0 / 2.8) | 5.5% / 0.11% (11.2 / 0.5) | 12.5% / 0.68% (15.1 / 1.9) |
| minimum phase 300 s | 13,397 | 30.3% / 2.29% (26.4 / 3.9) | 7.7% / 0.54% (9.9 / 1.1) | 14.8% / 1.40% (12.9 / 2.4) |

Injected fault (6 slices of 30 days, calibrated at the start of each slice; fault starts on day 15 and grows linearly over 7 days). Delay is measured from fault onset:

| Final ON/OFF ratio multiplier | Warnings before onset (windows) | Warning raised after | Critical raised after |
|---|---|---|---|
| 1.0x | 216 (2695) | 0.6 d median, range 0.1-6.4 (4/6) | 7.0 d median, range 5.8-8.3 (2/6) |
| 1.5x | 216 (2695) | 0.6 d median, range 0.1-3.2 (4/6) | 7.0 d median, range 4.5-9.5 (4/6) |
| 2.0x | 216 (2695) | 0.7 d median, range 0.1-13.0 (5/6) | 4.6 d median, range 3.1-6.4 (4/6) |
| 3.0x | 216 (2695) | 1.4 d median, range 0.1-10.2 (6/6) | 2.9 d median, range 1.8-6.4 (4/6) |
| 4.0x | 216 (2695) | 1.4 d median, range 0.1-10.2 (6/6) | 2.4 d median, range 0.9-10.2 (5/6) |
| 5.0x | 216 (2695) | 0.9 d median, range 0.1-10.1 (6/6) | 2.8 d median, range 0.9-10.2 (6/6) |

## House 15, Appliance1

- Rows 6,225,696; span 567 days; data gaps > 120 s: 1070; outages > 1 h: 203
- Complete phases found 18,133; kept 17,635 (8,828 ON, 8,807 OFF) covering 478 days
- Unbroken stretches between outages: 23; longest 93 days, median 15.4 days
- Handling: short dips merged into neighbours: 258; too short (< 120 s): 474; too long (> 6 h): 2; sub-meters above aggregate (Issues = 1): 0; ON phase above 2x median power (defrost): 22
- ON phase: median 21.5 min (5th-95th pct 11.2-43.2), median power 79 W (5th-95th pct 73-86)
- OFF phase: median 48.2 min (5th-95th pct 25.0-106.7)

False alarms on healthy data (episodes are per 30 days, Warning / Critical):

| Calibration | Windows | Median drift | 99th pct | Max | Above 1.8 | Above 3.5 | Episodes per 30 d |
|---|---|---|---|---|---|---|---|
| Never recalibrated | 17629 | 0.69 | 1.75 | 6.77 | 0.9% | 0.07% | 1.6 / 0.2 |
| Recalibrated after outages > 1 h | 17506 | 0.84 | 2.36 | 6.77 | 2.7% | 0.18% | 4.8 / 0.5 |
| Recalibrated after outages and every 30 days | 17446 | 0.93 | 2.49 | 6.77 | 3.0% | 0.32% | 5.0 / 1.0 |

Sensitivity to preprocessing (share of windows above 1.8 / above 3.5, with episodes per 30 days in brackets):

| Variant | Phases kept | Never recalibrated | Recalibrated after outages > 1 h | Recalibrated after outages and every 30 days |
|---|---|---|---|---|
| main | 17,635 | 0.9% / 0.07% (1.6 / 0.2) | 2.7% / 0.18% (4.8 / 0.5) | 3.0% / 0.32% (5.0 / 1.0) |
| Issues rows dropped | 14,710 | 11.1% / 0.46% (17.5 / 1.3) | 2.3% / 0.06% (4.3 / 0.4) | 2.6% / 0.12% (5.0 / 0.6) |
| minimum phase 300 s | 17,485 | 0.9% / 0.06% (1.6 / 0.2) | 2.7% / 0.18% (4.6 / 0.5) | 3.0% / 0.31% (4.6 / 0.9) |

Injected fault (6 slices of 30 days, calibrated at the start of each slice; fault starts on day 15 and grows linearly over 7 days). Delay is measured from fault onset:

| Final ON/OFF ratio multiplier | Warnings before onset (windows) | Warning raised after | Critical raised after |
|---|---|---|---|
| 1.0x | 87 (3505) | 5.7 d median, range 0.9-12.2 (4/6) | 3.8 d median, range 2.8-4.7 (2/6) |
| 1.5x | 87 (3505) | 4.8 d median, range 0.9-12.2 (5/6) | 4.8 d median, range 2.8-12.2 (3/6) |
| 2.0x | 87 (3505) | 4.1 d median, range 0.9-10.2 (6/6) | 6.8 d median, range 2.7-12.2 (4/6) |
| 3.0x | 87 (3505) | 2.8 d median, range 0.8-4.7 (6/6) | 4.9 d median, range 2.7-12.3 (5/6) |
| 4.0x | 87 (3505) | 2.2 d median, range 0.8-3.7 (6/6) | 4.5 d median, range 1.0-10.2 (6/6) |
| 5.0x | 87 (3505) | 1.6 d median, range 0.7-2.1 (6/6) | 4.1 d median, range 1.0-6.2 (6/6) |

## House 20, Appliance1

- Rows 5,168,605; span 460 days; data gaps > 120 s: 89; outages > 1 h: 12
- Complete phases found 20,437; kept 19,923 (9,963 ON, 9,960 OFF) covering 412 days
- Unbroken stretches between outages: 13; longest 99 days, median 21.9 days
- Handling: short dips merged into neighbours: 191; too short (< 120 s): 505; too long (> 6 h): 9; sub-meters above aggregate (Issues = 1): 0; ON phase above 2x median power (defrost): 0
- ON phase: median 14.5 min (5th-95th pct 11.4-90.0), median power 88 W (5th-95th pct 83-95)
- OFF phase: median 35.0 min (5th-95th pct 26.4-53.8)

False alarms on healthy data (episodes are per 30 days, Warning / Critical):

| Calibration | Windows | Median drift | 99th pct | Max | Above 1.8 | Above 3.5 | Episodes per 30 d |
|---|---|---|---|---|---|---|---|
| Never recalibrated | 19917 | 0.94 | 3.80 | 6.64 | 15.9% | 1.56% | 30.2 / 6.6 |
| Recalibrated after outages > 1 h | 19845 | 0.92 | 3.99 | 7.00 | 14.0% | 1.80% | 27.5 / 5.5 |
| Recalibrated after outages and every 30 days | 19782 | 0.97 | 4.03 | 7.31 | 14.6% | 1.79% | 28.5 / 5.2 |

Sensitivity to preprocessing (share of windows above 1.8 / above 3.5, with episodes per 30 days in brackets):

| Variant | Phases kept | Never recalibrated | Recalibrated after outages > 1 h | Recalibrated after outages and every 30 days |
|---|---|---|---|---|
| main | 19,923 | 15.9% / 1.56% (30.2 / 6.6) | 14.0% / 1.80% (27.5 / 5.5) | 14.6% / 1.79% (28.5 / 5.2) |
| Issues rows dropped | 14,223 | 8.8% / 0.25% (21.6 / 1.0) | 6.0% / 0.34% (12.0 / 1.3) | 6.6% / 0.27% (12.9 / 1.2) |
| minimum phase 300 s | 19,918 | 15.9% / 1.56% (30.1 / 6.6) | 14.0% / 1.80% (27.5 / 5.5) | 14.6% / 1.79% (28.5 / 5.2) |

Injected fault (6 slices of 30 days, calibrated at the start of each slice; fault starts on day 15 and grows linearly over 7 days). Delay is measured from fault onset:

| Final ON/OFF ratio multiplier | Warnings before onset (windows) | Warning raised after | Critical raised after |
|---|---|---|---|
| 1.0x | 434 (4687) | 0.8 d median, range 0.2-6.3 (5/6) | 9.1 d median, range 3.9-14.3 (2/6) |
| 1.5x | 434 (4687) | 2.2 d median, range 0.2-6.2 (6/6) | 8.9 d median, range 3.9-14.8 (4/6) |
| 2.0x | 434 (4687) | 1.6 d median, range 0.2-4.5 (6/6) | 4.8 d median, range 1.3-7.4 (5/6) |
| 3.0x | 434 (4687) | 1.6 d median, range 0.2-4.1 (6/6) | 4.1 d median, range 1.4-6.5 (6/6) |
| 4.0x | 434 (4687) | 1.5 d median, range 0.2-3.3 (6/6) | 4.1 d median, range 1.4-4.6 (6/6) |
| 5.0x | 434 (4687) | 1.1 d median, range 0.2-2.6 (6/6) | 2.7 d median, range 1.2-4.6 (6/6) |

## House 20, Appliance2

- Rows 5,168,605; span 460 days; data gaps > 120 s: 89; outages > 1 h: 12
- Complete phases found 15,435; kept 14,859 (7,404 ON, 7,455 OFF) covering 412 days
- Unbroken stretches between outages: 13; longest 99 days, median 21.9 days
- Handling: short dips merged into neighbours: 188; too short (< 120 s): 512; too long (> 6 h): 9; sub-meters above aggregate (Issues = 1): 0; ON phase above 2x median power (defrost): 55
- ON phase: median 30.5 min (5th-95th pct 22.5-78.4), median power 115 W (5th-95th pct 112-124)
- OFF phase: median 44.9 min (5th-95th pct 24.8-49.6)

False alarms on healthy data (episodes are per 30 days, Warning / Critical):

| Calibration | Windows | Median drift | 99th pct | Max | Above 1.8 | Above 3.5 | Episodes per 30 d |
|---|---|---|---|---|---|---|---|
| Never recalibrated | 14853 | 1.15 | 3.48 | 6.05 | 15.3% | 0.98% | 20.3 / 1.9 |
| Recalibrated after outages > 1 h | 14781 | 0.83 | 2.41 | 4.69 | 3.4% | 0.08% | 5.5 / 0.3 |
| Recalibrated after outages and every 30 days | 14717 | 0.95 | 2.57 | 4.98 | 5.7% | 0.09% | 9.7 / 0.2 |

Sensitivity to preprocessing (share of windows above 1.8 / above 3.5, with episodes per 30 days in brackets):

| Variant | Phases kept | Never recalibrated | Recalibrated after outages > 1 h | Recalibrated after outages and every 30 days |
|---|---|---|---|---|
| main | 14,859 | 15.3% / 0.98% (20.3 / 1.9) | 3.4% / 0.08% (5.5 / 0.3) | 5.7% / 0.09% (9.7 / 0.2) |
| Issues rows dropped | 9,532 | 5.2% / 0.03% (9.2 / 0.2) | 0.5% / 0.00% (1.8 / 0.0) | 2.7% / 0.00% (5.0 / 0.0) |
| minimum phase 300 s | 14,768 | 15.0% / 0.93% (20.0 / 1.8) | 3.2% / 0.08% (5.0 / 0.3) | 5.4% / 0.09% (8.8 / 0.2) |

Injected fault (6 slices of 30 days, calibrated at the start of each slice; fault starts on day 15 and grows linearly over 7 days). Delay is measured from fault onset:

| Final ON/OFF ratio multiplier | Warnings before onset (windows) | Warning raised after | Critical raised after |
|---|---|---|---|
| 1.0x | 179 (3312) | 2.5 d median, range 0.1-6.3 (5/6) | never (0/6) |
| 1.5x | 179 (3312) | 2.4 d median, range 0.1-6.1 (5/6) | 12.0 d median, range 2.6-13.6 (4/6) |
| 2.0x | 179 (3312) | 2.0 d median, range 0.1-3.8 (6/6) | 4.6 d median, range 2.5-13.3 (5/6) |
| 3.0x | 179 (3312) | 1.5 d median, range 0.1-3.4 (6/6) | 3.5 d median, range 2.5-6.2 (5/6) |
| 4.0x | 179 (3312) | 1.0 d median, range 0.1-3.2 (6/6) | 2.9 d median, range 2.4-4.8 (5/6) |
| 5.0x | 179 (3312) | 0.9 d median, range 0.1-3.2 (6/6) | 2.9 d median, range 2.3-3.8 (6/6) |


