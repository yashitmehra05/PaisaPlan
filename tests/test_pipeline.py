"""Tests for the LLM pipeline, validator, what-if logic, test set and evaluation (no real model needed)."""
import json
import os

import pytest

from model_pp import payloads, prompts, templates
from model_pp.evaluate import compare, evaluate, load_test, markdown_table
from model_pp.ollama_client import make_chat
from model_pp.pipeline import Pipeline
from model_pp.test_cases import explain_cases
from model_pp.validator import (check_explanation, check_extraction, has_tags, invented_numbers,
                           numbers_in, parse_json_reply, split_tagged)
from model_pp.whatif import apply_what_if
from solver import normalise, solve

HERE = os.path.dirname(os.path.abspath(__file__))
TRAIN = os.path.join(os.path.dirname(HERE), "data", "train.jsonl")

SCHEMA = {"income": 30000,
          "fixed_costs": [{"name": "rent", "amount": 9000}, {"name": "education", "amount": 3000}],
          "priorities": ["food", "transport"], "savings_goal": {"amount": 20000, "months": 4},
          "change_request": None}


def problem():
    return normalise(SCHEMA)


class FakeModel:
    """Stand-in for Ollama: answers extraction with `extraction`, explanations with `explain(payload)`."""

    def __init__(self, extraction=None, explain=None, fail=False):
        self.extraction = extraction if extraction is not None else SCHEMA
        self.explain = explain
        self.fail = fail
        self.extract_calls = self.explain_calls = 0
        self.extraction_replies = None

    def __call__(self, messages):
        if self.fail:
            raise RuntimeError("Ollama is down")
        if "input parser" in messages[0]["content"]:
            self.extract_calls += 1
            if self.extraction_replies:
                return self.extraction_replies.pop(0)
            return json.dumps(self.extraction)
        self.explain_calls += 1
        payload = json.loads(messages[-1]["content"])
        return self.explain(payload) if self.explain else "Everything is as the solver says [CERTAIN]."


# ---------------------------------------------------------------- prompts & formats

@pytest.mark.skipif(not os.path.exists(TRAIN), reason="data/train.jsonl not in this checkout")
def test_prompts_match_the_training_data_exactly():
    systems = {}
    with open(TRAIN, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            systems[row["task"]] = row["messages"][0]["content"]
    assert systems["extract"] == prompts.EXTRACT_SYS
    assert systems["explain"] == prompts.EXPLAIN_SYS


@pytest.mark.skipif(not os.path.exists(TRAIN), reason="data/train.jsonl not in this checkout")
def test_payload_keys_and_format_match_the_training_data():
    seen = {}
    with open(TRAIN, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row["task"] == "explain":
                user = row["messages"][1]["content"]
                kind = "what_if" if '"change"' in user else "infeasible" if "fixed_total" in user else "budget"
                seen.setdefault(kind, user)
    p = problem()
    result = solve(p)
    w = apply_what_if(p, {"category": "food", "action": "decrease", "amount": 1000})
    bad = dict(p, savings_goal=40000)
    ours = {"budget": payloads.budget_payload(p, result),
            "what_if": payloads.what_if_payload(p, {"category": "food", "action": "decrease", "amount": 1000},
                                                w["old"], w["new"]),
            "infeasible": payloads.infeasible_payload(bad, solve(bad))}
    for kind, text in seen.items():
        assert list(json.loads(text)) == list(ours[kind]), kind
        assert ", " in json.dumps(ours[kind]) and ": " in json.dumps(ours[kind])  # same separators


def test_months_round_up():
    assert payloads.months(20000, 6000) == 4
    assert payloads.months(None, 5000) is None and payloads.months(20000, 0) is None


def test_budget_payload_lists_fixed_then_flexible_then_savings():
    p = problem()
    pl = payloads.budget_payload(p, solve(p))
    assert list(pl["allocation"]) == ["rent", "education", "food", "transport", "entertainment", "other", "savings"]
    assert pl["savings_goal_total"] == 20000 and pl["months_to_goal"] == 4


def test_budget_payload_without_a_savings_goal():
    p = normalise({"income": 20000, "fixed_costs": [{"name": "rent", "amount": 6000}]})
    pl = payloads.budget_payload(p, solve(p))
    assert pl["savings_goal_total"] is None and pl["months_to_goal"] is None


def test_infeasible_payload_only_for_the_savings_case():
    too_much_saving = normalise({**SCHEMA, "savings_goal": {"amount": 40000, "months": 1}})
    pl = payloads.infeasible_payload(too_much_saving, solve(too_much_saving))
    assert pl["shortfall"] == pl["total_needed"] - pl["income"]
    assert pl["suggested_savings_goal"] == pl["savings_goal_monthly"] - pl["shortfall"]
    rent_too_big = normalise({"income": 5000, "fixed_costs": [{"name": "rent", "amount": 9000}]})
    assert payloads.infeasible_payload(rent_too_big, solve(rent_too_big)) is None


# ------------------------------------------------------------------------ validator

def test_numbers_understand_commas():
    assert numbers_in("₹1,000 and ₹21,500 and 0.8 months and 5000") == {1000.0, 21500.0, 0.8, 5000.0}


def test_invented_numbers_are_caught():
    payload = {"savings": 5000, "months": 4}
    assert invented_numbers("You save ₹5,000 for 4 months.", payload) == []
    assert invented_numbers("You save ₹5,500 for 4 months.", payload) == [5500.0]


def test_check_explanation_flags_each_problem():
    payload = {"a": 100}
    assert check_explanation("It is ₹100 [CERTAIN] as the solver says.", payload) == []
    assert any("invented" in p for p in check_explanation("It is ₹200 [CERTAIN] as the solver says.", payload))
    assert any("tags" in p for p in check_explanation("It is ₹100 as the solver says, fine.", payload))
    assert check_explanation("", payload)
    assert has_tags("ok [ESTIMATE: spending stays stable]")


def test_split_tagged_labels_sentences():
    segs = split_tagged("Rent ₹9,000 is fixed [CERTAIN]. You reach it in 3 months [ESTIMATE: spending stays stable]. Nice.")
    assert [s["label"] for s in segs] == ["certain", "estimate", None]
    assert segs[1]["reason"] == "spending stays stable" and "[" not in segs[0]["text"]


def test_parse_json_reply_is_forgiving():
    assert parse_json_reply('```json\n{"a": 1}\n```')[0] == {"a": 1}
    assert parse_json_reply('Sure! {"a": 1} hope that helps')[0] == {"a": 1}
    assert parse_json_reply("no json here")[0] is None and parse_json_reply("{bad json}")[0] is None


def test_check_extraction_shape():
    assert check_extraction(SCHEMA) == []
    assert check_extraction({"income": 1})
    assert check_extraction({**SCHEMA, "income": "30000"})
    assert check_extraction({**SCHEMA, "savings_goal": {"amount": 5, "months": 0}})
    assert check_extraction({**SCHEMA, "change_request": {"category": "yacht", "action": "increase", "amount": 5}})


# ------------------------------------------------------------------------ what-if

def change(cat, action, amount):
    return {"category": cat, "action": action, "amount": amount}


def test_cutting_a_category_moves_the_money_to_savings():
    w = apply_what_if(problem(), change("food", "decrease", 1000))
    assert w["mode"] == "savings_absorbs" and w["new"]["status"] == "ok"
    assert w["new"]["allocation"]["food"] == w["old"]["allocation"]["food"] - 1000
    assert w["new"]["allocation"]["savings"] == w["old"]["allocation"]["savings"] + 1000
    for name in ("transport", "entertainment", "other"):
        assert w["new"]["allocation"][name] == w["old"]["allocation"][name]


def test_spending_more_takes_the_money_from_savings():
    w = apply_what_if(problem(), change("food", "increase", 2000))
    assert w["new"]["allocation"]["food"] == w["old"]["allocation"]["food"] + 2000
    assert w["new"]["allocation"]["savings"] == w["old"]["allocation"]["savings"] - 2000


def test_spending_more_than_the_savings_is_refused_with_numbers():
    w = apply_what_if(problem(), change("food", "increase", 9000))
    assert w["new"]["status"] == "infeasible"
    assert w["new"]["unmet"][0]["short_by"] == 4000  # 9000 needed, 5000 saved


def test_a_cut_that_breaks_a_rule_is_refused():
    w = apply_what_if(problem(), change("food", "decrease", 7000))  # food 1000 < entertainment 2000
    assert w["new"]["status"] == "infeasible"
    assert "entertainment" in w["new"]["unmet"][0]["constraint"]


def test_cutting_more_than_the_category_has_stops_at_zero():
    w = apply_what_if(problem(), change("other", "decrease", 500))
    assert w["new"]["allocation"]["other"] == 0 and w["new"]["allocation"]["savings"] == 5000


def test_other_changes_use_the_general_solver():
    assert apply_what_if(problem(), change("rent", "increase", 1000))["mode"] == "generic"
    assert apply_what_if(problem(), change("income", "decrease", 3000))["mode"] == "generic"


def test_bad_changes_raise():
    with pytest.raises(ValueError):
        apply_what_if(problem(), change("food", "shrink", 100))
    with pytest.raises(ValueError):
        apply_what_if(problem(), change("pets", "increase", 100))


# ------------------------------------------------------------------------ templates

def test_templates_only_use_solver_numbers_and_always_have_tags():
    p = problem()
    r = solve(p)
    pl = payloads.budget_payload(p, r)
    text = templates.budget_text(p, r, pl)
    assert check_explanation(text, pl) == []
    for ch in (change("food", "decrease", 1000), change("food", "increase", 2000)):
        w = apply_what_if(p, ch)
        wp = payloads.what_if_payload(p, ch, w["old"], w["new"])
        assert check_explanation(templates.what_if_text(p, ch, w["old"], w["new"]), wp) == []
    bad = normalise({**SCHEMA, "savings_goal": {"amount": 40000, "months": 1}})
    ip = payloads.infeasible_payload(bad, solve(bad))
    assert check_explanation(templates.infeasible_text(solve(bad)["unmet"]), ip) == []


# ------------------------------------------------------------------------ pipeline

def test_full_plan_with_a_good_model():
    model = FakeModel(explain=lambda p: f"Your income is ₹{p['income']:,} [CERTAIN]. Savings are ₹{p['allocation']['savings']:,} [CERTAIN].")
    reply = Pipeline(model).handle("anything")
    assert reply["status"] == "ok" and reply["explanation"]["source"] == "model"
    assert reply["problem"]["income"] == 30000 and reply["result"]["status"] == "ok"
    assert [s["label"] for s in reply["explanation"]["segments"]] == ["certain", "certain"]


def test_a_model_that_invents_a_number_is_replaced_by_the_template():
    model = FakeModel(explain=lambda p: "Great news, you will save ₹99,999 [CERTAIN].")
    reply = Pipeline(model).handle("anything")
    assert reply["explanation"]["source"] == "template"
    assert "invented numbers" in reply["explanation"]["problems"][0]
    assert "99,999" not in reply["message"]
    assert model.explain_calls == 2  # first try + one retry


def test_a_model_without_tags_is_replaced_by_the_template():
    model = FakeModel(explain=lambda p: "Everything looks fine, enjoy your budget everyone.")
    assert Pipeline(model).handle("x")["explanation"]["source"] == "template"


def test_missing_income_asks_instead_of_guessing():
    model = FakeModel(extraction={**SCHEMA, "income": None})
    reply = Pipeline(model).handle("I want to save 5000")
    assert reply["status"] == "needs_input" and "income" in reply["message"].lower()
    assert reply["result"] is None and model.explain_calls == 0


def test_what_if_without_a_budget_asks_for_one_first():
    model = FakeModel(extraction={"income": None, "fixed_costs": [], "priorities": [], "savings_goal": None,
                                  "change_request": change("food", "decrease", 1000)})
    reply = Pipeline(model).handle("what if I cut food by 1000?", problem=None)
    assert reply["status"] == "needs_input"


def test_what_if_with_a_budget_uses_the_model_explanation():
    what_if = {"income": None, "fixed_costs": [], "priorities": [], "savings_goal": None,
               "change_request": change("food", "decrease", 1000)}
    model = FakeModel(extraction=what_if, explain=lambda p: (
        f"Food goes from ₹{p['category_old']:,} to ₹{p['category_new']:,} [CERTAIN]. "
        f"Savings go from ₹{p['savings_old']:,} to ₹{p['savings_new']:,} [CERTAIN]."))
    reply = Pipeline(model).handle("cut food by 1000", problem=problem())
    assert reply["status"] == "ok" and reply["explanation"]["source"] == "model"
    assert reply["old"]["allocation"]["food"] - reply["result"]["allocation"]["food"] == 1000


def test_what_if_outside_the_training_data_uses_the_template():
    what_if = {"income": None, "fixed_costs": [], "priorities": [], "savings_goal": None,
               "change_request": change("rent", "increase", 1000)}
    model = FakeModel(extraction=what_if)
    reply = Pipeline(model).handle("rent up by 1000", problem=problem())
    assert reply["explanation"]["source"] == "template" and model.explain_calls == 0
    assert "rent goes from ₹9,000 to ₹10,000" in reply["message"]


def test_infeasible_savings_goal_is_explained_by_the_model():
    data = {**SCHEMA, "savings_goal": {"amount": 40000, "months": 1}}
    model = FakeModel(extraction=data, explain=lambda p: f"You are ₹{p['shortfall']:,} short [CERTAIN]. Try saving ₹{p['suggested_savings_goal']:,} [CERTAIN].")
    reply = Pipeline(model).handle("x")
    assert reply["status"] == "infeasible" and reply["explanation"]["source"] == "model"


def test_other_infeasible_cases_never_call_the_model_for_the_explanation():
    data = {"income": 5000, "fixed_costs": [{"name": "rent", "amount": 9000}], "priorities": [],
            "savings_goal": None, "change_request": None}
    model = FakeModel(extraction=data)
    reply = Pipeline(model).handle("x")
    assert reply["status"] == "infeasible" and reply["explanation"]["source"] == "template"
    assert model.explain_calls == 0 and "4000" in reply["message"]


def test_invalid_json_is_retried_once():
    model = FakeModel()
    model.extraction_replies = ["Sure, here you go: not json", json.dumps(SCHEMA)]
    reply = Pipeline(model).handle("x")
    assert reply["status"] == "ok" and reply["extraction"]["attempts"] == 2


def test_hopeless_json_asks_the_user_to_rephrase():
    model = FakeModel()
    model.extraction_replies = ["nope", "still nope"]
    reply = Pipeline(model).handle("x")
    assert reply["status"] == "needs_input" and reply["extraction"]["attempts"] == 2


def test_model_down_gives_an_error_but_the_form_path_still_works():
    pipe = Pipeline(FakeModel(fail=True))
    assert pipe.handle("x")["status"] == "error"
    reply = pipe.plan(SCHEMA)  # structured data from the UI form, no extraction needed
    assert reply["status"] == "ok" and reply["explanation"]["source"] == "template"


def test_bad_numbers_from_the_model_ask_for_clarification():
    model = FakeModel(extraction={**SCHEMA, "income": -5})
    assert Pipeline(model).handle("x")["status"] == "needs_input"


def test_pipeline_works_without_the_optimiser():
    reply = Pipeline(FakeModel(), use_optimiser=False).handle("x")
    assert reply["status"] == "ok"


def test_unreachable_ollama_gives_a_helpful_error():
    chat = make_chat("paisaplan", host="http://127.0.0.1:9", timeout=2)
    with pytest.raises(RuntimeError, match="Ollama"):
        chat([{"role": "user", "content": "hi"}])


# -------------------------------------------------------------- test set & evaluation

def test_the_test_set_is_valid_and_independent():
    rows = load_test()
    assert len(rows) >= 55
    assert {r["type"] for r in rows} == {"budget", "what_if", "missing", "tricky"}
    assert len({r["input"] for r in rows}) == len(rows)
    for r in rows:
        assert check_extraction(r["gold"]) == [], r["input"]
        if r["gold"]["income"] is not None:
            assert normalise(r["gold"])["income"] == r["gold"]["income"]
    if os.path.exists(TRAIN):
        with open(TRAIN, encoding="utf-8") as f:
            train = {json.loads(l)["messages"][1]["content"].strip().lower() for l in f}
        assert not [r for r in rows if r["input"].strip().lower() in train]


def test_explain_cases_come_from_the_real_solver():
    cases = explain_cases()
    assert len(cases) >= 30 and {c["kind"] for c in cases} == {"budget", "what_if", "infeasible"}
    for c in cases:
        assert c["required"]


def test_compare_checks_every_field():
    gold = {"income": 30000, "fixed_costs": [{"name": "rent", "amount": 9000}], "priorities": ["food"],
            "savings_goal": {"amount": 5000, "months": 1}, "change_request": None}
    assert compare(gold, gold)["exact"]
    assert not compare({**gold, "income": 3000}, gold)["income_ok"]
    assert not compare({**gold, "priorities": []}, gold)["priorities_ok"]
    assert not compare({**gold, "savings_goal": {"amount": 5000, "months": 2}}, gold)["savings_ok"]
    assert not compare(None, gold)["exact"]


def _chat_factory(kind):
    gold = {r["input"]: r["gold"] for r in load_test()}

    def factory(model):
        def chat(messages):
            if "input parser" in messages[0]["content"] or "JSON with keys income" in messages[0]["content"]:
                text = messages[-1]["content"]
                if kind == "perfect":
                    return json.dumps(gold[text])
                if kind == "inventor":  # always invents an income
                    return json.dumps({**gold[text], "income": gold[text]["income"] or 25000})
                return "I cannot do that"
            payload = json.loads(messages[-1]["content"])
            return "Sure [CERTAIN]." if kind == "perfect" else f"Total ₹{12345} {payload['task']}"
        return chat
    return factory


def test_evaluation_scores_a_perfect_model_at_100_percent(tmp_path):
    rows = evaluate([("perfect", "stub", "trained")], str(tmp_path), chat_factory=_chat_factory("perfect"))
    r = rows[0]
    assert r["exact"] == 100.0 and r["valid_json"] == 100.0 and r["invented_income_pct"] == 0.0
    assert r["no_invented_numbers"] == 100.0 and r["has_tags"] == 100.0
    assert (tmp_path / "llm_eval.csv").exists() and (tmp_path / "llm_eval_details_perfect.jsonl").exists()
    assert "perfect" in (tmp_path / "llm_eval.md").read_text(encoding="utf-8")


def test_evaluation_catches_a_model_that_invents_incomes(tmp_path):
    r = evaluate([("inventor", "stub", "trained")], str(tmp_path), chat_factory=_chat_factory("inventor"), explain=False)[0]
    assert r["invented_income_pct"] == 100.0 and r["exact_missing"] == 0.0 and r["exact_budget"] == 100.0


def test_evaluation_scores_garbage_at_zero(tmp_path):
    r = evaluate([("junk", "stub", "simple")], str(tmp_path), chat_factory=_chat_factory("junk"))[0]
    assert r["valid_json"] == 0.0 and r["exact"] == 0.0 and r["safe"] == 0.0


def test_markdown_table_has_one_row_per_setup(tmp_path):
    rows = evaluate([("a", "m", "trained"), ("b", "m", "simple")], str(tmp_path), chat_factory=_chat_factory("perfect"))
    assert markdown_table(rows).count("\n") == 3
