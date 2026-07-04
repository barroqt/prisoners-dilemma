from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Callable
import re

from core.match_history import match_history_with_noise_events
from simulation.engine import run_tournament


StrategyFn = Callable[[list[tuple[bool, bool]]], bool]
ProgressFn = Callable[[float], None]


@dataclass(frozen=True)
class StrategyInfo:
    id: str
    number: int
    short_name: str
    category: str
    category_short: str
    intro: str
    description: str
    details: str


_CATEGORY_BY_STEM_SUFFIX: dict[str, str] = {
    # Cooperative / Reciprocal
    "always_coop": "Cooperative / Reciprocal",
    "tit_for_tat": "Cooperative / Reciprocal",
    "tit_for_two_tat": "Cooperative / Reciprocal",
    "soft_grudger": "Cooperative / Reciprocal",
    "champion": "Cooperative / Reciprocal",
    "sus_tit_for_tat": "Cooperative / Reciprocal",
    "random_tit_for_tat": "Cooperative / Reciprocal",
    # Retaliatory
    "grim_trigger": "Retaliatory",
    "hard_tit_for_tat": "Retaliatory",
    "cond_defect": "Retaliatory",
    "black": "Retaliatory",
    # Adaptive
    "pavlov": "Adaptive",
    "two_timer": "Adaptive",
    "tranquilizer": "Adaptive",
    # Exploitative
    "always_def": "Exploitative",
    "bully": "Exploitative",
    "prober": "Exploitative",
    "hard_prober": "Exploitative",
    # Statistical / Probabilistic
    "random": "Statistical / Probabilistic",
    "joss": "Statistical / Probabilistic",
}

_CATEGORY_SHORT: dict[str, str] = {
    "Cooperative / Reciprocal": "Co-op",
    "Retaliatory": "Retal",
    "Adaptive": "Adapt",
    "Exploitative": "Exploit",
    "Statistical / Probabilistic": "Stats",
    "Experimental / Complex": "Complex",
}

_INTRO_OVERRIDES: dict[str, str] = {
    "Tit For Tat": "Starts kind, then mirrors you.",
    "Grim Trigger": "One betrayal, then no mercy.",
    "Pavlov": "Repeats what worked, changes what failed.",
    "Prober": "Opens with a test to find weakness.",
}

_DESCRIPTION_OVERRIDES: dict[str, str] = {
    "Appold": "Starts friendly, then adapts based on how you react to cooperation and defection.",
    "Black": "Begins nice, then becomes less trusting when recent defections pile up.",
    "Borufsen": "Mostly mirrors you, but watches for suspicious patterns and can turn cold.",
    "Cave": "Starts kind, but may harden if you defect too often or seem chaotic.",
    "Champion": "Friendly at first, then tests whether you deserve long-term trust.",
    "Colbert": "Mostly cooperative, but answers betrayal with a fixed punishment sequence.",
    "Eatherley": "Cooperates freely, but retaliates more as your defection history grows.",
    "Getzler": "Remembers past betrayals, with recent ones hurting trust the most.",
    "Gladstein": "Opens with a test, then exploits the soft-hearted or falls back to mirroring.",
    "Graaskamp Katzen": "Plays cautiously and defects forever if its score falls too low.",
    "Grofman": "Starts nice, then uses a short memory window to judge your behavior.",
    "Harrington": "A tricky pattern-reader that probes, watches streaks, and changes modes.",
    "Kluepfel": "Looks for patterns in your responses and adjusts with a mix of logic and chance.",
    "Leyvraz": "A harsh strategy that quickly leans into defection when trust looks weak.",
    "Mikkelson": "Usually cooperative, but reacts sharply when it feels repeatedly betrayed.",
    "Richard Hufford": "A thoughtful cooperator that studies your habits before deciding how forgiving to be.",
    "Rowsam": "Starts nice, tracks your behavior closely, and punishes when defection becomes a trend.",
    "Tideman Chieruzzi": "Escalates punishment over time, but may offer a rare fresh start.",
    "Tranquilizer": "Tries to stay calm and profitable, sneaking in defections when the moment looks safe.",
    "Weiner": "A mostly mirroring strategy with occasional forgiveness and a limit to its patience.",
    "White": "Simple and nice early on, but less forgiving once defection becomes common.",
    "Wm Adams": "Stays cooperative for a while, then uses timed punishments as defections add up.",
    "Yamachi": "A strategic cooperator that watches for repeated patterns before turning against you.",
}


# Long-form, plain-English explanations of what each strategy's code actually
# does, written for readers with no coding background. "You" = the opponent.
_DETAILS_BY_LABEL: dict[str, str] = {
    "Always Coop": (
        "The ultimate optimist. It cooperates every single round, no matter what you do to it. "
        "It never retaliates, never tests you, and never changes its mind. Against other nice "
        "strategies it racks up steady points, but a hostile opponent can exploit it round after "
        "round without ever facing consequences."
    ),
    "Always Def": (
        "The ultimate cynic. It defects every single round, no matter what you do. It can never be "
        "talked into cooperating, so it wins big against trusting opponents but gets locked into "
        "low-scoring mutual defection against anyone who fights back."
    ),
    "Tit For Tat": (
        "The famous classic. It cooperates on the first round, and from then on it simply copies "
        "whatever you did last round: cooperate with it and it cooperates back; defect and it "
        "defects right back, exactly once per betrayal. It never holds a grudge longer than one "
        "round, which makes it easy to make peace with — but it also never lets a betrayal slide."
    ),
    "Grim Trigger": (
        "One strike and you're out. It cooperates happily until the very first time you defect — "
        "then it defects for every remaining round of the match, with no way to earn its trust "
        "back. Perfect partners never notice the trap; a single slip turns it into a permanent enemy."
    ),
    "Pavlov": (
        "Also known as 'win-stay, lose-shift'. It cooperates first. After that, it looks at how the "
        "last round went: if the result was good for it (you both cooperated, or it defected while "
        "you cooperated), it repeats its own last move. If the result was bad (it got betrayed, or "
        "you both defected), it switches to the other move. In practice this means it cooperates "
        "whenever the two of you made the same move last round, and defects when your moves differed."
    ),
    "Random": (
        "Pure chaos. Every round it flips a fair coin: heads it cooperates, tails it defects. It "
        "ignores everything you do, so there is no way to build trust with it — and no pattern to "
        "exploit either."
    ),
    "Sus Tit For Tat": (
        "Suspicious Tit For Tat. It plays exactly like Tit For Tat — copying your previous move "
        "each round — except it opens with a defection instead of cooperation. That single "
        "untrusting first move can poison the whole match: against another mirroring strategy it "
        "often triggers an endless cycle of tit-for-tat revenge."
    ),
    "Prober": (
        "It opens with a three-round test: cooperate, defect, cooperate. If you cooperated through "
        "all three rounds — including forgiving its round-two jab — it concludes you won't defend "
        "yourself and defects for the rest of the match. If you pushed back at all, it apologizes "
        "in behavior: it switches to plain Tit For Tat and simply mirrors you from then on."
    ),
    "Tit For Two Tat": (
        "A more patient Tit For Tat. It cooperates unless you defected in both of the last two "
        "rounds. One isolated defection is written off as a mistake and forgiven instantly; only "
        "back-to-back betrayals convince it to strike back."
    ),
    "Anti Tit For Tat": (
        "A contrarian that does the exact opposite of whatever you just did. If you cooperated last "
        "round, it defects; if you defected, it cooperates. It opens with cooperation. It rewards "
        "aggression and punishes kindness, which makes it deeply confusing for strategies that try "
        "to build mutual trust."
    ),
    "Hard Tit For Tat": (
        "In this arena it behaves identically to Tit For Tat: it cooperates on round one, then "
        "copies your previous move every round after. The 'hard' in the name signals its attitude — "
        "every single defection gets answered immediately, with zero randomness and zero extra "
        "forgiveness."
    ),
    "Random Tit For Tat": (
        "Tit For Tat with a mean streak. It cooperates on the first round. Each round after that, "
        "there is a 70% chance it copies your last move like normal Tit For Tat — and a 30% chance "
        "it just defects, regardless of how nice you've been. You can never feel fully safe around it."
    ),
    "Soft Grudger": (
        "A Grim Trigger with one heart to spare. It cooperates and forgives your first defection "
        "completely — but the second time you defect, at any point in the match, it writes you off "
        "and defects for every remaining round. You get exactly one free mistake."
    ),
    "Hard Prober": (
        "A rougher version of Prober. It opens cooperate, defect, defect — hitting you twice to see "
        "if you'll tolerate abuse. If you cooperated through all three opening rounds, it decides "
        "you're a pushover and defects forever. If you retaliated, it behaves itself and plays "
        "plain Tit For Tat from then on."
    ),
    "Joss": (
        "A sneaky Tit For Tat. Most of the time it mirrors your last move, but every round it also "
        "has a 10% chance of defecting out of nowhere, hoping to steal a few extra points. Against "
        "unforgiving opponents those little stabs tend to spiral into long revenge cycles that cost "
        "it dearly."
    ),
    "Bully": (
        "It defects first and keeps hitting anyone who doesn't fight back. If you retaliate, it "
        "backs off and offers one cooperation — then goes right back to defecting. In short: it "
        "only respects strength, briefly, and mercilessly exploits anyone who keeps turning the "
        "other cheek."
    ),
    "Cond Defect": (
        "A predator that targets the generous. It defects first, and each round checks your overall "
        "cooperation rate: if you've cooperated at least half the time, it defects to exploit your "
        "goodwill. Only when you cooperate less than half the time does it switch to mirroring your "
        "last move. Being nice to it is exactly what it's waiting for."
    ),
    "Two Timer": (
        "An erratic alternator. It cooperates on round one, defects on round two, and after that "
        "mostly alternates between cooperating and defecting on a fixed rhythm — unless you defect "
        "twice in a row, in which case it joins you in defecting. Its zigzag pattern makes it hard "
        "to settle into stable cooperation with."
    ),
    "Appold": (
        "A statistician. After four friendly opening rounds, it starts tracking two numbers: how "
        "often you cooperate after it was nice to you, and how often you cooperate after it "
        "betrayed you. Each round it looks at its own move from two rounds back, picks the matching "
        "statistic, and cooperates with that probability. Essentially, it learns how you respond to "
        "kindness versus betrayal and reflects your own behavior back at you. If you never "
        "cooperate after the opening, it simply defects."
    ),
    "Black": (
        "It cooperates unconditionally for the first five rounds. After that it only looks at your "
        "last five moves and counts your defections: zero or one and it still cooperates every "
        "time; two drops its cooperation chance to 88%, three to 68%, four to 40%, and five recent "
        "defections leave just a 4% chance it cooperates. Trust recovers just as fast once you "
        "clean up your recent record."
    ),
    "Borufsen": (
        "A Tit For Tat player with a review process. Roughly every 25 rounds it audits your recent "
        "behavior: if you barely cooperated — or only cooperated while it was defecting — it enters "
        "a punishment mode and defects for the entire next stretch. It also has two clever peace "
        "moves: it detects the endless echo of alternating revenge that two mirroring strategies "
        "can fall into and deliberately cooperates to break the loop, and after three straight "
        "rounds of mutual defection it offers cooperation to reset the relationship."
    ),
    "Cave": (
        "Starts friendly, but keeps a hard limit on how much hostility it will accept. If your "
        "overall defection rate climbs too high for how long the match has run (over ~80% early, "
        "~65% later, ~40% after forty rounds), it gives up on you and defects. Otherwise it "
        "cooperates whenever you just cooperated; if you just defected, it flips a coin — until "
        "you've racked up 18 total defections, after which the coin flips stop and it just defects back."
    ),
    "Champion": (
        "A three-phase diplomat. Phase one (rounds 1–10): unconditional cooperation, no matter "
        "what. Phase two (rounds 11–25): plain Tit For Tat, mirroring your last move. Phase three "
        "(round 26 on): it always cooperates when you just cooperated; when you just defected, it "
        "checks your overall record — if you've cooperated less than 60% of the time, it defects "
        "with a probability equal to your defection rate. The nastier your history, the more likely "
        "the punishment."
    ),
    "Colbert": (
        "Cooperates through the first eight rounds except for one planned test defection on round "
        "six. After that it lives by a fixed ritual: the moment you defect, it runs a four-move "
        "punishment script — defect, defect, cooperate, cooperate — punishing you twice and then "
        "extending the olive branch twice, ignoring whatever you do in the meantime. Outside the "
        "script, it cooperates as long as you did."
    ),
    "Eatherley": (
        "A proportional judge. Whenever you cooperate, it cooperates right back. When you defect, "
        "it retaliates with a probability equal to your overall defection rate so far. A rare slip "
        "from a mostly-nice player is usually forgiven; a chronic defector faces near-certain "
        "retaliation every time."
    ),
    "Getzler": (
        "It carries a fading grudge. Every defection of yours adds resentment, but each one's "
        "weight halves with every round that passes — last round's betrayal counts fully, one from "
        "two rounds ago counts half, and older ones fade toward nothing. Each round it defects with "
        "probability equal to its current resentment level. Recent or repeated betrayals make it "
        "almost certain to strike back; old ones are quickly forgotten."
    ),
    "Gladstein": (
        "It opens with a test defection to see what you're made of. If you never punish it, it "
        "stays in exploit mode: it keeps sprinkling in defections, carefully keeping them just "
        "under half of its moves so the relationship stays profitable. But the first time you "
        "defect back, it immediately offers one apology cooperation and then plays honest Tit For "
        "Tat for the rest of the match."
    ),
    "Graaskamp Katzen": (
        "A Tit For Tat player with a business plan. It checks its own total score against fixed "
        "milestones — at least 23 points by round 11, 53 by round 21, 83 by round 31, 113 by round "
        "41, 143 by round 51, and 293 by round 101. If it has ever come up short at a checkpoint, "
        "it concludes the partnership isn't paying and defects for the rest of the match. "
        "Otherwise it simply mirrors your last move."
    ),
    "Grofman": (
        "Cooperates for two rounds, plays Tit For Tat through round seven, then becomes a window "
        "judge: each round it reviews seven of your recent moves (skipping the very latest). If it "
        "cooperated last round, it keeps cooperating as long as you defected at most twice in that "
        "window. If it defected last round, it demands a cleaner record — at most one defection — "
        "before it returns to cooperating."
    ),
    "Harrington": (
        "Mostly a Tit For Tat player with a hidden test. On round 37 it throws in one surprise "
        "defection to see how you react; if you had been perfectly cooperative until then, it "
        "immediately returns to cooperation on round 38 rather than letting things spiral. It also "
        "has a patience limit: if you defect twenty rounds in a row, it decides you're beyond "
        "saving and defects too."
    ),
    "Kluepfel": (
        "A momentum reader with a random streak. It reacts to your recent consistency: repeat the "
        "same move three or more times and it simply copies you; twice in a row and it follows "
        "your lead about 90% of the time; after a single cooperation it cooperates 70% of the "
        "time, and after a single defection only 40%. Past round 26 it also runs a statistical "
        "check — if your responses look random, as if you're ignoring what it does entirely, it "
        "stops wasting kindness and defects."
    ),
    "Leyvraz": (
        "It decides using only your last three moves, looked up in a fixed table of cooperation "
        "chances. Three straight cooperations earn guaranteed cooperation. Steady recent defection "
        "drops its cooperation chance to 25%. And some patterns get judged harshly: a lone "
        "defection sandwiched between cooperations gets zero trust at all. It never looks further "
        "back than three rounds, so both grudges and gratitude are short-lived."
    ),
    "Mikkelson": (
        "It runs a trust account that starts at 7 points. Every cooperation of yours adds 1 (up to "
        "a cap of 8); every defection costs 2 (down to a floor of −7). While the account is "
        "positive, it cooperates. In the first ten rounds an emptied account gets topped back up "
        "to 4 — early mistakes are forgiven. Later on, once the account runs dry it defects, "
        "unless your lifetime defection rate is under 15%, in which case it gives you the benefit "
        "of the doubt."
    ),
    "Richard Hufford": (
        "It measures 'agreement' — how often your moves line up with what it played. When "
        "agreement is very high (over 90% overall and perfect across the last four rounds), it "
        "cooperates. Moderate agreement gets Tit For Tat: it copies your last move. Poor agreement "
        "gets defection. It also probes long peace: after about 21 straight rounds of you "
        "cooperating, it throws in one test defection to check you're paying attention, and your "
        "reaction determines how long it waits before testing again."
    ),
    "Rowsam": (
        "An auditor. Every six rounds it reviews its average score and adds 'distrust points' the "
        "worse things look — from one point when earnings are merely mediocre up to five when "
        "they're terrible. A disappointing audit triggers a short warning: defect, cooperate, "
        "defect. Distrust also slowly fades over time. But if distrust ever reaches seven points, "
        "it concludes you can't be worked with and defects for the rest of the match."
    ),
    "Tideman Chieruzzi": (
        "A Tit For Tat player with an endgame and a peace offer. It mirrors your moves and punishes "
        "your defections, but under specific conditions it offers a 'fresh start': if it's ahead by "
        "at least 10 points, twenty or more rounds have been played, and your behavior is clearly "
        "deliberate rather than random, it cooperates out of the blue to try to reset the "
        "relationship. It also always defects on the last two rounds of a standard 200-round "
        "match, when there's no future left to protect."
    ),
    "Tranquilizer": (
        "It plays by how well things are going. When its average score is poor, it plays it safe "
        "with plain Tit For Tat. In the middle range, it cooperates with a probability based on "
        "your overall cooperation rate, minus a penalty for your current defection streak. And "
        "when things are going well, it gets greedy: it cooperates only about 80% of the time, "
        "sneaking in random defections to skim extra points while the relationship feels safe."
    ),
    "Weiner": (
        "Tit For Tat with a noise filter and a patience limit. It watches for odd-length bursts of "
        "defection (one, three, five in a row) that you end by cooperating — it treats those as "
        "likely mistakes and forgives your next defection instead of retaliating. But its patience "
        "has a hard cap: if you defected five or more times within a recent twelve-round stretch, "
        "it defects no matter what."
    ),
    "White": (
        "Unconditionally kind for the first ten rounds. After that, it always cooperates when you "
        "just cooperated. When you defect, it weighs your total defections against how far the "
        "match has progressed, using an allowance that grows slowly over time — occasional "
        "defections stay within the allowance and are tolerated, but chronic defection pushes past "
        "it and gets met with defection."
    ),
    "Wm Adams": (
        "A very tolerant player with precise warning shots. It cooperates almost all the time, "
        "counting your defections as it goes — and fires back exactly one defection when your "
        "count hits 4, 7, and 9. Past nine defections its patience wears thin: each time you "
        "defect, its chance of still cooperating halves with every additional betrayal (50%, 25%, "
        "12.5%…), sliding steadily toward permanent retaliation."
    ),
    "Yamachi": (
        "A habit profiler. It builds a table of your behavior patterns: in each situation (your "
        "earlier move, then its reply), what did you do next? When deciding, it finds the current "
        "situation in that table and predicts your next move from your own history — cooperating "
        "if you usually cooperated in this spot, defecting if you usually didn't. One exception: "
        "past round 40, if your defection rate hovers near 50% — the signature of playing "
        "randomly — it stops trying to predict you and just defects."
    ),
}


def _stem_suffix(path_stem: str) -> str:
    # s03_tit_for_tat -> tit_for_tat
    return re.sub(r"^s\d{2}_", "", path_stem)


def _category_for_stem_suffix(suffix: str) -> str:
    return _CATEGORY_BY_STEM_SUFFIX.get(suffix, "Experimental / Complex")


def _first_sentence(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    # Take a short, player-facing one-liner.
    if "." in text:
        return text.split(".", 1)[0].strip() + "."
    return text


def available_strategies_meta() -> list[StrategyInfo]:
    strategies_dir = Path(__file__).resolve().parent.parent / "strategies"
    infos: list[StrategyInfo] = []

    for path in sorted(strategies_dir.glob("s*.py")):
        number = _strategy_number_from_filename(path.name)
        if number is None or number > 41:
            continue

        module = import_module(f"strategies.{path.stem}")
        function_name = f"s{number:02d}"
        function_object = getattr(module, function_name)
        label = _strategy_label(path.name)
        display_id = f"{function_name} - {label}"

        suffix = _stem_suffix(path.stem)
        category = _category_for_stem_suffix(suffix)
        category_short = _CATEGORY_SHORT.get(category, "Complex")

        doc = (function_object.__doc__ or "").strip()
        description = _DESCRIPTION_OVERRIDES.get(label, doc or "A unique approach to cooperation and betrayal.")
        intro = _INTRO_OVERRIDES.get(label, _first_sentence(description))
        details = _DETAILS_BY_LABEL.get(label, description)

        infos.append(
            StrategyInfo(
                id=display_id,
                number=number,
                short_name=label,
                category=category,
                category_short=category_short,
                intro=intro,
                description=description,
                details=details,
            )
        )

    infos.sort(key=lambda x: x.number)
    return infos


def _strategy_number_from_filename(filename: str) -> int | None:
    if not filename.startswith("s") or not filename.endswith(".py"):
        return None
    numeric = filename[1:3]
    if not numeric.isdigit():
        return None
    return int(numeric)


def _strategy_label(filename: str) -> str:
    stem = Path(filename).stem
    parts = stem.split("_")[1:]
    if not parts:
        return stem
    return " ".join(parts).replace("-", " ").title()


def load_strategy_registry(limit: int = 16) -> dict[str, StrategyFn]:
    strategies_dir = Path(__file__).resolve().parent.parent / "strategies"
    by_number: list[tuple[int, str, StrategyFn]] = []

    for path in sorted(strategies_dir.glob("s*.py")):
        number = _strategy_number_from_filename(path.name)
        if number is None or number > limit:
            continue

        module = import_module(f"strategies.{path.stem}")
        function_name = f"s{number:02d}"
        function_object = getattr(module, function_name)
        display_name = f"{function_name} - {_strategy_label(path.name)}"
        by_number.append((number, display_name, function_object))

    by_number.sort(key=lambda item: item[0])
    return {display_name: fn for _, display_name, fn in by_number}


DEFAULT_STRATEGIES = load_strategy_registry(limit=41)


def available_strategies() -> list[str]:
    return list(DEFAULT_STRATEGIES.keys())


def resolve_players(strategies: list[str]) -> tuple[dict[str, StrategyFn], dict[str, str]]:
    """Resolves strategy ids (built-in display ids or 'custom:<id>') to callables.

    Returns (players, labels) where labels maps ids to short display names.
    Built-in, builder-compiled, and marketplace-forked strategies all share the
    same pure-function interface, so they are interchangeable here.
    """
    players: dict[str, StrategyFn] = {}
    labels: dict[str, str] = {}
    unknown: list[str] = []

    for name in strategies:
        if name in players:
            continue
        if name.startswith("custom:"):
            import storage
            from builder.compiler import compile_definition

            record = storage.get_strategy(name)
            if record is None:
                unknown.append(name)
                continue
            players[name] = compile_definition(record["definition"])
            labels[name] = record["name"]
        elif name in DEFAULT_STRATEGIES:
            players[name] = DEFAULT_STRATEGIES[name]
            labels[name] = _short_display_name(name)
        else:
            unknown.append(name)

    if unknown:
        raise ValueError(f"Unknown strategies: {', '.join(unknown)}")
    return players, labels


def _short_display_name(name: str) -> str:
    return name.split(" - ", 1)[1] if " - " in name else name


def run_simulation(
    strategies: list[str],
    rounds: int,
    iterations: int,
    noise: float = 0.0,
    progress: ProgressFn | None = None,
) -> dict:
    if len(strategies) < 2:
        raise ValueError("At least two strategies must be selected.")
    if rounds <= 0:
        raise ValueError("rounds must be > 0.")
    if iterations <= 0:
        raise ValueError("iterations must be > 0.")
    if noise < 0 or noise > 1:
        raise ValueError("noise must be between 0 and 1.")

    players, labels = resolve_players(strategies)
    return run_tournament(
        players=players,
        rounds=rounds,
        iterations=iterations,
        noise=noise,
        labels=labels,
        progress=progress,
    )


def demo_match(strategy_id: str, rounds: int = 20) -> dict:
    """Short match against Tit for Tat for the encyclopedia's animated demos."""
    players, labels = resolve_players([strategy_id])
    strategy = players[strategy_id]
    tit_for_tat = import_module("strategies.s03_tit_for_tat").s03
    history, noise_events = match_history_with_noise_events(strategy, tit_for_tat, rounds, 0.0)
    return {
        "strategy": strategy_id,
        "label": labels[strategy_id],
        "opponent": "Tit For Tat",
        "moves": "".join("C" if m[0] else "D" for m in history),
        "opponent_moves": "".join("C" if m[1] else "D" for m in history),
    }
