from core.match_history import payoff


THRESHOLDS = {
    11: 23,
    21: 53,
    31: 83,
    41: 113,
    51: 143,
    101: 293,
}


def s28(match_history):
    # Cumulative score after each round, so past threshold checks stay fixed.
    scores_by_turn = []
    score = 0
    for my, opp in match_history:
        score += payoff[(my, opp)][0]
        scores_by_turn.append(score)

    # Failed threshold in the past => defect forever.
    for turn, threshold in THRESHOLDS.items():
        if len(match_history) >= turn and scores_by_turn[turn - 1] < threshold:
            return False

    if not match_history:
        return True
    return match_history[-1][1]
