import math


def s39(match_history):
    turn = len(match_history) + 1
    if turn <= 10:
        return True

    opp = [o for _, o in match_history]
    if opp[-1]:
        return True

    opp_defections = sum(1 for x in opp if not x)
    return not (math.floor(math.log(turn)) * opp_defections >= turn)
