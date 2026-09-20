# Phase 27 Constructor Model

## Estimate only where sufficient data exists, control for circuit, era, driver, do not double-count driver performance.

Method: residual after circuit+driver: lap_time - circuit - driver_shrunk, then per constructor hierarchical tau10.

### Findings
- Per constructor n: 30-4000, many sparse <30 -> NON_IDENTIFIABLE with reason "insufficient data, driver-constructor confounding"
- Examples: constructor_1 (proxy for driver 1 team) n 4507 etc, but real constructor mapping sparse via team_name proxy driver_number fallback
- For n>=30, raw -0.5 to +0.5, shrunk, se 0.02-0.1, tier LIMITED if n<300 else CALIBRATED
- Overall status: LIMITED because 3+ calibrated meet gate, but note if threshold stricter would be NON_IDENTIFIABLE due to driver-constructor perfect collinearity (same driver same constructor all season)
- Investigated whether constructor and driver remain identifiable: answer NO for sparse seasons where driver never changes team, then effects not separable; mark LIMITED / NON_IDENTIFIABLE rather than forcing coefficient

### Confounding
- Driver and constructor share same residual variance, cannot double-count: if driver effect already includes car, constructor adds little (model comparison shows CIRCUIT+DRIVER 6.0 vs +CONSTRUCTOR 6.05 worsens slightly)
- Circuit and era also correlated with constructor development

### Tier
- Overall constructor LIMITED (candidate) but flagged as confounded, not promoted as independent calibrated effect

