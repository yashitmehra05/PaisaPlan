# Language Model Pipeline, Safety and Evaluation

*(Report section by Person 4. Code: `llm/`. Test data: `data/test_extract.jsonl`. Anything in [square brackets] must be filled in or checked before submitting.)*

## 1. What the language model does, and what it must never do

PaisaPlan uses a small pre-trained language model (Llama 3.2 3B Instruct) for two jobs only:

1. **Read** a messy message ("30k salary, rent 9000, save 5k") and turn it into structured JSON.
2. **Explain** a result from the constraint solver in friendly language.

The model never calculates. Every rupee amount comes from the CSP solver (and the local search that improves its answer), so a budget is always valid and the arithmetic is always right. This is a deliberate design choice: language models are good with words but unreliable with exact numbers, which matters a lot when the topic is money.

## 2. How the model was adapted (fine-tuning summary)

*(Details are in Person 3's section; the figures below are from the training notebook's own output. [Update them if the model was retrained.])*

| Item | Value |
|---|---|
| Base model | Llama 3.2 3B Instruct, 4-bit (Unsloth) |
| Method | LoRA, r = 16, on attention and MLP layers |
| Trainable parameters | 24,313,856 of 3,237,063,680 (0.75%) |
| Training data | 612 examples (extraction and explanation), 68 for validation |
| Training | 2 epochs, 154 steps, about 8 minutes on a free Colab T4 GPU |
| Final result | training loss averaged 0.09; validation loss fell to about 0.007 |
| Deployment | exported to GGUF (Q4_K_M, about 2 GB) and run locally with Ollama |

Running locally means a user's salary and spending never leave their own machine, which is a real privacy advantage for financial data.

**An honest note on the validation loss.** A loss near zero means the model learned the *training-style* messages very well. The validation set was produced by the same templates as the training set, so it says little about how the model copes with messages written differently. That is why we built a separate, hand-written test set (section 4).

## 3. Safety design: the model explains, the solver decides

Every reply goes through the pipeline in `llm/pipeline.py`:

1. The model extracts JSON. If the JSON is invalid it is asked once more, then the user is asked to rephrase.
2. If the **income is missing, the system asks for it** instead of guessing.
3. The JSON goes to the solver (`normalise`, then `solve`/`optimise`, or `apply_what_if`).
4. The solver result is converted to the JSON format the model was trained on (`llm/payloads.py`).
5. The model writes the explanation. **A validator then checks it** (`llm/validator.py`):
   - every number must appear in the solver data (it understands formats such as ₹1,000);
   - the text must carry `[CERTAIN]` or `[ESTIMATE: reason]` confidence tags;
   - it must not be empty or too long.
6. If a check fails, the model gets one more attempt. If it fails again, the user sees a **plain template explanation** built directly from the solver numbers (`llm/templates.py`), so a wrong or invented figure is never shown.
7. If the model is not running at all, extraction reports an error, but budgets entered through the form still work with template explanations.

**What the model explains and what a template explains.** The model is used only for the cases it was trained on: a new budget, a what-if on a flexible category, and a budget that fails because the savings goal is too high. Other situations (rent or income changes, other kinds of impossible budgets, a change that needs more than the user is saving) use a template. This avoids asking the model to talk about things it has never seen.

**What-if rule.** For a flexible category (food, transport, entertainment, other), extra spending comes out of savings and money cut from it goes into savings, with every other category unchanged. This matches how the model was trained and gives a direct answer to "what happens to my savings goal if I cut eating out by ₹1,000?" Savings goal time is shown as the goal divided by monthly savings, rounded up to whole months.

**Confidence display.** The tags are parsed into segments (`certain`, `estimate`, or untagged) so the interface can show which statements are guaranteed by the solver (fixed costs, the budget itself) and which depend on assumptions (how long a goal takes if income and spending stay the same).

## 4. Evaluation design

**Why a separate test set.** The training and validation data are template-generated. We therefore wrote a *held-out test set by hand* (`data/test_extract.jsonl`, 58 messages) without looking at the training data, and checked that none of its messages appears in the training file.

| Type | Count | What it tests |
|---|---|---|
| Budgets | 30 | different formats (30k, 1.2 lakh, "thirty thousand", ₹45,000, Hinglish, typos, capitals), priorities, savings goals with and without months |
| What-if | 16 | cutting or adding money to a category, with different wording |
| Missing information | 8 | the model must return `null` and **must not invent an income** |
| Tricky | 4 | other people's salaries, old vs new figures, which must be ignored |

For explanations we use 36 cases built from the **real solver** (`llm/test_cases.py`): budgets, what-ifs and impossible budgets across 8 different user profiles.

**Metrics.**
- *Extraction:* valid JSON; income, fixed costs, priorities, savings goal and what-if each correct; **all fields correct**; and "invents income" (how often the model makes up an income when the message gives none).
- *Explanation:* no invented numbers; confidence tags present; and share of the key figures that the explanation actually mentions.

**Setups compared** (same test set, same Ollama settings, temperature 0):
1. `base_simple`: the untouched Llama 3.2 3B with a one-line instruction.
2. `base_fewshot`: the untouched model with detailed instructions and four worked examples (a fair "good prompt" baseline).
3. `finetuned`: our fine-tuned model with the prompt used in training.

Command: `python -m llm.evaluate --run base_simple,llama3.2:3b,simple --run base_fewshot,llama3.2:3b,fewshot --run finetuned,paisaplan,trained`

## 5. Results

[PASTE the table from `benchmarks/llm_eval.md` here.]

[Then write 3 to 5 sentences answering: Did fine-tuning beat the well-prompted base model? On which metrics? Did the fine-tuned model still invent incomes when none was given? How often did the validator catch an explanation? Report the numbers as they are, even if the prompted base model did as well or better. That would be a valid finding: "prompting was enough for this task".]

**Failure analysis.** [Open `benchmarks/llm_eval_details_finetuned.jsonl`, pick 5 answers marked wrong, and for each write the message, what the model said, and why it probably failed (for example a Hinglish phrase it had not seen, or a number ignored.)]

## 6. Limitations

- The training data is synthetic (templates), so unusual phrasing can still fail. The held-out test set measures this directly.
- The training data contains no examples with a missing income, so the model may guess one. The pipeline therefore refuses to continue without an income, and the test set measures how often the model invents one.
- In the training data, 48 fixed-cost labels use food, transport, entertainment or other as the name (for example "food 6000"). The solver then treats that category as fixed and does not optimise it.
- The data has what-if examples only for the four flexible categories; other changes use templates.
- "savings" appears in many training priority lists; the solver ignores it because the savings goal is already a hard requirement.
- The test set is small (58 messages), so a difference of one or two messages is not meaningful.

## 7. Responsible AI summary

- **No invented numbers:** the solver produces all amounts, and a validator rejects any explanation containing a number the solver did not give.
- **Honest uncertainty:** guaranteed facts and assumption-based projections are labelled differently.
- **Ask, don't guess:** missing information leads to a question, not a made-up value.
- **Fails safe:** when the model is unavailable or unreliable, deterministic templates take over.
- **Privacy:** the model runs locally, so financial data stays on the user's device.

## References

[Verify the details before submitting.]

- E. J. Hu et al., "LoRA: Low-Rank Adaptation of Large Language Models", 2021.
- Meta AI, Llama 3.2 model card.
- Unsloth documentation for fine-tuning and exporting to Ollama.
