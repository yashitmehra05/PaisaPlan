"""Demo: the three budget scenarios.  Run from the repo root:  python -m solver.demo_scenarios"""
from solver import normalise
from solver.scenarios import build_scenarios

problem = normalise({
    "income": 30000,
    "fixed_costs": [{"name": "rent", "amount": 9000}, {"name": "education", "amount": 3000}],
    "priorities": ["food", "transport", "entertainment"],
    "savings_goal": {"amount": 5000, "months": 1},
})

for name, scenario in build_scenarios(problem).items():
    result = scenario["result"]
    print(f"\n=== {scenario['label']} ({scenario['description']}) ===")
    if result["status"] != "ok":
        for item in result["unmet"]:
            print("  impossible:", item["suggestion"])
        continue
    for category, amount in result["allocation"].items():
        print(f"  {category:<14}{amount}")
    print(f"  score {result['score']}  (solver's first answer scored {result['start_score']})")
