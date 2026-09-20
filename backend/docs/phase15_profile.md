# Phase 15 Profile

**Scenario:** 2024-bahrain, 20 drivers, 58 laps, 200 simulations, seed 42
**Elapsed:** 3.715s
**Throughput:** 53.8 sims/s

## Top 20 Functions by Cumulative Time

| Function | Calls | Total | Cumulative | % |
|---|---|---|---|---|
| race_engine_v14.py:268:simulate | 1 | 0.0001 | 3.7150 | 100.0% |
| race_engine_v14.py:264:_build_calibration_state | 1 | 0.0000 | 2.9001 | 78.1% |
| calibration_state.py:147:build_calibration_state | 1 | 0.0000 | 2.9001 | 78.1% |
| calibration_state.py:22:__init__ | 1 | 0.0000 | 2.9000 | 78.1% |
| calibration_state.py:35:_build | 1 | 0.0632 | 2.9000 | 78.1% |
| calibration_api.py:18:_load_json | 172 | 0.0145 | 2.7959 | 75.3% |
| __init__.py:299:loads | 175 | 0.0009 | 2.2712 | 61.1% |
| decoder.py:332:decode | 175 | 0.0014 | 2.2700 | 61.1% |
| decoder.py:343:raw_decode | 175 | 2.2663 | 2.2663 | 61.0% |
| calibration_api.py:33:get_driver_performance | 60 | 0.0012 | 1.2936 | 34.8% |
| calibration_api.py:115:get_qualifying_distribution | 20 | 0.0147 | 0.9499 | 25.6% |
| montecarlo.py:23:run | 1 | 0.0128 | 0.8134 | 21.9% |
| race_engine_v14.py:162:simulate_race | 200 | 0.5169 | 0.7510 | 20.2% |
| calibration_api.py:135:get_reliability_probability | 20 | 0.0005 | 0.5350 | 14.4% |
| pathlib.py:1023:read_text | 175 | 0.0015 | 0.4865 | 13.1% |
| calibration_api.py:132:get_race_pace_distribution | 20 | 0.0150 | 0.4477 | 12.1% |
| calibration_api.py:158:get_overtaking_effect | 20 | 0.0003 | 0.4349 | 11.7% |
| ~:0:<method 'read' of '_io.TextIOWrapper' objects> | 175 | 0.3621 | 0.4114 | 11.1% |
| ~:0:<built-in method builtins.sorted> | 11840 | 0.0568 | 0.0882 | 2.4% |
| ~:0:<built-in method builtins.max> | 232070 | 0.0741 | 0.0742 | 2.0% |

## Analysis

Hot paths identified:
- race_engine_v14.py:268:simulate: 3.715s (100.0%)
- race_engine_v14.py:264:_build_calibration_state: 2.900s (78.1%)
- calibration_state.py:147:build_calibration_state: 2.900s (78.1%)
- calibration_state.py:22:__init__: 2.900s (78.1%)
- calibration_state.py:35:_build: 2.900s (78.1%)
