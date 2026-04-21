import random


def s19(match_history):
    turn = len(match_history)
    if turn < 4:
        return True

    # Opponent from turn 4 onward (0-indexed: index >= 3)
    if not any(opp for _, opp in match_history[3:]):
        return False

    after_my_d_total = 0
    after_my_d_coop = 0
    after_my_c_total = 1  # opponent first move counts as response to my cooperation
    after_my_c_coop = int(match_history[0][1]) if match_history else 0

    for t in range(1, turn):
        my_prev = match_history[t - 1][0]
        opp_now = match_history[t][1]
        if my_prev:
            after_my_c_total += 1
            after_my_c_coop += int(opp_now)
        else:
            after_my_d_total += 1
            after_my_d_coop += int(opp_now)

    p_after_d = (after_my_d_coop / after_my_d_total) if after_my_d_total else 0.0
    p_after_c = (after_my_c_coop / after_my_c_total) if after_my_c_total else 1.0

    my_two_ago = match_history[-2][0] if turn >= 2 else match_history[-1][0]
    p_coop = p_after_d if not my_two_ago else p_after_c
    return random.random() < max(0.0, min(1.0, p_coop))
