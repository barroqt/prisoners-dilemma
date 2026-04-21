import random


def s40(match_history):
    turn = len(match_history) + 1
    if turn <= 2:
        return True

    opp = [o for _, o in match_history]
    c_defect = sum(1 for x in opp[1:] if not x) if len(opp) > 1 else 0

    if c_defect in {4, 7, 9}:
        return False

    if c_defect > 9 and not opp[-1]:
        p_coop = 0.5 ** (c_defect - 9)
        return random.random() < p_coop

    return True
