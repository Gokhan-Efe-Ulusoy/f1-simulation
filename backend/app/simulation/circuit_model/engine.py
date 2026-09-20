"""Circuit engine - deterministic, compact tables."""
from __future__ import annotations
from .baseline import load_circuit_model

class CircuitEngine:
    def __init__(self):
        self.model=load_circuit_model()
    def get_circuit_effect(self, circuit_id: str):
        return self.model["circuit_effects"].get(circuit_id, {"estimate":0,"evidence_tier":"PRIOR_ONLY"})  # noqa: E501
    def predict(self, circuit_id: str, season: int):
        base=self.model["global_baseline"]
        ce=self.get_circuit_effect(circuit_id)["estimate"]
        return base+ce
