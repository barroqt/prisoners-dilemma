def s33(match_history):
    credit = 7
    turn = len(match_history) + 1
    if turn == 1:
        return True

    opp = [o for _, o in match_history]
    for t in range(2, turn + 1):
        if opp[t - 2]:
            credit = min(8, credit + 1)
        else:
            credit = max(-7, credit - 2)

        if t == turn:
            if t == 2:
                return True
            if credit > 0:
                return True
            if t <= 10:
                return False
            opp_defections = sum(1 for x in opp if not x)
            return not (opp_defections / t >= 0.15)

        if t > 2 and credit <= 0 and t <= 10:
            credit = 4
