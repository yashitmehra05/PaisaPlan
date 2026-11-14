"""PaisaPlan synthetic data generator (Person 3).

Usage (from the repo root):
    python data/generate.py
    python data/generate.py --extract 500 --explain 250 --seed 7

Writes next to this file:
    generated_extract.jsonl  -> {"input": "<messy message>", "output": {<schema json>}}
    generated_explain.jsonl  -> {"input": {<solver result>}, "output": "<explanation>"}

The data is SYNTHETIC (templates + random numbers). Say so in the report.
Every rupee figure in an explanation is checked to exist in its input,
so the training data itself teaches "never invent numbers".
"""
import argparse
import json
import math
import random
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
ONES = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
        "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
        "seventeen", "eighteen", "nineteen"]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def words_under_100(n):
    if n < 20:
        return ONES[n]
    t, o = divmod(n, 10)
    return TENS[t] + (" " + ONES[o] if o else "")


def pick(rng, lo, hi, step=500):
    """Random multiple of `step` between lo and hi (inclusive)."""
    return rng.randrange(math.ceil(lo / step), hi // step + 1) * step


def money_text(n, rng):
    """Write n rupees the way different people type it."""
    styles = ["raw", "comma", "rs", "rupee"]
    if n >= 1000 and n % 100 == 0:
        styles += ["k", "k", "k"]
    if n >= 1000 and n % 1000 == 0 and n // 1000 < 100:
        styles += ["words", "hindi"]
    s = rng.choice(styles)
    if s == "raw":
        return str(n)
    if s == "comma":
        return f"{n:,}"
    if s == "rs":
        return f"Rs {n}"
    if s == "rupee":
        return f"\u20b9{n:,}"
    if s == "k":
        return f"{n / 1000:g}k"
    if s == "words":
        return words_under_100(n // 1000) + " thousand"
    return f"{n // 1000} hazaar"


TYPOS = {"salary": "salry", "income": "incom", "rent": "rnt", "month": "mnth",
         "save": "sav", "want": "wnat", "college": "collage", "hostel": "hostal",
         "fees": "fess", "priority": "priorty", "important": "importnt",
         "reduce": "reduse", "increase": "incrase", "what": "wat"}


def add_typos(text, rng):
    for good, bad in TYPOS.items():
        if rng.random() < 0.5:
            text = re.sub(rf"\b{good}\b", bad, text, flags=re.IGNORECASE)
    return text


# ----------------------------------------------------------------------------
# Task A: message -> JSON
# ----------------------------------------------------------------------------
INCOME_T = [
    "I earn {a} a month", "my salary is {a}", "income {a}", "I get {a} per month",
    "salary {a}", "monthly allowance is {a}", "I have {a} every month",
    "mujhe {a} milte hain har mahine", "meri salary {a} hai", "stipend is {a}",
    "I make {a} monthly", "got {a} this month",
]
RENT_T = [
    "rent is {a}", "hostel {a}", "PG costs {a}", "rent {a}", "{a} goes to rent",
    "hostel fees {a}", "kiraya {a}", "I pay {a} for my room",
]
EDU_T = [
    "college fees {a}", "tuition {a}", "education {a}", "{a} for course fees",
    "fees {a} per month", "books and fees {a}", "college ki fees {a}",
]
SAVE_T = [  # needs {a} and {m}
    "want to save {a} in {m} months", "save {a} over {m} months",
    "goal: {a} savings in {m} months", "need {a} saved within {m} months",
    "mujhe {m} mahine mein {a} bachane hain",
]
SAVE1_T = [  # only {a} -> months = 1
    "want to save {a}", "save {a} per month", "saving target {a}",
    "mujhe {a} bachana hai", "I need to save {a} this month", "put aside {a}",
]
PRI_WORDS = {"savings": ["savings"], "food": ["food"], "transport": ["transport", "travel"],
             "entertainment": ["entertainment", "fun"], "other": ["other stuff"]}


def priority_text(order, rng):
    w = [rng.choice(PRI_WORDS[c]) for c in order]
    if len(w) == 1:
        return rng.choice(["{a} matters most", "{a} is my top priority", "{a} first"]).format(a=w[0])
    return rng.choice([
        "priority order: " + " > ".join(w),
        "most important is " + w[0] + ", then " + ", then ".join(w[1:]),
        w[0] + " first, then " + ", then ".join(w[1:]),
        "priorities: " + ", ".join(w),
    ])


def gen_fresh(rng):
    income = pick(rng, 10000, 80000, 1000 if rng.random() < 0.7 else 500)
    parts = [rng.choice(INCOME_T).format(a=money_text(income, rng))]
    fixed, priorities, savings_goal = [], [], None
    if rng.random() < 0.85:
        rent = pick(rng, 2000, int(income * 0.4))
        fixed.append({"name": "rent", "amount": rent})
        parts.append(rng.choice(RENT_T).format(a=money_text(rent, rng)))
    if rng.random() < 0.6:
        edu = pick(rng, 1000, int(income * 0.25))
        fixed.append({"name": "education", "amount": edu})
        parts.append(rng.choice(EDU_T).format(a=money_text(edu, rng)))
    if rng.random() < 0.7:
        monthly = pick(rng, 1000, max(1000, int(income * 0.25)))
        months = rng.choice([1, 1, 1, 2, 3, 4, 6, 12])
        total = monthly * months
        savings_goal = {"amount": total, "months": months}
        if months == 1:
            parts.append(rng.choice(SAVE1_T).format(a=money_text(total, rng)))
        else:
            parts.append(rng.choice(SAVE_T).format(a=money_text(total, rng), m=months))
    if rng.random() < 0.55:
        k = rng.choice([1, 2, 2, 3, 4])
        priorities = rng.sample(["savings", "food", "transport", "entertainment", "other"], k)
        parts.append(priority_text(priorities, rng))
    rest = parts[1:]
    rng.shuffle(rest)
    parts = [parts[0]] + rest if rng.random() < 0.8 else rng.sample(parts, len(parts))
    msg = rng.choice([", ", ". ", "; ", " and "]).join(parts)
    r = rng.random()
    if r < 0.5:
        msg = msg[0].upper() + msg[1:]
    elif r < 0.6:
        msg = msg.upper()
    if rng.random() < 0.15:
        msg = rng.choice(["hi, ", "hey ", "plan my budget: ", "help me budget. "]) + msg
    if rng.random() < 0.25:
        msg = add_typos(msg, rng)
    out = {"income": income, "fixed_costs": fixed, "priorities": priorities,
           "savings_goal": savings_goal, "change_request": None}
    return {"input": msg, "output": out}


CAT_WORDS = {"food": ["eating out", "food", "groceries", "mess food", "canteen"],
             "transport": ["transport", "travel", "cab rides", "petrol"],
             "entertainment": ["entertainment", "movies", "outings", "fun"],
             "other": ["other", "misc", "miscellaneous spending"]}
DEC_T = ["what if I cut {c} by {a}?", "reduce {c} by {a}", "what happens if I spend {a} less on {c}",
         "lower {c} by {a} please", "{c} mein {a} kam karo", "can I save more if I cut {c} by {a}",
         "cut {c} by {a}"]
INC_T = ["what if I spend {a} more on {c}", "increase {c} by {a}", "raise {c} budget by {a}",
         "add {a} to {c}", "{c} me {a} badha do", "what if {c} goes up by {a}"]


def gen_whatif(rng):
    cat = rng.choice(list(CAT_WORDS))
    action = rng.choice(["decrease", "increase"])
    amount = pick(rng, 500, 3000)
    t = rng.choice(DEC_T if action == "decrease" else INC_T)
    msg = t.format(c=rng.choice(CAT_WORDS[cat]), a=money_text(amount, rng))
    if rng.random() < 0.4:
        msg = msg[0].upper() + msg[1:]
    if rng.random() < 0.2:
        msg = add_typos(msg, rng)
    out = {"income": None, "fixed_costs": [], "priorities": [], "savings_goal": None,
           "change_request": {"category": cat, "action": action, "amount": amount}}
    return {"input": msg, "output": out}


# ----------------------------------------------------------------------------
# Task B: solver result -> explanation (with confidence tags)
# ----------------------------------------------------------------------------
def rupee(n):
    return f"\u20b9{n:,}"


def plural_months(n):
    return f"{n} month{'s' if n != 1 else ''}"


def ilist(items):
    items = [f"{k} {rupee(v)}" for k, v in items]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def gen_plan(rng):
    alloc = {"rent": pick(rng, 2000, 12000)}
    edu = rng.choice([0, pick(rng, 1000, 4000)])
    if edu:
        alloc["education"] = edu
    for cat, lo, hi in [("food", 2000, 8000), ("transport", 500, 3000),
                        ("entertainment", 0, 3000), ("other", 0, 2000)]:
        v = pick(rng, lo, hi)
        if v:
            alloc[cat] = v
    alloc["savings"] = pick(rng, 1000, 8000)
    unalloc = rng.choice([0, 0, 500, 1000, 1500])
    income = sum(alloc.values()) + unalloc
    return alloc, unalloc, income


def explain_ok(rng):
    alloc, unalloc, income = gen_plan(rng)
    s = alloc["savings"]
    goal = rng.random() < 0.8
    months = rng.choice([2, 3, 4, 6, 8, 10, 12]) if goal else None
    total = s * months if goal else None
    inp = {"task": "explain", "status": "ok", "income": income, "allocation": alloc,
           "unallocated": unalloc, "savings_goal_total": total, "months_to_goal": months}
    fixed = [(k, v) for k, v in alloc.items() if k in ("rent", "education")]
    flex = [(k, v) for k, v in alloc.items() if k in ("food", "transport", "entertainment", "other")]
    out = [rng.choice([f"Here is your monthly plan for an income of {rupee(income)}.",
                       f"I built a valid budget for your income of {rupee(income)}.",
                       f"Your income of {rupee(income)} can be split like this."])]
    out.append(f"Fixed costs are {ilist(fixed)} [CERTAIN].")
    if flex:
        out.append(rng.choice([f"Flexible spending is set to {ilist(flex)} [CERTAIN].",
                               f"The solver gave you {ilist(flex)} for flexible categories [CERTAIN]."]))
    if goal:
        out.append(f"You save {rupee(s)} per month, which reaches your {rupee(total)} goal in "
                   f"{plural_months(months)} [ESTIMATE: assumes your income and spending stay the same].")
    else:
        out.append(f"You save {rupee(s)} per month [CERTAIN].")
    if unalloc:
        out.append(f"{rupee(unalloc)} is left unallocated.")
    return inp, " ".join(out)


def explain_whatif(rng):
    alloc, _, _ = gen_plan(rng)
    s = alloc["savings"]
    action = rng.choice(["decrease", "increase"])
    if action == "decrease":
        cands = [c for c in ("food", "transport", "entertainment", "other") if alloc.get(c, 0) >= 500]
        cat = rng.choice(cands)
        old = alloc[cat]
        amt = pick(rng, 500, min(old, 3000))
        new, ns = old - amt, s + amt
    else:
        cat = rng.choice(["food", "transport", "entertainment", "other"])
        old = alloc.get(cat, 0)
        amt = pick(rng, 500, min(s - 500, 3000))
        new, ns = old + amt, s - amt
    goal = rng.random() < 0.8
    mo = rng.choice([2, 3, 4, 6, 8, 10, 12]) if goal else None
    total = s * mo if goal else None
    mn = math.ceil(total / ns) if goal else None
    inp = {"task": "explain", "status": "ok",
           "change": {"category": cat, "action": action, "amount": amt},
           "category_old": old, "category_new": new, "savings_old": s, "savings_new": ns,
           "savings_goal_total": total, "months_old": mo, "months_new": mn}
    if action == "decrease":
        first = rng.choice([f"Cutting {cat} by {rupee(amt)}", f"Spending {rupee(amt)} less on {cat}",
                            f"Reducing {cat} by {rupee(amt)}"])
        out = [f"{first} lowers it from {rupee(old)} to {rupee(new)} [CERTAIN].",
               f"The freed {rupee(amt)} moves to savings, raising it from {rupee(s)} to {rupee(ns)} per month [CERTAIN]."]
    else:
        first = rng.choice([f"Spending {rupee(amt)} more on {cat}", f"Raising {cat} by {rupee(amt)}",
                            f"Increasing {cat} by {rupee(amt)}"])
        out = [f"{first} raises it from {rupee(old)} to {rupee(new)} [CERTAIN].",
               f"That {rupee(amt)} comes out of savings, which drop from {rupee(s)} to {rupee(ns)} per month [CERTAIN]."]
    if goal:
        if mn == mo:
            out.append(f"Your {rupee(total)} goal still takes {plural_months(mn)} "
                       "[ESTIMATE: assumes spending stays stable].")
        else:
            out.append(f"Your {rupee(total)} goal now takes {plural_months(mn)} instead of {plural_months(mo)} "
                       "[ESTIMATE: assumes spending stays stable].")
    return inp, " ".join(out)


def explain_infeasible(rng):
    while True:
        fixed = pick(rng, 3000, 15000)
        sav = pick(rng, 1000, 10000)
        mins = pick(rng, 2000, 9000)
        short = pick(rng, 500, 6000)
        income = fixed + sav + mins - short
        if income >= 4000:
            break
    need = fixed + sav + mins
    sug = sav - short if sav - short >= 0 else None
    inp = {"task": "explain", "status": "infeasible", "income": income, "fixed_total": fixed,
           "savings_goal_monthly": sav, "min_flexible_total": mins, "total_needed": need,
           "shortfall": short, "suggested_savings_goal": sug}
    out = [rng.choice(["I couldn't build a valid budget.", "This budget is not possible as asked."]),
           f"Your fixed costs of {rupee(fixed)}, savings goal of {rupee(sav)} per month and minimum "
           f"spending of {rupee(mins)} add up to {rupee(need)}, but your income is {rupee(income)}, "
           f"so you are short by {rupee(short)} [CERTAIN]."]
    if sug is not None:
        out.append(f"One fix is to lower your monthly savings goal from {rupee(sav)} to {rupee(sug)} [CERTAIN].")
    else:
        out.append("Even without the savings goal, fixed costs and minimum spending are too high, "
                   f"so the category minimums would need to be lowered by at least {rupee(short)} [CERTAIN].")
    return inp, " ".join(out)


# ----------------------------------------------------------------------------
# faithfulness check: every number in the explanation must exist in the input
# ----------------------------------------------------------------------------
def numbers_in(obj):
    if isinstance(obj, bool) or obj is None:
        return set()
    if isinstance(obj, (int, float)):
        return {int(obj)}
    if isinstance(obj, dict):
        return set().union(*[numbers_in(v) for v in obj.values()]) if obj else set()
    if isinstance(obj, list):
        return set().union(*[numbers_in(v) for v in obj]) if obj else set()
    return set()


def check_explain(inp, out):
    allowed = numbers_in(inp)
    for m in re.findall(r"\d[\d,]*", out):
        if int(m.replace(",", "")) not in allowed:
            return False
    return True


# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--extract", type=int, default=400)
    ap.add_argument("--explain", type=int, default=200)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    # --- extraction: ~75% fresh budgets, ~25% what-if
    seen, ext = set(), []
    while len(ext) < args.extract:
        ex = gen_whatif(rng) if rng.random() < 0.25 else gen_fresh(rng)
        if ex["input"] in seen:
            continue
        seen.add(ex["input"])
        ext.append(ex)
    with open(HERE / "generated_extract.jsonl", "w", encoding="utf-8") as f:
        for ex in ext:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    # --- explanation: 35% plain plan, 45% what-if, 20% infeasible
    exp, seen_in = [], set()
    while len(exp) < args.explain:
        r = rng.random()
        fn = explain_ok if r < 0.35 else explain_whatif if r < 0.80 else explain_infeasible
        inp, out = fn(rng)
        key = json.dumps(inp, sort_keys=True)
        if key in seen_in or not check_explain(inp, out):
            continue
        seen_in.add(key)
        exp.append({"input": inp, "output": out})
    with open(HERE / "generated_explain.jsonl", "w", encoding="utf-8") as f:
        for ex in exp:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    print(f"Wrote {len(ext)} extraction and {len(exp)} explanation examples to {HERE}")
    print("\nSample extraction:", json.dumps(ext[0], ensure_ascii=False))
    print("\nSample explanation:", json.dumps(exp[0], ensure_ascii=False))


if __name__ == "__main__":
    main()
