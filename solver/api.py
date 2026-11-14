"""The two functions the rest of the team calls: solve() and resolve()."""
import copy

from .csp import search
from .explain import explain_infeasible
from .problem import validate


def solve(problem, method="forward", max_nodes=None):
    """Solve one budget problem.

    method: "backtracking" | "forward" | "mrv"   (default "forward")

    Returns
        {"status": "ok" | "infeasible" | "limit",
         "method": method,
         "allocation": {"rent": 9000, "food": 8000, ..., "savings": 5000},
         "unallocated": 0,           # income not assigned to anything
         "unmet": [],                # reasons, filled only when infeasible
         "stats": {"nodes": 12, "time_ms": 0.4}}
    """
    validate(problem)
    assignment, status, nodes, ms = search(problem, method, max_nodes)
    stats = {"nodes": nodes, "time_ms": round(ms, 3)}

    if status == "limit":
        return {"status": "limit", "method": method, "allocation": {},
                "unallocated": None, "unmet": [], "stats": stats}

    if assignment is None:
        return {"status": "infeasible", "method": method, "allocation": {},
                "unallocated": None, "unmet": explain_infeasible(problem), "stats": stats}

    allocation = dict(problem["fixed_costs"])
    allocation.update(assignment)
    allocation["savings"] = problem["savings_goal"]
    return {
        "status": "ok",
        "method": method,
        "allocation": allocation,
        "unallocated": problem["income"] - sum(allocation.values()),
        "unmet": [],
        "stats": stats,
    }


def resolve(problem, change, method="forward"):
    """Answer a what-if question: solve before and after one change.

    change = {"category": "food", "action": "decrease" | "increase", "amount": 1000}
    category can be a flexible category, a fixed cost, "income" or "savings".

    How a change is applied:
      * decrease a flexible category or a fixed cost: that amount drops, every
        other category stays as it was, and the freed money goes to savings.
      * any other change (increase, income, savings): the change is applied and
        the solver is free to re-balance the other flexible categories.

    Returns {"change", "old", "new", "diff", "freed_to_savings", "savings_effect"}.
    diff and savings_effect are None when either budget is impossible
    (look at new["unmet"] for the reason).
    """
    validate(problem)
    category = str(change.get("category", "")).strip().lower()
    action = change.get("action")
    amount = change.get("amount")
    if action not in ("increase", "decrease"):
        raise ValueError("change action must be 'increase' or 'decrease'")
    if not isinstance(amount, (int, float)) or isinstance(amount, bool) or amount <= 0:
        raise ValueError("change amount must be a number greater than 0")
    sign = 1 if action == "increase" else -1

    old = solve(problem, method)
    old_ok = old["status"] == "ok"
    old_alloc = old["allocation"]

    new_problem = copy.deepcopy(problem)
    freed = 0

    if category == "income":
        new_problem["income"] = max(0, problem["income"] + sign * amount)

    elif category == "savings":
        new_problem["savings_goal"] = max(0, problem["savings_goal"] + sign * amount)

    elif category in problem["fixed_costs"]:
        current = problem["fixed_costs"][category]
        target = max(0, current + sign * amount)
        new_problem["fixed_costs"][category] = target
        if sign < 0 and old_ok:
            freed = current - target
            _pin_others(new_problem, old_alloc, keep=None)
            new_problem["savings_goal"] += freed

    elif category in problem["bounds"]:
        lo, hi = problem["bounds"][category]
        current = old_alloc[category] if old_ok else hi
        target = max(0, current + sign * amount)
        if sign < 0:
            new_problem["bounds"][category] = (min(lo, target), target)
            if old_ok:
                freed = current - target
                _pin_others(new_problem, old_alloc, keep=category)
                new_problem["savings_goal"] += freed
        else:
            new_problem["bounds"][category] = (target, max(hi, target))

    else:
        raise ValueError(f"unknown category '{category}'")

    new = solve(new_problem, method)

    diff = savings_effect = None
    if old_ok and new["status"] == "ok":
        keys = list(old_alloc) + [k for k in new["allocation"] if k not in old_alloc]
        diff = {k: new["allocation"].get(k, 0) - old_alloc.get(k, 0) for k in keys}
        if freed > 0 and problem.get("savings_total") and problem["savings_goal"] > 0:
            monthly_old = problem["savings_goal"]
            savings_effect = {
                "extra_monthly": freed,
                "months_to_goal_old": round(problem["savings_total"] / monthly_old, 1),
                "months_to_goal_new": round(problem["savings_total"] / (monthly_old + freed), 1),
            }

    return {
        "change": {"category": category, "action": action, "amount": amount},
        "old": old,
        "new": new,
        "diff": diff,
        "freed_to_savings": freed if new["status"] == "ok" else 0,
        "savings_effect": savings_effect,
    }


def _pin_others(problem, old_alloc, keep):
    """Freeze every flexible category (except `keep`) at its old amount."""
    for name in problem["bounds"]:
        if name != keep:
            problem["bounds"][name] = (old_alloc[name], old_alloc[name])
