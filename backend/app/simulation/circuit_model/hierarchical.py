"""Hierarchical shrinkage implementation (global->era->circuit->circuit_era)."""
from __future__ import annotations
import statistics

def shrink(raw: float, n: int, tau: float, prior: float=0.0):
    w=n/(n+tau) if (n+tau)>0 else 0
    return raw*w + prior*(1-w), w
