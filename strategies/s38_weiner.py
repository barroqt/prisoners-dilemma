def s38(match_history):
    if not match_history:
        return True

    # Base TFT
    action = match_history[-1][1]

    opp = [o for _, o in match_history]

    # Forgiveness trigger for odd-sized defect blocks ended by cooperation.
    forgive_flag = False
    defect_padding = 0
    for i in range(1, len(opp)):
        if not opp[i - 1]:
            defect_padding += 1
        elif opp[i] and defect_padding % 2 == 1 and defect_padding > 0:
            forgive_flag = True
            defect_padding = 0
        else:
            defect_padding = 0

    if forgive_flag and not opp[-1]:
        action = True

    # Override using last 12 excluding most recent.
    relevant = opp[-13:-1] if len(opp) >= 2 else []
    if sum(1 for x in relevant if not x) >= 5:
        return False

    return action
