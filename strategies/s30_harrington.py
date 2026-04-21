def s30(match_history):
    # Lightweight local implementation: TFT core plus documented key events.
    # Full canonical Harrington state machine can be added later if needed.
    turn = len(match_history) + 1
    if turn == 1:
        return True
    if turn == 37:
        return False
    if turn == 38:
        first36_all_coop = all(opp for _, opp in match_history[:36])
        if first36_all_coop and not match_history[36][1]:
            return True

    # Extra streak logic: if opponent defects for 20 straight turns, defect.
    if len(match_history) >= 20 and all(not opp for _, opp in match_history[-20:]):
        return False

    return match_history[-1][1]
