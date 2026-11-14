"""The search algorithms: plain backtracking, forward checking, forward checking + MRV.

The budget CSP:
  * variables  = flexible categories (food, transport, ...)
  * domains    = amounts from min to max in steps of Rs 500 (tried biggest first)
  * constraints:
        - all flexible categories together use at most `flex_capacity` rupees
        - every pairwise rule holds, e.g. entertainment <= food

All three methods try values in the same order, so "backtracking" and "forward"
return exactly the same budget - forward checking only gets there with fewer
steps. "mrv" may pick a different (but equally valid) budget because it chooses
variables in a different order.

A "node" is counted every time the search tries one value for one category.
"""
import operator
import time

from .problem import (
    STEP,
    active_rules,
    flex_capacity,
    money_left,
    ordered_variables,
)

OPS = {
    "<=": operator.le,
    ">=": operator.ge,
    "<": operator.lt,
    ">": operator.gt,
    "==": operator.eq,
}

METHODS = ("backtracking", "forward", "mrv")


class SearchLimit(Exception):
    """Raised when a search uses more nodes than allowed (used by benchmarks)."""


class _Counter:
    def __init__(self, max_nodes=None):
        self.nodes = 0
        self.max_nodes = max_nodes

    def tick(self):
        self.nodes += 1
        if self.max_nodes is not None and self.nodes > self.max_nodes:
            raise SearchLimit()


# ------------------------------------------------------------ shared pieces

def _build_domains(problem, order):
    """Possible amounts per category, biggest first (so priorities get more)."""
    domains = {}
    for cat in order:
        lo, hi = problem["bounds"][cat]
        lo, hi = int(round(lo)), int(round(hi))
        values = set(range(lo, hi + 1, STEP))
        values.add(hi)  # make sure the exact maximum is always allowed
        domains[cat] = sorted(values, reverse=True)
    return domains


def _consistent(var, val, assigned, rules):
    """Does giving `var` the value `val` respect every rule with assigned categories?"""
    for a, op, b in rules:
        if a == var and b in assigned and not OPS[op](val, assigned[b]):
            return False
        if b == var and a in assigned and not OPS[op](assigned[a], val):
            return False
    return True


# ------------------------------------------------------- 1. plain backtracking

def _plain(order, domains, rules, capacity, counter):
    """Try values in a fixed order; only notice a problem once it happens."""
    assigned = {}

    def rec(i, left):
        if i == len(order):
            return True
        var = order[i]
        for val in domains[var]:
            counter.tick()
            if val > left:
                continue
            if not _consistent(var, val, assigned, rules):
                continue
            assigned[var] = val
            if rec(i + 1, left - val):
                return True
            del assigned[var]
        return False

    return assigned if rec(0, capacity) else None


# -------------------------------------------- 2/3. forward checking (+ MRV)

def _prune(doms, unassigned, assigned, left, rules):
    """Forward checking: drop values of unassigned categories that can no longer work.

    A value v for category u is impossible if
      * v plus the cheapest possible choice for every OTHER unassigned
        category already exceeds the money still left, or
      * v breaks a rule with an already assigned category.
    Returns the pruned domains, or None if some category has no value left
    (a dead end - the caller backtracks immediately).
    """
    pruned = {}
    for u in unassigned:
        others_min = sum(min(doms[w]) for w in unassigned if w != u)
        keep = [v for v in doms[u]
                if v + others_min <= left and _consistent(u, v, assigned, rules)]
        if not keep:
            return None
        pruned[u] = keep
    return pruned


def _forward(order, doms0, rules, capacity, counter, use_mrv):
    pos = {v: i for i, v in enumerate(order)}
    assigned = {}

    def rec(doms, left):
        unassigned = [v for v in order if v not in assigned]
        if not unassigned:
            return dict(assigned)
        if use_mrv:
            # Minimum Remaining Values: most constrained category first.
            var = min(unassigned, key=lambda v: (len(doms[v]), pos[v]))
        else:
            var = unassigned[0]
        rest = [v for v in unassigned if v != var]
        for val in doms[var]:
            counter.tick()
            assigned[var] = val
            new = _prune({v: doms[v] for v in rest}, rest, assigned, left - val, rules)
            if new is not None:
                found = rec(new, left - val)
                if found is not None:
                    return found
            del assigned[var]
        return None

    return rec(doms0, capacity)


# ------------------------------------------------------------------ entry

def search(problem, method="forward", max_nodes=None):
    """Run one search. Returns (assignment_or_None, status, nodes, time_ms).

    status is "ok", "infeasible" or "limit" (stopped after max_nodes).
    """
    if method not in METHODS:
        raise ValueError(f"unknown method '{method}', choose from {METHODS}")

    order = ordered_variables(problem)
    domains = _build_domains(problem, order)
    rules = active_rules(problem)
    capacity = flex_capacity(problem)
    counter = _Counter(max_nodes)

    start = time.perf_counter()
    assignment, status = None, "infeasible"
    if money_left(problem) >= 0:
        try:
            if method == "backtracking":
                assignment = _plain(order, domains, rules, capacity, counter)
            else:
                doms0 = _prune(domains, order, {}, capacity, rules)
                if doms0 is not None:
                    assignment = _forward(order, doms0, rules, capacity, counter,
                                          use_mrv=(method == "mrv"))
        except SearchLimit:
            status = "limit"
    elapsed_ms = (time.perf_counter() - start) * 1000

    if assignment is not None:
        status = "ok"
    return assignment, status, counter.nodes, elapsed_ms
