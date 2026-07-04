"""Regression checks for the fixed strategies."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.match_history import match_history, payoff
from strategies.s05_pavlov import s05
from strategies.s16_bully import s16
from strategies.s28_graaskamp_katzen import s28
from strategies.s01_always_coop import s01
from strategies.s02_always_def import s02
from strategies.s03_tit_for_tat import s03

failures = []


def check(name, cond, detail=""):
    print(f"[{'ok ' if cond else 'FAIL'}] {name}", "" if cond else detail)
    if not cond:
        failures.append(name)


def moves(h, side=0):
    return "".join("C" if m[side] else "D" for m in h)


# --- Pavlov (win-stay lose-shift) ---
# vs AlwaysDef every round is a losing payoff (0 or 1), so Pavlov shifts every
# round: the canonical C,D,C,D... alternation.
h = match_history(s05, s02, 8)
check("Pavlov vs AlwaysDef alternates", moves(h) == "CDCDCDCD", moves(h))
h = match_history(s05, s01, 8)
check("Pavlov vs AlwaysCoop = all C", moves(h) == "CCCCCCCC", moves(h))
h = match_history(s05, s03, 8)
check("Pavlov vs TFT = all C", moves(h) == "CCCCCCCC", moves(h))
# From a (D,C) state Pavlov keeps defecting (win-stay on 5 points)
check("Pavlov stays on winning D", s05([(False, True)]) is False)
# From (D,D) it shifts back to C
check("Pavlov shifts after mutual D", s05([(False, False)]) is True)

# --- Bully ---
check("Bully defects first", s16([]) is False)
check("Bully cooperates when hit back", s16([(False, False)]) is True)
check("Bully keeps hitting a cooperator", s16([(False, True)]) is False)

# --- Graaskamp-Katzen: failed past threshold stays failed ---
# 11 rounds of mutual defection = 11 pts < 23 -> fails turn-11 threshold.
bad_start = [(False, False)] * 11
# Then 60 rounds of (me D, opp C) = +5/round; current score rockets past every
# threshold, but the turn-11 failure must still force defection.
rich_later = bad_start + [(False, True)] * 60
score_now = sum(payoff[m][0] for m in rich_later)
check("GK: past failure persists despite high current score",
      s28(rich_later) is False, f"score_now={score_now}")
# Clean cooperative history passes all thresholds -> plays TFT (cooperates).
good = [(True, True)] * 50
check("GK: healthy history keeps cooperating", s28(good) is True)

print()
print("RESULT:", "ALL PASS" if not failures else f"{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
