def s24(match_history):
    turn = len(match_history) + 1
    if turn <= 8:
        return turn != 6

    # Reconstruct active punishment script D,D,C,C.
    script = [False, False, True, True]
    idx = 0
    t = 9
    while t < turn:
        if idx > 0:
            idx = (idx + 1) % 4
        else:
            # Trigger if opponent defected previous turn.
            if not match_history[t - 2][1]:
                idx = 1
            else:
                idx = 0
        t += 1

    if idx > 0:
        return script[idx]
    if not match_history[-1][1]:
        return False
    return True
