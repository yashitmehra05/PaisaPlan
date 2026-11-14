# Baseline: untouched Llama 3.2 3B (Ollama)

Valid JSON = the whole response is pure, parseable JSON (no extra text or code fences).
Numbers correct = the values in the answer match the user's message.

| # | Message | Valid JSON | Numbers correct |
|---|---------|-----------|-----------------|
| 1 | I get 30k a month, rent 9000, save 5k | no | yes |
| 2 | Salary 25000, hostel 8000, save 10000 in 4 months | no | yes |
| 3 | Income thirty thousand, rent 10000, fees 4000 | yes | yes |
| 4 | Mera salary 40k hai, rent 12k, savings 8k | no | yes |
| 5 | What if I cut eating out by 1000? | no | yes |
| 6 | Income 20000, rent 7000, education 2500, save 4000 in 2 months | no | no |
| 7 | I earn 50000, rent 15000, save 20000 in 5 months | no | yes |
| 8 | Reduce my transport spending by 500 | no | no |
| 9 | income 18k, rnt 6000, fees 2k, save 3k | no | no |
| 10 | Add 2000 more to entertainment | no | no |

**Summary:** 1/10 pure valid JSON, 6/10 numbers correct.

**Common failures:**
- Wraps the JSON in sentences and code fences, even when told "JSON only" (9 of 10).
- Key names do not follow our schema (monthly_salary, collegeFees, fixed_costs as a single number).
- Handles "k" and Hinglish amounts correctly for fresh budgets.
- What-if messages (#5, #8, #10): never gives a single change_request, and invents extra categories and amounts.
- #6 puts an arithmetic expression inside the JSON. #9 writes a Python script instead of JSON.
- Uses "$" instead of "₹".

**Takeaway for fine-tuning:** the model understands the numbers but not the output format, so training should teach pure JSON only, the exact schema keys, and the change_request format.
