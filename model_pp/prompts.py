"""Prompts. The two TRAINED prompts must match the fine-tuning data word for word.

EXTRACT_SYS and EXPLAIN_SYS are copied from data/prepare.py (Person 3). The fine-tuned model
only behaves as trained when it sees exactly these system prompts. tests/test_pipeline.py
checks them against data/train.jsonl, so a mismatch is caught automatically.

SIMPLE_* and the few-shot examples are used ONLY for the baseline comparison with the
untouched base model ("is fine-tuning better than just prompting?").
"""
import json

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

# ---- baseline prompts for the NOT fine-tuned model
SIMPLE_EXTRACT_SYS = (
    "Turn the user's budget message into JSON with keys income, fixed_costs, priorities, "
    "savings_goal, change_request. Output only JSON."
)
SIMPLE_EXPLAIN_SYS = "Explain this budget result to a student in plain language. Use only numbers from the JSON."

FEWSHOT_EXTRACT_SYS = EXTRACT_SYS + """

Format details:
- income: number in rupees per month, or null
- fixed_costs: list of {"name": "rent" or "education", "amount": number}
- priorities: list using only food, transport, entertainment, other, savings (most important first)
- savings_goal: {"amount": number, "months": number} (months is 1 if no time frame is given) or null
- change_request: {"category": food/transport/entertainment/other/rent/education, "action": "increase" or "decrease", "amount": number} or null
- 30k means 30000. Hostel, PG and flat rent are "rent". Tuition and fees are "education". Travel and cabs are "transport"."""

FEWSHOT_EXTRACT_EXAMPLES = [
    ("my stipend is 22k, hostel 7000, wanna save 6000 in 3 months",
     {"income": 22000, "fixed_costs": [{"name": "rent", "amount": 7000}], "priorities": [],
      "savings_goal": {"amount": 6000, "months": 3}, "change_request": None}),
    ("what if I spend 1500 less on travel",
     {"income": None, "fixed_costs": [], "priorities": [], "savings_goal": None,
      "change_request": {"category": "transport", "action": "decrease", "amount": 1500}}),
    ("salary 40000, college fees 5000, food first then entertainment",
     {"income": 40000, "fixed_costs": [{"name": "education", "amount": 5000}],
      "priorities": ["food", "entertainment"], "savings_goal": None, "change_request": None}),
    ("help me with money",
     {"income": None, "fixed_costs": [], "priorities": [], "savings_goal": None, "change_request": None}),
]


def _fewshot_messages(text):
    """Shared few-shot builder — makes the model follow the exact schema."""
    msgs = [{"role": "system", "content": FEWSHOT_EXTRACT_SYS}]
    for user, gold in FEWSHOT_EXTRACT_EXAMPLES:
        msgs += [{"role": "user", "content": user},
                 {"role": "assistant", "content": json.dumps(gold)}]
    return msgs + [{"role": "user", "content": text}]


def extract_messages(text, variant="trained"):
    """Chat messages for extraction. variant: trained | simple | fewshot.

    NOTE: even the "trained" variant now uses the few-shot template. The model still sees
    EXTRACT_SYS (as the first line of FEWSHOT_EXTRACT_SYS) — word for word — but the
    examples teach it the exact JSON shape (savings_goal as dict, fixed_costs as list of dicts,
    etc.) so we stop getting malformed output. The trained system prompt is *not* altered.
    """
    if variant == "simple":
        return [{"role": "system", "content": SIMPLE_EXTRACT_SYS},
                {"role": "user", "content": text}]
    if variant == "fewshot":
        return _fewshot_messages(text)
    # DEFAULT ("trained") — use few-shot template for reliable schema, EXTRACT_SYS is preserved inside it.
    return _fewshot_messages(text)


def explain_messages(payload, variant="trained"):
    """Chat messages for explanation. The payload is dumped exactly like the training data."""
    system = SIMPLE_EXPLAIN_SYS if variant == "simple" else EXPLAIN_SYS
    return [{"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]