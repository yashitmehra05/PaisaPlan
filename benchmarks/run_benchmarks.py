"""Benchmark the three solvers and the local search.

Run from the repo root:   python -m benchmarks.run_benchmarks

Writes into benchmarks/:
    results.csv           one row per (problem, method)
    optimise_results.csv  one row per solvable problem (score before/after local search)
    summary.csv           the table used in the report
    charts/*.png          the charts used in the report (needs matplotlib)
"""
import csv
import os
import statistics

from solver import solve
from solver.optimize import optimise

from .generate import problem_set

SIZES = (4, 6, 8, 10, 12)
PER_SIZE = 20
MAX_NODES = 200_000
METHODS = ("backtracking", "forward", "mrv")


def _write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run(sizes, per_size, max_nodes, restarts):
    results, opt_rows = [], []
    for n in sizes:
        for i, problem in enumerate(problem_set(n, per_size)):
            statuses = {}
            for method in METHODS:
                r = solve(problem, method, max_nodes=max_nodes)
                statuses[method] = r["status"]
                results.append({
                    "n_categories": n, "problem": i, "method": method,
                    "status": r["status"], "nodes": r["stats"]["nodes"],
                    "time_ms": r["stats"]["time_ms"],
                    "hit_limit": int(r["status"] == "limit"),
                })
            if statuses["forward"] == "ok":
                o = optimise(problem, method="forward", restarts=restarts, seed=i)
                opt_rows.append({
                    "n_categories": n, "problem": i,
                    "start_score": o["start_score"], "score": o["score"],
                    "improvement_pct": round(
                        100 * (o["score"] - o["start_score"]) / o["start_score"], 2)
                        if o["start_score"] else 0.0,
                    "moves": o["stats"]["moves"], "time_ms": o["stats"]["time_ms"],
                })
    return results, opt_rows


def summarise(results, opt_rows, sizes):
    rows = []
    for n in sizes:
        for method in METHODS:
            part = [r for r in results if r["n_categories"] == n and r["method"] == method]
            rows.append({
                "n_categories": n, "method": method, "problems": len(part),
                "finished_pct": round(100 * (1 - sum(r["hit_limit"] for r in part) / len(part)), 1),
                "median_nodes": int(statistics.median(r["nodes"] for r in part)),
                "max_nodes_finished": max([r["nodes"] for r in part if not r["hit_limit"]] or [0]),
                "median_time_ms": round(statistics.median(r["time_ms"] for r in part), 3),
            })
    opt_summary = []
    for n in sizes:
        part = [r for r in opt_rows if r["n_categories"] == n]
        if part:
            opt_summary.append({
                "n_categories": n, "solvable_problems": len(part),
                "improved_pct": round(100 * sum(r["improvement_pct"] > 0 for r in part) / len(part), 1),
                "mean_improvement_pct": round(statistics.mean(r["improvement_pct"] for r in part), 2),
                "median_search_time_ms": round(statistics.median(r["time_ms"] for r in part), 2),
            })
    return rows, opt_summary


def disagreements(results):
    """Methods that finished must agree on feasible/infeasible. Count conflicts."""
    by_problem = {}
    for r in results:
        if r["status"] != "limit":
            by_problem.setdefault((r["n_categories"], r["problem"]), set()).add(r["status"])
    return sum(1 for s in by_problem.values() if len(s) > 1)


def make_charts(summary, opt_summary, charts_dir, sizes):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(charts_dir, exist_ok=True)
    colours = {"backtracking": "#d1495b", "forward": "#2e86ab", "mrv": "#3c8d40"}
    labels = {"backtracking": "Backtracking", "forward": "Forward checking",
              "mrv": "Forward checking + MRV"}

    def line_chart(key, ylabel, title, filename, log=False):
        plt.figure(figsize=(6.4, 4))
        for m in METHODS:
            ys = [next(r[key] for r in summary if r["n_categories"] == n and r["method"] == m)
                  for n in sizes]
            plt.plot(sizes, ys, marker="o", label=labels[m], color=colours[m])
        if log:
            plt.yscale("log")
        plt.xlabel("Number of flexible categories")
        plt.ylabel(ylabel)
        plt.title(title)
        plt.xticks(list(sizes))
        plt.grid(alpha=0.3)
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(charts_dir, filename), dpi=150)
        plt.close()

    line_chart("finished_pct", "Problems finished within node limit (%)",
               "How often each method finishes", "finished_pct.png")
    line_chart("median_nodes", "Median nodes tried (log scale)",
               "Search effort", "median_nodes.png", log=True)
    line_chart("max_nodes_finished", "Worst case nodes among finished runs (log scale)",
               "Worst-case search effort", "worst_case_nodes.png", log=True)
    line_chart("median_time_ms", "Median time in ms (log scale)",
               "Running time", "median_time.png", log=True)

    if opt_summary:
        plt.figure(figsize=(6.4, 4))
        xs = [r["n_categories"] for r in opt_summary]
        plt.bar([str(x) for x in xs], [r["mean_improvement_pct"] for r in opt_summary],
                color="#2e86ab")
        plt.xlabel("Number of flexible categories")
        plt.ylabel("Mean score improvement (%)")
        plt.title("Local search vs the solver's first answer")
        plt.grid(axis="y", alpha=0.3)
        plt.tight_layout()
        plt.savefig(os.path.join(charts_dir, "local_search_improvement.png"), dpi=150)
        plt.close()


def main(sizes=SIZES, per_size=PER_SIZE, max_nodes=MAX_NODES, out_dir="benchmarks",
         charts=True, restarts=5):
    os.makedirs(out_dir, exist_ok=True)
    results, opt_rows = run(sizes, per_size, max_nodes, restarts)
    summary, opt_summary = summarise(results, opt_rows, sizes)

    _write_csv(os.path.join(out_dir, "results.csv"), results)
    if opt_rows:
        _write_csv(os.path.join(out_dir, "optimise_results.csv"), opt_rows)
    _write_csv(os.path.join(out_dir, "summary.csv"), summary)
    if opt_summary:
        _write_csv(os.path.join(out_dir, "optimise_summary.csv"), opt_summary)

    print(f"{'size':>4} {'method':<13} {'finished%':>9} {'median nodes':>13} "
          f"{'worst nodes':>12} {'median ms':>10}")
    for r in summary:
        print(f"{r['n_categories']:>4} {r['method']:<13} {r['finished_pct']:>9} "
              f"{r['median_nodes']:>13} {r['max_nodes_finished']:>12} {r['median_time_ms']:>10}")
    print("\nLocal search:")
    for r in opt_summary:
        print(r)
    print("\nProblems where finished methods disagreed on solvability:", disagreements(results))

    if charts:
        try:
            make_charts(summary, opt_summary, os.path.join(out_dir, "charts"), sizes)
            print("Charts saved in", os.path.join(out_dir, "charts"))
        except ImportError:
            print("matplotlib not installed: run  pip install matplotlib  to get charts")
    return summary, opt_summary


if __name__ == "__main__":
    main()
