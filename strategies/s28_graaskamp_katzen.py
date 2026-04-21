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
    score = 0
    for my, opp in match_history:
        score += payoff[(my, opp)][0]

    # Failed threshold in the past => defect forever.
    for turn, threshold in THRESHOLDS.items():
        if len(match_history) >= turn and score < threshold:
            return False

    if not match_history:
        return True
    return match_history[-1][1]
