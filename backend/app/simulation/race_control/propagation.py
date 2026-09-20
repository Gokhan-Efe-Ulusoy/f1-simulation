"""Deterministic event propagation — queue with causal chaining."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.simulation.race_control.models import RaceEvent
from app.simulation.race_control.rng import deterministic_event_id


@dataclass
class EventQueue:
    """Deterministic FIFO with priority resolution per lap."""

    race_id: str
    _events: list[RaceEvent] = field(default_factory=list)
    _counter: int = 0

    def push(
        self,
        event_type,
        lap: int,
        sector: int = -1,
        driver_ids: list[str] | None = None,
        severity=None,
        trigger: str | None = None,
        cause: str | None = None,
        parent_event_id: str | None = None,
        evidence_tier=None,
        metadata: dict | None = None,
    ) -> RaceEvent:
        self._counter += 1
        eid = deterministic_event_id(self.race_id, lap, self._counter)
        from app.simulation.race_control.models import EvidenceTier

        ev = RaceEvent(
            id=eid,
            event_type=event_type,
            lap=lap,
            sector=sector,
            driver_ids=driver_ids or [],
            severity=severity,
            trigger=trigger,
            cause=cause,
            parent_event_id=parent_event_id,
            evidence_tier=evidence_tier or EvidenceTier.PRIOR_ONLY,
            metadata=metadata or {},
        )
        self._events.append(ev)
        return ev

    def for_lap(self, lap: int) -> list[RaceEvent]:
        return [e for e in self._events if e.lap == lap]

    def active_ids(self, lap: int) -> list[str]:
        return [e.id for e in self._events if e.lap == lap and not e.resolved]

    def resolve(self, event_id: str) -> None:
        for e in self._events:
            if e.id == event_id:
                e.resolved = True
                break

    def all_events(self) -> list[RaceEvent]:
        return list(self._events)

    def sorted_by_causality(self) -> list[RaceEvent]:
        # Parent before child, then by lap, then id
        def key(e: RaceEvent):
            return (e.lap, 0 if e.parent_event_id is None else 1, e.id)

        return sorted(self._events, key=key)
