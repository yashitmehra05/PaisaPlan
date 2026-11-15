"""Tests for the PaisaPlan solver. Run from the repo root with:  pytest -v"""
import pytest

from solver import normalise, resolve, solve

METHODS = ["backtracking", "forward", "mrv"]


def make(**overrides):
    """A normal student budget; override any field of the schema."""
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
    """Every feasible result must obey all constraints."""
    alloc = result["allocation"]
    assert sum(alloc.values()) + result["unallocated"] == problem["income"]
    assert result["unallocated"] >= 0
    for name, (lo, hi) in problem["bounds"].items():
        assert lo <= alloc[name] <= hi
    for a, op, b in problem["rules"]:
        if a in alloc and b in alloc:
            assert eval(f"{alloc[a]} {op} {alloc[b]}")
    assert alloc["savings"] == problem["savings_goal"]
    flex_total = sum(alloc[n] for n in problem["bounds"])
    assert flex_total <= 0.6 * problem["income"]


# ------------------------------------------------------------ normalise

def test_normalise_converts_savings_to_monthly():
    p = make(savings_goal={"amount": 10000, "months": 4})
    assert p["savings_goal"] == 2500
    assert p["savings_total"] == 10000 and p["savings_months"] == 4


def test_normalise_null_savings_goal_is_zero():
    assert make(savings_goal=None)["savings_goal"] == 0


def test_normalise_fixed_costs_become_dict_and_remove_flexible_category():
    p = make(fixed_costs=[{"name": "Rent", "amount": 9000}, {"name": "food", "amount": 4000}])
    assert p["fixed_costs"] == {"rent": 9000, "food": 4000}
    assert "food" not in p["bounds"]


@pytest.mark.parametrize("bad", [
    {"income": -1},
    {"income": None},
    {"fixed_costs": [{"name": "rent", "amount": -5}]},
])
def test_normalise_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        make(**bad)


# --------------------------------------------------------------- solving

@pytest.mark.parametrize("method", METHODS)
def test_normal_budget_is_valid(method):
    p = make()
    r = solve(p, method)
    assert r["status"] == "ok"
    check_valid(p, r)


def test_backtracking_and_forward_find_the_same_budget():
    p = make()
    assert solve(p, "backtracking")["allocation"] == solve(p, "forward")["allocation"]


def test_priorities_get_the_most_money_first():
    r = solve(make(priorities=["food"]))
    assert r["allocation"]["food"] == 8000  # food's maximum


@pytest.mark.parametrize("method", METHODS)
def test_exactly_tight_budget_uses_only_minimums(method):
    p = make(income=14500, savings_goal=None)
    r = solve(p, method)
    assert r["status"] == "ok"
    assert (r["allocation"]["food"], r["allocation"]["transport"]) == (2000, 500)
    assert r["unallocated"] == 0
    check_valid(p, r)


@pytest.mark.parametrize("method", METHODS)
def test_all_fixed_categories_still_solves(method):
    p = make(fixed_costs=[{"name": n, "amount": 1000} for n in
                          ["rent", "education", "food", "transport", "entertainment", "other"]])
    r = solve(p, method)
    assert r["status"] == "ok"
    assert r["allocation"]["savings"] == 5000


def test_pairwise_rule_is_respected():
    p = make(income=60000, bounds={"food": (0, 1000), "entertainment": (0, 3000)})
    r = solve(p)
    assert r["status"] == "ok"
    assert r["allocation"]["entertainment"] <= r["allocation"]["food"]


# ------------------------------------------------------------ infeasible

@pytest.mark.parametrize("method", METHODS)
def test_minimums_exceed_income(method):
    r = solve(make(income=14000, savings_goal=None), method)
    assert r["status"] == "infeasible"
    assert r["unmet"][0]["constraint"] == "essential_minimums"
    assert r["unmet"][0]["short_by"] == 500


@pytest.mark.parametrize("method", METHODS)
def test_savings_goal_too_high(method):
    r = solve(make(income=20000, savings_goal={"amount": 6000, "months": 1}), method)
    assert r["status"] == "infeasible"
    assert r["unmet"][0]["constraint"] == "savings_goal"
    assert r["unmet"][0]["short_by"] == 500
    assert "5500" in r["unmet"][0]["suggestion"]


@pytest.mark.parametrize("method", METHODS)
def test_fixed_costs_exceed_income(method):
    r = solve(make(income=10000), method)
    assert r["status"] == "infeasible"
    assert r["unmet"][0]["constraint"] == "fixed_costs"
    assert r["unmet"][0]["short_by"] == 2000


@pytest.mark.parametrize("method", METHODS)
def test_zero_income_is_infeasible_not_a_crash(method):
    r = solve(make(income=0, savings_goal=None), method)
    assert r["status"] == "infeasible"


@pytest.mark.parametrize("method", METHODS)
def test_conflicting_rule_is_reported(method):
    p = make(income=60000, bounds={"food": (0, 1000), "entertainment": (2000, 3000)})
    r = solve(p, method)
    assert r["status"] == "infeasible"
    assert r["unmet"][0]["constraint"] == "rule: entertainment <= food"
    assert r["unmet"][0]["short_by"] == 1000


# ------------------------------------------------ algorithm behaviour

def test_forward_checking_uses_fewer_nodes_than_plain_backtracking():
    p = make(income=14000, savings_goal=None)  # impossible: plain tries, forward sees it at once
    plain = solve(p, "backtracking")["stats"]["nodes"]
    forward = solve(p, "forward")["stats"]["nodes"]
    assert plain > 0 and forward < plain


def test_node_limit_stops_the_search():
    r = solve(make(income=14000, savings_goal=None), "backtracking", max_nodes=1)
    assert r["status"] == "limit"


def test_unknown_method_is_rejected():
    with pytest.raises(ValueError):
        solve(make(), "magic")


# --------------------------------------------------------------- resolve

def test_cut_food_sends_the_money_to_savings():
    p = make()
    out = resolve(p, {"category": "food", "action": "decrease", "amount": 1000})
    assert out["old"]["status"] == out["new"]["status"] == "ok"
    assert out["diff"]["food"] == -1000
    assert out["diff"]["savings"] == 1000
    assert out["freed_to_savings"] == 1000
    assert out["new"]["allocation"]["savings"] == 6000
    assert out["savings_effect"]["months_to_goal_new"] < out["savings_effect"]["months_to_goal_old"]
    check_valid({**p, "savings_goal": 6000}, out["new"])


def test_cut_that_breaks_a_rule_is_explained():
    out = resolve(make(), {"category": "food", "action": "decrease", "amount": 6500})
    assert out["new"]["status"] == "infeasible"
    assert out["diff"] is None
    assert out["new"]["unmet"][0]["constraint"] == "rule: entertainment <= food"


def test_increase_food_makes_other_categories_shrink():
    out = resolve(make(), {"category": "food", "action": "increase", "amount": 3000})
    assert out["new"]["status"] == "ok"
    assert out["new"]["allocation"]["food"] == 11000
    assert out["diff"]["transport"] < 0


def test_rent_going_up_is_resolved():
    out = resolve(make(), {"category": "rent", "action": "increase", "amount": 1000})
    assert out["new"]["status"] == "ok"
    assert out["new"]["allocation"]["rent"] == 10000


def test_income_drop_can_make_the_budget_impossible():
    out = resolve(make(), {"category": "income", "action": "decrease", "amount": 20000})
    assert out["new"]["status"] == "infeasible"


def test_resolve_does_not_change_the_original_problem():
    p = make()
    before = repr(p)
    resolve(p, {"category": "food", "action": "decrease", "amount": 1000})
    assert repr(p) == before


@pytest.mark.parametrize("change", [
    {"category": "pets", "action": "decrease", "amount": 100},
    {"category": "food", "action": "shrink", "amount": 100},
    {"category": "food", "action": "decrease", "amount": 0},
])
def test_resolve_rejects_bad_changes(change):
    with pytest.raises(ValueError):
        resolve(make(), change)
