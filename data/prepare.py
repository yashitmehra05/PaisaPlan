"""Merge, validate, de-duplicate and split the PaisaPlan fine-tuning data (Person 3).

Usage (from the repo root, after running generate.py):
    python data/prepare.py

Reads (next to this file):
    train_extract.jsonl       your hand-written examples  {"input": str, "output": dict}
    generated_extract.jsonl   from generate.py
    generated_explain.jsonl   from generate.py
Writes:
    train.jsonl, val.jsonl    chat format for Unsloth (90/10 split, fixed seed)
"""
import json
import random
from pathlib import Path

from generate import check_explain  # same folder

HERE = Path(__file__).resolve().parent
SEED = 42
VAL_FRACTION = 0.10

EXTRACT_SYS = (
    "You are the input parser for PaisaPlan, a budget planner. Convert the user's message into JSON "
    "with exactly these keys: income, fixed_costs, priorities, savings_goal, change_request. "
    "Output only the JSON. Use null (or an empty list) when something is not mentioned. "
    "Never invent numbers."
)
EXPLAIN_SYS = (
    "You are the explainer for PaisaPlan, a budget planner. You receive solver results as JSON. "
    "Explain them in plain, friendly language. Use only numbers that appear in the JSON and never "
    "calculate new ones. Mark facts as [CERTAIN] and projections as [ESTIMATE: reason]."
)

KEYS = {"income", "fixed_costs", "priorities", "savings_goal", "change_request"}
FIXED_NAMES = {"rent", "education", "food", "transport", "entertainment", "other"}  # solver accepts any category as fixed
PRIORITY_NAMES = {"savings", "food", "transport", "entertainment", "other"}
FLEX_NAMES = {"food", "transport", "entertainment", "other"}


def is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def extract_problems(o):
    """Return a list of problems (empty list = valid)."""
    p = []
    if not isinstance(o, dict) or set(o) != KEYS:
        return [f"keys must be exactly {sorted(KEYS)}"]
    if o["income"] is not None and not (is_num(o["income"]) and o["income"] >= 0):
        p.append("income must be a number or null")
    if not isinstance(o["fixed_costs"], list):
        p.append("fixed_costs must be a list")
    else:
        for fc in o["fixed_costs"]:
            if not (isinstance(fc, dict) and fc.get("name") in FIXED_NAMES and is_num(fc.get("amount"))):
                p.append(f"bad fixed cost {fc} (names allowed: {sorted(FIXED_NAMES)})")
    if not (isinstance(o["priorities"], list) and all(x in PRIORITY_NAMES for x in o["priorities"])):
        p.append(f"priorities must be a list of {sorted(PRIORITY_NAMES)}")
    sg = o["savings_goal"]
    if sg is not None and not (isinstance(sg, dict) and is_num(sg.get("amount")) and is_num(sg.get("months"))):
        p.append("savings_goal must be null or {amount, months}")
    cr = o["change_request"]
    if cr is not None and not (isinstance(cr, dict) and cr.get("category") in FLEX_NAMES | FIXED_NAMES | {"income", "savings"}
                               and cr.get("action") in {"decrease", "increase"} and is_num(cr.get("amount"))):
        p.append("change_request must be null or {category, action, amount}")
    return p


def load(name):
    path = HERE / name
    if not path.exists():
        print(f"  [warn] {name} not found, skipping")
        return []
    rows = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append((name, i, json.loads(line)))
        except json.JSONDecodeError as e:
            print(f"  [bad JSON] {name} line {i}: {e}")
    return rows


def main():
    records, bad = [], 0
    seen = set()

    def add(task, sys_msg, user, assistant, src, line):
        nonlocal bad
        key = (task, user)
        if key in seen:
            print(f"  [duplicate] {src} line {line}")
            return
        seen.add(key)
        records.append({"task": task, "messages": [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant}]})

    for name in ("train_extract.jsonl", "generated_extract.jsonl"):
        for src, i, ex in load(name):
            if not isinstance(ex, dict) or not isinstance(ex.get("input"), str):
                print(f"  [skip] {src} line {i}: needs an 'input' string")
                bad += 1
                continue
            probs = extract_problems(ex.get("output"))
            if probs:
                print(f"  [skip] {src} line {i}: {'; '.join(probs)}")
                bad += 1
                continue
            add("extract", EXTRACT_SYS, ex["input"], json.dumps(ex["output"], ensure_ascii=False), src, i)

    for src, i, ex in load("generated_explain.jsonl"):
        if not check_explain(ex["input"], ex["output"]):
            print(f"  [skip] {src} line {i}: explanation contains a number not in the input")
            bad += 1
            continue
        add("explain", EXPLAIN_SYS, json.dumps(ex["input"], ensure_ascii=False), ex["output"], src, i)

    rng = random.Random(SEED)
    train, val = [], []
    for task in ("extract", "explain"):
        group = [r for r in records if r["task"] == task]
        rng.shuffle(group)
        n_val = max(1, round(len(group) * VAL_FRACTION)) if group else 0
        val += group[:n_val]
        train += group[n_val:]
    rng.shuffle(train)
    rng.shuffle(val)

    for name, rows in (("train.jsonl", train), ("val.jsonl", val)):
        with open(HERE / name, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def count(rows, t):
        return sum(r["task"] == t for r in rows)

    print(f"\nSkipped {bad} bad rows.")
    print(f"train.jsonl: {len(train)} rows (extract {count(train, 'extract')}, explain {count(train, 'explain')})")
    print(f"val.jsonl:   {len(val)} rows (extract {count(val, 'extract')}, explain {count(val, 'explain')})")


if __name__ == "__main__":
    main()
