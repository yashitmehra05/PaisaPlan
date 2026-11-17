"""Safety checks on what the language model says. The model may EXPLAIN; it may never INVENT.

  * parse_json_reply     - pull a JSON object out of a model reply
  * check_extraction     - is the extracted JSON in the agreed shape? (also normalises it)
  * invented_numbers     - numbers in an explanation that were not in the solver data
  * check_explanation    - invented numbers + missing [CERTAIN]/[ESTIMATE] tags + length
  * split_tagged         - break an explanation into sentences with their confidence label
"""
import json
import re

# 1,000  /  21,500  /  0.8  /  5000   (commas are thousands separators in the training data)
_NUMBER = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")
_TAG = re.compile(r"\[(CERTAIN|ESTIMATE)(?::\s*([^\]]*))?\]", re.IGNORECASE)
KEYS = ["income", "fixed_costs", "priorities", "savings_goal", "change_request"]
CHANGE_CATEGORIES = {"food", "transport", "entertainment", "other", "rent", "education",
                     "income", "savings"}


# ----------------------------------------------------------------- JSON replies

def parse_json_reply(text):
    """Return (object, None) or (None, error). Tolerates code fences and extra words."""
    if text is None:
        return None, "empty reply"
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        return None, "no JSON object found"
    try:
        return json.loads(cleaned[start:end + 1]), None
    except json.JSONDecodeError as e:
        return None, f"invalid JSON: {e}"


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x >= 0


def _coerce_amount(x):
    """Turn a value into a non-negative int, or return None if impossible."""
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)) and x >= 0:
        return int(x)
    if isinstance(x, str):
        s = x.replace(",", "").replace("₹", "").strip()
        try:
            v = float(s)
            return int(v) if v >= 0 else None
        except ValueError:
            return None
    return None


def check_extraction(obj):
    """Problems with the SHAPE of an extraction (empty list = fine).

    NOTE: this function both validates AND normalises. It rewrites `obj` in place so the
    rest of the pipeline always sees the agreed schema, even when the model is slightly off.
    Accepted normalisations:
      * fixed_costs: dict {name: amount}  →  list of {"name","amount"}
      * savings_goal: bare number          →  {"amount": n, "months": 1}
      * savings_goal: {"amount": n}        →  {"amount": n, "months": 1}
      * missing keys                       →  filled with null / [] defaults
      * priorities: null                   →  []
    """
    if not isinstance(obj, dict):
        return ["reply is not a JSON object"]

    # Fill any missing key with a safe default so downstream code never KeyErrors.
    for key, default in [
        ("income", None),
        ("fixed_costs", []),
        ("priorities", []),
        ("savings_goal", None),
        ("change_request", None),
    ]:
        obj.setdefault(key, default)

    # Drop any extra keys the model invented (e.g. "notes", "explanation").
    for extra in list(obj):
        if extra not in KEYS:
            del obj[extra]

    problems = []

    # --- income ---
    if obj["income"] is not None:
        coerced = _coerce_amount(obj["income"])
        if coerced is None:
            problems.append("income must be a number or null")
        else:
            obj["income"] = coerced

    # --- fixed_costs: accept dict OR list ---
    fc = obj["fixed_costs"]
    if fc is None:
        obj["fixed_costs"] = []
    elif isinstance(fc, dict):
        normalised = []
        for name, amount in fc.items():
            coerced = _coerce_amount(amount)
            if coerced is None:
                problems.append(f"fixed cost '{name}' has non-numeric amount {amount!r}")
            else:
                normalised.append({"name": str(name).strip().lower(), "amount": coerced})
        obj["fixed_costs"] = normalised
    elif isinstance(fc, list):
        normalised = []
        for item in fc:
            if not isinstance(item, dict) or "name" not in item or "amount" not in item:
                problems.append(f"bad fixed cost entry: {item!r}")
                continue
            coerced = _coerce_amount(item["amount"])
            if coerced is None:
                problems.append(f"fixed cost '{item['name']}' has bad amount {item['amount']!r}")
                continue
            normalised.append({"name": str(item["name"]).strip().lower(), "amount": coerced})
        obj["fixed_costs"] = normalised
    else:
        problems.append("fixed_costs must be a list, dict or null")

    # --- priorities ---
    pr = obj["priorities"]
    if pr is None:
        obj["priorities"] = []
    elif not isinstance(pr, list):
        problems.append("priorities must be a list of names")
    else:
        obj["priorities"] = [str(p).strip().lower() for p in pr if isinstance(p, str)]

    # --- savings_goal: accept {"amount","months"} OR a bare number ---
    sg = obj["savings_goal"]
    if sg is None:
        pass
    elif isinstance(sg, dict):
        amount = _coerce_amount(sg.get("amount"))
        if amount is None:
            problems.append("savings_goal.amount must be a non-negative number")
        else:
            months = sg.get("months")
            if months is None:
                months = 1
            elif not isinstance(months, int) or isinstance(months, bool) or months < 1:
                problems.append("savings_goal.months must be an integer >= 1")
                months = None
            if months is not None:
                obj["savings_goal"] = {"amount": amount, "months": months}
    elif isinstance(sg, (int, float)) and not isinstance(sg, bool):
        coerced = _coerce_amount(sg)
        if coerced is None:
            problems.append("savings_goal number must be >= 0")
        else:
            obj["savings_goal"] = {"amount": coerced, "months": 1}
    else:
        problems.append("savings_goal must be null, a number, or {amount, months}")

    # --- change_request ---
    ch = obj["change_request"]
    if ch is not None:
        if not isinstance(ch, dict):
            problems.append("change_request must be null or a dict")
        else:
            cat = str(ch.get("category", "")).strip().lower()
            action = ch.get("action")
            amount = _coerce_amount(ch.get("amount"))
            if cat not in CHANGE_CATEGORIES:
                problems.append(f"change_request.category '{cat}' not allowed")
            if action not in ("increase", "decrease"):
                problems.append("change_request.action must be 'increase' or 'decrease'")
            if amount is None or amount <= 0:
                problems.append("change_request.amount must be > 0")
            if not problems:
                obj["change_request"] = {"category": cat, "action": action, "amount": amount}

    return problems


# ------------------------------------------------------------------ explanations

def numbers_in(text):
    """All numbers in a text as floats ('₹1,000' -> 1000.0)."""
    return {float(x.replace(",", "")) for x in _NUMBER.findall(text)}


def invented_numbers(text, payload):
    """Numbers in `text` that are not in `payload` (payload = dict or its JSON text)."""
    source = payload if isinstance(payload, str) else json.dumps(payload)
    return sorted(numbers_in(text) - numbers_in(source))


def has_tags(text):
    return bool(_TAG.search(text))


def check_explanation(text, payload, max_chars=1200):
    """Problems with a model explanation (empty list = safe to show).

    NOTE: tag check is now a *warning*, not a hard failure — we still accept explanations
    without tags (template fallback is available), but we report it so the pipeline can
    try once more before giving up.
    """
    problems = []
    if not text or len(text.strip()) < 15:
        return ["explanation is empty"]
    bad = invented_numbers(text, payload)
    if bad:
        problems.append(f"invented numbers: {bad}")
    if not has_tags(text):
        problems.append("missing [CERTAIN]/[ESTIMATE] tags")
    if len(text) > max_chars:
        problems.append("explanation is too long")
    return problems


def split_tagged(text):
    """Split an explanation into [{"text", "label", "reason"}] for the confidence display.

    label is "certain", "estimate" or None (no tag). The tag itself is removed from the text.
    """
    out, pos = [], 0
    for m in _TAG.finditer(text):
        sentence = text[pos:m.start()].strip(" .")
        # a tag can follow several sentences; keep them together as one segment
        if sentence:
            out.append({"text": sentence + ".", "label": m.group(1).lower(),
                        "reason": (m.group(2) or "").strip() or None})
        pos = m.end()
    rest = text[pos:].strip(" .")
    if rest:
        out.append({"text": rest + ".", "label": None, "reason": None})
    return out