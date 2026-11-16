"""How close does local search get to the TRUE best budget?

For small problems (4 categories) we can try every combination (brute force)
and find the real optimum of the score, then compare with local search.

Run from the repo root:   python -m benchmarks.optimality_check
"""
import csv
import itertools
import os
import statistics

from solver import solve
from solver.csp import OPS, _build_domains
from solver.optimize import optimise, score
from solver.problem import active_rules, flex_capacity, money_left, ordered_variables

from .generate import problem_set


def best_possible(problem):
    """Highest score over every valid combination (brute force)."""
    order = ordered_variables(problem)
    domains = _build_domains(problem, order)
    rules = active_rules(problem)
    capacity = flex_capacity(problem)
    best = None
    for combo in itertools.product(*[domains[v] for v in order]):
        if sum(combo) > capacity:
            continue
        values = dict(zip(order, combo))
        if all(OPS[op](values[a], values[b]) for a, op, b in rules):
            s = score(problem, values)
            if best is None or s > best:
                best = s
    return best


def main(count=200, out_dir="benchmarks", restarts=5):
    rows = []
    for i, problem in enumerate(problem_set(4, count)):
        if money_left(problem) < 0 or solve(problem)["status"] != "ok":
            continue
        optimum = best_possible(problem)
        found = optimise(problem, restarts=restarts, seed=i)["score"]
        gap = 100 * (optimum - found) / optimum if optimum else 0.0
        rows.append({"problem": i, "optimum": round(optimum, 6), "local_search": found,
                     "gap_pct": round(gap, 3), "is_optimal": int(gap < 1e-4)})

    with open(os.path.join(out_dir, "optimality.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print("problems checked          :", len(rows))
    print("local search found optimum:", f"{100 * sum(r['is_optimal'] for r in rows) / len(rows):.1f}%")
    print("mean gap to optimum       :", f"{statistics.mean(r['gap_pct'] for r in rows):.3f}%")
    print("worst gap to optimum      :", f"{max(r['gap_pct'] for r in rows):.3f}%")
    return rows


if __name__ == "__main__":
    main()
