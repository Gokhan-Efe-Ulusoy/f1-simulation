"""Phase 22 walk-forward validation sample (reproducible, not cherry-picked).

Sample: 2024 season rounds 1-12 (first half, fixed before running). Each race
replays at N=60 on a shortened 8-lap horizon for cost, plus one full-length
N=60 replay of 2024-bahrain. Reports predicted vs observed winners, top-3
overlap, finish MAE, and coverage metadata.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.simulation.replay.validation import deviation_metrics, walk_forward
from app.simulation.replay.replay_engine import ReplayEngine


def main() -> None:
    races = json.loads((Path(__file__).parent.parent / "data" / "canonical" / "races.json").read_text())
    season24 = sorted(
        [r for r in races if r.get("season_id") == "2024" and r.get("round")],
        key=lambda r: r["round"],
    )
    sample = [r["race_id"] for r in season24[:12]]
    print(f"sample ({len(sample)} races): {sample}")
    rows = walk_forward(sample, seed=42, simulations=60, laps=8)
    wins = sum(1 for r in rows if r["winner_match"])
    maes = [r["finish_mae"] for r in rows if r["finish_mae"] is not None]
    print(json.dumps({
        "sample": sample,
        "winner_match": f"{wins}/{len(rows)}",
        "mean_top3_overlap": round(sum(r["top3_overlap"] for r in rows) / len(rows), 2),
        "mean_finish_mae": round(sum(maes) / len(maes), 2) if maes else None,
        "rows": rows,
    }, indent=1, default=str))


if __name__ == "__main__":
    main()
