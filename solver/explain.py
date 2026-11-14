"""Explain WHY a budget is impossible, with exact numbers.

The LLM layer must never invent figures, so every number it says about a
failed budget comes from here. Each entry in the returned list looks like:

    {"constraint": "savings_goal",
     "short_by": 500,
     "suggestion": "Lower the monthly savings goal by Rs 500 (to Rs 5500 or less)."}
"""
from .problem import flex_cap_from_share


def _inr(x):
    return f"₹{int(round(x))}"


def _rule_gap(a_rng, op, b_rng):
    """How far apart the ranges are for rule 'a <op> b' (0 means it can be met)."""
    (alo, ahi), (blo, bhi) = a_rng, b_rng
    if op == "<=":
        gap = alo - bhi
    elif op == "<":
        gap = alo - bhi + 1
    elif op == ">=":
        gap = blo - ahi
    elif op == ">":
        gap = blo - ahi + 1
    else:  # "=="
        gap = max(blo - ahi, alo - bhi)
    return max(0, gap)


def explain_infeasible(problem):
    """List every reason the problem has no solution (never empty)."""
    income = problem["income"]
    fixed_total = sum(problem["fixed_costs"].values())
    savings = problem["savings_goal"]
    bounds = problem["bounds"]
    mins_total = sum(lo for lo, _ in bounds.values())
    need = fixed_total + mins_total  # cost of living before any savings
    unmet = []

    # 1-3: a chain - report the first one that fails.
    if income < fixed_total:
        short = fixed_total - income
        unmet.append({
            "constraint": "fixed_costs",
            "short_by": short,
            "suggestion": f"Fixed costs are {_inr(short)} more than income. "
                          f"Reduce fixed costs by {_inr(short)} or raise income.",
        })
    elif income < need:
        short = need - income
        unmet.append({
            "constraint": "essential_minimums",
            "short_by": short,
            "suggestion": f"Fixed costs plus minimum spending ({_inr(need)}) are "
                          f"{_inr(short)} more than income, even with no savings. "
                          f"Lower the minimums or raise income by {_inr(short)}.",
        })
    elif income < need + savings:
        short = need + savings - income
        max_save = income - need
        unmet.append({
            "constraint": "savings_goal",
            "short_by": short,
            "suggestion": f"Lower the monthly savings goal by {_inr(short)} "
                          f"(to {_inr(max_save)} or less).",
        })

    # 4: the 'flexible spending share of income' cap.
    share_cap = flex_cap_from_share(problem)
    if share_cap is not None and mins_total > share_cap:
        short = mins_total - share_cap
        unmet.append({
            "constraint": "flex_share_cap",
            "short_by": short,
            "suggestion": f"Flexible spending is capped at {_inr(share_cap)} "
                          f"({int(problem['max_flex_share'] * 100)}% of income) but the "
                          f"minimums need {_inr(mins_total)}. Lower minimums by "
                          f"{_inr(short)} or raise income.",
        })

    # 5: rules that cannot be met even on their own.
    for a, op, b in problem.get("rules", []):
        if a in bounds and b in bounds:
            gap = _rule_gap(bounds[a], op, bounds[b])
            if gap > 0:
                unmet.append({
                    "constraint": f"rule: {a} {op} {b}",
                    "short_by": gap,
                    "suggestion": f"The rule '{a} {op} {b}' cannot hold with the current "
                                  f"limits; they are {_inr(gap)} apart. Relax the rule or "
                                  f"change the limits of {a} or {b}.",
                })

    # Fallback: every check passes alone but they conflict together.
    if not unmet:
        unmet.append({
            "constraint": "combined_constraints",
            "short_by": None,
            "suggestion": "No spending plan satisfies all limits and rules at the same "
                          "time. Lower the savings goal or relax one of the rules.",
        })
    return unmet
