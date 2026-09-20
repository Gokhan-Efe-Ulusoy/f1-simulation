"""Phase 28 — Replay service (thin wrapper over ReplayEngine)."""

from __future__ import annotations

from typing import Any

from app.simulation.replay.checkpoints import valid_checkpoints
from app.simulation.replay.replay_engine import ReplayEngine


def replay_race(
    race_id: str,
    seed: int | None = None,
    simulations: int = 100,
    laps: int | None = None,
    checkpoint: str | None = None,
) -> dict[str, Any]:
    seed_val = int(seed) if seed is not None else 42
    sims = int(simulations) if simulations is not None else 100
    if not (1 <= sims <= 5000):
        raise ValueError("simulations must be 1..5000")
    if seed is not None and not (-(2**31) <= seed <= 2**31 - 1):
        raise ValueError("seed out of int32 range")

    engine = ReplayEngine(seed=seed_val, simulations=sims)

    # Single checkpoint mode
    if checkpoint is not None:
        # checkpoint may be lap number or name like lap_5, pre_race, finish
        # Try to parse lap
        lap_val: int | None = None
        low = str(checkpoint).lower().strip()
        if low.startswith("lap_"):
            try:
                lap_val = int(low.split("_")[1])
            except Exception:
                lap_val = None
        elif low in ("pre_race", "prerace", "formation", "pre-race"):
            lap_val = 0
        elif low == "finish":
            # need total laps
            try:
                from app.simulation.replay.state_builder import load_historical_race

                h = load_historical_race(race_id)
                lap_val = int(h.total_laps or 58)
            except Exception:
                lap_val = 58
        else:
            try:
                lap_val = int(checkpoint)
            except Exception as err:
                raise ValueError(f"unknown checkpoint {checkpoint!r}") from err

        # For lap 0 pre_race, treat as lap 1 truncated?
        if lap_val is not None and lap_val <= 0:
            # pre_race: return replay with only pre_race checkpoint
            base = engine.replay(
                race_id=race_id, seed=seed_val, simulations=sims, laps=laps, with_checkpoints=False
            )
            # build a synthetic checkpoint result for pre_race
            data = base.model_dump() if hasattr(base, "model_dump") else dict(base)  # type: ignore[attr-defined]  # noqa: E501
            # inject single checkpoint
            ck = engine.checkpoint(race_id=race_id, lap=1, seed=seed_val, simulations=sims)
            ckd = ck.model_dump() if hasattr(ck, "model_dump") else dict(ck)  # type: ignore[attr-defined]  # noqa: E501
            ckd["name"] = "pre_race"
            ckd["lap"] = 0
            return {
                "race_id": data.get("race_id"),
                "seed": data.get("seed"),
                "simulations": data.get("simulations"),
                "laps": data.get("laps"),
                "checkpoint": ckd,
                "checkpoint_name": "pre_race",
                "checkpoints": [ckd],
                "deviation_metrics": data.get("deviation_metrics").model_dump()
                if hasattr(data.get("deviation_metrics"), "model_dump")
                else data.get("deviation_metrics"),
                "provenance": data.get("provenance"),
                "evidence_summary": data.get("evidence_summary"),
                "raw": data,
            }

        ck = engine.checkpoint(race_id=race_id, lap=int(lap_val), seed=seed_val, simulations=sims)
        ckd = ck.model_dump() if hasattr(ck, "model_dump") else dict(ck)  # type: ignore[attr-defined]  # noqa: E501
        # also need race context
        return {
            "race_id": race_id,
            "seed": seed_val,
            "simulations": sims,
            "laps": int(lap_val),
            "checkpoint": ckd,
            "checkpoint_name": ckd.get("name"),
            "checkpoints": [ckd],
            "provenance": ckd.get("provenance"),
            "raw": ckd,
        }

    # Full replay
    result = engine.replay(
        race_id=race_id, seed=seed_val, simulations=sims, laps=laps, with_checkpoints=True
    )
    data = result.model_dump() if hasattr(result, "model_dump") else dict(result)  # type: ignore[attr-defined]  # noqa: E501

    # Ensure checkpoint_results are serializable
    cps = []
    for c in data.get("checkpoint_results") or []:
        # c may already be dict
        if hasattr(c, "model_dump"):
            cps.append(c.model_dump())  # type: ignore[attr-defined]
        else:
            cps.append(dict(c))

    return {
        "race_id": data.get("race_id"),
        "seed": data.get("seed"),
        "simulations": data.get("simulations"),
        "laps": data.get("laps"),
        "baseline_fingerprint": data.get("baseline_fingerprint"),
        "checkpoint_results": cps,
        "checkpoints": cps,
        "deviation_metrics": (
            data.get("deviation_metrics").model_dump()
            if hasattr(data.get("deviation_metrics"), "model_dump")
            else data.get("deviation_metrics")
        )
        if data.get("deviation_metrics")
        else None,
        "observed_result": data.get("observed_result"),
        "provenance": data.get("provenance"),
        "evidence_summary": data.get("evidence_summary"),
        "raw": data,
    }


def get_checkpoint_valid_names(total_laps: int | None = None) -> list[str]:
    return valid_checkpoints(total_laps)
