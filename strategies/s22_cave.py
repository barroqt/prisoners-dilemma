import random


def s22(match_history):
    if not match_history:
        return True

    total = len(match_history)
    opp_defections = sum(1 for _, opp in match_history if not opp)
    defect_rate = opp_defections / total

    if (total > 39 and defect_rate > 0.39) or (total > 29 and defect_rate > 0.65) or (total > 19 and defect_rate > 0.79):
        return False

    if match_history[-1][1]:
        return True

    if opp_defections >= 18:
        return False
    return random.random() < 0.5
