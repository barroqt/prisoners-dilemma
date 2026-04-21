from core.match_history import payoff


def s35(match_history):
    mode = "Normal"
    distrust_points = 0
    current_score = 0

    next_action = True
    for t in range(1, len(match_history) + 1):
        if t > 1:
            my_last, opp_last = match_history[t - 2]
            current_score += payoff[(my_last, opp_last)][0]

        if mode == "Defect":
            next_action = False
            continue

        if mode == "Coop Def Cycle 1":
            mode = "Coop Def Cycle 2"
            next_action = True
            continue

        if mode == "Coop Def Cycle 2":
            mode = "Normal"
            next_action = False
            continue

        if t % 18 == 0 and distrust_points >= 3:
            distrust_points -= 1

        if t % 6 != 0:
            next_action = True
            continue

        points_per_turn = current_score / t
        if points_per_turn < 1.0:
            distrust_points += 5
        elif points_per_turn < 1.5:
            distrust_points += 3
        elif points_per_turn < 2.0:
            distrust_points += 2
        elif points_per_turn < 2.5:
            distrust_points += 1
        else:
            next_action = True
            continue

        if distrust_points >= 7:
            mode = "Defect"
        else:
            mode = "Coop Def Cycle 1"
        next_action = False

    return next_action
