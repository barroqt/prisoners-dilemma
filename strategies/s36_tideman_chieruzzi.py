import math

from core.match_history import payoff


def s36(match_history):
    turn = len(match_history) + 1
    if turn == 1:
        return True

    # Defect on the last two moves for typical 200-round matches.
    if turn >= 199:
        return False

    my_score = 0
    opp_score = 0
    for my, opp in match_history:
        s1, s2 = payoff[(my, opp)]
        my_score += s1
        opp_score += s2

    # Basic escalating retaliation by run count reconstruction.
    runs = []
    current = 0
    for _, opp in match_history:
        if not opp:
            current += 1
        elif current > 0:
            runs.append(current)
            current = 0
    if current > 0:
        runs.append(current)

    punishment_len = len(runs)
    if punishment_len > 0 and runs[-1] > 0 and (not match_history[-1][1]):
        return False

    # Fresh start conditions (finite-horizon approximation).
    opp_defections = sum(1 for _, opp in match_history if not opp)
    n = len(match_history)
    expected = n / 2
    std = math.sqrt(max(1.0, n * 0.25))
    random_far = abs(opp_defections - expected) >= 3 * std
    if (my_score - opp_score) >= 10 and n >= 20 and random_far and turn <= 190:
        return True

    return match_history[-1][1]
