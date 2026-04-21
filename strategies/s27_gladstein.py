def s27(match_history):
    if not match_history:
        return False

    opp_ever_defected = any(not opp for _, opp in match_history)
    if opp_ever_defected:
        # Apology move immediately after first observed opponent defection.
        first_defect_idx = next(i for i, (_, opp) in enumerate(match_history) if not opp)
        if len(match_history) == first_defect_idx + 1:
            return True
        return match_history[-1][1]  # TFT forever afterwards

    # Patsy mode exploitation while no observed opponent defection.
    # Exclude first-turn test defection from ratio.
    if len(match_history) == 1:
        return False

    later_moves = [my for my, _ in match_history[1:]]
    my_defects = sum(1 for my in later_moves if not my)
    total = len(later_moves)
    if total == 0:
        return False
    # Keep defection ratio under 0.5.
    projected_ratio = (my_defects + 1) / (total + 1)
    return projected_ratio >= 0.5
