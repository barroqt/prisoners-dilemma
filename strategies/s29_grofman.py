def s29(match_history):
    turn = len(match_history) + 1
    if turn <= 2:
        return True
    if 3 <= turn <= 7:
        return match_history[-1][1]

    # Turn 8 onward: use previous 7 rounds out of last 8, ignoring most recent.
    window = match_history[-8:-1]
    opp_defections = sum(1 for _, opp in window if not opp)
    my_last = match_history[-1][0]
    if my_last:
        return opp_defections <= 2
    return opp_defections <= 1
