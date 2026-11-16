"""Three alternative budgets for the same user, shown side by side in the app.

    aggressive  - save more (up to the most the user can afford), spend less on
                  entertainment and "other".
    balanced    - the user's own savings goal and priorities.
    comfortable - save half as much, spend more on food and fun.

Each scenario changes the savings goal and the category weights, then runs the
CSP solver and the local search. A scenario that is impossible comes back with
the solver's exact explanation (result["unmet"]), so the app can show why.
"""
import copy

from .optimize import default_weights, optimise
from .problem import STEP

SCENARIOS = {
    "aggressive": {
        "label": "Aggressive savings",
        "description": "Saves as much as you can afford; trims entertainment and other.",
        "weight_scale": {"entertainment": 0.5, "other": 0.5},
    },
    "balanced": {
        "label": "Balanced",
        "description": "Your own savings goal and priorities.",
        "weight_scale": {},
    },
    "comfortable": {
        "label": "Comfortable",
        "description": "Saves half as much and leaves more for food and fun.",
        "weight_scale": {"food": 1.2, "entertainment": 1.5, "other": 1.25},
    },
}


def scenario_savings(problem, name):
    """Monthly savings goal used by a scenario (a multiple of Rs 500)."""
    current = problem["savings_goal"]
    if name == "balanced":
        return current
    if name == "comfortable":
        return (int(0.5 * current) // STEP) * STEP
    # aggressive: 1.5x the goal or 20% of income, but never more than affordable
    fixed = sum(problem["fixed_costs"].values())
    minimums = sum(lo for lo, _ in problem["bounds"].values())
    affordable = problem["income"] - fixed - minimums
    wanted = min(affordable, max(1.5 * current, 0.2 * problem["income"]))
    return max(current, (int(wanted) // STEP) * STEP)


def build_scenarios(problem, method="forward", restarts=5, seed=0):
    """Return {"aggressive": {...}, "balanced": {...}, "comfortable": {...}}.

    Each value: {"label", "description", "savings_goal", "result"} where
    result is the output of solver.optimise().
    """
    out = {}
    for name, spec in SCENARIOS.items():
        scenario_problem = copy.deepcopy(problem)
        scenario_problem["savings_goal"] = scenario_savings(problem, name)
        weights = default_weights(scenario_problem)
        for cat, factor in spec["weight_scale"].items():
            if cat in weights:
                weights[cat] *= factor
        out[name] = {
            "label": spec["label"],
            "description": spec["description"],
            "savings_goal": scenario_problem["savings_goal"],
            "result": optimise(scenario_problem, method=method, weights=weights,
                               restarts=restarts, seed=seed),
        }
    return out
