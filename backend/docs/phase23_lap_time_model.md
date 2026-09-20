# Lap-Time Performance Model

Baseline 93.943s n=552029
Decomposition: baseline + driver + constructor + circuit + tyre + tyre_age + progression + traffic + residual
Controls: qualifying vs race vs SC etc where observable; sector LIMITED/NON_IDENTIFIABLE due to insufficient sector data
Driver shrunk effects sample: [('aitken', {'n': 86, 'raw': -30.99220866865901, 'se': 1.079435364783077, 'shrunk': -26.389405401036385}), ('albon', {'n': 3447, 'raw': -1.570366200317821, 'se': 0.2935848559225211, 'shrunk': -1.563562187318177})]
Circuit shrunk effects: 41 circuits, hierarchical
Evidence tier LIMITED, train/val/test via walk-forward, stability across folds moderate, no training-only promotion
