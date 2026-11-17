"""The whole chat pipeline: message -> JSON -> solver -> explanation, with safety checks."""

from solver import normalise, solve

from . import payloads, templates
from .prompts import explain_messages, extract_messages
from .validator import check_explanation, check_extraction, parse_json_reply, split_tagged
from .whatif import apply_what_if

try:  # Person 2's local search; the pipeline works without it
    from solver.optimize import optimise
except ImportError:  # pragma: no cover
    optimise = None

RETRY_NOTE = ("That was not valid. Reply with ONLY a JSON object with exactly the keys "
              "income, fixed_costs, priorities, savings_goal, change_request.")


class Pipeline:
    def __init__(self, chat, extract_chat=None, method="forward", use_optimiser=True,
                 extract_variant="trained", extract_retries=1, explain_retries=1):
        self.chat = chat
        self.extract_chat = extract_chat or chat
        self.method = method
        self.use_optimiser = use_optimiser and optimise is not None
        self.extract_variant = extract_variant
        self.extract_retries = extract_retries
        self.explain_retries = explain_retries

    # ------------------------------------------------------------ extraction
    def extract(self, text):
        """Ask the model to turn a message into the agreed JSON. Retries once on bad output."""
        messages = extract_messages(text, self.extract_variant)
        raw, problems = "", ["model not called"]
        chat_fn = getattr(self, "extract_chat", self.chat)
        for attempt in range(1, self.extract_retries + 2):
            try:
                raw = chat_fn(messages)
            except Exception as e:  # Ollama down, timeout, ...
                return {"ok": False, "data": None, "raw": "",
                        "problems": [f"model unavailable: {e}"], "attempts": attempt}
            obj, error = parse_json_reply(raw)
            problems = [error] if error else check_extraction(obj)
            if not problems:
                return {"ok": True, "data": obj, "raw": raw,
                        "problems": [], "attempts": attempt}
            messages = messages + [{"role": "assistant", "content": raw},
                                   {"role": "user", "content": RETRY_NOTE}]
        return {"ok": False, "data": None, "raw": raw, "problems": problems,
                "attempts": self.extract_retries + 1}

    # ----------------------------------------------------------- main entry
    def handle(self, text, problem=None):
        """Handle one chat message. Pass the previous reply's `problem` to allow what-ifs."""
        ex = self.extract(text)
        if not ex["ok"]:
            if any(p.startswith("model unavailable") for p in ex["problems"]):
                return self._reply("error", "The language model is not available right now. "
                                   "You can still enter your numbers in the form.", extraction=ex)
            return self._reply("needs_input", "Sorry, I couldn't read that. Could you tell me your "
                               "monthly income, your fixed costs (like rent) and how much you want "
                               "to save?", extraction=ex)
        data = ex["data"]
        has_budget_info = (data["income"] is not None or data["fixed_costs"] or data["savings_goal"])
        if data["change_request"] and not has_budget_info:
            if problem is None:
                return self._reply("needs_input", "Tell me your income, fixed costs and savings goal "
                                   "first, then I can answer what-if questions.", extraction=ex)
            return self.what_if(problem, data["change_request"], extraction=ex)
        if data["income"] is None:
            return self._reply("needs_input", "What is your monthly income? I don't want to guess it.",
                               problem=problem, extraction=ex)
        return self.plan(data, extraction=ex)

    # ----------------------------------------------------------------- plan
    def plan(self, data, extraction=None):
        """Build a budget from already-structured data (works without the language model)."""
        try:
            problem = normalise(data)
        except (ValueError, KeyError, TypeError) as e:
            return self._reply("needs_input", f"Something in those numbers doesn't look right: {e}",
                               extraction=extraction)
        result = optimise(problem, method=self.method) if self.use_optimiser else solve(problem, self.method)
        if result["status"] == "ok":
            payload = payloads.budget_payload(problem, result)
            fallback = templates.budget_text(problem, result, payload)
            explanation = self._explain(payload, fallback)
            return self._reply("ok", explanation["text"], problem=problem, result=result,
                               explanation=explanation, extraction=extraction)
        payload = payloads.infeasible_payload(problem, result)
        fallback = templates.infeasible_text(result["unmet"])
        explanation = self._explain(payload, fallback) if payload else self._template(fallback)
        return self._reply("infeasible", explanation["text"], problem=problem, result=result,
                           explanation=explanation, extraction=extraction)

    # --------------------------------------------------------------- what-if
    def what_if(self, problem, change, extraction=None):
        try:
            w = apply_what_if(problem, change, self.method)
        except ValueError as e:
            return self._reply("needs_input", f"I can't apply that change: {e}",
                               problem=problem, extraction=extraction)
        old, new = w["old"], w["new"]
        if w["mode"] == "base_infeasible":
            fallback = templates.infeasible_text(old["unmet"])
            return self._reply("infeasible", fallback, problem=problem, result=old,
                               explanation=self._template(fallback), extraction=extraction)
        fallback = templates.what_if_text(problem, change, old, new)
        if w["mode"] == "savings_absorbs" and new["status"] == "ok":
            payload = payloads.what_if_payload(problem, change, old, new)
            explanation = self._explain(payload, fallback)
        else:  # not covered by the training data -> plain template
            explanation = self._template(fallback)
        status = "ok" if new["status"] == "ok" else "infeasible"
        reply = self._reply(status, explanation["text"], problem=problem, result=new,
                            explanation=explanation, extraction=extraction)
        reply["old"] = old
        return reply

    # --------------------------------------------------------- explanations
    def _explain(self, payload, fallback_text):
        """Model explanation if it passes every check, otherwise the template."""
        problems = []
        for attempt in range(1, self.explain_retries + 2):
            try:
                text = self.chat(explain_messages(payload)).strip()
            except Exception as e:
                problems = [f"model unavailable: {e}"]
                break
            problems = check_explanation(text, payload)
            if not problems:
                return {"text": text, "source": "model", "segments": split_tagged(text),
                        "problems": [], "attempts": attempt}
        out = self._template(fallback_text)
        out["problems"] = problems
        return out

    def _template(self, text):
        return {"text": text, "source": "template", "segments": split_tagged(text),
                "problems": [], "attempts": 0}

    @staticmethod
    def _reply(status, message, problem=None, result=None, explanation=None, extraction=None):
        return {"status": status, "message": message, "problem": problem, "result": result,
                "old": None, "explanation": explanation, "extraction": extraction}