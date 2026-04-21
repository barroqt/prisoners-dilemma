from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib import import_module
from pathlib import Path
from typing import Callable

from core.match_history import match_history_with_noise, payoff


StrategyFn = Callable[[list[tuple[bool, bool]]], bool]


@dataclass
class StrategyMetrics:
    strategy: str
    total_score: int
    average_score: float
    cooperation_rate: float
    matches_played: int


@dataclass
class SimulationResult:
    selected_strategies: list[str]
    rounds: int
    iterations: int
    noise: float
    leaderboard: list[StrategyMetrics]
    cumulative_scores_by_round: dict[str, list[int]]
    head_to_head_totals: dict[str, dict[str, int]]

    def to_dict(self) -> dict:
        return asdict(self)


def _strategy_number_from_filename(filename: str) -> int | None:
    if not filename.startswith("s") or not filename.endswith(".py"):
        return None
    numeric = filename[1:3]
    if not numeric.isdigit():
        return None
    return int(numeric)


def _strategy_label(filename: str) -> str:
    stem = Path(filename).stem
    parts = stem.split("_")[1:]
    if not parts:
        return stem
    return " ".join(parts).replace("-", " ").title()


def load_strategy_registry(limit: int = 16) -> dict[str, StrategyFn]:
    strategies_dir = Path(__file__).resolve().parent.parent / "strategies"
    by_number: list[tuple[int, str, StrategyFn]] = []

    for path in sorted(strategies_dir.glob("s*.py")):
        number = _strategy_number_from_filename(path.name)
        if number is None or number > limit:
            continue

        module = import_module(f"strategies.{path.stem}")
        function_name = f"s{number:02d}"
        function_object = getattr(module, function_name)
        display_name = f"{function_name} - {_strategy_label(path.name)}"
        by_number.append((number, display_name, function_object))

    by_number.sort(key=lambda item: item[0])
    return {display_name: fn for _, display_name, fn in by_number}


DEFAULT_STRATEGIES = load_strategy_registry(limit=41)


def available_strategies() -> list[str]:
    return list(DEFAULT_STRATEGIES.keys())


def run_simulation(
    strategies: list[str],
    rounds: int,
    iterations: int,
    noise: float = 0.0,
) -> SimulationResult:
    if not strategies:
        raise ValueError("At least one strategy must be selected.")
    if rounds <= 0:
        raise ValueError("rounds must be > 0.")
    if iterations <= 0:
        raise ValueError("iterations must be > 0.")
    if noise < 0 or noise > 1:
        raise ValueError("noise must be between 0 and 1.")

    unknown = [strategy for strategy in strategies if strategy not in DEFAULT_STRATEGIES]
    if unknown:
        raise ValueError(f"Unknown strategies: {', '.join(unknown)}")

    selected = {name: DEFAULT_STRATEGIES[name] for name in strategies}
    totals = {name: 0 for name in selected}
    cooperation_actions = {name: 0 for name in selected}
    action_counts = {name: 0 for name in selected}
    matches_played = {name: 0 for name in selected}
    cumulative_scores_by_round = {name: [0 for _ in range(rounds)] for name in selected}
    head_to_head_totals: dict[str, dict[str, int]] = {}

    strategy_names = list(selected.keys())
    for _ in range(iterations):
        for i in range(len(strategy_names) - 1):
            for j in range(i + 1, len(strategy_names)):
                name1 = strategy_names[i]
                name2 = strategy_names[j]
                strat1 = selected[name1]
                strat2 = selected[name2]
                history = match_history_with_noise(strat1, strat2, rounds, noise)

                matches_played[name1] += 1
                matches_played[name2] += 1

                pair_key = f"{name1} vs {name2}"
                if pair_key not in head_to_head_totals:
                    head_to_head_totals[pair_key] = {
                        name1: 0,
                        name2: 0,
                        f"{name1}_cooperate_actions": 0,
                        f"{name2}_cooperate_actions": 0,
                        "rounds_played": 0,
                    }

                for round_index, (move1, move2) in enumerate(history):
                    score1, score2 = payoff[(move1, move2)]

                    totals[name1] += score1
                    totals[name2] += score2
                    cumulative_scores_by_round[name1][round_index] += score1
                    cumulative_scores_by_round[name2][round_index] += score2

                    cooperation_actions[name1] += int(move1)
                    cooperation_actions[name2] += int(move2)
                    action_counts[name1] += 1
                    action_counts[name2] += 1

                    head_to_head_totals[pair_key][name1] += score1
                    head_to_head_totals[pair_key][name2] += score2
                    head_to_head_totals[pair_key][f"{name1}_cooperate_actions"] += int(move1)
                    head_to_head_totals[pair_key][f"{name2}_cooperate_actions"] += int(move2)
                    head_to_head_totals[pair_key]["rounds_played"] += 1

    leaderboard: list[StrategyMetrics] = []
    for name in strategy_names:
        plays = matches_played[name]
        actions = action_counts[name]
        average_score = totals[name] / plays if plays else 0.0
        cooperation_rate = cooperation_actions[name] / actions if actions else 0.0
        leaderboard.append(
            StrategyMetrics(
                strategy=name,
                total_score=totals[name],
                average_score=round(average_score, 4),
                cooperation_rate=round(cooperation_rate, 4),
                matches_played=plays,
            )
        )

    leaderboard.sort(key=lambda item: item.total_score, reverse=True)

    return SimulationResult(
        selected_strategies=strategy_names,
        rounds=rounds,
        iterations=iterations,
        noise=noise,
        leaderboard=leaderboard,
        cumulative_scores_by_round=cumulative_scores_by_round,
        head_to_head_totals=head_to_head_totals,
    )
