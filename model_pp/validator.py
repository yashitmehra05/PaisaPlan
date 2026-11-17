"""Safety checks on what the language model says. The model may EXPLAIN; it may never INVENT.

  * parse_json_reply     - pull a JSON object out of a model reply
  * check_extraction     - is the extracted JSON in the agreed shape?
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


def check_extraction(obj):
    """Problems with the SHAPE of an extraction (empty list = fine)."""
    if not isinstance(obj, dict):
        return ["reply is not a JSON object"]
    problems = []
    if set(obj) != set(KEYS):
        problems.append(f"keys must be exactly {KEYS}")
        return problems
    if obj["income"] is not None and not _num(obj["income"]):
        problems.append("income must be a number or null")
    if not isinstance(obj["fixed_costs"], list):
        problems.append("fixed_costs must be a list")
    else:
        for item in obj["fixed_costs"]:
            if not (isinstance(item, dict) and isinstance(item.get("name"), str) and _num(item.get("amount"))):
                problems.append(f"bad fixed cost {item}")
    if not (isinstance(obj["priorities"], list) and all(isinstance(p, str) for p in obj["priorities"])):
        problems.append("priorities must be a list of names")
    goal = obj["savings_goal"]
    if goal is not None and not (isinstance(goal, dict) and _num(goal.get("amount"))
                                 and isinstance(goal.get("months"), int) and goal["months"] >= 1):
        problems.append("savings_goal must be null or {amount, months>=1}")
    ch = obj["change_request"]
    if ch is not None and not (isinstance(ch, dict) and ch.get("category") in CHANGE_CATEGORIES
                               and ch.get("action") in ("increase", "decrease") and _num(ch.get("amount"))):
        problems.append("bad change_request")
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
    """Problems with a model explanation (empty list = safe to show)."""
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
