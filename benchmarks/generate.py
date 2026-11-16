"""Random budget problems of any size, for benchmarking the solvers.

Every problem is built from a fixed seed, so anyone can regenerate exactly the
same set. The money available is picked so that problems range from clearly
impossible to comfortably solvable, and random pairwise rules ("a <= b",
"a >= b") are added, which is what makes larger problems genuinely hard.
"""
import math
import random

from solver.problem import STEP, validate

RULE_OPS = ("<=", ">=")


def random_problem(n_categories, rng):
    """One random problem with `n_categories` flexible categories."""
    names = [f"cat{i + 1}" for i in range(n_categories)]
    bounds = {}
    for name in names:
        lo = rng.choice([0, 500, 1000, 1500])
        hi = lo + rng.choice([2000, 3000, 4000, 6000])
        bounds[name] = (lo, hi)

    minimums = sum(lo for lo, _ in bounds.values())
    maximums = sum(hi for _, hi in bounds.values())
    fixed = rng.choice([3000, 6000, 9000, 12000])
    savings = rng.choice([0, 2000, 4000, 6000])

    # How much money is left for flexible categories: from a bit below the
    # minimums (impossible) up to 70% of the way to the maximums.
    capacity = minimums + (maximums - minimums) * rng.uniform(-0.15, 0.7)
    income = math.ceil((fixed + savings + max(capacity, 0)) / STEP) * STEP

    rules = []
    for _ in range(rng.randint(0, max(1, n_categories // 2))):
        a, b = rng.sample(names, 2)
        rules.append((a, rng.choice(RULE_OPS), b))

    priorities = names[:]
    rng.shuffle(priorities)

    problem = {
        "income": income,
        "fixed_costs": {"rent": fixed},
        "savings_goal": savings,
        "savings_total": None,
        "savings_months": None,
        "priorities": priorities,
        "bounds": bounds,
        "rules": rules,
        "max_flex_share": None,
    }
    validate(problem)
    return problem


def problem_set(n_categories, count):
    """`count` reproducible problems of one size."""
    return [random_problem(n_categories, random.Random(1000 * n_categories + i))
            for i in range(count)]
