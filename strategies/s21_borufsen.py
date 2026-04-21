def _is_echo_pattern(last_three):
    # Alternating echo-like pattern in the last three rounds.
    if len(last_three) < 3:
        return False
    return (
        last_three[0][0] == last_three[1][1]
        and last_three[1][0] == last_three[2][1]
        and last_three[0][1] == last_three[1][0]
        and last_three[1][1] == last_three[2][0]
    )


def s21(match_history):
    turn = len(match_history) + 1
    if turn == 1:
        return True

    defect_mode = False
    just_exited_defect = False
    flip_next_defect = False
    cc_count = 0
    cd_count = 0

    for idx in range(1, len(match_history) + 1):
        my_prev = match_history[idx - 1][0]
        opp_now = match_history[idx - 1][1]
        if opp_now:
            if my_prev:
                cc_count += 1
            else:
                cd_count += 1

        simulated_turn = idx + 1
        if simulated_turn >= 27 and simulated_turn % 25 == 2:
            coops = cc_count + cd_count
            next_defect_mode = coops < 3 or (8 <= coops <= 17 and (cc_count / coops) < 0.7)
            just_exited_defect = defect_mode and not next_defect_mode
            defect_mode = next_defect_mode
            cc_count = 0
            cd_count = 0

        if not defect_mode and _is_echo_pattern(match_history[max(0, idx - 3):idx]):
            flip_next_defect = True

    if defect_mode:
        return False
    if just_exited_defect:
        return False

    if len(match_history) >= 3 and all((not m and not o) for m, o in match_history[-3:]):
        return True

    tft_move = match_history[-1][1]
    if flip_next_defect and not tft_move:
        return True
    return tft_move
