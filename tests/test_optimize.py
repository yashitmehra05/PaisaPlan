"""Tests for local search, scenarios and the benchmark helpers. Run:  pytest -v"""
import csv

import pytest

from benchmarks import optimality_check, run_benchmarks
from benchmarks.generate import problem_set, random_problem
from solver import normalise, solve
from solver.optimize import default_weights, optimise, score
from solver.problem import validate
from solver.scenarios import build_scenarios, scenario_savings


def make(**overrides):
    schema = {
        "income": 30000,
        "fixed_costs": [{"name": "rent", "amount": 9000},
                        {"name": "education", "amount": 3000}],
        "priorities": ["food", "transport", "entertainment"],
        "savings_goal": {"amount": 5000, "months": 1},
    }
    schema.update(overrides)
    return normalise(schema)


def check_valid(problem, result):
    alloc = result["allocation"]
    assert sum(alloc.values()) + result["unallocated"] == problem["income"]
    assert result["unallocated"] >= 0
    for name, (lo, hi) in problem["bounds"].items():
        assert lo <= alloc[name] <= hi
    for a, op, b in problem["rules"]:
        if a in alloc and b in alloc:
            assert eval(f"{alloc[a]} {op} {alloc[b]}")
    assert alloc["savings"] == problem["savings_goal"]


# --------------------------------------------------------------- scoring

def test_default_weights_follow_priority_order():
    w = default_weights(make())
    assert w["food"] > w["transport"] > w["entertainment"] > w["other"]


def test_score_prefers_spreading_money():
    p = make()
    lopsided = {"food": 8000, "transport": 500, "entertainment": 0, "other": 0}
    spread = {"food": 4000, "transport": 2000, "entertainment": 1500, "other": 1000}
    assert score(p, spread) > score(p, lopsided)


# ---------------------------------------------------------- local search

def test_optimise_is_valid_and_never_worse_than_the_solver():
    p = make()
    r = optimise(p)
    assert r["status"] == "ok"
    check_valid(p, r)
    assert r["score"] >= r["start_score"]
    assert r["improved"] is True


def test_optimise_is_repeatable_with_the_same_seed():
    p = make()
    a, b = optimise(p, seed=3), optimise(p, seed=3)
    assert a["allocation"] == b["allocation"] and a["score"] == b["score"]


def test_optimise_passes_through_an_impossible_budget():
    r = optimise(make(income=14000, savings_goal=None))
    assert r["status"] == "infeasible"
    assert r["score"] is None and r["unmet"]


def test_optimise_handles_no_flexible_categories():
    p = make(fixed_costs=[{"name": n, "amount": 1000} for n in
                          ["rent", "education", "food", "transport", "entertainment", "other"]])
    r = optimise(p)
    assert r["status"] == "ok" and r["score"] == 0


def test_optimise_moves_rule_linked_categories_together():
    # food and transport are forced equal; they can only improve by moving as a pair.
    p = make(income=40000, rules=[("food", ">=", "transport"), ("food", "<=", "transport")],
             bounds={"food": (0, 4000), "transport": (0, 4000)})
    r = optimise(p)
    assert r["allocation"]["food"] == r["allocation"]["transport"]
    assert r["allocation"]["food"] > 0
    check_valid(p, r)


def test_custom_weights_change_the_budget():
    p = make()
    food_heavy = optimise(p, weights={"food": 10.0})
    fun_heavy = optimise(p, weights={"entertainment": 10.0, "food": 0.1})
    assert food_heavy["allocation"]["food"] > fun_heavy["allocation"]["food"]
    assert fun_heavy["allocation"]["entertainment"] >= food_heavy["allocation"]["entertainment"]


def test_local_search_matches_brute_force_on_small_problems():
    rows = optimality_check.main(count=40, out_dir=_tmp_dir())
    assert all(r["is_optimal"] for r in rows)


# ------------------------------------------------------------- scenarios

def test_three_scenarios_are_built_and_valid():
    p = make()
    scenarios = build_scenarios(p)
    assert list(scenarios) == ["aggressive", "balanced", "comfortable"]
    for name, sc in scenarios.items():
        assert sc["result"]["status"] == "ok"
        scenario_problem = {**p, "savings_goal": sc["savings_goal"]}
        check_valid(scenario_problem, sc["result"])


def test_scenarios_differ_in_savings_in_the_right_direction():
    p = make()
    s = build_scenarios(p)
    assert s["aggressive"]["savings_goal"] > s["balanced"]["savings_goal"] > s["comfortable"]["savings_goal"]
    assert s["balanced"]["savings_goal"] == p["savings_goal"]


def test_aggressive_never_asks_for_more_than_affordable():
    p = make(income=20000, savings_goal={"amount": 4000, "months": 1})
    s = build_scenarios(p)
    assert s["aggressive"]["result"]["status"] == "ok"


def test_scenario_savings_is_a_multiple_of_500():
    p = make(savings_goal={"amount": 3333, "months": 1})
    for name in ("aggressive", "balanced", "comfortable"):
        if name != "balanced":
            assert scenario_savings(p, name) % 500 == 0


def test_comfortable_can_rescue_a_budget_with_too_high_a_savings_goal():
    p = make(income=20000, savings_goal={"amount": 6000, "months": 1})  # impossible as asked
    s = build_scenarios(p)
    assert s["balanced"]["result"]["status"] == "infeasible"
    assert s["balanced"]["result"]["unmet"][0]["constraint"] == "savings_goal"
    assert s["comfortable"]["result"]["status"] == "ok"


# ------------------------------------------------------------ benchmarks

def test_random_problems_are_valid_and_reproducible():
    a, b = problem_set(6, 5), problem_set(6, 5)
    assert a == b
    for p in a:
        validate(p)
        assert len(p["bounds"]) == 6


def test_random_problem_sizes():
    import random
    for n in (4, 8, 12):
        assert len(random_problem(n, random.Random(1))["bounds"]) == n


def test_methods_agree_on_solvability_for_random_problems():
    for p in problem_set(8, 10):
        statuses = {solve(p, m, max_nodes=200000)["status"] for m in ("backtracking", "forward", "mrv")}
        statuses.discard("limit")
        assert len(statuses) == 1


def test_benchmark_script_writes_its_files(tmp_path):
    summary, opt_summary = run_benchmarks.main(
        sizes=(4, 6), per_size=3, max_nodes=5000, out_dir=str(tmp_path), charts=False, restarts=1)
    assert len(summary) == 6  # 2 sizes x 3 methods
    for name in ("results.csv", "summary.csv"):
        with open(tmp_path / name, encoding="utf-8") as f:
            assert len(list(csv.DictReader(f))) > 0


def _tmp_dir():
    import tempfile
    return tempfile.mkdtemp()
