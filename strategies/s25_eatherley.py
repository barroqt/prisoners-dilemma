import random


def s25(match_history):
    if not match_history:
        return True
    if match_history[-1][1]:
        return True

    total = len(match_history)
    opp_defections = sum(1 for _, opp in match_history if not opp)
    p_defect = opp_defections / total if total else 0.0
    return not (random.random() < p_defect)
