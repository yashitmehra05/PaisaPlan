"""Plain-Python explanations (no language model). Used when the model is unavailable, when
its answer fails the safety checks, and for cases it was not trained on. Every number comes
straight from solver data, and the text uses the same [CERTAIN]/[ESTIMATE: ...] tags."""
from .payloads import months

FLEX = ("food", "transport", "entertainment", "other")


def rs(n):
    return f"₹{int(round(n)):,}"


def join_and(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1] if items else ""


def _items(d):
    return [f"{k} {rs(v)}" for k, v in d.items()]


def budget_text(problem, result, payload):
    alloc = result["allocation"]
    fixed = {k: alloc[k] for k in problem["fixed_costs"] if k in alloc}
    flex = {k: v for k, v in alloc.items() if k not in fixed and k != "savings"}
    parts = [f"Here is your monthly plan for an income of {rs(problem['income'])}."]
    if fixed:
        parts.append(f"Fixed costs are {join_and(_items(fixed))} [CERTAIN].")
    if flex:
        parts.append(f"The solver gave you {join_and(_items(flex))} for flexible categories [CERTAIN].")
    parts.append(f"You save {rs(alloc['savings'])} per month [CERTAIN].")
    if payload.get("months_to_goal"):
        parts.append(f"That reaches your {rs(payload['savings_goal_total'])} goal in "
                     f"{payload['months_to_goal']} months [ESTIMATE: assumes your income and spending stay the same].")
    else:
        parts.append("This assumes your income and spending stay about the same [ESTIMATE: no income change].")
    if result["unallocated"]:
        parts.append(f"{rs(result['unallocated'])} is left unallocated.")
    return " ".join(parts)


def _intro(change):
    cat, amt = change["category"], rs(change["amount"])
    down = change["action"] == "decrease"
    if cat in FLEX:
        return f"If you {'cut' if down else 'raise'} {cat} by {amt}"
    if cat == "savings":
        return f"If you {'lower' if down else 'raise'} your savings by {amt}"
    if cat == "income":
        return f"If your income {'drops' if down else 'goes up'} by {amt}"
    return f"If {cat} {'drops' if down else 'goes up'} by {amt}"


def infeasible_text(unmet, intro="I couldn't build a valid budget."):
    parts = [intro] + [u["suggestion"] for u in unmet[:2]]
    return " ".join(parts) + " [CERTAIN]"


def what_if_text(problem, change, old, new):
    intro = _intro(change)
    if new["status"] != "ok":
        return infeasible_text(new["unmet"], intro + ", the budget stops working.")
    lines = []
    for key, value in new["allocation"].items():
        before = old["allocation"].get(key, 0)
        if before != value:
            name = "savings go" if key == "savings" else f"{key} goes"
            lines.append(f"{name} from {rs(before)} to {rs(value)}")
    if old["unallocated"] != new["unallocated"]:
        lines.append(f"unallocated money goes from {rs(old['unallocated'])} to {rs(new['unallocated'])}")
    text = intro + (f", {join_and(lines)} [CERTAIN]." if lines else ", nothing else in your budget changes [CERTAIN].")
    total = problem.get("savings_total")
    m_old = months(total, old["allocation"]["savings"])
    m_new = months(total, new["allocation"]["savings"])
    if m_old and m_new and m_old != m_new:
        text += (f" Your {rs(total)} goal would take {m_new} months instead of {m_old} "
                 f"[ESTIMATE: assumes your spending stays the same].")
    else:
        text += " Everything else is assumed to stay the same [ESTIMATE: other costs may change]."
    return text
