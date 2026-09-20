# Error Decomposition

Overall baseline MAE 12.05s candidate 6.47s improvement 5.58s (53% due to circuit)
Dominant sources: circuit baseline differences 10-23s range (spielberg -21 vs marina-bay +23), era 1-2s, driver 0.5s, constructor 0.3s, tyre 0.08s, fuel confounded 0.02s, weather PRIOR, SC 3-5s
Why ~13s wrong? Global baseline 94s ignores circuit length variation 70s (spielberg) to 110s (spa); per-circuit residuals show baseline error >20s for extremes, circuit-aware reduces but residual 6.5s remains due to driver/tyre/traffic/SC not fully modelled
[
  {
    "yeongam": {
      "base_MAE": 25.939362723743837,
      "candidate_MAE": 17.400677106825356,
      "improvement": 8.538685616918482,
      "n": 2623
    }
  },
  {
    "spa-francorchamps": {
      "base_MAE": 25.307163265203336,
      "candidate_MAE": 9.154334581360867,
      "improvement": 16.15282868384247,
      "n": 12406
    }
  }
]