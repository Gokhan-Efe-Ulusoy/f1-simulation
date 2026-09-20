"""Tyre age validation."""
from __future__ import annotations
from typing import List, Dict

def validate_stint(stint: Dict, laps: List[Dict]) -> List[str]:
    errors=[]
    ages=[]
    for lap in sorted(laps, key=lambda x: x["lap_number"]):
        age=stint["tyre_age_at_start"] + (lap["lap_number"]-stint["lap_start"])
        ages.append(age)
        if age <0:
            errors.append("negative_age")
    # monotonic
    for i in range(1,len(ages)):
        if ages[i] < ages[i-1]:
            errors.append("non_monotonic")
            break
    return errors
