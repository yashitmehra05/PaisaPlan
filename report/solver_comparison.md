# Optimisation, Scenarios and Solver Comparison

*(Report section by Person 2. Code: `solver/optimize.py`, `solver/scenarios.py`, `benchmarks/`. All numbers below come from `python -m benchmarks.run_benchmarks` and `python -m benchmarks.optimality_check`; the raw data is in `benchmarks/*.csv`.)*

## 1. From "valid" to "best"

The CSP solver (see the CSP Formulation section) answers one question: *is there a budget that obeys every rule?* It returns the first valid budget it finds, which is correct but not necessarily good. For the example user (₹30,000 income, ₹12,000 fixed costs, ₹5,000 savings) it returns food ₹8,000, transport ₹3,000, entertainment ₹2,000 and other ₹0, which satisfies every rule but spends nothing on "other" at all.

The optimisation module improves such a budget with **local search**.

**Score.** A budget is scored as the sum over flexible categories of `weight × √(amount ÷ category maximum)`. The weight comes from the user's priority order (first priority gets the largest weight). The square root models *diminishing returns*: the first rupees spent on a category are worth more than the last ones, so money is spread across categories instead of being piled into one.

**Local search.**
1. Start from the solver's valid budget.
2. A *move* shifts one step of ₹500, either from unallocated income into a category or from one category to another.
3. Take the best move that keeps every constraint satisfied and raises the score (hill climbing). Repeat until no move helps.
4. If no single move helps, try *pairs* of moves. This matters when a rule ties two categories together (for example food ≥ transport and food ≤ transport): neither can change alone without breaking the rule, but both can change together.
5. Restart five times from randomly perturbed copies of the start and keep the best result (the random seed is fixed so results are repeatable).

On the example above, local search moves the budget to food ₹5,500, transport ₹3,000, entertainment ₹3,000 and other ₹1,500, raising the score from 8.63 to 9.18 while every rule still holds.

## 2. Scenarios

Users see three alternative budgets side by side (`solver/scenarios.py`). Each scenario changes the savings goal and the category weights, then runs the solver and local search.

| Scenario | Savings goal | Food | Transport | Entertainment | Other |
|---|---|---|---|---|---|
| Aggressive savings | ₹7,500 | ₹6,000 | ₹3,000 | ₹1,000 | ₹500 |
| Balanced (user's goal) | ₹5,000 | ₹5,500 | ₹3,000 | ₹3,000 | ₹1,500 |
| Comfortable | ₹2,500 | ₹7,500 | ₹3,000 | ₹3,000 | ₹2,000 |

*Aggressive* raises savings to the highest affordable amount (up to 1.5× the goal or 20% of income) and cuts entertainment and other. *Comfortable* saves half as much. If a scenario is impossible, the exact reason from the solver is returned instead; for instance, when the user's own savings goal is too high, the comfortable scenario can still succeed and shows the user an achievable alternative.

## 3. Benchmark design

- **Problems.** 20 random problems for each of 5 sizes (4, 6, 8, 10 and 12 flexible categories), generated from fixed seeds so anyone can reproduce them. Money is chosen so that problems range from impossible to comfortable, and random pairwise rules (`a ≤ b`, `a ≥ b`) are added, which is what makes the larger problems hard.
- **Methods.** Plain backtracking, forward checking, and forward checking with MRV.
- **Limit.** Each run is stopped after 200,000 nodes (a node is one value tried for one category). A run that hits the limit counts as "not finished".
- **Measures.** Percentage finished, median nodes, worst-case nodes among finished runs, and median time.

## 4. Results: solver comparison

| Categories | Method | Finished | Median nodes | Worst nodes | Median time (ms) |
|---|---|---|---|---|---|
| 4 | Backtracking | 100% | 60 | 1,509 | 0.008 |
| 4 | Forward checking | 100% | 4 | 13 | 0.025 |
| 4 | FC + MRV | 100% | 4 | 29 | 0.026 |
| 6 | Backtracking | 100% | 450 | 18,224 | 0.044 |
| 6 | Forward checking | 100% | 6 | 20 | 0.048 |
| 6 | FC + MRV | 100% | 6 | 13 | 0.048 |
| 8 | Backtracking | 100% | 1,401 | 141,030 | 0.127 |
| 8 | Forward checking | 100% | 8 | 1,468 | 0.085 |
| 8 | FC + MRV | 100% | 8 | 363 | 0.093 |
| 10 | Backtracking | **70%** | 16,619 | 118,409 | 1.395 |
| 10 | Forward checking | 100% | 14 | 7,867 | 0.170 |
| 10 | FC + MRV | 100% | 10 | 775 | 0.170 |
| 12 | Backtracking | **85%** | 16,916 | 95,061 | 1.577 |
| 12 | Forward checking | 100% | 12 | 40 | 0.236 |
| 12 | FC + MRV | 100% | 12 | 33 | 0.257 |

Charts: `benchmarks/charts/finished_pct.png`, `median_nodes.png`, `worst_case_nodes.png`, `median_time.png`.

**What the data shows**

1. **Plain backtracking breaks down as problems grow.** It finishes everything up to 8 categories, but at 10 and 12 categories it fails to finish 30% and 15% of problems within the node limit. Its median effort grows from 60 nodes (4 categories) to about 17,000 (10 and 12 categories). Its worst-case figures are even *understated* because runs that hit the limit are excluded from them.
2. **Forward checking removes the problem.** It finished every problem at every size, with a median of 4 to 14 nodes. Impossible budgets are usually rejected with 0 nodes, because the pruning step before the search already empties a category's options.
3. **MRV helps in the worst cases, not the typical case.** Medians for forward checking and MRV are almost identical, but the worst case drops from 1,468 to 363 nodes (8 categories) and from 7,867 to 775 nodes (10 categories). At 4 categories MRV was actually slightly worse (29 vs 13 worst-case nodes), so MRV is not better everywhere.
4. **Fewer nodes does not always mean less time on small problems.** For 4 to 6 categories plain backtracking has the lowest median time (0.008 ms vs 0.025 ms at 4 categories) because forward checking pays for pruning at every step. From 8 categories forward checking is faster, and at 10 categories it is roughly 8 times faster (0.17 ms vs 1.4 ms).
5. **All methods agree.** Across all 100 problems, no two methods that finished ever disagreed on whether a budget was solvable.

*Timings depend on the machine and vary slightly between runs; the node counts are deterministic.*

## 5. Results: local search

| Categories | Solvable problems | Improved by local search | Mean score gain | Median search time (ms) |
|---|---|---|---|---|
| 4 | 17 | 64.7% | 4.16% | 1.77 |
| 6 | 19 | 73.7% | 4.73% | 7.37 |
| 8 | 15 | 93.3% | 10.80% | 22.24 |
| 10 | 17 | 100% | 9.08% | 61.40 |
| 12 | 16 | 93.8% | 5.00% | 159.98 |

Chart: `benchmarks/charts/local_search_improvement.png`. The solver's first answer was improved in most problems, and the cost grows with the number of categories (about 0.16 seconds at 12 categories), which is still fast enough for an interactive app.

**How close is it to the best possible budget?** For small problems (4 categories) we can try every combination and find the true best score. Over 168 solvable random problems, local search found the exact optimum in **100%** of cases (`benchmarks/optimality.csv`). This was *not* true for our first version: with single-step moves only, the worst case ended 14% below the true best (and the average gap was about 0.1%), because categories tied together by rules could not move alone. Adding the two-step moves fixed this. We could only check problems of 4 categories this way (brute force is too slow beyond that), so for larger problems we know the budget is valid and improved but cannot prove it is optimal.

## 6. Limitations

- The benchmark problems are randomly generated, not real student budgets, and there are only 20 per size.
- The score function (weights and square root) is our own design choice for "a good budget"; it is not learned from user data.
- Local search is a heuristic: it is exact on the small problems we checked but comes with no guarantee on larger ones.
- Run times depend on the machine, and the 200,000-node limit is an arbitrary cut-off.

## References

[Verify the details of each reference before submitting.]

- S. Russell and P. Norvig, *Artificial Intelligence: A Modern Approach*, Pearson (chapters on local search and constraint satisfaction).
- S. Minton, M. D. Johnston, A. B. Philips and P. Laird, "Minimizing conflicts: a heuristic repair method for constraint satisfaction and scheduling problems", *Artificial Intelligence*, 58, 1992.
- R. M. Haralick and G. L. Elliott, "Increasing tree search efficiency for constraint satisfaction problems", *Artificial Intelligence*, 14(3), 1980.
