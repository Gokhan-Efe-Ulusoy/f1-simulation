# Performance

Join/calibration offline 30s, production simulation must not receive NDL tensors, precompute compact coefficients (3 compounds) overhead <10% (N=1000 8.1->8.3s, N=10000 41->42s)
Memory bounded, no (N,D,L,tyre) tensors
