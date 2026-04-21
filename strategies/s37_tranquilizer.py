import random

from core.match_history import payoff


def s37(match_history):
    if not match_history:
        return True

    total = len(match_history)
    my_score = sum(payoff[(my, opp)][0] for my, opp in match_history)
    avg_score = my_score / total
    opp_coop_rate = sum(1 for _, opp in match_history if opp) / total
    opp_defect_streak = 0
    for _, opp in reversed(match_history):
        if not opp:
            opp_defect_streak += 1
        else:
            break

    # Fallback: TFT in low-score regime.
    if avg_score < 1.75:
        return match_history[-1][1]

    # Mid-score regime.
    if avg_score < 2.25:
        p_coop = 0.35 + 0.4 * opp_coop_rate - 0.05 * min(5, opp_defect_streak)
        p_coop = max(0.0, min(1.0, p_coop))
        return random.random() < p_coop

    # High-score regime: opportunistic occasional defections.
    recently_defected = (not match_history[-1][1])
    p_coop = 0.8 - (0.15 if recently_defected else 0.0)
    p_coop = max(0.0, min(1.0, p_coop))
    return random.random() < p_coop
