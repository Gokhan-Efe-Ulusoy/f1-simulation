# Counterfactual Sanity

- increase tyre degradation -> slower pace expected: model predicts faster due to negative beta -> FAIL, indicates misspecification
- increase tyre age -> slower expected but model predicts faster -> FAIL
- reset tyre age -> faster expected: model predicts slower -> FAIL
- change compound soft->hard -> slower expected: model shows hard less negative than soft -> plausible but not causal
- move pit earlier/later -> not tested due to fuel confounding
Many expected directionality fail due to negative beta -> indicates model not physically sensible, do not promote
