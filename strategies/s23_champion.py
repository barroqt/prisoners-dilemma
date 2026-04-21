import random


def s23(match_history):
    turn = len(match_history) + 1
    if turn <= 10:
        return True
    if turn <= 25:
        return match_history[-1][1]

    opp_last = match_history[-1][1]
    if opp_last:
        return True

    total = len(match_history)
    opp_coop = sum(1 for _, opp in match_history if opp)
    opp_defect = total - opp_coop
    coop_rate = opp_coop / total if total else 1.0
    defect_rate = opp_defect / total if total else 0.0

    if coop_rate < 0.6 and random.random() <= defect_rate:
        return False
    return True
