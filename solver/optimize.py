"""Local search: turn a *valid* budget into a *better* one.

The CSP solver (solver/csp.py) answers "is there a budget that obeys every
rule?" and returns the first one it finds. This module answers "which valid
budget is best for this user?" using hill climbing with random restarts.

Score of a budget (higher is better):

    score = sum over flexible categories of  weight * sqrt(amount / max_amount)

* weight comes from the user's priorities (first priority = biggest weight).
* the square root models diminishing returns: the first rupees spent on a
  category are worth more than the last ones, so money is spread sensibly
  instead of piling everything into one category.

A move shifts one step (Rs 500) of money: either from unallocated income into a
category, or from one category to another. A move is only accepted if every
constraint still holds and the score goes up. When no single move helps, pairs
of moves are tried, so categories tied together by a rule can move together.
"""
import math
import random
import time

from .api import solve
from .csp import OPS
from .problem import STEP, active_rules, flex_capacity, ordered_variables


def default_weights(problem):
    """Highest weight for the first priority: n, n-1, ..., 1."""
    order = ordered_variables(problem)
    n = len(order)
    return {cat: float(n - i) for i, cat in enumerate(order)}


def score(problem, values, weights=None):
    """Score of {flexible category: amount}. Higher is better."""
    w = default_weights(problem)
    if weights:
        w.update(weights)
    total = 0.0
    for cat, amount in values.items():
        hi = problem["bounds"][cat][1]
        if hi > 0:
            total += w.get(cat, 1.0) * math.sqrt(amount / hi)
    return total


def _valid(problem, values, capacity, rules):
    """Do these amounts obey the bounds, the money limit and every rule?"""
    if sum(values.values()) > capacity:
        return False
    for cat, amount in values.items():
        lo, hi = problem["bounds"][cat]
        if amount < lo or amount > hi:
            return False
    return all(OPS[op](values[a], values[b]) for a, op, b in rules)


def _neighbours(problem, values, capacity, include_remove=False):
    """Every one-step change: add from unallocated, shift between categories."""
    bounds = problem["bounds"]
    unallocated = capacity - sum(values.values())
    cats = list(values)
    for b in cats:
        amount = min(STEP, bounds[b][1] - values[b], unallocated)
        if amount > 0:
            new = dict(values)
            new[b] += amount
            yield new
    for a in cats:
        for b in cats:
            if a == b:
                continue
            amount = min(STEP, values[a] - bounds[a][0], bounds[b][1] - values[b])
            if amount > 0:
                new = dict(values)
                new[a] -= amount
                new[b] += amount
                yield new
    if include_remove:
        for a in cats:
            amount = min(STEP, values[a] - bounds[a][0])
            if amount > 0:
                new = dict(values)
                new[a] -= amount
                yield new


def _best_single(problem, current, current_score, capacity, rules, weights):
    """Best improving one-step move, or (None, current_score)."""
    best, best_score = None, current_score
    for cand in _neighbours(problem, current, capacity):
        if not _valid(problem, cand, capacity, rules):
            continue
        s = score(problem, cand, weights)
        if s > best_score + 1e-12:
            best, best_score = cand, s
    return best, best_score


def _best_pair(problem, current, current_score, capacity, rules, weights):
    """Best improving TWO-step move, or (None, current_score).

    Needed when rules tie categories together (e.g. food >= transport): neither
    can move alone without breaking the rule, but both moving together is fine.
    The first step may break a rule; only the final budget must be valid.
    """
    best, best_score = None, current_score
    for first in _neighbours(problem, current, capacity):
        for cand in _neighbours(problem, first, capacity):
            if not _valid(problem, cand, capacity, rules):
                continue
            s = score(problem, cand, weights)
            if s > best_score + 1e-12:
                best, best_score = cand, s
    return best, best_score


def _climb(problem, values, capacity, rules, weights):
    """Hill climbing: take improving moves until none is left.

    One-step moves are tried first. Only when none improves do we pay for the
    slower two-step search, so ordinary problems stay fast.
    """
    current = dict(values)
    current_score = score(problem, current, weights)
    moves = 0
    while True:
        best, best_score = _best_single(problem, current, current_score, capacity, rules, weights)
        if best is None:
            best, best_score = _best_pair(problem, current, current_score, capacity, rules, weights)
        if best is None:
            return current, current_score, moves
        current, current_score, moves = best, best_score, moves + 1


def _perturb(problem, values, capacity, rules, rng, steps=6):
    """Random walk of valid moves, used to restart the climb from elsewhere."""
    current = dict(values)
    for _ in range(steps):
        options = [c for c in _neighbours(problem, current, capacity, include_remove=True)
                   if _valid(problem, c, capacity, rules)]
        if not options:
            break
        current = rng.choice(options)
    return current


def optimise(problem, method="forward", weights=None, restarts=5, seed=0):
    """Solve the problem, then improve the budget with local search.

    Returns the same format as solver.solve(), plus
        "score", "start_score", "improved"
    and stats["moves"] (number of improving moves taken).
    If the problem is impossible the solver's result is returned unchanged
    with score None (look at result["unmet"]).
    """
    t0 = time.perf_counter()
    base = solve(problem, method)
    if base["status"] != "ok":
        return {**base, "score": None, "start_score": None, "improved": False}

    rules = active_rules(problem)
    capacity = flex_capacity(problem)
    order = ordered_variables(problem)
    start = {cat: base["allocation"][cat] for cat in order}
    start_score = score(problem, start, weights)

    rng = random.Random(seed)
    best, best_score, total_moves = _climb(problem, start, capacity, rules, weights)
    for _ in range(restarts):
        begin = _perturb(problem, start, capacity, rules, rng)
        cand, cand_score, moves = _climb(problem, begin, capacity, rules, weights)
        total_moves += moves
        if cand_score > best_score + 1e-12:
            best, best_score = cand, cand_score

    allocation = dict(problem["fixed_costs"])
    allocation.update(best)
    allocation["savings"] = problem["savings_goal"]
    stats = {
        "nodes": base["stats"]["nodes"],
        "time_ms": round((time.perf_counter() - t0) * 1000, 3),
        "moves": total_moves,
    }
    return {
        "status": "ok",
        "method": method,
        "allocation": allocation,
        "unallocated": problem["income"] - sum(allocation.values()),
        "unmet": [],
        "score": round(best_score, 6),
        "start_score": round(start_score, 6),
        "improved": best_score > start_score + 1e-9,
        "stats": stats,
    }
