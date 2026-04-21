import math


def s34(match_history):
    num_agreements = 2
    last_four_agreements = [1, 1, 1, 1]
    last_four_index = 0
    streak_needed = 21
    current_streak = 2
    last_aberration = float("inf")
    coop_after_ab_count = 2
    def_after_ab_count = 2

    opp = [o for _, o in match_history]
    me = [m for m, _ in match_history]

    next_action = True
    for t in range(1, len(match_history) + 1):
        if t == 1:
            next_action = True
        else:
            last_four_index = (last_four_index + 1) % 4
            me_two_ago = True if t <= 2 else me[t - 3]
            if me_two_ago == opp[t - 2]:
                num_agreements += 1
                last_four_agreements[last_four_index] = 1
            else:
                last_four_agreements[last_four_index] = 0

            if t < last_aberration:
                if opp[t - 2]:
                    current_streak += 1
                else:
                    current_streak = 0
                if current_streak >= streak_needed:
                    last_aberration = t
                    if current_streak == streak_needed:
                        next_action = False
                        continue
            elif t == last_aberration + 2:
                last_aberration = float("inf")
                if opp[t - 2]:
                    coop_after_ab_count += 1
                else:
                    def_after_ab_count += 1
                streak_needed = math.floor(20.0 * def_after_ab_count / coop_after_ab_count) + 1
                current_streak = 0
                next_action = True
                continue

            proportion_agree = num_agreements / t
            last_four_num = sum(last_four_agreements)
            if proportion_agree > 0.9 and last_four_num >= 4:
                next_action = True
            elif proportion_agree >= 0.625 and last_four_num >= 2:
                next_action = opp[t - 2]
            else:
                next_action = False

    return next_action
