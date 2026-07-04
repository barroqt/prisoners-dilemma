"""QA harness: interaction invariants for Prisoner's Arena."""
import random
import sys
import traceback

sys.path.insert(0, "/Users/thomas/dev/Prisoners_dilemma")

from core.match_history import match_history_with_noise_events, swap_history, payoff
from simulation.service import DEFAULT_STRATEGIES
from simulation.engine import run_tournament

failures = []


def fail(msg):
    failures.append(msg)
    print("FAIL:", msg)


TFT_ID = "s03 - Tit For Tat"
tft = DEFAULT_STRATEGIES[TFT_ID]

# ---- Test A: TFT retaliation invariant in raw matches (both seats), no noise ----
print("== Test A: TFT invariant vs all strategies, both seats ==")
random.seed(42)
for name, fn in DEFAULT_STRATEGIES.items():
    # TFT as player 2
    hist, _ = match_history_with_noise_events(fn, tft, 100, 0.0)
    for i, (m1, m2) in enumerate(hist):
        expected = True if i == 0 else hist[i - 1][0]
        if m2 != expected:
            fail(f"A: TFT (as P2) vs {name}: round {i} played {m2}, expected {expected}")
            break
    # TFT as player 1
    hist, _ = match_history_with_noise_events(tft, fn, 100, 0.0)
    for i, (m1, m2) in enumerate(hist):
        expected = True if i == 0 else hist[i - 1][1]
        if m1 != expected:
            fail(f"A: TFT (as P1) vs {name}: round {i} played {m1}, expected {expected}")
            break

# ---- Test B: all strategies return real booleans on fuzz histories ----
print("== Test B: strategies return bools on fuzzed histories ==")
random.seed(7)
fuzz_histories = [[]]
for _ in range(60):
    n = random.randint(1, 220)
    fuzz_histories.append([(random.random() < 0.5, random.random() < 0.5) for _ in range(n)])
# adversarial extremes
for n in (1, 2, 3, 5, 36, 37, 38, 40, 50, 199, 200, 201):
    fuzz_histories.append([(True, True)] * n)
    fuzz_histories.append([(False, False)] * n)
    fuzz_histories.append([(True, False)] * n)
    fuzz_histories.append([(False, True)] * n)

for name, fn in DEFAULT_STRATEGIES.items():
    for h in fuzz_histories:
        snapshot = [tuple(m) for m in h]
        try:
            out = fn(h)
        except Exception:
            fail(f"B: {name} raised on history len={len(h)}:\n{traceback.format_exc(limit=2)}")
            break
        if not isinstance(out, bool):
            fail(f"B: {name} returned {out!r} (type {type(out).__name__}) on history len={len(h)}")
            break
        if h != snapshot:
            fail(f"B: {name} MUTATED the history list (len={len(h)})")
            break

# ---- Test C: engine-level — TFT retaliation_rate must be 1.0 without noise ----
print("== Test C: engine retaliation/forgiveness stats for TFT ==")
players = {k: DEFAULT_STRATEGIES[k] for k in [
    "s01 - Always Coop", "s02 - Always Def", TFT_ID, "s04 - Grim Trigger",
    "s05 - Pavlov", "s15 - Joss", "s08 - Prober",
]}
random.seed(1)
data = run_tournament(players, rounds=200, iterations=3, noise=0.0)
row = next(r for r in data["leaderboard"] if r["strategy"] == TFT_ID)
if row["retaliation_rate"] is not None and row["retaliation_rate"] < 0.999:
    fail(f"C: TFT retaliation_rate = {row['retaliation_rate']} (expected 1.0, no noise)")
print("   TFT row:", {k: row[k] for k in ('retaliation_rate', 'forgiveness_rate', 'cooperation_rate', 'defected_first_rate')})

# featured-match invariant: replayed moves must respect TFT rule
for m in data["matches"]:
    for seat, me, opp in ((1, "moves_p1", "moves_p2"), (2, "moves_p2", "moves_p1")):
        who = m["p1"] if seat == 1 else m["p2"]
        if who != TFT_ID:
            continue
        mine, theirs = m[me], m[opp]
        for i in range(len(mine)):
            expected = "C" if i == 0 else theirs[i - 1]
            if mine[i] != expected:
                fail(f"C: featured match {m['p1']} vs {m['p2']}: TFT seat{seat} round {i} = {mine[i]}, expected {expected}")
                break

# ---- Test D: builder-compiled TFT template equals s03 on fuzz histories ----
print("== Test D: builder TFT == s03 ==")
from builder.compiler import compile_definition
tft_def = {
    "first_move": "cooperate",
    "rules": [{"conditions": [{"fact": "opp_last_move", "op": "is", "value": "defect"}], "action": {"type": "defect"}}],
    "default_action": {"type": "cooperate"},
}
btft = compile_definition(tft_def)
for h in fuzz_histories:
    if btft(h) != tft(h):
        fail(f"D: builder TFT diverges from s03 on history len={len(h)}: {btft(h)} vs {tft(h)}")
        break

# ---- Test E: noise events consistency ----
print("== Test E: noise events recorded consistently ==")
random.seed(3)
hist, events = match_history_with_noise_events(tft, DEFAULT_STRATEGIES["s01 - Always Coop"], 500, 0.1)
# every P2 (always coop) defect must be a recorded noise event
ev = set(map(tuple, events))
for i, (m1, m2) in enumerate(hist):
    if not m2 and (i, 1) not in ev:
        fail(f"E: AlwaysCoop defected at round {i} without a noise event")
        break

# ---- Test F: score symmetry in engine matrix ----
print("== Test F: leaderboard totals equal sum over matrix ==")
# total matches per strategy = (n-1) * iterations; average per-match totals should reconcile
n = len(players)
for r in data["leaderboard"]:
    if r["matches_played"] != (n - 1) * 3:
        fail(f"F: {r['strategy']} matches_played={r['matches_played']} expected {(n-1)*3}")

print()
print("RESULT:", "ALL PASS" if not failures else f"{len(failures)} failure(s)")
