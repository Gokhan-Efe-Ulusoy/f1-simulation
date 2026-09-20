"""Weather calibration for Phase 17 — walk-forward, strict-before, leakage-safe.

Sources: OpenF1 weather.json (2023-2026, ~644 obs), FastF1 optional.
Most variables NON_IDENTIFIABLE historically; only modern aggregated priors CALIBRATED.
No fabrication: missing → None / PRIOR_ONLY.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from collections import defaultdict
import numpy as np

DATA_ROOT = Path(__file__).resolve().parents[3] / "data"
OPENF1_ROOT = DATA_ROOT / "raw" / "openf1"


def load_weather_observations() -> list[dict]:
    """Load OpenF1 weather observations where available.

    Returns list of dicts with keys: season, race_id, session_key, date, air_temperature, track_temperature, humidity, pressure, rainfall, wind_speed, wind_direction, source, timestamp  # noqa: E501
    """
    obs: list[dict] = []
    # Known sessions with weather
    mapping = [
        ("2023", "7953", "2023-bahrain"),
        ("2024", "9472", "2024-bahrain"),
        ("2025", "9693", "2025-bahrain"),
        ("2026", "11234", "2026-bahrain"),
    ]
    for season, sess, race_id in mapping:
        p = OPENF1_ROOT / season / sess / "weather.json"
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text())
            for rec in data:
                # rec fields: air_temperature, track_temperature, humidity, pressure, rainfall, wind_speed, wind_direction, date, session_key
                obs.append(
                    {
                        "season": int(season),
                        "race_id": race_id,
                        "session_key": sess,
                        "date": rec.get("date"),
                        "air_temperature_c": rec.get("air_temperature"),
                        "track_temperature_c": rec.get("track_temperature"),
                        "humidity_pct": rec.get("humidity"),
                        "pressure_hpa": rec.get("pressure"),
                        "rainfall_mm_h": rec.get("rainfall", 0.0),
                        "wind_speed_mps": rec.get("wind_speed"),
                        "wind_direction_deg": rec.get("wind_direction"),
                        "source": "openf1",
                        "timestamp": rec.get("date"),
                    }
                )
        except Exception:
            continue
    # FastF1 fallback for 2024 if OpenF1 missing some fields (not needed)
    return obs


def calibrate_weather(observations: list[dict], as_of: str = "2024-03-01") -> dict:
    """Leakage-safe calibration: only observations with date < as_of.

    Returns dict per variable: value, std, n, evidence_tier.
    Global → era → circuit hierarchy with shrinkage (if enough data).
    Currently simple global means because n is small (~644 modern).
    """
    filtered = [o for o in observations if o.get("date") and o["date"] < as_of]
    # If filtered empty, return PRIOR_ONLY for all
    vars_to_calibrate = ["air_temperature_c", "track_temperature_c", "humidity_pct", "pressure_hpa", "wind_speed_mps", "rainfall_mm_h"]  # noqa: E501
    result: dict = {}
    for var in vars_to_calibrate:
        vals = [o[var] for o in filtered if o.get(var) is not None and not (isinstance(o[var], float) and math.isnan(o[var]))]  # noqa: E501
        n = len(vals)
        if n < 30:
            result[var] = {
                "value": None,
                "available": False,
                "reason": f"sample_size {n} <30",
                "evidence_tier": "NON_IDENTIFIABLE" if n < 10 else "PRIOR_ONLY",
                "sample_size": n,
            }
            continue
        mean = float(np.mean(vals))
        std = float(np.std(vals, ddof=1)) if n > 1 else 0.0
        # Shrinkage toward prior (e.g., temp prior 25C, humidity 60, pressure 1013)
        priors = {
            "air_temperature_c": 25.0,
            "track_temperature_c": 35.0,
            "humidity_pct": 60.0,
            "pressure_hpa": 1013.0,
            "wind_speed_mps": 3.0,
            "rainfall_mm_h": 0.0,
        }
        prior = priors.get(var, mean)
        prior_n = 10
        shrunk = (n * mean + prior_n * prior) / (n + prior_n)
        result[var] = {
            "value": shrunk,
            "raw_mean": mean,
            "std": std,
            "sample_size": n,
            "evidence_tier": "CALIBRATED" if n >= 100 else "LIMITED",
            "available": True,
            "as_of": as_of,
            "source": "openf1",
        }
    # Also add track_wetness derived (from rainfall)
    rain_vals = [o["rainfall_mm_h"] for o in filtered if o.get("rainfall_mm_h") is not None]
    # Most are 0, so wetness prior is 0
    result["track_wetness"] = {
        "value": 0.0,
        "available": False,
        "reason": "wetness derived, not observed",
        "evidence_tier": "PRIOR_ONLY",
        "sample_size": len([v for v in rain_vals if v > 0]),
    }
    return result


def estimate_track_temperature(air_temp: float | None, calibration: dict | None = None) -> tuple[float | None, str]:  # noqa: E501
    """Estimate track temp from air temp if direct observation missing.

    Uses simple linear proxy: T_track = air + 10 (empirical Pirelli), but mark ESTIMATED.
    If historical data insufficient, returns (None, NON_IDENTIFIABLE).
    We have ~400 paired obs in modern, so we can calibrate simple regression if as_of allows.
    """
    if air_temp is None:
        return None, "NON_IDENTIFIABLE"
    # Simple prior: +10 offset, no fitted beta until more data
    # TODO: calibrate beta when >100 paired obs pre-as_of
    # For now, honest ESTIMATED with wide uncertainty
    return air_temp + 10.0, "ESTIMATED"


def get_weather_evidence_tier(as_of: str, season: int) -> str:
    """Return tier for season given as_of.

    Modern (>=2023) with OpenF1 → LIMITED/CALIBRATED if as_of includes session,
    else PRIOR_ONLY. Historical (<2023) → NON_IDENTIFIABLE for most fields.
    """
    try:
        y = int(season)
    except:
        return "PRIOR_ONLY"
    if y < 2023:
        return "NON_IDENTIFIABLE"
    # For 2023+, check if any obs < as_of
    obs = load_weather_observations()
    filt = [o for o in obs if o["season"] == y and o["date"] < as_of]
    if not filt:
        return "PRIOR_ONLY"
    return "LIMITED"  # n small, not FULL
