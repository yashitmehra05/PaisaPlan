"""Quick demo: run with  python -m solver.demo  from the repo root."""
from solver import normalise, resolve, solve


def show(title, result):
    print(f"\n=== {title} ===")
    print("status     :", result["status"])
    if result["status"] == "ok":
        for name, amount in result["allocation"].items():
            print(f"  {name:<14}{amount}")
        print("  unallocated   ", result["unallocated"])
    for item in result["unmet"]:
        print("  UNMET:", item["constraint"], "| short by", item["short_by"])
        print("        ", item["suggestion"])
    print("stats      :", result["stats"])


schema = {
    "income": 30000,
    "fixed_costs": [{"name": "rent", "amount": 9000}, {"name": "education", "amount": 3000}],
    "priorities": ["food", "transport", "entertainment"],
    "savings_goal": {"amount": 5000, "months": 1},
}
problem = normalise(schema)

for method in ("backtracking", "forward", "mrv"):
    show(f"Normal budget ({method})", solve(problem, method))

impossible = normalise({**schema, "income": 14000, "savings_goal": None})
show("Impossible budget (income too low)", solve(impossible))

what_if = resolve(problem, {"category": "food", "action": "decrease", "amount": 1000})
print("\n=== What if I cut food by 1000? ===")
print("diff              :", what_if["diff"])
print("freed to savings  :", what_if["freed_to_savings"])
print("savings effect    :", what_if["savings_effect"])
