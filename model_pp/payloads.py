"""Turn solver results into the JSON the fine-tuned model was trained on (Person 3's formats).

Three payload types, with the key order and number formatting used in data/train.jsonl:

  budget      {"task","status":"ok","income","allocation","unallocated","savings_goal_total","months_to_goal"}
  what-if     {"task","status":"ok","change","category_old","category_new","savings_old","savings_new",
               "savings_goal_total","months_old","months_new"}
  infeasible  {"task","status":"infeasible","income","fixed_total","savings_goal_monthly",
               "min_flexible_total","total_needed","shortfall","suggested_savings_goal"}

What-if convention (same as the training data): money spent on a flexible category comes OUT
of savings, and money cut from it goes INTO savings. months = ceil(goal total / monthly savings).
"""
import math

FLEX_ORDER = ("food", "transport", "entertainment", "other")


def _int(x):
    """Whole numbers as int so the JSON reads 5000, not 5000.0."""
    if isinstance(x, float) and x.is_integer():
        return int(x)
    return x


def months(total, monthly):
    """Months to reach a savings goal, rounded up (None if there is no goal or no saving)."""
    if not total or not monthly or monthly <= 0:
        return None
    return math.ceil(total / monthly)


def canonical_allocation(problem, allocation):
    """Fixed costs first, then flexible categories in food/transport/... order, then savings."""
    out = {name: _int(allocation[name]) for name in problem["fixed_costs"] if name in allocation}
    flex = [c for c in FLEX_ORDER if c in problem["bounds"]]
    flex += [c for c in problem["bounds"] if c not in flex]
    for name in flex:
        if name in allocation:
            out[name] = _int(allocation[name])
    out["savings"] = _int(allocation.get("savings", 0))
    return out


def budget_payload(problem, result):
    total = _int(problem.get("savings_total"))
    savings = result["allocation"]["savings"]
    return {
        "task": "explain", "status": "ok", "income": _int(problem["income"]),
        "allocation": canonical_allocation(problem, result["allocation"]),
        "unallocated": _int(result["unallocated"]),
        "savings_goal_total": total, "months_to_goal": months(total, savings),
    }


def what_if_payload(problem, change, old, new):
    """Both results must be 'ok'. Only for flexible-category what-ifs."""
    cat = change["category"]
    total = _int(problem.get("savings_total"))
    s_old, s_new = old["allocation"]["savings"], new["allocation"]["savings"]
    return {
        "task": "explain", "status": "ok",
        "change": {"category": cat, "action": change["action"], "amount": _int(change["amount"])},
        "category_old": _int(old["allocation"][cat]), "category_new": _int(new["allocation"][cat]),
        "savings_old": _int(s_old), "savings_new": _int(s_new),
        "savings_goal_total": total,
        "months_old": months(total, s_old), "months_new": months(total, s_new),
    }


def infeasible_payload(problem, result):
    """Only the 'savings goal too high' case is in the training data; otherwise return None."""
    if not any(u["constraint"] == "savings_goal" for u in result["unmet"]):
        return None
    fixed = sum(problem["fixed_costs"].values())
    mins = sum(lo for lo, _ in problem["bounds"].values())
    savings = problem["savings_goal"]
    needed = fixed + savings + mins
    shortfall = needed - problem["income"]
    return {
        "task": "explain", "status": "infeasible", "income": _int(problem["income"]),
        "fixed_total": _int(fixed), "savings_goal_monthly": _int(savings),
        "min_flexible_total": _int(mins), "total_needed": _int(needed),
        "shortfall": _int(shortfall), "suggested_savings_goal": _int(savings - shortfall),
    }
