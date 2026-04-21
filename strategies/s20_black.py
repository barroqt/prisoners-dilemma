import random


def s20(match_history):
    turn = len(match_history)
    if turn < 5:
        return True

    recent = match_history[-5:]
    d = sum(1 for _, opp in recent if not opp)
    p_coop = 1 - ((d**2 - 1) / 25)
    p_coop = max(0.0, min(1.0, p_coop))
    return random.random() < p_coop
