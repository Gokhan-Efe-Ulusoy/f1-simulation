"""Phase 28 — Scenario service (thin wrapper over ReplayEngine + ScenarioEngine)."""

from __future__ import annotations

from typing import Any

from app.simulation.replay.replay_engine import ReplayEngine
from app.simulation.scenario.models import Intervention


def compare_scenario(
    race_id: str,
    interventions: list[dict[str, Any]],
    seed: int | None = None,
    simulations: int = 100,
    laps: int | None = None,
    experiment_id: str | None = None,
    question: str | None = None,
) -> dict[str, Any]:
    if not interventions:
        raise ValueError("at least one intervention required")
    if len(interventions) > 20:
        raise ValueError("too many interventions (max 20)")
    if simulations is not None and not (1 <= simulations <= 5000):
        raise ValueError("simulations must be 1..5000")
    if seed is not None and not (-(2**31) <= seed <= 2**31 - 1):
        raise ValueError("seed out of int32 range")

    seed_val = int(seed) if seed is not None else 42
    sims = int(simulations) if simulations is not None else 100

    # Build Intervention objects (validation via Pydantic + registry)
    ivs: list[Intervention] = []
    for idx, raw in enumerate(interventions):
        # leakage blocklist early rejection (also enforced in validation)
        param = str(raw.get("parameter", ""))
        low = param.lower()
        leakage_subs = (
            "future_",
            "observed_result",
            "actual_",
            "realized",
            "final_position",
            "championship",
            "standing",
        )
        if any(s in low for s in leakage_subs):
            raise ValueError(f"intervention {idx} parameter {param!r} rejected: leakage blocklist")
        try:
            iv = Intervention.model_validate(raw)
        except Exception as e:
            raise ValueError(f"intervention {idx} invalid: {e}") from e
        ivs.append(iv)

    engine = ReplayEngine(seed=seed_val, simulations=sims)
    try:
        exp = engine.counterfactual(
            race_id=race_id,
            interventions=ivs,
            experiment_id=experiment_id or f"exp-{race_id}-api",
            question=question or "",
            seed=seed_val,
            simulations=sims,
            laps=laps,
        )
    except ValueError as e:
        # may be ScenarioValidationError or race not found
        msg = str(e)
        # map to structured codes upstream
        raise ValueError(msg) from e
    except Exception as e:
        raise RuntimeError(f"scenario execution failed: {e}") from e

    data = exp.model_dump() if hasattr(exp, "model_dump") else dict(exp)  # type: ignore[attr-defined]  # noqa: E501
    # Provide API-friendly view
    return {
        "experiment_id": data.get("experiment_id"),
        "race_id": data.get("race_id"),
        "seed": data.get("seed"),
        "simulations": data.get("simulations"),
        "spec": data.get("spec"),
        "trace": data.get("trace"),
        "comparison": (
            data.get("comparison").model_dump()
            if hasattr(data.get("comparison"), "model_dump")
            else data.get("comparison")
        )
        if data.get("comparison")
        else None,
        "attribution": (
            data.get("attribution").model_dump()
            if hasattr(data.get("attribution"), "model_dump")
            else data.get("attribution")
        )
        if data.get("attribution")
        else None,
        "crn_manifest": (
            data.get("crn_manifest").model_dump()
            if hasattr(data.get("crn_manifest"), "model_dump")
            else data.get("crn_manifest")
        )
        if data.get("crn_manifest")
        else None,
        "provenance": data.get("provenance"),
        "evidence": data.get("evidence"),
        "limitations": data.get("limitations"),
        "fingerprint": data.get("fingerprint"),
        "baseline_fingerprint": data.get("baseline_fingerprint"),
        "counterfactual_fingerprint": data.get("counterfactual_fingerprint"),
        "warnings": data.get("provenance", {}).get("compile_warnings", [])
        if isinstance(data.get("provenance"), dict)
        else [],
        "raw": data,
    }
