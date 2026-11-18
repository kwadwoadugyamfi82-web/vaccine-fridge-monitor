# Detector comparison on REFIT traces (leave-one-house-out)

Calibration 24 phases of each kind, persistence 6, injected faults as in refit_sweep.py. Each detector has one alarm threshold, chosen on the two training houses to meet a false-alarm target, then applied unchanged to the held-out house.

## Target: at most 2 false-alarm episodes per 30 days on the training houses

| Held-out appliance | Detector | Healthy episodes per 30 d | 3x fault found (median delay) | 5x fault found (median delay) |
|---|---|---|---|---|
| House 15, Appliance1 | ratio (threshold 2.45) | 0.6 | 100% (3.7 d) | 100% (2.8 d) |
| House 15, Appliance1 | ewma (threshold 1.65) | 0.3 | 100% (2.9 d) | 100% (2.0 d) |
| House 15, Appliance1 | iforest (threshold 0.62) | 0.9 | 83% (5.1 d) | 100% (5.7 d) |
| House 2, Appliance1 | ratio (threshold 2.35) | 1.9 | 100% (4.1 d) | 100% (1.8 d) |
| House 2, Appliance1 | ewma (threshold 1.35) | 8.3 | 100% (1.8 d) | 100% (1.3 d) |
| House 2, Appliance1 | iforest (threshold 0.62) | 5.2 | 100% (3.0 d) | 100% (1.9 d) |
| House 20, Appliance1 | ratio (threshold 2.10) | 6.1 | 100% (1.9 d) | 100% (1.6 d) |
| House 20, Appliance2 | ratio (threshold 2.10) | 2.1 | 100% (2.8 d) | 100% (2.4 d) |
| House 20, Appliance1 | ewma (threshold 1.70) | 1.4 | 100% (3.9 d) | 100% (2.3 d) |
| House 20, Appliance2 | ewma (threshold 1.70) | 0.3 | 100% (3.4 d) | 100% (2.4 d) |
| House 20, Appliance1 | iforest (threshold 0.62) | 16.2 | 100% (1.2 d) | 100% (1.2 d) |
| House 20, Appliance2 | iforest (threshold 0.62) | 3.1 | 100% (4.3 d) | 100% (2.5 d) |

## Target: at most 5 false-alarm episodes per 30 days on the training houses

| Held-out appliance | Detector | Healthy episodes per 30 d | 3x fault found (median delay) | 5x fault found (median delay) |
|---|---|---|---|---|
| House 15, Appliance1 | ratio (threshold 1.95) | 1.1 | 100% (3.0 d) | 100% (2.0 d) |
| House 15, Appliance1 | ewma (threshold 1.30) | 1.1 | 100% (2.0 d) | 100% (1.6 d) |
| House 15, Appliance1 | iforest (threshold 0.58) | 2.3 | 100% (4.7 d) | 100% (2.9 d) |
| House 2, Appliance1 | ratio (threshold 1.85) | 4.9 | 100% (2.1 d) | 100% (1.4 d) |
| House 2, Appliance1 | ewma (threshold 1.15) | 9.5 | 100% (1.0 d) | 100% (1.0 d) |
| House 2, Appliance1 | iforest (threshold 0.59) | 11.7 | 100% (1.1 d) | 100% (1.1 d) |
| House 20, Appliance1 | ratio (threshold 1.60) | 14.1 | 100% (1.2 d) | 100% (1.2 d) |
| House 20, Appliance2 | ratio (threshold 1.60) | 6.3 | 100% (2.1 d) | 100% (1.5 d) |
| House 20, Appliance1 | ewma (threshold 1.35) | 3.1 | 100% (2.4 d) | 100% (1.4 d) |
| House 20, Appliance2 | ewma (threshold 1.35) | 1.7 | 100% (2.5 d) | 100% (1.8 d) |
| House 20, Appliance1 | iforest (threshold 0.57) | 28.8 | 100% (0.5 d) | 100% (0.4 d) |
| House 20, Appliance2 | iforest (threshold 0.57) | 7.1 | 100% (1.8 d) | 100% (1.7 d) |

## Averages over the four held-out appliances

| Target | Detector | Mean healthy episodes per 30 d | Mean 3x found | Mean 3x median delay (d) | Mean 5x found |
|---|---|---|---|---|---|
| 2 | ratio | 2.7 | 100% | 3.1 | 100% |
| 2 | ewma | 2.6 | 100% | 3.0 | 100% |
| 2 | iforest | 6.4 | 96% | 3.4 | 100% |
| 5 | ratio | 6.6 | 100% | 2.1 | 100% |
| 5 | ewma | 3.9 | 100% | 2.0 | 100% |
| 5 | iforest | 12.5 | 100% | 2.0 | 100% |
