"""Weather source abstraction (Phase 10 - multi-source)."""
from __future__ import annotations

import json
import os

from app.data.provenance import make_provenance
from app.data.sources.base import DataUnavailable, RawBundle, SourceAdapter


class WeatherSourceAdapter(SourceAdapter):
    """Adapter for historical weather observations."""

    provider = "weather"

    def __init__(self, base_dir: str = "data/raw/weather") -> None:
        self.base_dir = base_dir

    def import_observations(
        self,
        file_path: str,
        source: str = "unknown",
    ) -> RawBundle:
        """Import weather observations from local JSON/CSV file."""
        if not os.path.exists(file_path):
            raise DataUnavailable(f"Weather file not found: {file_path}")

        with open(file_path, encoding="utf-8") as handle:
            if file_path.endswith(".json"):
                data = json.load(handle)
                records = data if isinstance(data, list) else [data]
            else:
                # CSV fallback would go here
                records = []

        # Ensure records have required fields with provenance
        for record in records:
            record["_weather_source"] = source
            # Provenance per record
            prov = make_provenance(
                source_provider=self.provider,
                source_record_id=record.get("observation_id", ""),
                raw_payload=record,
                steps=["import_observations"],
            )
            record["_provenance_hash"] = prov.raw_file_hash[:8]

        return RawBundle(
            provider=self.provider,
            endpoint=file_path,
            records=records,
        )

    def fetch_race_weather(self, season: int, round_number: int) -> RawBundle:
        """Fetch weather for a specific race (if available locally)."""
        pattern = f"{season}_{round_number}_weather.json"
        path = os.path.join(self.base_dir, pattern)
        if not os.path.exists(path):
            raise DataUnavailable(f"No weather data for {season} round {round_number}")
        return self.import_observations(path)

    def fetch_season(self, season: int) -> RawBundle:
        raise DataUnavailable("Weather adapter: use fetch_race_weather or import_observations")

    def fetch_race(self, season: int, round_number: int) -> RawBundle:
        return self.fetch_race_weather(season, round_number)
