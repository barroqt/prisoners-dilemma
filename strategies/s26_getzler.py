import random


def s26(match_history):
    flack = 0.0
    n = len(match_history)
    for i, (_, opp) in enumerate(match_history):
        if not opp:
            k = n - 1 - i
            flack += 0.5**k
    flack = max(0.0, min(1.0, flack))
    return not (random.random() < flack)
