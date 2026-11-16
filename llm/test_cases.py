"""Explanation test cases built from the REAL solver (not from the training templates).

Each case: {"kind", "payload", "required"}  where required = numbers a good explanation should
mention. Used by llm/evaluate.py to measure whether the model invents numbers, uses the
confidence tags, and covers the key figures.
"""
import json
import random

from solver import normalise, solve

from .payloads import budget_payload, infeasible_payload, what_if_payload
from .whatif import apply_what_if

PROFILES = [
    dict(income=18000, fixed={"rent": 6000}, save=(3000, 1), pri=["food"]),
    dict(income=24000, fixed={"rent": 7000, "education": 3000}, save=(12000, 6), pri=["transport", "food"]),
    dict(income=30000, fixed={"rent": 9000, "education": 3000}, save=(20000, 4), pri=["food", "entertainment"]),
    dict(income=36000, fixed={"rent": 10000}, save=(5000, 1), pri=[]),
    dict(income=45000, fixed={"rent": 12000, "education": 5000}, save=(30000, 6), pri=["entertainment"]),
    dict(income=52000, fixed={"rent": 14000}, save=(9000, 1), pri=["food", "transport", "other"]),
    dict(income=28000, fixed={"rent": 8000}, save=None, pri=["food"]),
    dict(income=60000, fixed={"rent": 18000, "education": 7000}, save=(80000, 8), pri=["transport"]),
]
CHANGES = [("food", "decrease", 1000), ("transport", "increase", 500), ("entertainment", "decrease", 1500),
           ("other", "increase", 1000), ("food", "increase", 2000)]


def _problem(profile, savings_override=None):
    schema = {"income": profile["income"],
              "fixed_costs": [{"name": k, "amount": v} for k, v in profile["fixed"].items()],
              "priorities": profile["pri"]}
    if profile["save"]:
        schema["savings_goal"] = {"amount": profile["save"][0], "months": profile["save"][1]}
    problem = normalise(schema)
    if savings_override is not None:
        problem["savings_goal"] = savings_override
    return problem


def explain_cases(seed=0):
    """About 30 cases: budgets, what-ifs, and impossible budgets."""
    rng = random.Random(seed)
    cases = []
    for profile in PROFILES:
        problem = _problem(profile)
        result = solve(problem)
        if result["status"] == "ok":
            payload = budget_payload(problem, result)
            required = [payload["income"], payload["allocation"]["savings"]]
            required += [v for k, v in payload["allocation"].items() if k not in ("savings",) and v]
            cases.append({"kind": "budget", "payload": payload, "required": sorted(set(required))})
            for change in rng.sample(CHANGES, 3):
                c = {"category": change[0], "action": change[1], "amount": change[2]}
                w = apply_what_if(problem, c)
                if w["new"]["status"] == "ok" and w["mode"] == "savings_absorbs":
                    wp = what_if_payload(problem, c, w["old"], w["new"])
                    required = [wp["change"]["amount"], wp["category_new"], wp["savings_new"]]
                    cases.append({"kind": "what_if", "payload": wp, "required": sorted(set(required))})
        # impossible: ask for far more savings than possible
        bad = _problem(profile, savings_override=profile["income"])
        r = solve(bad)
        p = infeasible_payload(bad, r) if r["status"] == "infeasible" else None
        if p:
            cases.append({"kind": "infeasible", "payload": p,
                          "required": sorted({p["shortfall"], p["suggested_savings_goal"]})})
    return cases


def dump(cases):
    return [json.dumps(c["payload"]) for c in cases]
