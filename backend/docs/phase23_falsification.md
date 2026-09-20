# Falsification Tests

- circuit_randomize: {'passed': True, 'result': 'weakened'}
- constructor_shuffle: {'passed': True, 'result': 'weakened'}
- driver_randomize: {'passed': True, 'result': 'disappeared (0.5s -> 0.02)'}
- pit_shuffle: {'passed': True, 'result': 'predictive degraded'}
- temporal_inject_future: {'passed': True, 'result': 'identical (leakage 0)'}
- tyre_randomize_age: {'effect': 'should weaken', 'passed': True, 'result': 'weakened (0.08 -> 0.01)'}
If supposedly important effect survives randomization -> leakage/bias investigation; all passed
