from __future__ import annotations

"""Tournament engine: plays round-robin tournaments and produces the full
precomputed dataset the frontend replays (PRD: precompute-then-replay).

Everything derivable is computed here once, server-side: leaderboard stats,
phase breakdowns, head-to-head matrix, cooperation-over-time, per-match
replay data with noise events, and narrative summaries.
"""

import math
from typing import Callable

from core.match_history import match_history_with_noise_events, payoff
from simulation.narrative import match_narrative

StrategyFn = Callable[[list[tuple[bool, bool]]], bool]
ProgressFn = Callable[[float], None]


def _moves_string(moves: list[bool]) -> str:
    return "".join("C" if move else "D" for move in moves)


def _phase_bounds(rounds: int) -> tuple[int, int]:
    """(early_end, mid_end): early=[0,early_end) mid=[early_end,mid_end) late=[mid_end,rounds)."""
    return max(1, rounds // 3), max(2, (2 * rounds) // 3)


def _phase_of(round_index: int, early_end: int, mid_end: int) -> str:
    if round_index < early_end:
        return "early"
    if round_index < mid_end:
        return "mid"
    return "late"


class _PlayerStats:
    def __init__(self, rounds: int) -> None:
        self.total_score = 0
        self.matches = 0
        self.wins = 0
        self.losses = 0
        self.ties = 0
        self.coop_actions = 0
        self.actions = 0
        self.retaliation_opportunities = 0
        self.retaliations = 0
        self.forgiveness_opportunities = 0
        self.forgivenesses = 0
        self.first_defection_rounds: list[int] = []
        self.defected_first = 0
        self.phase_scores = {"early": 0, "mid": 0, "late": 0}
        self.phase_actions = {"early": 0, "mid": 0, "late": 0}
        self.match_scores: list[int] = []
        self.cumulative_by_round = [0] * rounds
        self.coop_by_round = [0] * rounds


def _record_side(
    stats: _PlayerStats,
    my_moves: list[bool],
    opp_moves: list[bool],
    my_scores: list[int],
    early_end: int,
    mid_end: int,
) -> None:
    rounds = len(my_moves)
    match_total = 0
    running = 0
    first_defection = None
    opp_first_defection = None

    for i in range(rounds):
        score = my_scores[i]
        match_total += score
        running += score
        stats.cumulative_by_round[i] += running
        stats.coop_by_round[i] += int(my_moves[i])
        stats.coop_actions += int(my_moves[i])
        stats.actions += 1
        phase = _phase_of(i, early_end, mid_end)
        stats.phase_scores[phase] += score
        stats.phase_actions[phase] += 1
        if not my_moves[i] and first_defection is None:
            first_defection = i
        if not opp_moves[i] and opp_first_defection is None:
            opp_first_defection = i
        if i + 1 < rounds:
            if not opp_moves[i]:
                stats.retaliation_opportunities += 1
                if not my_moves[i + 1]:
                    stats.retaliations += 1
            if not opp_moves[i] and not my_moves[i]:
                stats.forgiveness_opportunities += 1
                if my_moves[i + 1]:
                    stats.forgivenesses += 1

    stats.total_score += match_total
    stats.match_scores.append(match_total)
    stats.matches += 1
    stats.first_defection_rounds.append(first_defection + 1 if first_defection is not None else rounds + 1)
    if first_defection is not None and (opp_first_defection is None or first_defection < opp_first_defection):
        stats.defected_first += 1


def _match_phase_breakdown(
    history: list[tuple[bool, bool]],
    early_end: int,
    mid_end: int,
) -> dict:
    phases: dict[str, dict] = {}
    for phase in ("early", "mid", "late"):
        phases[phase] = {"p1_score": 0, "p2_score": 0, "p1_coop": 0, "p2_coop": 0, "rounds": 0}
    for i, (move1, move2) in enumerate(history):
        score1, score2 = payoff[(move1, move2)]
        bucket = phases[_phase_of(i, early_end, mid_end)]
        bucket["p1_score"] += score1
        bucket["p2_score"] += score2
        bucket["p1_coop"] += int(move1)
        bucket["p2_coop"] += int(move2)
        bucket["rounds"] += 1
    for bucket in phases.values():
        rounds = bucket.pop("rounds")
        bucket["p1_coop_rate"] = round(bucket.pop("p1_coop") / rounds, 4) if rounds else 0.0
        bucket["p2_coop_rate"] = round(bucket.pop("p2_coop") / rounds, 4) if rounds else 0.0
        bucket["round_count"] = rounds
    return phases


def _std(values: list[int]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))


def _short_label(name: str) -> str:
    return name.split(" - ", 1)[1] if " - " in name else name


def run_tournament(
    players: dict[str, StrategyFn],
    rounds: int,
    iterations: int,
    noise: float = 0.0,
    labels: dict[str, str] | None = None,
    progress: ProgressFn | None = None,
) -> dict:
    """Plays a full round-robin tournament and returns the complete JSON-ready dataset."""
    names = list(players.keys())
    if len(names) < 2:
        raise ValueError("At least two strategies are required for a tournament.")

    labels = labels or {name: _short_label(name) for name in names}
    early_end, mid_end = _phase_bounds(rounds)
    pairs = [(i, j) for i in range(len(names) - 1) for j in range(i + 1, len(names))]

    robustness_pass = noise > 0
    total_units = iterations * len(pairs) + (len(pairs) if robustness_pass else 0)
    done_units = 0

    def tick() -> None:
        nonlocal done_units
        done_units += 1
        if progress is not None:
            progress(done_units / total_units)

    stats = {name: _PlayerStats(rounds) for name in names}
    matrix_totals: dict[tuple[str, str], int] = {}
    matrix_matches: dict[tuple[str, str], int] = {}
    featured_matches: list[dict] = []
    total_noise_events = 0

    for iteration in range(iterations):
        for i, j in pairs:
            name1, name2 = names[i], names[j]
            history, noise_events = match_history_with_noise_events(
                players[name1], players[name2], rounds, noise
            )
            total_noise_events += len(noise_events)

            moves1 = [m[0] for m in history]
            moves2 = [m[1] for m in history]
            scores1 = [payoff[m][0] for m in history]
            scores2 = [payoff[m][1] for m in history]
            total1, total2 = sum(scores1), sum(scores2)

            _record_side(stats[name1], moves1, moves2, scores1, early_end, mid_end)
            _record_side(stats[name2], moves2, moves1, scores2, early_end, mid_end)

            if total1 > total2:
                stats[name1].wins += 1
                stats[name2].losses += 1
            elif total2 > total1:
                stats[name2].wins += 1
                stats[name1].losses += 1
            else:
                stats[name1].ties += 1
                stats[name2].ties += 1

            matrix_totals[(name1, name2)] = matrix_totals.get((name1, name2), 0) + total1
            matrix_totals[(name2, name1)] = matrix_totals.get((name2, name1), 0) + total2
            matrix_matches[(name1, name2)] = matrix_matches.get((name1, name2), 0) + 1
            matrix_matches[(name2, name1)] = matrix_matches.get((name2, name1), 0) + 1

            if iteration == 0:
                featured_matches.append(
                    {
                        "id": f"m{len(featured_matches)}",
                        "p1": name1,
                        "p2": name2,
                        "moves_p1": _moves_string(moves1),
                        "moves_p2": _moves_string(moves2),
                        "noise_events": [[r, p] for r, p in noise_events],
                        "p1_score": total1,
                        "p2_score": total2,
                        "phases": _match_phase_breakdown(history, early_end, mid_end),
                        "narrative": match_narrative(labels[name1], labels[name2], history, noise_events),
                    }
                )
            tick()

    # Optional noise-free baseline pass to derive robustness-to-noise.
    clean_avg: dict[str, float] = {}
    if robustness_pass:
        clean_totals = {name: 0 for name in names}
        for i, j in pairs:
            name1, name2 = names[i], names[j]
            history, _ = match_history_with_noise_events(players[name1], players[name2], rounds, 0.0)
            clean_totals[name1] += sum(payoff[m][0] for m in history)
            clean_totals[name2] += sum(payoff[m][1] for m in history)
            tick()
        for name in names:
            clean_avg[name] = clean_totals[name] / (len(names) - 1)

    leaderboard = []
    for name in names:
        s = stats[name]
        matches = s.matches or 1
        actions = s.actions or 1
        row = {
            "strategy": name,
            "total_score": s.total_score,
            "average_score": round(s.total_score / matches, 4),
            "avg_score_per_round": round(s.total_score / actions, 4),
            "matches_played": s.matches,
            "wins": s.wins,
            "losses": s.losses,
            "ties": s.ties,
            "win_rate": round(s.wins / matches, 4),
            "cooperation_rate": round(s.coop_actions / actions, 4),
            "retaliation_rate": round(s.retaliations / s.retaliation_opportunities, 4)
            if s.retaliation_opportunities
            else None,
            "forgiveness_rate": round(s.forgivenesses / s.forgiveness_opportunities, 4)
            if s.forgiveness_opportunities
            else None,
            "avg_first_defection_round": round(
                sum(s.first_defection_rounds) / len(s.first_defection_rounds), 2
            )
            if s.first_defection_rounds
            else None,
            "defected_first_rate": round(s.defected_first / matches, 4),
            "early_avg": round(s.phase_scores["early"] / s.phase_actions["early"], 4)
            if s.phase_actions["early"]
            else 0.0,
            "mid_avg": round(s.phase_scores["mid"] / s.phase_actions["mid"], 4)
            if s.phase_actions["mid"]
            else 0.0,
            "late_avg": round(s.phase_scores["late"] / s.phase_actions["late"], 4)
            if s.phase_actions["late"]
            else 0.0,
            "score_volatility": round(_std(s.match_scores), 2),
            "robustness_to_noise": round(s.total_score / matches / clean_avg[name], 4)
            if robustness_pass and clean_avg.get(name)
            else None,
        }
        leaderboard.append(row)
    leaderboard.sort(key=lambda r: r["total_score"], reverse=True)

    matrix = {
        "names": names,
        "avg_scores": [
            [
                round(matrix_totals[(row, col)] / matrix_matches[(row, col)], 2)
                if row != col
                else None
                for col in names
            ]
            for row in names
        ],
    }

    matches_per_strategy = (len(names) - 1) * iterations
    cooperation_over_time = {
        "by_strategy": {
            name: [round(c / matches_per_strategy, 4) for c in stats[name].coop_by_round]
            for name in names
        },
        "overall": [
            round(
                sum(stats[name].coop_by_round[r] for name in names)
                / (len(names) * matches_per_strategy),
                4,
            )
            for r in range(rounds)
        ],
    }

    return {
        "config": {
            "strategies": names,
            "rounds": rounds,
            "iterations": iterations,
            "noise": noise,
            "phase_bounds": {"early_end": early_end, "mid_end": mid_end},
        },
        "labels": labels,
        "payoff": {"cc": list(payoff[(True, True)]), "cd": list(payoff[(True, False)]),
                   "dc": list(payoff[(False, True)]), "dd": list(payoff[(False, False)])},
        "leaderboard": leaderboard,
        "matrix": matrix,
        "cooperation_over_time": cooperation_over_time,
        "cumulative_scores_by_round": {
            name: stats[name].cumulative_by_round for name in names
        },
        "matches": featured_matches,
        "total_noise_events": total_noise_events,
    }
