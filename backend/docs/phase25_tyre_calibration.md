# Tyre Calibration Model A-F

## soft: beta -0.6812 se 0.0200 n 10998 walk-forward improvement inconsistent
## medium: beta -0.3878 se 0.0088 n 33259 walk-forward improvement inconsistent
## hard: beta -0.2525 se 0.0059 n 44147 walk-forward improvement inconsistent
Model A tyre_age -0.3090 B per compound as above C circuit -0.2410 D circuit+driver -0.2399 E circuit+driver+constructor same, F hierarchical soft global -0.6812
Central question: CAN TYRE AGE BE IDENTIFIED AFTER CONTROLLING FOR CIRCUIT, DRIVER? Answer: NO - coefficients negative (-0.3) implausible (should be positive degradation), fuel confounding strong (corr tyre_age vs lap_number 0.497, beta changes 59% when controlling lap_number)
