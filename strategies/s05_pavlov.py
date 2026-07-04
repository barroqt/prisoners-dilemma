def s05(match_history):
    """Repeats last move if payoff was good; switches if it was bad."""
    if not match_history:
        return True
    # Win-stay, lose-shift: CC (3) and DC (5) pay well -> repeat my move;
    # CD (0) and DD (1) pay badly -> switch. Equivalent to cooperating iff
    # both players made the same move last round.
    return match_history[-1][0] == match_history[-1][1]