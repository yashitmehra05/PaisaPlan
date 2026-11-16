"""What-if questions with the convention the language model was trained on.

For a flexible category (food, transport, entertainment, other):
    spend MORE  -> the extra comes out of savings
    spend LESS  -> the freed money goes into savings
Every other category stays where it was. If the change breaks a rule, or needs more
money than is being saved, the result is "infeasible" with an exact reason.

Fixed costs, income and savings changes use solver.resolve() (the general solver logic).
"""
import copy

from solver import resolve, solve


def _infeasible(method, unmet):
    return {"status": "infeasible", "method": method, "allocation": {}, "unallocated": None,
            "unmet": unmet, "stats": {"nodes": 0, "time_ms": 0}}


def apply_what_if(problem, change, method="forward"):
    """Return {"mode", "old", "new"} (both are solver-style results).

    mode: "savings_absorbs" | "generic" | "base_infeasible".
    Raises ValueError for an unknown category or a bad change.
    """
    cat = str(change.get("category", "")).strip().lower()
    action, amount = change.get("action"), change.get("amount")
    if action not in ("increase", "decrease") or not isinstance(amount, (int, float)) or amount <= 0:
        raise ValueError("the change needs an action (increase or decrease) and a positive amount")

    if cat not in problem["bounds"]:
        out = resolve(problem, {"category": cat, "action": action, "amount": amount}, method)
        return {"mode": "generic", "old": out["old"], "new": out["new"]}

    old = solve(problem, method)
    if old["status"] != "ok":
        return {"mode": "base_infeasible", "old": old, "new": old}

    current = old["allocation"][cat]
    target = max(0, current + (amount if action == "increase" else -amount))
    delta = target - current                       # what the category really changes by
    new_savings = problem["savings_goal"] - delta  # savings pay for it (or receive it)

    if new_savings < 0:
        saved = problem["savings_goal"]
        unmet = [{
            "constraint": "savings_goal",
            "short_by": int(-new_savings),
            "suggestion": f"Raising {cat} by ₹{int(delta)} needs that money from savings, but only "
                          f"₹{int(saved)} is being saved. Raise {cat} by at most ₹{int(saved)}.",
        }]
        return {"mode": "savings_absorbs", "old": old, "new": _infeasible(method, unmet)}

    new_problem = copy.deepcopy(problem)
    for name in new_problem["bounds"]:
        value = target if name == cat else old["allocation"][name]
        new_problem["bounds"][name] = (value, value)
    new_problem["savings_goal"] = new_savings
    return {"mode": "savings_absorbs", "old": old, "new": solve(new_problem, method)}
