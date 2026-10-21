INCOME = 30000
FIXED = {"rent": 9000, "education": 3000}
SAVINGS_GOAL = 5000
FLEX = {                      # (minimum, maximum)
    "food": (3000, 8000),
    "transport": (500, 3000),
    "entertainment": (0, 3000),
    "other": (0, 2000),
}
STEP = 500

def backtrack(assigned, cats_left, budget_left):
    if not cats_left:
        return assigned
    cat = cats_left[0]
    lo, hi = FLEX[cat]
    for amount in range(lo, hi + 1, STEP):
        if amount <= budget_left:
            result = backtrack({**assigned, cat: amount}, cats_left[1:], budget_left - amount)
            if result is not None:
                return result
    return None

if __name__ == "__main__":
    budget_left = INCOME - sum(FIXED.values()) - SAVINGS_GOAL
    print(backtrack({}, list(FLEX), budget_left))