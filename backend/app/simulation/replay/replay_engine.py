"""Phase 22 — ReplayEngine: baseline replay + counterfactual replay.

Pipeline: HistoricalRace -> pre-race Scenario (observed result excluded) ->
engine leg(s) with common random numbers -> ReplayResult /
CounterfactualExperiment. No new RNG is introduced: compilation is
deterministic and both legs share the caller's seed.
"""
from __future__ import annotations

import hashlib
from typing import Any

from app.simulation.replay import (
    REPLAY_MODEL_VERSION,
    COUNTERFACTUAL_MODEL_VERSION,
)
from app.simulation.replay.models import (
    CheckpointResult,
    CounterfactualExperiment,
    CRNManifest,
    HistoricalRace,
    ReplayResult,
)

STREAM_MANIFEST: dict[str, str] = {
    "base_pace": "seed + sim_idx*1000 (per-sim Level A; constructor + driver)",
    "qualifying_noise": "seed + sim_idx*1000 + 2",
    "reliability": "seed + sim_idx*1000 + 3",
    "ar1_lap_noise": "seed + 100 + lap (Level B, documented)",
    "weather_trajectories": "WeatherEngine isolated stream (seed, sim_idx)",
    "race_control_trajectories": "RaceControlEngine isolated stream (seed, sim_idx)",
    "scenario_compile": "none: deterministic, no RNG consumed",
    "pit_loss": "none: deterministic fixed cost, no RNG consumed",
}


class ReplayEngine:
    """Historical replay + counterfactual replay over the existing engines."""

    def __init__(self, seed: int = 42, simulations: int = 60):
        self.seed = seed
        self.simulations = simulations

    # ------------------------------------------------------------------
    # Loading / scenario construction
    # ------------------------------------------------------------------
    def load_race(self, race_id: str) -> HistoricalRace:
        from app.simulation.replay.state_builder import load_historical_race

        return load_historical_race(race_id)

    def scenario_for_race(
        self, hrace: HistoricalRace, laps: int | None = None,
        scenario_type: str = "historical",
    ) -> Any:
        from app.simulation.replay.state_builder import build_scenario_for_race

        return build_scenario_for_race(hrace, laps=laps, scenario_type=scenario_type)

    def _simulate(self, scenario: Any, simulations: int, seed: int) -> dict[str, Any]:
        from app.simulation.race_engine_v22 import ReplayAwareRaceEngine

        eng = ReplayAwareRaceEngine(seed=seed)
        snapshot = scenario.model_copy(deep=True)
        return eng.simulate(snapshot, simulations=simulations, seed=seed)

    # ------------------------------------------------------------------
    # Baseline replay
    # ------------------------------------------------------------------
    def replay(
        self,
        race_id: str,
        seed: int | None = None,
        simulations: int | None = None,
        laps: int | None = None,
        with_checkpoints: bool = True,
    ) -> ReplayResult:
        from app.simulation.replay.checkpoints import checkpoint_lap, valid_checkpoints
        from app.simulation.replay.historical_observer import build_observation
        from app.simulation.replay.provenance import (
            build_experiment_provenance,
            experiment_fingerprint,
            model_versions,
        )
        from app.simulation.replay.validation import deviation_metrics
        from app.simulation.scenario.compiler import scenario_content_hash

        seed = self.seed if seed is None else int(seed)
        simulations = self.simulations if simulations is None else int(simulations)
        hrace = self.load_race(race_id)
        scenario = self.scenario_for_race(hrace, laps=laps)
        total = int((scenario.race_distance.get("laps") or 58))
        content_hash = scenario_content_hash(scenario)
        result = self._simulate(scenario, simulations, seed)
        fp = experiment_fingerprint(
            race_id, content_hash,
            {"kind": "baseline_replay", "laps": total},
            seed, simulations, model_versions(),
        )
        ckpts: list[CheckpointResult] = []
        if with_checkpoints:
            for name in valid_checkpoints(total):
                lap = checkpoint_lap(name, total)
                if lap <= 0:
                    continue
                leg_scen = self.scenario_for_race(hrace, laps=lap)
                leg = self._simulate(leg_scen, simulations, seed)
                wins = {
                    did: float(d.get("win_probability", 0.0) or 0.0)
                    for did, d in (leg.get("drivers", {}) or {}).items()
                }
                top = max(wins, key=lambda k: wins[k]) if wins else ""
                ckpts.append(CheckpointResult(
                    name=name,
                    lap=lap,
                    simulations=simulations,
                    seed=seed,
                    fingerprint=experiment_fingerprint(
                        race_id, scenario_content_hash(leg_scen),
                        {"kind": "checkpoint", "lap": lap},
                        seed, simulations, model_versions(),
                    ),
                    top_driver_by_win_prob=top,
                    top_win_probability=float(wins.get(top, 0.0)),
                    provenance={"engine": "replay-v22", "truncated_horizon": True},
                ))
        dev = deviation_metrics(result, hrace.observed_result, race_id)
        obs = build_observation(hrace, lap=0)
        prov = build_experiment_provenance(
            race_id, hrace.as_of, hrace.race_date, seed, simulations, total,
            extra={
                "replay_version": REPLAY_MODEL_VERSION,
                "scenario_content_hash": content_hash,
                "total_laps_tier": hrace.total_laps_tier,
            },
        )
        return ReplayResult(
            race_id=race_id,
            seed=seed,
            simulations=simulations,
            laps=total,
            baseline_fingerprint=fp,
            checkpoint_results=ckpts,
            deviation_metrics=dev,
            observed_result={k: dict(v) for k, v in hrace.observed_result.items()},
            provenance=prov,
            evidence_summary=dict(hrace.evidence_summary),
        )

    # ------------------------------------------------------------------
    # Counterfactual replay
    # ------------------------------------------------------------------
    def counterfactual(
        self,
        race_id: str,
        interventions: list[Any] | Any,
        experiment_id: str = "",
        question: str = "",
        seed: int | None = None,
        simulations: int | None = None,
        laps: int | None = None,
        scenario_type: str = "counterfactual",
    ) -> CounterfactualExperiment:
        from app.simulation.replay.attribution import build_attribution
        from app.simulation.replay.comparison import extended_compare
        from app.simulation.replay.provenance import (
            build_experiment_provenance,
            experiment_fingerprint,
            model_versions,
        )
        from app.simulation.scenario.compiler import (
            baseline_fingerprint,
            compile_spec,
            scenario_content_hash,
            spec_fingerprint,
        )
        from app.simulation.scenario.engine import ScenarioEngine
        from app.simulation.scenario.models import ScenarioSpec

        seed = self.seed if seed is None else int(seed)
        simulations = self.simulations if simulations is None else int(simulations)
        hrace = self.load_race(race_id)
        baseline = self.scenario_for_race(hrace, laps=laps)
        total = int((baseline.race_distance.get("laps") or 58))
        ivs = list(interventions) if isinstance(interventions, list) else [interventions]
        experiment_id = experiment_id or f"exp-{race_id}-cf"
        spec = ScenarioSpec(
            spec_id=experiment_id,
            baseline_scenario_id=baseline.scenario_id,
            scenario_type=scenario_type,  # type: ignore[arg-type]
            interventions=ivs,
            seed=seed,
            simulations=simulations,
            reason=question,
        )
        eng = ScenarioEngine(seed=seed, simulations=simulations)
        # Two legs total (CRN): baseline + compiled counterfactual. We call
        # the leg primitives directly so the raw result dicts are available
        # for the extended comparison (run_spec would hide them and force
        # re-runs).
        baseline_result = eng.run_baseline(
            self.scenario_for_race(hrace, laps=laps),
            simulations=simulations, seed=seed)
        compiled, trace, warnings = compile_spec(baseline, spec)
        cf_result = eng._simulate(compiled, simulations, seed)
        b_fp = baseline_fingerprint(baseline)
        c_fp = spec_fingerprint(spec, scenario_content_hash(baseline))
        tiers = {t.family: t.evidence_tier for t in trace}
        comparison = extended_compare(
            spec.spec_id, experiment_id, baseline_result, cf_result,
            baseline_fp=b_fp,
            counterfactual_fp=c_fp,
            seed=seed, simulations=simulations, evidence_tiers=tiers,
            baseline_scenario=baseline, counterfactual_scenario=compiled,
        )
        attribution = build_attribution(experiment_id, trace, comparison)
        crn = CRNManifest(
            experiment_id=experiment_id,
            baseline_seed=seed,
            counterfactual_seed=seed,
            same_seed=True,
            simulations=simulations,
            stream_manifest=dict(STREAM_MANIFEST),
            unrelated_streams_unchanged=True,
        )
        spec_payload = {
            "spec_id": spec.spec_id,
            "scenario_type": spec.scenario_type,
            "interventions": [
                {"family": str(getattr(iv, 'family', '')),
                 "op": str(getattr(iv, 'op', '')),
                 "target": str(getattr(iv, 'target', '')),
                 "parameter": str(getattr(iv, 'parameter', '')),
                 "value": getattr(iv, 'value', None)}
                for iv in ivs
            ],
        }
        fp = experiment_fingerprint(
            race_id, scenario_content_hash(baseline), spec_payload,
            seed, simulations, model_versions(),
        )
        prov = build_experiment_provenance(
            race_id, hrace.as_of, hrace.race_date, seed, simulations, total,
            intervention=[t.describe() if hasattr(t, "describe") else str(t) for t in trace],
            crn=crn.model_dump(),
            evidence=dict(comparison.evidence_tiers),
            extra={
                "experiment_id": experiment_id,
                "counterfactual_version": COUNTERFACTUAL_MODEL_VERSION,
                "baseline_fingerprint": b_fp,
                "counterfactual_fingerprint": c_fp,
                "baseline_scenario_hash": scenario_content_hash(baseline),
                "compile_warnings": warnings,
            },
        )
        return CounterfactualExperiment(
            experiment_id=experiment_id,
            race_id=race_id,
            question=question,
            seed=seed,
            simulations=simulations,
            laps=total,
            spec=spec_payload,
            trace=[t.model_dump() for t in trace],
            baseline_fingerprint=b_fp,
            counterfactual_fingerprint=c_fp,
            comparison=comparison,
            attribution=attribution,
            crn_manifest=crn,
            evidence=dict(comparison.evidence_tiers),
            limitations=[
                "Baseline setup is the neutral Phase 20 baseline (historical setups unknown).",
                "Pit stops carry no time loss unless pit_loss_seconds is explicitly enabled.",
                "All effect tiers are PRIOR_ONLY unless stated; Monte Carlo never upgrades tiers.",
                "Model-attributed effects are not real-world causal claims.",
            ],
            provenance=prov,
            fingerprint=fp,
        )

    def checkpoint(self, race_id: str, lap: int, seed: int | None = None,
                   simulations: int | None = None) -> CheckpointResult:
        """Arbitrary checkpoint(lap=N) without rebuilding the race."""
        from app.simulation.replay.provenance import (
            experiment_fingerprint,
            model_versions,
        )
        from app.simulation.scenario.compiler import scenario_content_hash

        seed = self.seed if seed is None else int(seed)
        simulations = self.simulations if simulations is None else int(simulations)
        hrace = self.load_race(race_id)
        leg_scen = self.scenario_for_race(hrace, laps=max(1, int(lap)))
        leg = self._simulate(leg_scen, simulations, seed)
        wins = {
            did: float(d.get("win_probability", 0.0) or 0.0)
            for did, d in (leg.get("drivers", {}) or {}).items()
        }
        top = max(wins, key=lambda k: wins[k]) if wins else ""
        return CheckpointResult(
            name=f"lap_{lap}",
            lap=int(lap),
            simulations=simulations,
            seed=seed,
            fingerprint=experiment_fingerprint(
                race_id, scenario_content_hash(leg_scen),
                {"kind": "checkpoint", "lap": int(lap)},
                seed, simulations, model_versions(),
            ),
            top_driver_by_win_prob=top,
            top_win_probability=float(wins.get(top, 0.0)),
            provenance={"engine": "replay-v22", "truncated_horizon": True},
        )


def sha16(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
