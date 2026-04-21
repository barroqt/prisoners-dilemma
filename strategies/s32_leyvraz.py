import random


def s32(match_history):
    opp = [o for _, o in match_history]
    recent = [True, True, True]
    for go_back in range(1, 4):
        if len(opp) >= go_back:
            recent[-go_back] = opp[-go_back]

    prob_coop = {
        (True, True, True): 1.0,
        (True, True, False): 0.5,
        (True, False, True): 0.0,
        (True, False, False): 0.25,
        (False, True, True): 1.0,
        (False, True, False): 1.0,
        (False, False, True): 1.0,
        (False, False, False): 0.25,
    }
    return random.random() < prob_coop[(recent[-3], recent[-2], recent[-1])]
