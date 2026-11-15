# Dataset and fine-tuning (data/ and llm/)

Owner: Rakshit

## What the model learns
The fine-tuned model does two jobs. The solver does all the arithmetic; the model only parses and explains.

1. **Extract**: messy user message -> JSON with the keys `income`, `fixed_costs`, `priorities`, `savings_goal`, `change_request` (see `llm/schema.json`).
2. **Explain**: solver result (JSON) -> plain-language explanation. Facts are tagged `[CERTAIN]`, projections `[ESTIMATE: reason]`, and the model must only use numbers present in the input.

## Files
| File | What it is |
|------|-----------|
| `train_extract.jsonl` | 118 hand-written extraction examples |
| `generate.py` | Template-based generator (fixed seed 7) |
| `generated_extract.jsonl` | 400 generated extraction examples |
| `generated_explain.jsonl` | 200 generated explanation examples |
| `prepare.py` | Merges, validates, de-duplicates and splits the data |
| `train.jsonl` / `val.jsonl` | Final chat-format data: 646 train, 72 validation |
| `test_budgets.csv`, `categories.md` | Small reference files |

## How the data was made
- **Synthetic, not collected from real users.** The generated examples (600 of 718) come from templates with random amounts. `generate.py` does not call an LLM.
- Messages vary in style on purpose: "k" amounts (`30k`), number words (`thirty thousand`), Hinglish (`mujhe 20 hazaar milte hain`), typos (`salry`), shuffled order, upper case, and what-if questions ("cut food by 1000").
- Explanation examples cover three cases: a normal plan, a what-if change, and an infeasible budget.
- **Faithfulness check:** every number in a generated explanation must appear in its input. Examples that fail are dropped, so the data teaches the model not to invent figures.
- `prepare.py` checks every extraction output against the schema, removes duplicates, and splits each task 90/10 with a fixed seed (42).

## Fine-tuning
- Base model: Llama 3.2 3B Instruct, 4-bit, via Unsloth on a Colab T4 GPU
- Method: LoRA (r=16, alpha=16, all attention and MLP projections)
- 2 epochs, learning rate 2e-4, batch size 2 with 4 gradient-accumulation steps
- Loss is computed on the assistant's answer only
- Notebook: `llm/finetune_paisaplan.ipynb`; loss curve: `llm/loss_curve.png`
- Exported to GGUF (Q4_K_M) for Ollama

## Limits
- Templates cover fewer phrasings than real users produce, so unusual messages may still fail.
- The test set used for the final comparison is separate and was not used in training.

## Regenerate
```
python3 data/generate.py
python3 data/prepare.py
```
