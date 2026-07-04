"""Full 41-strategy tournament, in-process (no server, no network)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from simulation.service import available_strategies, run_simulation

names = available_strategies()
d = run_simulation(strategies=names, rounds=200, iterations=2, noise=0.0)
print(f"{len(d['matches'])} featured matches, {len(d['leaderboard'])} leaderboard rows")
print(f"{'strategy':36} {'retal':>6} {'forgive':>7} {'coop%':>6} {'1st_def':>7}")
for row in d["leaderboard"]:
    print(f"{row['strategy']:36} {str(row['retaliation_rate']):>6} {str(row['forgiveness_rate']):>7} {row['cooperation_rate']:>6} {str(row['avg_first_defection_round']):>7}")
