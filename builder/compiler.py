from __future__ import annotations

"""No-code strategy builder: validates a constrained rule graph and compiles it
to a strategy function with the standard pure-function interface
(history in, cooperate/defect out).

The vocabulary is deliberately closed (fixed facts, comparison ops, actions,
first-match-wins rule evaluation) so user-built strategies can never loop,
recurse, or escape the sandbox. Execution never uses exec/eval on user input:
the graph is interpreted by a closure. A readable Python source rendering is
generated alongside purely for display/export.
"""

import random
from typing import Callable

StrategyFn = Callable[[list[tuple[bool, bool]]], bool]

MAX_RULES = 20
MAX_CONDITIONS = 5

MOVE_FACTS = {"opp_last_move", "my_last_move", "opp_move_n_back", "my_move_n_back"}
NUMERIC_FACTS = {
    "round_number",
    "opp_defection_count",
    "opp_defection_rate",
    "opp_cooperation_rate",
    "opp_coop_streak",
    "opp_defect_streak",
    "mutual_coop_streak",
    "my_score",
    "opp_score",
    "score_diff",
}
CHANCE_FACT = "chance"
ALL_FACTS = MOVE_FACTS | NUMERIC_FACTS | {CHANCE_FACT}

NUMERIC_OPS = {"eq", "gt", "gte", "lt", "lte"}
ACTIONS = {"cooperate", "defect", "copy_opponent", "opposite_of_opponent", "random"}

FACT_LABELS = {
    "opp_last_move": "opponent's last move",
    "my_last_move": "my last move",
    "opp_move_n_back": "opponent's move N rounds back",
    "my_move_n_back": "my move N rounds back",
    "round_number": "current round number",
    "opp_defection_count": "opponent's total defections",
    "opp_defection_rate": "opponent's defection rate",
    "opp_cooperation_rate": "opponent's cooperation rate",
    "opp_coop_streak": "opponent's current cooperation streak",
    "opp_defect_streak": "opponent's current defection streak",
    "mutual_coop_streak": "current mutual cooperation streak",
    "my_score": "my score so far",
    "opp_score": "opponent's score so far",
    "score_diff": "my score minus opponent's score",
    "chance": "random chance",
}


class BuilderValidationError(ValueError):
    pass


def _fail(message: str) -> None:
    raise BuilderValidationError(message)


def validate_definition(definition: dict) -> dict:
    """Validates and normalizes a builder definition. Returns the normalized dict."""
    if not isinstance(definition, dict):
        _fail("Definition must be an object.")

    first_move = definition.get("first_move", "cooperate")
    if first_move not in ("cooperate", "defect"):
        _fail("first_move must be 'cooperate' or 'defect'.")

    default_action = _validate_action(definition.get("default_action", {"type": "cooperate"}), "default action")

    rules = definition.get("rules", [])
    if not isinstance(rules, list):
        _fail("rules must be a list.")
    if len(rules) > MAX_RULES:
        _fail(f"At most {MAX_RULES} rules are allowed.")

    normalized_rules = []
    for index, rule in enumerate(rules):
        label = f"rule {index + 1}"
        if not isinstance(rule, dict):
            _fail(f"{label} must be an object.")
        conditions = rule.get("conditions", [])
        if not isinstance(conditions, list) or not conditions:
            _fail(f"{label} needs at least one condition.")
        if len(conditions) > MAX_CONDITIONS:
            _fail(f"{label}: at most {MAX_CONDITIONS} conditions per rule.")
        normalized_conditions = [
            _validate_condition(condition, f"{label}, condition {c + 1}")
            for c, condition in enumerate(conditions)
        ]
        action = _validate_action(rule.get("action"), label)
        normalized_rules.append({"conditions": normalized_conditions, "action": action})

    return {"first_move": first_move, "rules": normalized_rules, "default_action": default_action}


def _validate_condition(condition: dict, label: str) -> dict:
    if not isinstance(condition, dict):
        _fail(f"{label} must be an object.")
    fact = condition.get("fact")
    if fact not in ALL_FACTS:
        _fail(f"{label}: unknown fact '{fact}'. Allowed: {', '.join(sorted(ALL_FACTS))}.")

    if fact in MOVE_FACTS:
        value = condition.get("value")
        if value not in ("cooperate", "defect"):
            _fail(f"{label}: value for {fact} must be 'cooperate' or 'defect'.")
        normalized = {"fact": fact, "op": "is", "value": value}
        if fact.endswith("_n_back"):
            n = condition.get("n", 1)
            if not isinstance(n, int) or not 1 <= n <= 10:
                _fail(f"{label}: n must be an integer between 1 and 10.")
            normalized["n"] = n
        return normalized

    if fact == CHANCE_FACT:
        p = condition.get("value")
        if not isinstance(p, (int, float)) or not 0 <= p <= 1:
            _fail(f"{label}: chance value must be a number between 0 and 1.")
        return {"fact": fact, "op": "lt", "value": float(p)}

    op = condition.get("op")
    if op not in NUMERIC_OPS:
        _fail(f"{label}: op for {fact} must be one of {', '.join(sorted(NUMERIC_OPS))}.")
    value = condition.get("value")
    if not isinstance(value, (int, float)):
        _fail(f"{label}: value for {fact} must be a number.")
    return {"fact": fact, "op": op, "value": value}


def _validate_action(action, label: str) -> dict:
    if isinstance(action, str):
        action = {"type": action}
    if not isinstance(action, dict) or action.get("type") not in ACTIONS:
        _fail(f"{label}: action must be one of {', '.join(sorted(ACTIONS))}.")
    normalized = {"type": action["type"]}
    if action["type"] == "random":
        p = action.get("p", 0.5)
        if not isinstance(p, (int, float)) or not 0 <= p <= 1:
            _fail(f"{label}: random action probability must be between 0 and 1.")
        normalized["p"] = float(p)
    return normalized


# ---------------------------------------------------------------------------
# Fact evaluation
# ---------------------------------------------------------------------------

def _facts(history: list[tuple[bool, bool]]) -> dict:
    from core.match_history import payoff

    rounds = len(history)
    opp_moves = [m[1] for m in history]
    my_moves = [m[0] for m in history]
    opp_defections = sum(1 for m in opp_moves if not m)

    opp_coop_streak = 0
    for move in reversed(opp_moves):
        if move:
            opp_coop_streak += 1
        else:
            break
    opp_defect_streak = 0
    for move in reversed(opp_moves):
        if not move:
            opp_defect_streak += 1
        else:
            break
    mutual_coop_streak = 0
    for mine, theirs in reversed(history):
        if mine and theirs:
            mutual_coop_streak += 1
        else:
            break

    my_score = sum(payoff[m][0] for m in history)
    opp_score = sum(payoff[m][1] for m in history)

    return {
        "round_number": rounds + 1,
        "opp_defection_count": opp_defections,
        "opp_defection_rate": opp_defections / rounds if rounds else 0.0,
        "opp_cooperation_rate": (rounds - opp_defections) / rounds if rounds else 0.0,
        "opp_coop_streak": opp_coop_streak,
        "opp_defect_streak": opp_defect_streak,
        "mutual_coop_streak": mutual_coop_streak,
        "my_score": my_score,
        "opp_score": opp_score,
        "score_diff": my_score - opp_score,
        "my_moves": my_moves,
        "opp_moves": opp_moves,
    }


def _condition_holds(condition: dict, facts: dict) -> bool:
    fact = condition["fact"]

    if fact in MOVE_FACTS:
        moves = facts["opp_moves"] if fact.startswith("opp") else facts["my_moves"]
        n = condition.get("n", 1)
        if len(moves) < n:
            return False
        move = moves[-n]
        return move if condition["value"] == "cooperate" else not move

    if fact == CHANCE_FACT:
        return random.random() < condition["value"]

    actual = facts[fact]
    value = condition["value"]
    op = condition["op"]
    if op == "eq":
        return actual == value
    if op == "gt":
        return actual > value
    if op == "gte":
        return actual >= value
    if op == "lt":
        return actual < value
    return actual <= value  # lte


def _apply_action(action: dict, facts: dict) -> bool:
    kind = action["type"]
    if kind == "cooperate":
        return True
    if kind == "defect":
        return False
    if kind == "copy_opponent":
        return facts["opp_moves"][-1] if facts["opp_moves"] else True
    if kind == "opposite_of_opponent":
        return (not facts["opp_moves"][-1]) if facts["opp_moves"] else True
    return random.random() < action["p"]  # random


def compile_definition(definition: dict) -> StrategyFn:
    """Compiles a validated definition into a strategy function (safe closure)."""
    normalized = validate_definition(definition)
    first_move = normalized["first_move"] == "cooperate"
    rules = normalized["rules"]
    default_action = normalized["default_action"]

    def strategy(history: list[tuple[bool, bool]]) -> bool:
        if not history:
            return first_move
        facts = _facts(history)
        for rule in rules:
            if all(_condition_holds(condition, facts) for condition in rule["conditions"]):
                return _apply_action(rule["action"], facts)
        return _apply_action(default_action, facts)

    return strategy


# ---------------------------------------------------------------------------
# Python source rendering (display/export only — never executed)
# ---------------------------------------------------------------------------

_FACT_EXPR = {
    "round_number": "len(history) + 1",
    "opp_defection_count": "sum(1 for _, opp in history if not opp)",
    "opp_defection_rate": "sum(1 for _, opp in history if not opp) / len(history)",
    "opp_cooperation_rate": "sum(1 for _, opp in history if opp) / len(history)",
    "opp_coop_streak": "streak(history, lambda mine, opp: opp)",
    "opp_defect_streak": "streak(history, lambda mine, opp: not opp)",
    "mutual_coop_streak": "streak(history, lambda mine, opp: mine and opp)",
    "my_score": "score(history)[0]",
    "opp_score": "score(history)[1]",
    "score_diff": "score(history)[0] - score(history)[1]",
}

_OP_SYMBOL = {"eq": "==", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}


def _condition_source(condition: dict) -> str:
    fact = condition["fact"]
    if fact in MOVE_FACTS:
        n = condition.get("n", 1)
        side = 1 if fact.startswith("opp") else 0
        expr = f"history[-{n}][{side}]" if n > 1 or fact.endswith("_n_back") else f"history[-1][{side}]"
        guard = f"len(history) >= {n} and " if n > 1 else ""
        return f"{guard}{expr}" if condition["value"] == "cooperate" else f"{guard}not {expr}"
    if fact == CHANCE_FACT:
        return f"random.random() < {condition['value']}"
    return f"{_FACT_EXPR[fact]} {_OP_SYMBOL[condition['op']]} {condition['value']}"


def _action_source(action: dict) -> str:
    kind = action["type"]
    if kind == "cooperate":
        return "return True  # cooperate"
    if kind == "defect":
        return "return False  # defect"
    if kind == "copy_opponent":
        return "return history[-1][1]  # copy opponent"
    if kind == "opposite_of_opponent":
        return "return not history[-1][1]  # opposite of opponent"
    return f"return random.random() < {action['p']}  # cooperate with probability {action['p']}"


def render_python_source(definition: dict, function_name: str = "custom_strategy") -> str:
    normalized = validate_definition(definition)
    lines = [
        "import random",
        "",
        "from core.match_history import score",
        "",
        "",
        "def streak(history, predicate):",
        "    count = 0",
        "    for mine, opp in reversed(history):",
        "        if predicate(mine, opp):",
        "            count += 1",
        "        else:",
        "            break",
        "    return count",
        "",
        "",
        f"def {function_name}(history):",
        '    """Built with the no-code strategy builder. Rules run top-down; first match wins."""',
        "    if not history:",
        f"        return {normalized['first_move'] == 'cooperate'}  # first move",
    ]
    for rule in normalized["rules"]:
        joined = " and ".join(f"({_condition_source(c)})" for c in rule["conditions"])
        lines.append(f"    if {joined}:")
        lines.append(f"        {_action_source(rule['action'])}")
    lines.append(f"    {_action_source(normalized['default_action'])}")
    return "\n".join(lines) + "\n"


def describe_definition(definition: dict) -> list[str]:
    """Plain-language, line-per-rule description for marketplace cards."""
    normalized = validate_definition(definition)
    lines = [f"First move: {normalized['first_move']}"]
    for index, rule in enumerate(normalized["rules"]):
        conditions = " AND ".join(_describe_condition(c) for c in rule["conditions"])
        lines.append(f"{index + 1}. IF {conditions} THEN {_describe_action(rule['action'])}")
    lines.append(f"Otherwise: {_describe_action(normalized['default_action'])}")
    return lines


def _describe_condition(condition: dict) -> str:
    fact = condition["fact"]
    label = FACT_LABELS[fact]
    if fact in MOVE_FACTS:
        n = condition.get("n", 1)
        if fact.endswith("_n_back"):
            label = label.replace("N rounds back", f"{n} round{'s' if n > 1 else ''} back")
        return f"{label} was {condition['value']}"
    if fact == CHANCE_FACT:
        return f"with {condition['value'] * 100:.0f}% chance"
    return f"{label} {_OP_SYMBOL[condition['op']]} {condition['value']}"


def _describe_action(action: dict) -> str:
    kind = action["type"]
    if kind == "random":
        return f"cooperate with {action['p'] * 100:.0f}% probability"
    return kind.replace("_", " ")
