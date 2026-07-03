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

        infos.append(
            StrategyInfo(
                id=display_id,
                number=number,
                short_name=label,
                category=category,
                category_short=category_short,
                intro=intro,
                description=description,
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
