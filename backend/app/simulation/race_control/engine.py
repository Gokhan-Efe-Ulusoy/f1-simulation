"""RaceControlEngine — deterministic, vectorized (N,L) generation + sequential state machine.

Uses isolated RNG stream (600) and explicit policy.
"""
from __future__ import annotations

import numpy as np

from app.simulation.race_control.models import EvidenceTier, IncidentSeverity, RaceControlState, RaceEventType  # noqa: E501
from app.simulation.race_control.policy import RaceControlPolicy, DEFAULT_RACE_CONTROL_POLICY, IncidentAssessment  # noqa: E501
from app.simulation.race_control.rng import race_control_rng, deterministic_event_id
from app.simulation.race_control.kernels import PHASE_GREEN, PHASE_YELLOW, PHASE_DOUBLE_YELLOW, PHASE_VSC, PHASE_SAFETY_CAR, PHASE_RED_FLAG, PHASE_FORMATION_LAP, PHASE_START, PHASE_RESTART, PHASE_CHEQUERED_FLAG, PHASE_RACE_SUSPENDED, PHASE_RACE_RESUMED, PHASE_MAP  # noqa: E501
from app.simulation.race_control.state_machine import VALID_TRANSITIONS, PRIORITY, resolve_highest_priority  # noqa: E501

# Reverse
INT_TO_PHASE = {v: k for k, v in PHASE_MAP.items()}

# Duration priors as lap counts (PRIOR_ONLY)
YELLOW_LAPS = 1
DOUBLE_YELLOW_LAPS = 1


def _severity_from_incident_type(incident_type_str: str, is_retirement: bool) -> IncidentSeverity:
    if is_retirement:
        return IncidentSeverity.SEVERE if np.random.random() < 0.5 else IncidentSeverity.MAJOR  # placeholder, actual decision uses policy roll  # noqa: E501
    s = incident_type_str.lower()
    if s in ("collision", "track_blockage", "stopped_car", "obstruction"):
        return IncidentSeverity.MAJOR
    if s in ("spin", "off_track", "debris"):
        return IncidentSeverity.MODERATE
    if s in ("lockup",):
        return IncidentSeverity.MINOR
    return IncidentSeverity.MODERATE


class RaceControlEngine:
    """Generates race-level trajectories (N,L) and handles sequential transitions."""

    def __init__(
        self,
        policy: RaceControlPolicy | None = None,
        num_sectors: int = 3,
        seed: int = 42,
        race_id: str = "race",
        enable_yellow: bool = True,
        enable_vsc: bool = True,
        enable_safety_car: bool = True,
        enable_red_flag: bool = True,
        enable_first_lap_incidents: bool = True,
        weather_coupling: bool = True,
    ):
        self.policy = policy or DEFAULT_RACE_CONTROL_POLICY
        self.num_sectors = num_sectors
        self.seed = seed
        self.race_id = race_id
        self.enable_yellow = enable_yellow
        self.enable_vsc = enable_vsc
        self.enable_safety_car = enable_safety_car
        self.enable_red_flag = enable_red_flag
        self.enable_first_lap_incidents = enable_first_lap_incidents
        self.weather_coupling = weather_coupling

    # ------------------------------------------------------------------
    # Vectorized batch generation — returns (N,L) int phases + (N,L,S) sector flags
    # ------------------------------------------------------------------
    def generate_batch(
        self,
        N: int,
        L: int,
        base_seed: int,
        weather_wetness_traj: np.ndarray | None = None,  # (N,L) or None
        weather_rainfall_traj: np.ndarray | None = None,  # (N,L)
        reference_incident_prob: float = 0.008,  # per lap per sim aggregated
        first_lap_multiplier: float | None = None,
    ) -> dict:
        """Deterministic (N,L) race-control generation; shared across drivers.

        Strategy: walk per-sim sequential with isolated RNG; still vectorized storage.
        This preserves explicit state machine & avoids per-driver blow up.
        """
        if first_lap_multiplier is None:
            first_lap_multiplier = self.policy.start_incident_multiplier

        # Allocate
        phase = np.full((N, L), PHASE_GREEN, dtype=np.int8)
        sector_flags = np.zeros((N, L, self.num_sectors), dtype=np.int8)
        # Lap counters for durations
        # We'll walk per sim
        # Store reason per sim per lap for debugging? Not needed
        for sim in range(N):
            # Use per-sim sequential state machine
            cur = PHASE_GREEN
            # Durations remaining
            sc_remaining = 0
            vsc_remaining = 0
            yellow_remaining = 0
            double_remaining = 0
            red_remaining = 0
            restart_pending = False
            # Track consecutive wet laps for red flag
            consec_wet = 0
            for lap_idx in range(L):
                lap = lap_idx + 1
                rng = race_control_rng(base_seed, sim, lap)

                # If restart pending, transition to GREEN after one lap of RESTART
                if cur == PHASE_RESTART:
                    # Next lap becomes GREEN deterministically
                    cur = PHASE_GREEN
                    restart_pending = False
                    phase[sim, lap_idx] = cur
                    continue

                # Handle ongoing durations (count down) — stay in phase for remaining laps, then transition next lap
                if cur == PHASE_SAFETY_CAR and sc_remaining > 0:
                    # This lap remains SC
                    phase[sim, lap_idx] = cur
                    sc_remaining -= 1
                    if sc_remaining == 0:
                        # Next lap will be RESTART (transition deferred)
                        # Mark for next iteration by setting cur to RESTART at start of next lap; for now keep SC this lap
                        # Instead we set pending transition flag via sc_remaining==0 and cur still SC; next lap top will detect RESTART case
                        # Set cur to RESTART for next lap handling
                        # Use a sentinel: set a flag by setting sc_remaining=-1 to trigger restart
                        sc_remaining = -1  # signals next lap is RESTART
                    continue
                if sc_remaining == -1:
                    # Previous SC ended, this lap is RESTART
                    cur = PHASE_RESTART
                    phase[sim, lap_idx] = cur
                    sc_remaining = 0
                    continue
                if cur == PHASE_VSC and vsc_remaining > 0:
                    phase[sim, lap_idx] = cur
                    vsc_remaining -= 1
                    if vsc_remaining == 0:
                        # At end of VSC, decide escalation for next lap
                        if self.enable_safety_car and rng.random() < 0.2:
                            cur = PHASE_SAFETY_CAR
                            sc_remaining = int(rng.integers(self.policy.sc_duration_laps[0], self.policy.sc_duration_laps[1] + 1))  # noqa: E501
                            # Don't set phase now; next lap will be SC. Keep current lap as VSC (already set). Defer.
                            # Store pending SC for next lap: we need to remember cur for next iteration. Set a flag.
                            # We set cur for next iteration via keeping cur as VSC? Instead set pending
                            # Simple: set vsc_remaining=-1 to signal escalate
                            vsc_remaining = -2  # special: next phase SC
                        else:
                            # Next lap GREEN
                            cur = PHASE_GREEN
                            vsc_remaining = -1  # will transition to GREEN next lap
                        # Keep current lap as VSC (already set), defer transition
                        # To defer, we need to keep cur as VSC this lap and set next lap's cur accordingly
                        # So revert cur for now
                        cur = PHASE_VSC
                        phase[sim, lap_idx] = cur
                        # But we already decremented and set flag; continue will go to next lap where we handle -1/-2
                    continue
                if vsc_remaining == -1:
                    cur = PHASE_GREEN
                    phase[sim, lap_idx] = cur
                    vsc_remaining = 0
                    continue
                if vsc_remaining == -2:
                    cur = PHASE_SAFETY_CAR
                    phase[sim, lap_idx] = cur
                    # Already sampled sc_remaining above
                    vsc_remaining = 0
                    continue
                if cur == PHASE_RED_FLAG and red_remaining > 0:
                    phase[sim, lap_idx] = cur
                    red_remaining -= 1
                    if red_remaining == 0:
                        red_remaining = -1  # next lap restart/chequered
                    continue
                if red_remaining == -1:
                    if lap_idx >= L - 3:
                        cur = PHASE_CHEQUERED_FLAG
                    else:
                        cur = PHASE_RESTART
                    phase[sim, lap_idx] = cur
                    red_remaining = 0
                    continue
                if cur in (PHASE_YELLOW, PHASE_DOUBLE_YELLOW) and (yellow_remaining > 0 or double_remaining > 0):  # noqa: E501
                    # Stay yellow/double
                    phase[sim, lap_idx] = cur
                    if cur == PHASE_YELLOW and yellow_remaining > 0:
                        yellow_remaining -= 1
                    if cur == PHASE_DOUBLE_YELLOW and double_remaining > 0:
                        double_remaining -= 1
                    # Preserve sector flags for continuity
                    if lap_idx > 0:
                        if np.all(sector_flags[sim, lap_idx, :] == 0):
                            sector_flags[sim, lap_idx, :] = sector_flags[sim, lap_idx - 1, :]
                    # If durations exhausted, next lap will decide escalation or green (deferred)
                    if (cur == PHASE_YELLOW and yellow_remaining == 0) or (cur == PHASE_DOUBLE_YELLOW and double_remaining == 0):  # noqa: E501
                        # Mark for next lap transition via pending
                        # Use remaining=-1 to signal end
                        if cur == PHASE_YELLOW:
                            yellow_remaining = -1
                        else:
                            double_remaining = -1
                    continue
                if yellow_remaining == -1 or double_remaining == -1:
                    # End of yellow period — decide escalation
                    if yellow_remaining == -1:
                        yellow_remaining = 0
                        # 10% to VSC
                        if self.enable_vsc and rng.random() < 0.10:
                            cur = PHASE_VSC
                            vsc_remaining = int(rng.integers(self.policy.vsc_duration_laps[0], self.policy.vsc_duration_laps[1] + 1)) - 1  # noqa: E501
                            phase[sim, lap_idx] = cur
                            continue
                        elif self.enable_safety_car and rng.random() < 0.05:
                            cur = PHASE_SAFETY_CAR
                            sc_remaining = int(rng.integers(self.policy.sc_duration_laps[0], self.policy.sc_duration_laps[1] + 1)) - 1  # noqa: E501
                            phase[sim, lap_idx] = cur
                            continue
                        else:
                            cur = PHASE_GREEN
                            sector_flags[sim, lap_idx, :] = 0
                            phase[sim, lap_idx] = cur
                            continue
                    if double_remaining == -1:
                        double_remaining = 0
                        if self.enable_safety_car and rng.random() < 0.15:
                            cur = PHASE_SAFETY_CAR
                            sc_remaining = int(rng.integers(self.policy.sc_duration_laps[0], self.policy.sc_duration_laps[1] + 1)) - 1  # noqa: E501
                            phase[sim, lap_idx] = cur
                            continue
                        elif self.enable_vsc and rng.random() < 0.20:
                            cur = PHASE_VSC
                            vsc_remaining = int(rng.integers(self.policy.vsc_duration_laps[0], self.policy.vsc_duration_laps[1] + 1)) - 1  # noqa: E501
                            phase[sim, lap_idx] = cur
                            continue
                        else:
                            cur = PHASE_GREEN
                            sector_flags[sim, lap_idx, :] = 0
                            phase[sim, lap_idx] = cur
                            continue

                # If currently GREEN, evaluate triggers for this lap
                if cur == PHASE_GREEN:
                    # Weather -> race control pre-emptive (before incident)
                    if self.weather_coupling and weather_wetness_traj is not None and weather_rainfall_traj is not None:  # noqa: E501
                        w = float(weather_wetness_traj[sim, lap_idx])
                        r = float(weather_rainfall_traj[sim, lap_idx])
                        if w >= 0.5:
                            consec_wet += 1
                        else:
                            consec_wet = 0
                        from app.simulation.race_control.policy import RaceControlDecision
                        vis = 1.0  # placeholder visibility
                        dec = self.policy.decide_for_weather(r, w, vis if w < 0.8 else 0.6, consec_wet)  # noqa: E501
                        if dec == RaceControlDecision.RED_FLAG and self.enable_red_flag:
                            # Extreme: deploy red
                            # Enforce red only if enough laps remain
                            if lap_idx < L - 5:
                                cur = PHASE_RED_FLAG
                                red_remaining = int(rng.integers(self.policy.red_flag_duration_laps[0], self.policy.red_flag_duration_laps[1] + 1)) - 1  # noqa: E501
                                phase[sim, lap_idx] = cur
                                continue
                        elif dec == RaceControlDecision.SAFETY_CAR and self.enable_safety_car:
                            cur = PHASE_SAFETY_CAR
                            sc_remaining = int(rng.integers(self.policy.sc_duration_laps[0], self.policy.sc_duration_laps[1] + 1)) - 1  # noqa: E501
                            phase[sim, lap_idx] = cur
                            continue
                        elif dec == RaceControlDecision.VSC and self.enable_vsc:
                            cur = PHASE_VSC
                            vsc_remaining = int(rng.integers(self.policy.vsc_duration_laps[0], self.policy.vsc_duration_laps[1] + 1)) - 1  # noqa: E501
                            phase[sim, lap_idx] = cur
                            continue

                    # Incident -> race control (aggregate per-sim probability)
                    prob = reference_incident_prob
                    if lap == 1 and self.enable_first_lap_incidents:
                        prob *= first_lap_multiplier
                    elif lap == 2:
                        prob *= self.policy.first_lap_density_multiplier * 0.5
                    # Weather increases incident prob slightly via wetness prior (small)
                    if weather_wetness_traj is not None:
                        wet = float(weather_wetness_traj[sim, lap_idx])
                        prob *= (1.0 + wet * 0.6)  # PRIOR_ONLY modest

                    if rng.random() < prob:
                        # Sample severity via policy distribution (prior)
                        # Use same distribution as incident model: MINOR 0.5, MOD 0.3, MAJOR 0.15, SEVERE 0.05
                        roll = rng.random()
                        if roll < 0.5:
                            sev = IncidentSeverity.MINOR
                        elif roll < 0.8:
                            sev = IncidentSeverity.MODERATE
                        elif roll < 0.95:
                            sev = IncidentSeverity.MAJOR
                        else:
                            sev = IncidentSeverity.SEVERE
                        is_ret = sev == IncidentSeverity.SEVERE and rng.random() < 0.4
                        block = sev in (IncidentSeverity.MAJOR, IncidentSeverity.SEVERE) and rng.random() < 0.35  # noqa: E501
                        marshal = sev != IncidentSeverity.MINOR
                        assess = IncidentAssessment(severity=sev, is_retirement=is_ret, causes_blockage=block, requires_marshal=marshal)  # noqa: E501
                        dec = self.policy.decide_for_incident(assess, rng)
                        # Map decision to phase respecting enable flags
                        if dec.value == "NO_ACTION":
                            cur = PHASE_GREEN
                        elif dec.value == "YELLOW" and self.enable_yellow:
                            cur = PHASE_YELLOW
                            yellow_remaining = self.policy.yellow_duration_laps - 1
                            # assign sector
                            sec = int(rng.integers(0, self.num_sectors))
                            sector_flags[sim, lap_idx, sec] = 1
                            # also propagate to next lap if duration>1? handled via counter
                            if yellow_remaining > 0:
                                # mark next laps yellow sectors as well? We'll propagate in loop
                                pass
                        elif dec.value == "DOUBLE_YELLOW" and self.enable_yellow:
                            cur = PHASE_DOUBLE_YELLOW
                            double_remaining = self.policy.double_yellow_duration_laps - 1
                            sec = int(rng.integers(0, self.num_sectors))
                            sector_flags[sim, lap_idx, sec] = 2
                            # often double yellows affect 2 sectors
                            if rng.random() < 0.5:
                                sec2 = (sec + 1) % self.num_sectors
                                sector_flags[sim, lap_idx, sec2] = 2
                        elif dec.value == "VSC" and self.enable_vsc:
                            cur = PHASE_VSC
                            vsc_remaining = int(rng.integers(self.policy.vsc_duration_laps[0], self.policy.vsc_duration_laps[1] + 1)) - 1  # noqa: E501
                        elif dec.value == "SAFETY_CAR" and self.enable_safety_car:
                            cur = PHASE_SAFETY_CAR
                            sc_remaining = int(rng.integers(self.policy.sc_duration_laps[0], self.policy.sc_duration_laps[1] + 1)) - 1  # noqa: E501
                        elif dec.value == "RED_FLAG" and self.enable_red_flag:
                            if lap_idx < L - 4:  # enough to restart
                                cur = PHASE_RED_FLAG
                                red_remaining = int(rng.integers(self.policy.red_flag_duration_laps[0], self.policy.red_flag_duration_laps[1] + 1)) - 1  # noqa: E501
                            else:
                                # near end -> SC instead
                                cur = PHASE_SAFETY_CAR
                                sc_remaining = int(rng.integers(self.policy.sc_duration_laps[0], self.policy.sc_duration_laps[1] + 1)) - 1  # noqa: E501
                        else:
                            # if disabled, fallback to next lower enabled
                            if dec.value in ("VSC", "SAFETY_CAR", "RED_FLAG") and not self.enable_safety_car and not self.enable_vsc:  # noqa: E501
                                cur = PHASE_DOUBLE_YELLOW
                                double_remaining = 0
                                sec = int(rng.integers(0, self.num_sectors))
                                sector_flags[sim, lap_idx, sec] = 2
                            else:
                                cur = PHASE_GREEN
                        phase[sim, lap_idx] = cur
                        continue
                    else:
                        phase[sim, lap_idx] = PHASE_GREEN
                        continue

                # If currently neutralised beyond GREEN but duration not handled (should not happen)
                phase[sim, lap_idx] = cur

            # Post-process: ensure sector flags persistence for duration laps (yellow spans)
            # We already set current lap sector but not future; fix by forward fill for active durations
            # For simplicity, propagate yellow sectors forward for remaining duration
            for lap_idx in range(L):
                p = phase[sim, lap_idx]
                if p in (PHASE_YELLOW, PHASE_DOUBLE_YELLOW):
                    # if sector flags empty (duration extension), copy from previous lap
                    if np.all(sector_flags[sim, lap_idx, :] == 0) and lap_idx > 0:
                        sector_flags[sim, lap_idx, :] = sector_flags[sim, lap_idx - 1, :]

        # Formation lap handling: first lap phase FORMATION if we inject? For now keep GREEN for batch; formation handled separately in sequential engine.
        # CHEQUERED: last lap if not already
        for sim in range(N):
            if phase[sim, -1] not in (PHASE_CHEQUERED_FLAG, PHASE_RED_FLAG, PHASE_RACE_SUSPENDED):
                # Keep last as GREEN; chequered event not represented as phase in trajectory (terminal state after race)
                pass

        return {"phase": phase, "sector_flags": sector_flags}

    # ------------------------------------------------------------------
    # Sequential single-race generation (for RaceEngine core path)
    # ------------------------------------------------------------------
    def next_state(
        self,
        current_phase: int,
        lap: int,
        rng,
        weather_wetness: float = 0.0,
        rainfall: float = 0.0,
        visibility: float = 1.0,
        incident_severity: IncidentSeverity | None = None,
        incident_is_retirement: bool = False,
        incident_causes_blockage: bool = False,
        consec_wet_laps: int = 0,
        counters: dict | None = None,
    ) -> tuple[int, dict]:
        """Sequential step used by core RaceEngine. Returns (new_phase, updated_counters)."""
        if counters is None:
            counters = {"sc": 0, "vsc": 0, "yellow": 0, "double": 0, "red": 0}

        # Handle ongoing counters first
        if counters["sc"] > 0:
            counters["sc"] -= 1
            if counters["sc"] == 0:
                return PHASE_RESTART, counters
            return PHASE_SAFETY_CAR, counters
        if counters["vsc"] > 0:
            counters["vsc"] -= 1
            if counters["vsc"] == 0:
                # escalate or green?
                if self.enable_safety_car and rng.random() < 0.2:
                    counters["sc"] = int(rng.integers(self.policy.sc_duration_laps[0], self.policy.sc_duration_laps[1] + 1)) - 1  # noqa: E501
                    return PHASE_SAFETY_CAR, counters
                return PHASE_GREEN, counters
            return PHASE_VSC, counters
        if counters["red"] > 0:
            counters["red"] -= 1
            if counters["red"] == 0:
                return PHASE_RESTART, counters
            return PHASE_RED_FLAG, counters
        if counters["yellow"] > 0:
            counters["yellow"] -= 1
            if counters["yellow"] == 0:
                return PHASE_GREEN, counters
            return PHASE_YELLOW, counters
        if counters["double"] > 0:
            counters["double"] -= 1
            if counters["double"] == 0:
                return PHASE_GREEN, counters
            return PHASE_DOUBLE_YELLOW, counters
        if current_phase == PHASE_RESTART:
            return PHASE_GREEN, counters

        # If GREEN evaluate triggers
        if current_phase == PHASE_GREEN:
            # weather coupling
            if self.weather_coupling:
                from app.simulation.race_control.policy import RaceControlDecision

                dec = self.policy.decide_for_weather(rainfall, weather_wetness, visibility, consec_wet_laps)  # noqa: E501
                if dec == RaceControlDecision.RED_FLAG and self.enable_red_flag:
                    counters["red"] = int(rng.integers(self.policy.red_flag_duration_laps[0], self.policy.red_flag_duration_laps[1] + 1)) - 1  # noqa: E501
                    return PHASE_RED_FLAG, counters
                if dec == RaceControlDecision.SAFETY_CAR and self.enable_safety_car:
                    counters["sc"] = int(rng.integers(self.policy.sc_duration_laps[0], self.policy.sc_duration_laps[1] + 1)) - 1  # noqa: E501
                    return PHASE_SAFETY_CAR, counters
                if dec == RaceControlDecision.VSC and self.enable_vsc:
                    counters["vsc"] = int(rng.integers(self.policy.vsc_duration_laps[0], self.policy.vsc_duration_laps[1] + 1)) - 1  # noqa: E501
                    return PHASE_VSC, counters

            if incident_severity is not None:
                assess = IncidentAssessment(
                    severity=incident_severity, is_retirement=incident_is_retirement, causes_blockage=incident_causes_blockage, requires_marshal=incident_severity != IncidentSeverity.MINOR  # noqa: E501
                )
                dec = self.policy.decide_for_incident(assess, rng)
                if dec.value == "YELLOW" and self.enable_yellow:
                    counters["yellow"] = self.policy.yellow_duration_laps - 1
                    return PHASE_YELLOW, counters
                if dec.value == "DOUBLE_YELLOW" and self.enable_yellow:
                    counters["double"] = self.policy.double_yellow_duration_laps - 1
                    return PHASE_DOUBLE_YELLOW, counters
                if dec.value == "VSC" and self.enable_vsc:
                    counters["vsc"] = int(rng.integers(self.policy.vsc_duration_laps[0], self.policy.vsc_duration_laps[1] + 1)) - 1  # noqa: E501
                    return PHASE_VSC, counters
                if dec.value == "SAFETY_CAR" and self.enable_safety_car:
                    counters["sc"] = int(rng.integers(self.policy.sc_duration_laps[0], self.policy.sc_duration_laps[1] + 1)) - 1  # noqa: E501
                    return PHASE_SAFETY_CAR, counters
                if dec.value == "RED_FLAG" and self.enable_red_flag:
                    counters["red"] = int(rng.integers(self.policy.red_flag_duration_laps[0], self.policy.red_flag_duration_laps[1] + 1)) - 1  # noqa: E501
                    return PHASE_RED_FLAG, counters

        return current_phase, counters
