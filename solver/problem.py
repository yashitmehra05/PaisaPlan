"""Problem definition for the PaisaPlan budget CSP.

A *problem* is a plain Python dict so every teammate can build one easily:

    {
      "income": 30000,
      "fixed_costs": {"rent": 9000, "education": 3000},
      "savings_goal": 5000,                 # rupees per month
      "savings_total": 5000,                # optional: total the user wants to save
      "savings_months": 1,                  # optional: over how many months
      "priorities": ["food", "transport"],  # most important first
      "bounds": {"food": (2000, 8000)},     # (min, max) per flexible category
      "rules": [("entertainment", "<=", "food")],
      "max_flex_share": 0.6,                # flexible spending <= 60% of income (None = off)
    }

Terms used everywhere in the solver:
  * fixed costs      - money that must be paid (rent, fees). Not a variable.
  * flexible categories - the CSP variables (food, transport, entertainment, other).
  * savings goal     - treated as a hard requirement: it is set aside first.
  * money_left       - income - fixed costs - savings goal.
  * flex_capacity    - the most all flexible categories together may use.
"""
import math

STEP = 500  # amounts are chosen in steps of Rs 500

# Default (min, max) spending range per flexible category, in rupees per month.
DEFAULT_BOUNDS = {
    "food": (2000, 8000),
    "transport": (500, 3000),
    "entertainment": (0, 3000),
    "other": (0, 2000),
}

# Default pairwise rules: (category_a, operator, category_b) means a <op> b.
DEFAULT_RULES = [("entertainment", "<=", "food")]

# Flexible spending may not exceed this share of income (None switches it off).
DEFAULT_MAX_FLEX_SHARE = 0.6

VALID_OPS = ("<=", ">=", "<", ">", "==")


def _is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def normalise(schema):
    """Turn the LLM's JSON (see llm/schema.json) into a solver problem dict.

    Raises ValueError if the input is unusable (missing income, negative
    amounts, ...), so callers can ask the user to clarify.
    """
    income = schema.get("income")

    # fixed_costs may arrive as a list of {"name", "amount"} or as a dict.
    raw_fixed = schema.get("fixed_costs") or []
    if isinstance(raw_fixed, dict):
        fixed = {str(k).strip().lower(): v for k, v in raw_fixed.items()}
    else:
        fixed = {str(item["name"]).strip().lower(): item["amount"] for item in raw_fixed}

    # savings goal: {"amount": total, "months": n}  ->  rupees per month
    goal = schema.get("savings_goal")
    savings_total = savings_months = None
    savings = 0
    if goal:
        savings_total = goal.get("amount") or 0
        savings_months = max(1, int(goal.get("months") or 1))
        savings = math.ceil(savings_total / savings_months)

    bounds = {k: tuple(v) for k, v in DEFAULT_BOUNDS.items()}
    for name, rng in (schema.get("bounds") or {}).items():
        bounds[str(name).strip().lower()] = tuple(rng)
    # A category the user declared as fixed is no longer flexible.
    for name in fixed:
        bounds.pop(name, None)

    problem = {
        "income": income,
        "fixed_costs": fixed,
        "savings_goal": savings,
        "savings_total": savings_total,
        "savings_months": savings_months,
        "priorities": [str(p).strip().lower() for p in (schema.get("priorities") or [])],
        "bounds": bounds,
        "rules": [tuple(r) for r in schema.get("rules", DEFAULT_RULES)],
        "max_flex_share": schema.get("max_flex_share", DEFAULT_MAX_FLEX_SHARE),
    }
    validate(problem)
    return problem


def validate(problem):
    """Raise ValueError with a clear message if the problem is malformed."""
    income = problem.get("income")
    if not _is_number(income) or income < 0:
        raise ValueError("income must be a number that is 0 or more")

    for name, amount in problem.get("fixed_costs", {}).items():
        if not _is_number(amount) or amount < 0:
            raise ValueError(f"fixed cost '{name}' must be a number that is 0 or more")

    goal = problem.get("savings_goal", 0)
    if not _is_number(goal) or goal < 0:
        raise ValueError("savings goal must be a number that is 0 or more")

    for name, rng in problem.get("bounds", {}).items():
        if len(rng) != 2:
            raise ValueError(f"bounds for '{name}' must be (min, max)")
        lo, hi = rng
        if not (_is_number(lo) and _is_number(hi)) or lo < 0 or lo > hi:
            raise ValueError(f"bounds for '{name}' must satisfy 0 <= min <= max")

    for rule in problem.get("rules", []):
        if len(rule) != 3 or rule[1] not in VALID_OPS:
            raise ValueError(f"bad rule {rule}: use (a, op, b) with op in {VALID_OPS}")

    share = problem.get("max_flex_share")
    if share is not None and not (_is_number(share) and 0 <= share <= 1):
        raise ValueError("max_flex_share must be between 0 and 1 (or None)")


# ---------------------------------------------------------------- helpers

def money_left(problem):
    """Income minus fixed costs minus the savings goal."""
    return problem["income"] - sum(problem["fixed_costs"].values()) - problem["savings_goal"]


def flex_cap_from_share(problem):
    """Largest flexible spending allowed by the 'share of income' rule (or None)."""
    share = problem.get("max_flex_share")
    if share is None:
        return None
    return math.floor(round(share * problem["income"], 6))


def flex_capacity(problem):
    """Most that all flexible categories together may spend."""
    cap = money_left(problem)
    share_cap = flex_cap_from_share(problem)
    if share_cap is not None:
        cap = min(cap, share_cap)
    return cap


def ordered_variables(problem):
    """Flexible categories, user priorities first, then the rest in config order."""
    flex = list(problem["bounds"])
    order, seen = [], set()
    for name in [p for p in problem.get("priorities", []) if p in problem["bounds"]] + flex:
        if name not in seen:
            seen.add(name)
            order.append(name)
    return order


def active_rules(problem):
    """Rules whose two categories are both flexible variables."""
    bounds = problem["bounds"]
    return [tuple(r) for r in problem.get("rules", []) if r[0] in bounds and r[2] in bounds]
