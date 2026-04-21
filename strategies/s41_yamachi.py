def s41(match_history):
    count_them_us_them = {
        (True, True, True): 0,
        (True, True, False): 0,
        (True, False, True): 0,
        (True, False, False): 0,
        (False, True, True): 0,
        (False, True, False): 0,
        (False, False, True): 0,
        (False, False, False): 0,
    }
    mod_history = []
    opp_defections = 0
    next_action = True
    opp = [o for _, o in match_history]

    def maybe_override(action, current_turn, current_opp_defections):
        if current_turn > 40:
            portion_defect = (current_opp_defections + 0.5) / current_turn
            if 0.45 < portion_defect < 0.55:
                return False
        return action

    for t in range(1, len(match_history) + 1):
        if t == 1:
            base_action = True
        else:
            us_last = mod_history[-1]
            them_two_ago = True
            us_two_ago = True
            them_three_ago = True
            if t >= 3:
                them_two_ago = opp[t - 3]
                us_two_ago = mod_history[-2]
            if t >= 4:
                them_three_ago = opp[t - 4]

            if t >= 3:
                count_them_us_them[(them_three_ago, us_two_ago, them_two_ago)] += 1

            if count_them_us_them[(them_two_ago, us_last, True)] >= count_them_us_them[(them_two_ago, us_last, False)]:
                base_action = True
            else:
                base_action = False

        next_action = maybe_override(base_action, t, opp_defections)
        mod_history.append(base_action)
        if not opp[t - 1]:
            opp_defections += 1

    return next_action
