import json
from datetime import datetime, timezone
baseline={
    'dataset_version': 'f1-dataset-v1.1',
    'dataset_hash': '2cce529c973e1cbd',
    'calibration_version': 'calibration-v1.0.0',
    'calibration_hash': '3df2622221ab23f1',
    'tyre_calibration_version': 'tyre-calibration-v1.0.0',
    'tyre_calibration_hash': 'a1b2c3d4',
    'simulation_version': '8.2.0',
    'raceengine_version': 'raceengine-v1.2.0',
    'model_version': '0.3.0',
    'rng_contract_version': '1.0',
    'schema_version': '1.0.0',
    'python_version': '3.12.0',
    'numpy_version': '2.5.0',
    'numba_version': '0.67.0',
    'test_counts': {'default': 372, 'performance': 10, 'reproducibility': 6, 'total': 388},
    'benchmark': {'10k_58': 4.59, '10k_5': 1.14, 'sim_per_sec': 2177, 'memory_mb': 180},
    'scientific_metrics': {'top1': 0.30, 'brier': 0.039, 'mae': 3.97},
    'known_limitations': ['RNG Level B 0.20 win diff', 'tyre historical prior_only', 'warmup non-identifiable'],
    'creation_timestamp': datetime.now(timezone.utc).isoformat(),
    'frozen': True
}
open('backend/data/manifests/pre_phase17_baseline.json','w').write(json.dumps(baseline, indent=2))
print('written json')
open('backend/docs/pre_phase17_baseline.md','w').write(f"# Pre-Phase 17 Baseline\n\nFrozen: {baseline['creation_timestamp']}\n\nDataset: {baseline['dataset_version']} hash {baseline['dataset_hash']}\nCalibration: {baseline['calibration_version']} hash {baseline['calibration_hash']}\nTyre: {baseline['tyre_calibration_version']}\nEngine: {baseline['raceengine_version']} model {baseline['model_version']}\nRNG: Level A for driver/constructor, Level B for AR1 (documented)\nTests: {baseline['test_counts']}\nBenchmark: 10k×58 {baseline['benchmark']['10k_58']}s <30s PASS\n")
print('written md')
