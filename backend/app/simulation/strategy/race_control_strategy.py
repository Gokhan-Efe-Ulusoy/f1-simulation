"""Race Control Strategy — VSC/SC/RED awareness."""
from __future__ import annotations


class RaceControlStrategyEngine:
    def __init__(self):
        pass

    def pit_opportunity(
        self, phase: str, pit_loss_green: float
    ) -> tuple[float, str]:
        if phase == "SAFETY_CAR":
            return pit_loss_green * 0.35, "SC cheap"
        if phase == "VSC":
            return pit_loss_green * 0.55, "VSC cheap"
        if phase in ("YELLOW", "DOUBLE_YELLOW"):
            return pit_loss_green * 0.90, "yellow slightly cheap"
        if phase == "RED_FLAG":
            return 0.0, "RED_FLAG free"
        return pit_loss_green, "green"
