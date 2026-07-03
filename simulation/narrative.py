from __future__ import annotations

"""Auto-generated plain-language narrative summaries for a single match.

The generator is template-based: it inspects the match history for the
story beats a commentator would call out (first betrayal, defection locks,
comebacks, exploitation, noise-triggered spirals) and composes 1-3 sentences.
"""

from core.match_history import payoff


def _cumulative_diff(history: list[tuple[bool, bool]]) -> list[int]:
    diff = []
    running = 0
    for move1, move2 in history:
        score1, score2 = payoff[(move1, move2)]
        running += score1 - score2
        diff.append(running)
    return diff


def _locked_defection_start(moves: list[bool], min_tail: int = 10) -> int | None:
    """Round index from which a player defects for every remaining round."""
    if not moves or moves[-1]:
        return None
    start = len(moves)
    for i in range(len(moves) - 1, -1, -1):
        if moves[i]:
            break
        start = i
    if len(moves) - start >= min_tail and start > 0:
        return start
    return None


def _longest_mutual_coop(history: list[tuple[bool, bool]]) -> tuple[int, int]:
    """Returns (length, start_round) of the longest mutual-cooperation streak."""
    best = 0
    best_start = 0
    current = 0
    for i, (move1, move2) in enumerate(history):
        if move1 and move2:
            current += 1
            if current > best:
                best = current
                best_start = i - current + 1
        else:
            current = 0
    return best, best_start


def _spiral_after_noise(history, noise_events, min_len: int = 5) -> int | None:
    """Round of the first noise event that a mutual-defection spiral followed within 2 rounds."""
    for event_round, _player in noise_events:
        for start in range(event_round, min(event_round + 3, len(history))):
            run = 0
            for move1, move2 in history[start:]:
                if not move1 and not move2:
                    run += 1
                else:
                    break
            if run >= min_len:
                return event_round
    return None


def match_narrative(
    name1: str,
    name2: str,
    history: list[tuple[bool, bool]],
    noise_events: list[tuple[int, int]],
) -> str:
    if not history:
        return "No rounds were played."

    rounds = len(history)
    score1 = sum(payoff[m][0] for m in history)
    score2 = sum(payoff[m][1] for m in history)
    coop1 = sum(1 for m in history if m[0]) / rounds
    coop2 = sum(1 for m in history if m[1]) / rounds

    sentences: list[str] = []

    # First betrayal.
    first_defect_round = None
    first_defector = None
    for i, (move1, move2) in enumerate(history):
        if not move1 or not move2:
            first_defect_round = i + 1
            if not move1 and not move2:
                first_defector = "both sides"
            else:
                first_defector = name1 if not move1 else name2
            break

    if first_defect_round is None:
        return (
            f"A perfect peace: {name1} and {name2} cooperated on every single one of "
            f"the {rounds} rounds and split the maximum payoff evenly."
        )

    if first_defect_round == 1:
        sentences.append(f"{first_defector} came out swinging with a defection on the very first round.")
    else:
        sentences.append(
            f"Trust held for {first_defect_round - 1} rounds before {first_defector} threw the first defection."
        )

    # Noise-triggered spiral.
    spiral_round = _spiral_after_noise(history, noise_events)
    if spiral_round is not None:
        sentences.append(
            f"A misread move at round {spiral_round + 1} sparked a mutual defection spiral the pair never fully escaped."
        )

    # Permanent defection lock.
    lock1 = _locked_defection_start([m[0] for m in history])
    lock2 = _locked_defection_start([m[1] for m in history])
    if lock1 is not None and lock2 is not None:
        locker, lock_round = (name1, lock1) if lock1 <= lock2 else (name2, lock2)
        sentences.append(f"{locker} locked in permanent defection at round {lock_round + 1} and never looked back.")
    elif lock1 is not None:
        sentences.append(f"{name1} locked in permanent defection at round {lock1 + 1} and never looked back.")
    elif lock2 is not None:
        sentences.append(f"{name2} locked in permanent defection at round {lock2 + 1} and never looked back.")

    # Outcome flavor.
    diff = _cumulative_diff(history)
    winner = name1 if score1 > score2 else name2 if score2 > score1 else None
    if winner is None:
        sentences.append(f"After {rounds} rounds the fight ended in a dead heat, {score1}-{score2}.")
    else:
        winner_score, loser_score = (score1, score2) if winner == name1 else (score2, score1)
        loser = name2 if winner == name1 else name1
        two_thirds = diff[(rounds * 2) // 3 - 1] if rounds >= 3 else diff[-1]
        was_behind_late = (two_thirds < 0) if winner == name1 else (two_thirds > 0)
        winner_coop = coop1 if winner == name1 else coop2
        loser_coop = coop2 if winner == name1 else coop1

        if was_behind_late:
            sentences.append(
                f"{winner} was still trailing entering the late game but stormed back to win {winner_score}-{loser_score}."
            )
        elif winner_coop < 0.4 and loser_coop > 0.7:
            sentences.append(
                f"{winner} exploited {loser}'s goodwill relentlessly, cashing out a {winner_score}-{loser_score} win "
                f"while cooperating only {winner_coop * 100:.0f}% of the time."
            )
        else:
            sentences.append(f"{winner} took the match {winner_score}-{loser_score}.")

    # Cooperation streak color, only when it is actually notable.
    streak, streak_start = _longest_mutual_coop(history)
    if streak >= max(10, rounds // 4) and first_defect_round is not None:
        sentences.append(
            f"The longest stretch of mutual cooperation ran {streak} rounds starting at round {streak_start + 1}."
        )

    return " ".join(sentences[:3])
