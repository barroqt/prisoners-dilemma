from __future__ import annotations

import argparse
import json

from simulation.service import available_strategies, run_simulation


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Prisoner's Dilemma simulations.")
    parser.add_argument(
        "--strategies",
        nargs="+",
        required=True,
        help="List of strategy names. Use --list-strategies to see available values.",
    )
    parser.add_argument("--rounds", type=int, default=200, help="Rounds per match.")
    parser.add_argument("--iterations", type=int, default=1, help="Tournament iterations.")
    parser.add_argument("--noise", type=float, default=0.0, help="Noise probability [0, 1].")
    parser.add_argument(
        "--list-strategies",
        action="store_true",
        help="Print all available strategy names and exit.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.list_strategies:
        for strategy in available_strategies():
            print(strategy)
        return

    result = run_simulation(
        strategies=args.strategies,
        rounds=args.rounds,
        iterations=args.iterations,
        noise=args.noise,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
