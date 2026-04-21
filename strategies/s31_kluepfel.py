import math
import random


def s31(match_history):
    if not match_history:
        return True

    cd_count = dd_count = cc_count = dc_count = 0
    for t in range(1, len(match_history)):
        my_prev = match_history[t - 1][0]
        opp_now = match_history[t][1]
        if not my_prev:
            if opp_now:
                cd_count += 1
            else:
                dd_count += 1
        else:
            if opp_now:
                cc_count += 1
            else:
                dc_count += 1

    turn = len(match_history) + 1
    if turn > 26:
        left_total = cd_count + dd_count
        right_total = dc_count + cc_count
        left_ok = left_total == 0 or cd_count >= (left_total / 2) - 0.75 * math.sqrt(left_total)
        right_ok = right_total == 0 or dc_count >= (right_total / 2) - 0.75 * math.sqrt(right_total)
        if left_ok and right_ok:
            return False

    opp = [o for _, o in match_history]
    if len(opp) >= 3 and opp[-1] == opp[-2] == opp[-3]:
        return opp[-1]
    if len(opp) >= 2 and opp[-1] == opp[-2]:
        return random.random() < 0.9 if opp[-1] else random.random() >= 0.9
    if opp[-1]:
        return random.random() < 0.7
    return random.random() >= 0.6
