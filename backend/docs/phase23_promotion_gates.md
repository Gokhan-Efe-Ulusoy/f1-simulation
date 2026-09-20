# Promotion Gates

{
  "CALIBRATED": "sufficient independent observations, multiple races, multiple circuits, leakage 0, finite uncertainty, stable direction, walk-forward passes, no severe train/test degradation, confounding documented, reproducibility, sensitivity bounded",
  "gates": {
    "circuit": {
      "decision": "LIMITED"
    },
    "constructor": {
      "decision": "LIMITED"
    },
    "driver": {
      "decision": "LIMITED"
    },
    "era": {
      "decision": "CALIBRATED"
    },
    "fuel": {
      "decision": "NON_IDENTIFIABLE"
    },
    "lap_time_baseline": {
      "decision": "CALIBRATED"
    },
    "pit_split": {
      "decision": "NON_IDENTIFIABLE"
    },
    "pit_total": {
      "decision": "CALIBRATED",
      "n": 12147,
      "required": 500
    },
    "race_control": {
      "decision": "PRIOR_ONLY"
    },
    "setup": {
      "decision": "NON_IDENTIFIABLE"
    },
    "strategy": {
      "decision": "NON_IDENTIFIABLE"
    },
    "tyre_hard": {
      "decision": "LIMITED"
    },
    "tyre_medium": {
      "decision": "LIMITED"
    },
    "tyre_soft": {
      "decision": "LIMITED",
      "leakage": 0,
      "n_circuits": 34,
      "n_laps": 913,
      "n_races": 74,
      "required_circuits": 3,
      "required_races": 5,
      "uncertainty": 0.02,
      "walk_forward": "fail (hurts validation)"
    },
    "weather": {
      "decision": "PRIOR_ONLY"
    }
  }
}