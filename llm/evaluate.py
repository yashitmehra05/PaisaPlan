"""Compare language-model setups on the HELD-OUT test set (data/test_extract.jsonl + solver-built explanation cases).

Typical use (Ollama must be running and both models created):

    python -m llm.evaluate \
        --run base_simple,llama3.2:3b,simple \
        --run base_fewshot,llama3.2:3b,fewshot \
        --run finetuned,paisaplan,trained

Each --run is  NAME,MODEL,PROMPT  where PROMPT is
    simple   - one-line instructions            (base model baseline)
    fewshot  - detailed instructions + 4 examples (base model with a good prompt)
    trained  - the exact prompt used in fine-tuning (use this for the fine-tuned model)

Writes benchmarks/llm_eval.csv, benchmarks/llm_eval.md (the table for the report) and
benchmarks/llm_eval_details_<name>.jsonl (every answer, for the failure analysis).

EXTRACTION metrics (per message, vs. the hand-written answer):
    valid_json, schema_ok, income_ok, fixed_ok, priorities_ok, savings_ok, change_ok,
    exact (everything right), invented_income (made up an income the user never gave)
EXPLANATION metrics (per solver result):
    no_invented_numbers, has_tags, safe (both), coverage (share of the key figures it mentions)
"""
import argparse
import csv
import json
import os
import statistics
import sys

from .ollama_client import make_chat
from .prompts import explain_messages, extract_messages
from .test_cases import explain_cases
from .validator import check_extraction, invented_numbers, has_tags, numbers_in, parse_json_reply

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_TEST = os.path.join(ROOT, "data", "test_extract.jsonl")


def load_test(path=DEFAULT_TEST):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


# ------------------------------------------------------------------- extraction

def _same_num(a, b):
    return a == b or (a is not None and b is not None and abs(float(a) - float(b)) < 1e-9)


def _fixed_key(items):
    try:
        return sorted((str(i["name"]).lower(), float(i["amount"])) for i in items)
    except (TypeError, KeyError, ValueError):
        return None


def compare(pred, gold):
    """Field-by-field comparison of one extraction with the hand-written answer."""
    out = {k: False for k in ("income_ok", "fixed_ok", "priorities_ok", "savings_ok", "change_ok")}
    out["invented_income"] = False
    if not isinstance(pred, dict):
        return {**out, "exact": False}
    out["income_ok"] = _same_num(pred.get("income"), gold["income"])
    out["invented_income"] = gold["income"] is None and pred.get("income") is not None
    out["fixed_ok"] = _fixed_key(pred.get("fixed_costs") or []) == _fixed_key(gold["fixed_costs"])
    out["priorities_ok"] = pred.get("priorities") == gold["priorities"]
    ps, gs = pred.get("savings_goal"), gold["savings_goal"]
    out["savings_ok"] = (ps is None and gs is None) or (
        isinstance(ps, dict) and gs is not None and _same_num(ps.get("amount"), gs["amount"])
        and ps.get("months") == gs["months"])
    pc, gc = pred.get("change_request"), gold["change_request"]
    out["change_ok"] = (pc is None and gc is None) or (
        isinstance(pc, dict) and gc is not None and pc.get("category") == gc["category"]
        and pc.get("action") == gc["action"] and _same_num(pc.get("amount"), gc["amount"]))
    out["exact"] = all(out[k] for k in ("income_ok", "fixed_ok", "priorities_ok", "savings_ok", "change_ok"))
    return out


def run_extraction(chat, variant, rows):
    details = []
    for row in rows:
        try:
            reply = chat(extract_messages(row["input"], variant))
        except Exception as e:
            reply = f"<<error: {e}>>"
        obj, error = parse_json_reply(reply)
        schema_problems = [error] if error else check_extraction(obj)
        cmp = compare(obj, row["gold"])
        details.append({"input": row["input"], "type": row["type"], "reply": reply,
                        "valid_json": error is None, "schema_ok": not schema_problems, **cmp})
    return details


def summarise_extraction(details):
    n = len(details)
    rate = lambda key, rows=details: round(100 * sum(d[key] for d in rows) / len(rows), 1) if rows else None
    summary = {"extract_n": n}
    for key in ("valid_json", "schema_ok", "income_ok", "fixed_ok", "priorities_ok",
                "savings_ok", "change_ok", "exact"):
        summary[key] = rate(key)
    missing = [d for d in details if d["type"] == "missing"]
    summary["invented_income_pct"] = rate("invented_income", missing)
    for kind in ("budget", "what_if", "missing", "tricky"):
        summary[f"exact_{kind}"] = rate("exact", [d for d in details if d["type"] == kind])
    return summary


# ------------------------------------------------------------------ explanations

def run_explanations(chat, variant, cases):
    details = []
    for case in cases:
        payload = case["payload"]
        try:
            reply = chat(explain_messages(payload, variant)).strip()
        except Exception as e:
            reply = f"<<error: {e}>>"
        bad = invented_numbers(reply, payload)
        mentioned = numbers_in(reply)
        coverage = (sum(float(r) in mentioned for r in case["required"]) / len(case["required"])
                    if case["required"] else 1.0)
        details.append({"kind": case["kind"], "payload": payload, "reply": reply,
                        "no_invented_numbers": not bad, "invented": bad, "has_tags": has_tags(reply),
                        "safe": (not bad) and has_tags(reply), "coverage": round(coverage, 3)})
    return details


def summarise_explanations(details):
    n = len(details)
    pct = lambda key: round(100 * sum(d[key] for d in details) / n, 1)
    return {"explain_n": n, "no_invented_numbers": pct("no_invented_numbers"),
            "has_tags": pct("has_tags"), "safe": pct("safe"),
            "coverage": round(100 * statistics.mean(d["coverage"] for d in details), 1)}


# ------------------------------------------------------------------------ output

COLUMNS = ["name", "model", "prompt", "valid_json", "schema_ok", "income_ok", "fixed_ok",
           "priorities_ok", "savings_ok", "change_ok", "exact", "exact_budget", "exact_what_if",
           "exact_missing", "exact_tricky", "invented_income_pct", "no_invented_numbers",
           "has_tags", "safe", "coverage", "extract_n", "explain_n"]


def markdown_table(rows):
    head = ("| Setup | Valid JSON | Income | Fixed costs | Priorities | Savings goal | What-if | **All correct** "
            "| Invents income | Explanations without invented numbers | With tags | Key figures covered |")
    sep = "|" + "---|" * 12
    lines = [head, sep]
    for r in rows:
        lines.append(f"| {r['name']} | {r['valid_json']}% | {r['income_ok']}% | {r['fixed_ok']}% | "
                     f"{r['priorities_ok']}% | {r['savings_ok']}% | {r['change_ok']}% | **{r['exact']}%** | "
                     f"{r['invented_income_pct']}% | {r['no_invented_numbers']}% | {r['has_tags']}% | {r['coverage']}% |")
    return "\n".join(lines)


def evaluate(runs, out_dir, test_path=DEFAULT_TEST, chat_factory=make_chat, explain=True):
    """runs: list of (name, model, prompt). Returns the list of summary rows."""
    os.makedirs(out_dir, exist_ok=True)
    rows_in = load_test(test_path)
    cases = explain_cases() if explain else []
    summaries = []
    for name, model, prompt in runs:
        chat = chat_factory(model)
        ex = run_extraction(chat, prompt, rows_in)
        summary = {"name": name, "model": model, "prompt": prompt, **summarise_extraction(ex)}
        details = ex
        if cases:
            exp = run_explanations(chat, "simple" if prompt == "simple" else "trained", cases)
            summary.update(summarise_explanations(exp))
            details = ex + exp
        else:
            summary.update({"no_invented_numbers": "", "has_tags": "", "safe": "", "coverage": "", "explain_n": 0})
        with open(os.path.join(out_dir, f"llm_eval_details_{name}.jsonl"), "w", encoding="utf-8") as f:
            for d in details:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
        summaries.append(summary)
        print(f"{name}: exact {summary['exact']}%  valid JSON {summary['valid_json']}%")

    with open(os.path.join(out_dir, "llm_eval.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(summaries)
    with open(os.path.join(out_dir, "llm_eval.md"), "w", encoding="utf-8") as f:
        f.write(markdown_table(summaries) + "\n")
    return summaries


def main(argv=None):
    parser = argparse.ArgumentParser(description="Evaluate model setups on the held-out test set.")
    parser.add_argument("--run", action="append", required=True, metavar="NAME,MODEL,PROMPT")
    parser.add_argument("--out", default="benchmarks")
    parser.add_argument("--test", default=DEFAULT_TEST)
    parser.add_argument("--no-explain", action="store_true", help="skip the explanation test")
    args = parser.parse_args(argv)
    runs = []
    for spec in args.run:
        parts = spec.split(",")
        if len(parts) != 3 or parts[2] not in ("simple", "fewshot", "trained"):
            sys.exit(f"bad --run '{spec}': use NAME,MODEL,PROMPT with PROMPT simple|fewshot|trained")
        runs.append(tuple(parts))
    rows = evaluate(runs, args.out, args.test, explain=not args.no_explain)
    print()
    print(markdown_table(rows))


if __name__ == "__main__":
    main()
