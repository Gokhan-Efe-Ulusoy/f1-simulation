# Calibration v1.0.0

Methodology: hierarchical shrinkage with prior_n=5, Beta(5,95) for reliability, Normal for pace.
Datasets: f1-dataset-v1.1 (77 seasons, 1172 races, 34856 results)
Temporal policy: strict_before_as_of, no future leakage.
Era handling: 10 eras with field_spread.
Circuit normalization: baseline via average finish, overtaking_env via gains.
Driver latent: race_pace, qualifying, consistency, reliability, overtaking with CI95.
Constructor: race_pace, reliability, development_rate with confounding flag.
Backtest: walk-forward 2010-2026, 320 races.
Metrics: top1 0.3, Brier 0.03959657784809886.
Limitations: tyre/weather null where unavailable, small sample drivers shrunk.
