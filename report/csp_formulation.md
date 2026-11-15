# CSP Formulation and Solver

*(Report section by Person 1. Folder: `solver/`. Replace the bracketed notes before submitting.)*

## 1. Why a Constraint Satisfaction Problem?

Budgeting is a natural CSP: there is a fixed pool of money, several categories that must share it, and rules that every acceptable plan must obey. Instead of asking a language model to "guess" a budget, PaisaPlan formulates the problem formally and solves it with search. This guarantees that every number in a budget is exact and that the plan really satisfies the user's constraints. The language model is only used to understand the user's message and to explain the solver's result.

## 2. Formal definition

**Input.** Monthly income, fixed costs (e.g. rent, tuition), a monthly savings goal, an ordered list of priorities, and optional limits.

**Variables.** The flexible categories: food, transport, entertainment and other. Categories the user declares as fixed costs are removed from the variables.

**Domains.** Each variable takes an amount from its minimum to its maximum in steps of ₹500, for example food ∈ {2000, 2500, ..., 8000}. The default ranges are our own assumptions for a student budget and can be overridden per user. Values are tried largest first, so higher-priority categories receive more money.

**Hard constraints** (a plan that breaks any of these is rejected):
1. *Budget constraint:* total flexible spending ≤ income − fixed costs − savings goal.
2. *Share-of-income cap:* total flexible spending ≤ 60% of income (a configurable sanity rule).
3. *Pairwise rules:* by default entertainment ≤ food; any rule of the form `a <op> b` can be added.
4. *Bounds:* every category stays between its minimum and maximum.

The savings goal is set aside first and is treated as a requirement, not as a variable. Income that no category uses is reported as `unallocated`.

**Soft constraints.** User priorities. In this module they decide which categories are served first. Fine-grained optimisation of priorities (local search) is handled in the optimisation module [link Person 2's section].

## 3. Algorithms

All three algorithms use the same value ordering. A *node* is counted each time one value is tried for one category.

1. **Plain backtracking.** Categories are assigned in priority order. A value is accepted if it fits in the money left and respects the rules with categories already assigned. If a category has no acceptable value, the algorithm returns to the previous category and tries its next value. It only discovers a dead end when it reaches it.
2. **Backtracking with forward checking.** After each assignment the solver removes, from every unassigned category, the values that can no longer be part of any solution: values that, together with the cheapest possible choice for all other unassigned categories, exceed the remaining money, or that break a rule with an assigned category. If any category runs out of values, the solver backtracks immediately. The check runs once before the search starts, so many impossible budgets are rejected at zero cost.
3. **Forward checking with MRV.** As in 2, but the next category to assign is the one with the fewest remaining values (Minimum Remaining Values, the "fail-first" principle), with ties broken by user priority.

Methods 1 and 2 try values in the same order, so they always return the identical budget; forward checking only reaches it with fewer steps. Method 3 may return a different, equally valid budget because it picks categories in a different order. [Note: the default method used by the app is forward checking, because it keeps the user's priority order.]

### Measured behaviour on our test cases

| Case | Backtracking | Forward checking | FC + MRV |
|---|---|---|---|
| Normal budget (₹30,000, savings ₹5,000) | 10 nodes | 4 nodes | 4 nodes |
| Exactly tight (₹14,500, no savings) | 37 nodes | 4 nodes | 4 nodes |
| Impossible (₹14,000, no savings) | 19 nodes | 0 nodes | 0 nodes |

Larger benchmarks over randomly generated problems are reported in the solver comparison section [link Person 2's section].

## 4. Explaining impossible budgets

When no solution exists, the solver does not just answer "no". `explain_infeasible` works out exactly which requirement fails and by how much, and returns a suggestion built from exact numbers:

- fixed costs exceed income;
- fixed costs plus minimum spending exceed income even with zero savings;
- the savings goal is too high (and the highest affordable savings amount);
- the minimums exceed the share-of-income cap;
- a pairwise rule cannot be satisfied with the current limits.

Because every figure comes from the solver, the language model can describe the failure in plain language without calculating or inventing anything.

## 5. What-if questions

`resolve(problem, change)` solves the budget before and after one change and returns the difference.

- *Decreasing* a flexible category or a fixed cost: that amount drops, all other categories stay as they were, and the freed money goes to savings. If the problem has a savings target, the module also reports how many months sooner the target is reached.
- *Any other change* (an increase, income, or savings): the change is applied and the solver may re-balance the other flexible categories.
- If the changed budget is impossible, the result carries the explanation from section 4.

Example: cutting food by ₹1,000 from a ₹5,000 monthly saving goal raises monthly savings to ₹6,000, so a ₹5,000 target is reached in 0.8 months instead of 1.0.

## 6. Verification

- 45 unit tests cover normalisation, feasible and impossible budgets, rules, tight budgets, node limits and what-if changes.
- We also compared all three algorithms against exhaustive enumeration on 3,000 randomly generated problems (2,357 solvable). They agreed on solvability in every case, and plain backtracking and forward checking always returned the same budget.

## 7. Limitations

- Amounts are discrete (steps of ₹500), which keeps the search finite but means exact-rupee optima can be missed.
- The default category ranges and rules are assumptions for a typical student, not learned from data.
- The solver returns the first valid budget it finds; choosing the *best* one among many is the job of the optimisation module.
- Forward checking removes values that conflict with assigned categories, but does not enforce full arc consistency between two unassigned categories.

## References

[Verify the details of each reference before submitting.]

- S. Russell and P. Norvig, *Artificial Intelligence: A Modern Approach*, Pearson (chapter on constraint satisfaction problems).
- R. M. Haralick and G. L. Elliott, "Increasing tree search efficiency for constraint satisfaction problems", *Artificial Intelligence*, 14(3), 1980 (forward checking and the fail-first principle).
- A. K. Mackworth, "Consistency in networks of relations", *Artificial Intelligence*, 8(1), 1977 (arc consistency).
