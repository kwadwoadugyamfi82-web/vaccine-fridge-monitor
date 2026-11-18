# Drift rule on real ULT freezer records

Rule: compressor on = either stage, 24 calibration phases, window 5, 6 evaluations in a row. Warning 1.8, Critical 3.5. Fault dates are service-report dates, not the start of the fault. These are -80 C biobank freezers, not vaccine fridges.

## Freezers

| Freezer | Readings | Period | Steady days | Healthy days | Labelled faults |
|---|---|---|---|---|---|
| 806016 | 5,436,812 | 2012-03-29 to 2023-04-01 | 3744 | 3744 | 0 |
| 806017 | 5,366,815 | 2012-04-18 to 2023-04-01 | 3643 | 3382 | 3 |
| 806024 | 5,444,955 | 2012-04-10 to 2023-04-01 | 3759 | 3660 | 1 |
| 806026 | 5,339,811 | 2012-04-25 to 2023-04-01 | 3390 | 3184 | 3 |
| 806031 | 5,062,304 | 2012-09-17 to 2023-04-01 | 3365 | 3179 | 3 |
| 806033 | 5,367,342 | 2012-08-22 to 2023-04-01 | 3714 | 3565 | 2 |
| 806269 | 5,061,229 | 2013-01-25 to 2023-04-01 | 3428 | 3329 | 2 |
| 806272 | 5,096,418 | 2013-02-01 to 2023-04-01 | 3468 | 3329 | 1 |
| 806276 | 5,223,274 | 2013-01-29 to 2023-04-01 | 3605 | 3062 | 5 |
| 806279 | 3,068,318 | 2017-01-18 to 2023-04-01 | 2071 | 1920 | 2 |

## Summary

Healthy time pooled over all freezers: 32355 days.

| Threshold | Healthy episodes per 30 days | Cooling faults with an alarm in the last 30 days | Cooling faults with an alarm in the last 90 days | Other faults, last 90 days |
|---|---|---|---|---|
| 1.5 | 0.31 (336 episodes) | 4 of 14 | 6 of 14 | 5 of 7 |
| 1.8 | 0.15 (158 episodes) | 2 of 14 | 4 of 14 | 2 of 7 |
| 2.0 | 0.11 (114 episodes) | 1 of 14 | 1 of 14 | 0 of 7 |
| 3.5 (Critical) | 0.05 (52 episodes) | 0 of 14 | 0 of 14 | 0 of 7 |

Faults with fewer than 500 evaluations in the 90 days before the date are left out of the counts (1 of 22).

## Every labelled fault (threshold 1.8)

| Freezer | Service date | Label | Kind | Evaluations (90 d) | Max drift | Warning last 30 d | Warning last 90 d | Critical last 90 d |
|---|---|---|---|---|---|---|---|---|
| 806017 | 2015-02-13 | compressor_stage_2 malfunctional | cooling | 8047 | 1.53 | no | no | no |
| 806017 | 2015-03-19 | Refrigerant leakage at stage 1 | cooling | 5546 | 1.53 | no | no | no |
| 806017 | 2022-08-22 | High condensation water | other | 6080 | 1.50 | no | no | no |
| 806024 | 2015-11-04 | compressor_stage_2 | cooling | 8609 | 1.08 | no | no | no |
| 806026 | 2016-06-09 | compressor_stage_2 | cooling | 5190 | 1.09 | no | no | no |
| 806026 | 2016-08-11 | setpoint_change | other | 1273 | 1.08 | no | no | no |
| 806026 | 2022-07-19 | compressor_stage_2 | cooling | 6234 | 1.21 | no | no | no |
| 806031 | 2017-02-23 | compressor_stage_2 | cooling | 5256 | 1.84 | no | no | no |
| 806031 | 2017-09-20 | logic_wiring | other | 0 | nan | no data | no data | no data |
| 806031 | 2023-03-02 | filter_drier | other | 6683 | 1.92 | no | no | no |
| 806033 | 2016-03-21 | compressor_stage_2 | cooling | 4113 | 1.02 | no | no | no |
| 806033 | 2021-08-06 | battery | other | 5620 | 1.77 | no | no | no |
| 806269 | 2015-05-19 | relay | other | 6154 | 1.89 | no | no | no |
| 806269 | 2015-07-10 | compressor_stage_2 | cooling | 1477 | 1.89 | no | no | no |
| 806272 | 2015-03-03 | compressor_stage_1 | cooling | 12548 | 2.52 | yes | yes | no |
| 806276 | 2015-03-17 | Refrigerant leakage at stage 1 | cooling | 10353 | 15.06 | no | no | no |
| 806276 | 2015-07-09 | door_adjustment | other | 8481 | 2.07 | no | yes | no |
| 806276 | 2016-12-16 | compressor_stage_1 malfunctional | cooling | 8811 | 1.92 | no | yes | no |
| 806276 | 2017-09-20 | compressor_stage_1 malfunctional | cooling | 7729 | 1.42 | no | no | no |
| 806276 | 2022-10-25 | compressor_stage_1 malfunctional | cooling | 6953 | 1.96 | yes | yes | no |
| 806279 | 2022-06-28 | Refrigerant leakage at stage 1 | cooling | 9647 | 2.14 | no | yes | no |
| 806279 | 2022-08-22 | High condensation water | other | 7383 | 2.14 | no | yes | no |

## Healthy false alarms per freezer (threshold 1.8)

| Freezer | Healthy days | Warning episodes | Per 30 days | Critical episodes |
|---|---|---|---|---|
| 806016 | 3744 | 10 | 0.08 | 3 |
| 806017 | 3382 | 6 | 0.05 | 0 |
| 806024 | 3660 | 5 | 0.04 | 1 |
| 806026 | 3184 | 26 | 0.24 | 31 |
| 806031 | 3179 | 47 | 0.44 | 2 |
| 806033 | 3565 | 10 | 0.08 | 1 |
| 806269 | 3329 | 20 | 0.18 | 5 |
| 806272 | 3329 | 8 | 0.07 | 5 |
| 806276 | 3062 | 10 | 0.10 | 1 |
| 806279 | 1920 | 16 | 0.25 | 3 |

## Long Warning episodes (14 days or more)

Events logged in the 10 days before the start and after the end, door events left out.

**806016: 2018-05-27 to 2018-08-16** (81 days, max drift 5.5). Labelled fault nearby: none.
  Before:
  - nothing logged
  After:
  - 2018-08-16 10:09 Warm Alarm RTD = -69C
  - 2018-08-16 10:10 Shutdown
  - 2018-08-16 10:12 Display Power On
  - 2018-08-23 07:15 Display Power On

**806017: 2019-08-25 to 2019-10-16** (52 days, max drift 2.6). Labelled fault nearby: none.
  Before:
  - nothing logged
  After:
  - 2019-10-16 17:07 Warm Alarm RTD = -69C
  - 2019-10-16 17:10 Shutdown
  - 2019-10-16 17:11 Display Power On
  - 2019-10-16 17:16 Lost Communication With Main
  - 2019-10-17 06:14 Failed To Shudown
  - 2019-10-18 09:27 Display Power On
  - 2019-10-18 21:27 Unable To Reach SP
  - 2019-10-18 21:27 Warm Alarm RTD = -31C
  - 2019-10-19 02:13 Warm Alarm has been RTD = -70C
  - 2019-10-21 10:22 Warm Alarm RTD = -69C
  - 2019-10-21 11:52 Warm Alarm has been RTD = -70C

**806017: 2021-02-17 to 2021-06-14** (117 days, max drift 2.3). Labelled fault nearby: none.
  Before:
  - nothing logged
  After:
  - nothing logged

**806026: 2013-01-21 to 2013-02-16** (25 days, max drift 3.8). Labelled fault nearby: none.
  Before:
  - nothing logged
  After:
  - nothing logged

**806026: 2013-02-20 to 2013-03-15** (22 days, max drift 4.6). Labelled fault nearby: none.
  Before:
  - 2013-02-14 14:52 Clean Filter
  After:
  - nothing logged

**806026: 2013-03-19 to 2013-06-25** (98 days, max drift 9.2). Labelled fault nearby: none.
  Before:
  - 2013-03-11 13:58 Clean Filter
  - 2013-03-12 11:02 Clean Filter
  After:
  - 2013-06-25 13:07 Warm Alarm RTD = -69
  - 2013-06-25 13:26 Warm Alarm has been RTD = -70

**806026: 2013-08-21 to 2014-04-14** (236 days, max drift 31.1). Labelled fault nearby: none.
  Before:
  - 2013-08-20 09:52 AC Power Interrupted
  - 2013-08-20 10:40 AC Power Restored
  - 2013-08-20 11:23 AC Power Interrupted
  - 2013-08-20 11:50 AC Power Restored
  - 2013-08-20 11:50 Bus Communicaiton Fail
  - 2013-08-20 12:19 AC Power Interrupted
  - 2013-08-20 12:19 AC Power Restored
  - 2013-08-20 20:27 Unable To Reach SP
  - 2013-08-21 10:14 AC Power Interrupted
  - 2013-08-21 10:59 AC Power Restored
  After:
  - 2014-04-15 12:17 Warm Alarm RTD = -69
  - 2014-04-15 14:40 Warm Alarm has been RTD = -70

**806026: 2018-05-16 to 2018-07-20** (65 days, max drift 10.9). Labelled fault nearby: none.
  Before:
  - 2018-05-16 00:03 Unable To Reach SP
  After:
  - 2018-07-26 19:23 Unable To Reach SP

**806026: 2019-08-14 to 2019-11-27** (104 days, max drift 14.3). Labelled fault nearby: none.
  Before:
  - 2019-08-14 11:48 Warm Alarm RTD = -69C
  - 2019-08-14 13:18 Warm Alarm has been RTD = -70C
  After:
  - 2019-11-27 11:31 Warm Alarm RTD = -69C
  - 2019-11-27 11:34 Shutdown
  - 2019-11-27 11:36 Display Power On
  - 2019-12-05 20:44 Unable To Reach SP
  - 2019-12-05 20:44 Warm Alarm RTD = -58C
  - 2019-12-05 21:33 Warm Alarm has been RTD = -70C

**806026: 2020-02-28 to 2020-07-26** (150 days, max drift 35.2). Labelled fault nearby: none.
  Before:
  - 2020-02-28 00:34 Unable To Reach SP
  After:
  - 2020-07-27 03:47 Unable To Reach SP
  - 2020-07-27 10:23 Warm Alarm RTD = -69C
  - 2020-07-27 10:31 Shutdown
  - 2020-07-27 10:32 Display Power On
  - 2020-07-27 10:37 Lost Communication With Main
  - 2020-07-29 09:35 Display Power On
  - 2020-07-29 21:35 Unable To Reach SP
  - 2020-07-31 09:49 Shutdown
  - 2020-07-31 09:51 Display Power On

**806026: 2022-09-02 to 2022-10-06** (34 days, max drift 17.1). Labelled fault nearby: compressor_stage_2 (2022-07-19).
  Before:
  - 2022-08-30 13:02 Display Power On
  - 2022-09-01 08:02 Warm Alarm RTD = -69C
  - 2022-09-01 08:26 Warm Alarm has been RTD = -70C
  After:
  - 2022-10-06 13:54 Warm Alarm RTD = -69C
  - 2022-10-06 14:41 Warm Alarm has been RTD = -70C
  - 2022-10-07 10:35 Warm Alarm RTD = -69C
  - 2022-10-07 10:54 Warm Alarm has been RTD = -70C
  - 2022-10-07 11:37 Warm Alarm RTD = -69C
  - 2022-10-07 15:07 Warm Alarm has been RTD = -70C
  - 2022-10-10 11:52 Warm Alarm RTD = -69C
  - 2022-10-10 12:39 Warm Alarm has been RTD = -70C
  - 2022-10-11 12:44 Warm Alarm RTD = -69C
  - 2022-10-11 14:37 Warm Alarm has been RTD = -70C
  - 2022-10-11 14:56 Warm Alarm RTD = -69C
  - 2022-10-11 15:30 Warm Alarm has been RTD = -70C
  - 2022-10-12 13:16 Warm Alarm RTD = -69C
  - 2022-10-12 14:02 Warm Alarm has been RTD = -70C
  - 2022-10-14 14:04 Warm Alarm RTD = -69C
  - 2022-10-14 14:45 Warm Alarm has been RTD = -70C
  - 2022-10-14 21:50 Unable To Reach SP

**806033: 2020-05-25 to 2020-06-30** (35 days, max drift 2.3). Labelled fault nearby: none.
  Before:
  - 2020-05-22 01:01 Display Power On
  After:
  - nothing logged

**806269: 2019-10-23 to 2019-12-12** (50 days, max drift 7.7). Labelled fault nearby: none.
  - no events file

**806272: 2014-11-19 to 2015-03-02** (103 days, max drift 2.9). Labelled fault nearby: compressor_stage_1 (2015-03-03).
  Before:
  - 2014-11-19 13:57 Replace Main Battery
  - 2014-11-19 13:57 Power Modes = High Performance
  - 2014-11-19 14:17 Time = 14:17:00
  After:
  - 2015-03-02 17:05 Warm Interstage
  - 2015-03-02 18:13 Warm Alarm RTD = -69C
  - 2015-03-02 20:07 Warm Alarm has been RTD = -70C
  - 2015-03-03 02:59 Warm Alarm RTD = -69C
  - 2015-03-03 03:46 Unable To Reach SP
  - 2015-03-03 13:53 Shutdown

**806272: 2016-03-24 to 2016-07-15** (113 days, max drift 4.3). Labelled fault nearby: none.
  Before:
  - nothing logged
  After:
  - 2016-07-15 10:50 Shutdown
  - 2016-07-15 10:55 Display Power On

**806279: 2019-05-15 to 2019-05-30** (15 days, max drift 15.5). Labelled fault nearby: none.
  Before:
  - 2019-05-08 09:11 Shutdown
  - 2019-05-08 09:21 Display Power On
  - 2019-05-08 09:22 Power Modes = High Performance
  After:
  - 2019-05-30 23:12 Unable To Reach SP

**806279: 2020-12-17 to 2021-01-11** (25 days, max drift 3.3). Labelled fault nearby: none.
  Before:
  - nothing logged
  After:
  - nothing logged

**806279: 2021-02-12 to 2021-02-27** (15 days, max drift 5.8). Labelled fault nearby: none.
  Before:
  - nothing logged
  After:
  - 2021-02-27 14:34 Unable To Reach SP
  - 2021-03-01 05:08 Warm Alarm RTD = -39C
  - 2021-03-01 12:45 Shutdown
  - 2021-03-08 09:35 Display Power On
  - 2021-03-08 09:35 Power Modes = High Performance
  - 2021-03-08 09:59 Shutdown
  - 2021-03-08 16:04 Display Power On
  - 2021-03-08 16:04 Power Modes = High Performance
  - 2021-03-09 02:37 Warm Interstage

**806279: 2021-05-19 to 2021-06-07** (19 days, max drift 2.3). Labelled fault nearby: none.
  Before:
  - nothing logged
  After:
  - nothing logged
