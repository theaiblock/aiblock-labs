"""Analysis: backtest results -> distribution, return clusters, per-year table, chart specs. No model involved.

Reads backtests/*.result.json (dev window; `--window sealed` reads backtests-sealed/) and writes analysis/:
  summary.json   every number below, for the synthesis step and the script
  analysis.md    the same, readable
  specs/*.json   chart specs for the repo's viz/ renderer (--render draws them if viz/ is found)

One row per IDEA, not per implementation: an idea's implementations are scored separately and their
spread is reported, but counting all three would triple every bar without adding information.
Clusters are built from daily RETURN series, never from thesis text: two ideas that read
differently can trade the same.

    python analyse.py populations/broad
    python analyse.py populations/broad --render
    python analyse.py populations/broad --window sealed --render

Each idea is compared with the benchmark by a paired bootstrap of the Sharpe difference (stats.py):
"above" and "below" mean the 95% interval excludes zero; "unclear" means the backtest cannot tell.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import dendrogram, fcluster, linkage
from scipy.spatial.distance import squareform

ROOT = Path(__file__).parent
PREFIX = {"claude": "CLD", "codex": "GPT"}
COLORS = {"CLD": "#F59E0B", "GPT": "#A78BFA", "BENCH": "#E6EDF3", "MIXED": "#00E0B8"}  # MIXED = a stream both models wrote
GROUP_NAMES = {"CLD": "Claude", "GPT": "GPT"}
CUT = 0.05       # family = returns correlate above 0.95 (average linkage). Every idea modifies the same
                 # benchmark, so most of the population correlates highly and a loose cut finds one cluster.
SAME = 0.001     # below this distance two ideas produce the same return stream


def model_stats(rows: list[dict], bench: float) -> dict:
    a = np.array([r["sharpe"] for r in rows])
    verdicts = [r["vs_benchmark"]["verdict"] for r in rows]
    return {"n": len(a), "median": float(np.median(a)), "q1": float(np.percentile(a, 25)),
            "q3": float(np.percentile(a, 75)), "min": float(a.min()), "max": float(a.max()),
            "higher_sharpe": int((a > bench).sum()),
            **{v: verdicts.count(v) for v in ("above", "unclear", "below")},
            "median_delta": float(np.median([r["vs_benchmark"]["delta_sharpe"] for r in rows]))}


def mean_offdiag(corr: pd.DataFrame, cols: list[str]) -> float | None:
    if len(cols) < 2:
        return None
    m = corr.loc[cols, cols].to_numpy()
    return float(m[~np.eye(len(cols), dtype=bool)].mean())


def by_label_title(ideas, label):
    return next(i["title"] for i in ideas if i["label"] == label)


def by_label_vs(ideas, label):
    i = next(i for i in ideas if i["label"] == label)
    return {**i["vs_benchmark"], "sharpe": i["sharpe"]}


def find_viz() -> Path | None:
    for parent in ROOT.resolve().parents:
        if (parent / "viz" / "render.mjs").exists():
            return parent / "viz"
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("idea_dir", type=Path)
    ap.add_argument("--render", action="store_true", help="render the specs with viz/ (needs node + Chrome)")
    ap.add_argument("--cut", type=float, default=CUT, help="cluster cut on 1 - correlation")
    ap.add_argument("--window", choices=("dev", "sealed"), default="dev")
    args = ap.parse_args()
    suffix = "" if args.window == "dev" else "-sealed"
    out = args.idea_dir / f"analysis{suffix}"
    (out / "specs").mkdir(parents=True, exist_ok=True)

    bench = json.loads((args.idea_dir / f"backtests{suffix}" / "benchmark.result.json").read_text())
    by_spec = defaultdict(list)
    for p in sorted((args.idea_dir / f"backtests{suffix}").glob("*.impl-*.result.json")):
        r = json.loads(p.read_text())
        if "errors" not in r:
            by_spec[r["spec_id"]].append(r)

    # one row per idea: impl-A carries the return series; the spread across impls is recorded
    ideas, counters = [], defaultdict(int)
    for spec_id in sorted(by_spec):
        impls = sorted(by_spec[spec_id], key=lambda r: r["impl_id"])
        spec = json.loads((args.idea_dir / "ideas" / f"{spec_id}.json").read_text())
        prefix = PREFIX[spec["runner"]]
        counters[prefix] += 1
        rep = impls[0]
        sh = [r["sharpe"] for r in impls]
        ideas.append({"label": f"{prefix}_{counters[prefix]:02d}", "group": prefix, "spec_id": spec_id,
                      "model": spec["model"], "title": spec["thesis"]["title"],
                      "sharpe": rep["sharpe"], "vs_benchmark": rep["vs_benchmark"],
                      "impl_sharpes": sh, "impl_spread": max(sh) - min(sh),
                      "annual_return": rep["annual_return"], "max_drawdown": rep["max_drawdown"],
                      "exposure": rep["exposure"], "coins_held": rep["coins_held"],
                      "turnover_week": rep["turnover_week"], "fees_per_year": rep["fees_per_year"],
                      "years": rep["years"], "_returns": rep["daily_returns"]})
    labels = [i["label"] for i in ideas]
    groups = {g: [i for i in ideas if i["group"] == g] for g in PREFIX.values() if any(i["group"] == g for i in ideas)}

    # distribution
    stats = {g: model_stats(v, bench["sharpe"]) for g, v in groups.items()}
    stats["ALL"] = model_stats(ideas, bench["sharpe"])

    # correlation of daily returns, benchmark included as a row
    rets = pd.DataFrame({i["label"]: pd.Series(i["_returns"]) for i in ideas})
    rets["BENCH"] = pd.Series(bench["daily_returns"])
    rets = rets.sort_index()
    corr = rets.corr()
    dist = (1 - corr).clip(lower=0).to_numpy(copy=True)
    np.fill_diagonal(dist, 0)
    Z = linkage(squareform(dist, checks=False), method="average")
    cluster_ids = fcluster(Z, t=args.cut, criterion="distance")
    tree = dendrogram(Z, labels=list(corr.columns), no_plot=True, color_threshold=args.cut)
    streams = fcluster(Z, t=SAME, criterion="distance")
    distinct = {g: len({s for col, s in zip(corr.columns, streams) if col.startswith(g)}) for g in groups}
    distinct["ALL"] = len({s for col, s in zip(corr.columns, streams) if col != "BENCH"})
    # one row per distinct return stream, represented by its first idea: the honest unit for "how many
    # different things beat the benchmark"
    stream_rows = defaultdict(list)
    for col, sid in zip(corr.columns, streams):
        if col != "BENCH":
            stream_rows[int(sid)].append(col)
    stream_list = []
    for members in stream_rows.values():
        lead = min(members, key=lambda m: (m[:3], m))
        stream_list.append({"lead": lead, "members": sorted(members), "size": len(members),
                            "by_group": {g: n for g in groups if (n := sum(m.startswith(g) for m in members))},
                            "title": by_label_title(ideas, lead), **by_label_vs(ideas, lead)})
    stream_list.sort(key=lambda r: -r["delta_sharpe"])
    # a stream shared by both models counts for both, same as distinct_return_streams
    stream_verdicts = {g: {v: sum(r["verdict"] == v for r in stream_list if g in r["by_group"])
                           for v in ("above", "unclear", "below")} for g in groups}
    order = tree["ivl"]

    clusters = defaultdict(list)
    for col, cid in zip(corr.columns, cluster_ids):
        clusters[int(cid)].append(col)
    by_label = {i["label"]: i for i in ideas}
    cluster_rows = []
    for members in clusters.values():
        members = sorted(members, key=order.index)
        idea_members = [m for m in members if m != "BENCH"]
        sh = [by_label[m]["sharpe"] for m in idea_members]
        cluster_rows.append({
            "members": members, "size": len(idea_members),
            "by_group": {g: sum(m.startswith(g) for m in idea_members) for g in groups},
            "includes_benchmark": "BENCH" in members,
            "median_sharpe": float(np.median(sh)) if sh else None,
            "titles": sorted({by_label[m]["title"] for m in idea_members}),
            "mean_corr": mean_offdiag(corr, members)})
    cluster_rows.sort(key=lambda c: (-c["size"], order.index(c["members"][0])))
    for k, c in enumerate(cluster_rows, 1):
        c["id"] = k

    corr_stats = {g: mean_offdiag(corr, [i["label"] for i in v]) for g, v in groups.items()}
    corr_stats["to_benchmark"] = {g: float(corr.loc[[i["label"] for i in v], "BENCH"].mean()) for g, v in groups.items()}

    # per year
    # Sharpe alone misreads a year spent mostly flat (tiny returns, tiny vol), so compound returns too
    years = sorted(bench["years"])
    yret = (1 + rets.fillna(0)).groupby(rets.index.str[:4]).prod() - 1
    per_year = {y: {"benchmark": bench["years"][y], "benchmark_return": float(yret.loc[y, "BENCH"]),
                    **{g: {"median": float(np.median([i["years"][y] for i in v])),
                           "median_return": float(yret.loc[y, [i["label"] for i in v]].median()),
                           "above_benchmark": sum(i["years"][y] > bench["years"][y] for i in v), "n": len(v)}
                       for g, v in groups.items()}} for y in years}

    summary = {"idea_dir": str(args.idea_dir), "window": args.window, "period": bench["period"],
               "benchmark_sharpe": bench["sharpe"], "benchmark_annual_return": bench["annual_return"],
               "benchmark_max_drawdown": bench["max_drawdown"],
               "unit": "one row per idea (impl-A); implementation spread reported separately",
               "comparison": "paired block bootstrap of the Sharpe difference vs the benchmark, 95% interval "
                             "(above/below = interval excludes zero)",
               "streams": stream_list, "stream_verdicts": stream_verdicts,
               "cluster_rule": f"average linkage on 1 - correlation of daily returns, cut at {args.cut}",
               "distinct_return_streams": distinct, "cut": args.cut,
               "sharpe": stats, "mean_pairwise_corr": corr_stats,
               "max_impl_spread": max(i["impl_spread"] for i in ideas),
               "clusters": cluster_rows, "per_year": per_year,
               "ideas": [{k: v for k, v in i.items() if k != "_returns"} for i in ideas]}
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (out / "analysis.md").write_text(report(summary, groups))
    write_specs(out / "specs", summary, ideas, groups, bench, rets, corr, order, tree)
    print((out / "analysis.md").read_text())

    if args.render:
        viz = find_viz()
        if viz is None:
            raise SystemExit("viz/ not found above this folder; specs are in " + str(out / "specs"))
        subprocess.run(["node", "render.mjs", str((out / "specs").resolve()), str((out / "charts").resolve())],
                       cwd=viz, check=True)


def write_specs(d: Path, summary, ideas, groups, bench, rets, corr, order, tree) -> None:
    names = GROUP_NAMES
    b = bench["sharpe"]
    def dump(name, spec):
        (d / f"{name}.json").write_text(json.dumps(spec) + "\n")

    # 1. Sharpe histogram vs benchmark
    lo = np.floor(min(min(i["sharpe"] for i in ideas), b) / 0.05) * 0.05
    hi = np.ceil(max(max(i["sharpe"] for i in ideas), b) / 0.05 + 1e-9) * 0.05
    edges = np.round(np.arange(lo, hi + 1e-9, 0.05), 2)
    dump("01_sharpe_histogram", {
        "type": "histogram", "title": "Sharpe ratio of each idea",
        "subtitle": f"{len(ideas)} ideas, {bench['period'][0]} to {bench['period'][1]}",
        "binEdges": edges.tolist(), "xName": "Sharpe ratio", "yName": "ideas",
        "series": [{"name": names[g], "color": COLORS[g],
                    "data": np.histogram([i["sharpe"] for i in v], bins=edges)[0].tolist()} for g, v in groups.items()],
        "refs": [{"x": round(b, 3), "label": f"benchmark {b:.2f}"}]})

    # 2. cumulative growth fan
    growth = (1 + rets.fillna(0)).cumprod()
    step = max(1, len(growth) // 400)
    g = growth.iloc[::step]
    leads = {r["lead"] for r in summary["streams"]}
    series = [{"name": i["label"], "data": np.round(g[i["label"]].to_numpy(), 3).tolist(),
               "color": COLORS[i["group"]], "width": 2, "opacity": 0.45, "area": False} for i in ideas if i["label"] in leads]
    series.append({"name": "Benchmark", "data": np.round(g["BENCH"].to_numpy(), 3).tolist(),
                   "color": COLORS["BENCH"], "width": 5, "area": False, "z": 5})
    dump("02_growth_fan", {"type": "line", "title": "Growth of $1, every idea vs the benchmark",
                           "subtitle": "One line per distinct return stream. Amber = Claude, violet = GPT, white = benchmark. Log scale.",
                           "x": [str(x) for x in g.index], "series": series, "logScale": True,
                           "hideLegend": True, "valueFormat": "mult",
                           "yMin": round(float(g.min().min()) * 0.9, 2), "yMax": round(float(g.max().max()) * 1.3, 1)})

    # 3. correlation heatmap, dendrogram order
    idx = {l: k for k, l in enumerate(order)}
    dump("03_correlation_matrix", {
        "type": "heatmap", "title": "Correlation of daily returns",
        "subtitle": "Ordered by the clustering tree. Amber = Claude, violet = GPT.",
        "labels": order, "labelColors": COLORS,
        "min": float(np.floor(corr.to_numpy().min() * 10) / 10), "max": 1.0,
        "data": [[idx[c], idx[r], round(float(corr.loc[r, c]), 3)] for r in order for c in order]})

    # 4. dendrogram
    color_of = lambda lab: COLORS["BENCH"] if lab == "BENCH" else COLORS[lab[:3]]
    dump("04_dendrogram", {
        "type": "dendrogram", "title": "Which ideas trade the same",
        "subtitle": f"Clustered on daily returns. Joined below the dashed line = correlation above {1 - summary['cut']:.2f}.",
        "links": [{"x": x, "y": y, "color": "#3B82F6" if max(y) <= summary["cut"] else "#8B97A7"}
                  for x, y in zip(tree["icoord"], tree["dcoord"])],
        "leaves": [{"x": 5 + 10 * k, "label": lab, "color": color_of(lab)} for k, lab in enumerate(order)],
        "yMax": float(np.ceil(max(max(y) for y in tree["dcoord"]) * 20) / 20), "yName": "1 − correlation",
        "cut": summary["cut"], "cutLabel": f"{1 - summary['cut']:.2f} correlation"})

    # 6. forest: every distinct stream's Sharpe difference vs the benchmark, with its 95% interval
    dump("06_vs_benchmark", {
        "type": "forest", "title": "Better than the benchmark, or noise?",
        "subtitle": "95% interval, one row per distinct return stream. A bar crossing zero shows no difference. "
                    "Amber Claude · violet GPT · teal both.",
        "xName": "Sharpe difference vs benchmark",
        "rows": [{"label": r["lead"] + " · " + " + ".join(f"{n} {GROUP_NAMES[g]}" for g, n in r["by_group"].items()),
                  "value": round(r["delta_sharpe"], 3), "low": round(r["ci_low"], 3), "high": round(r["ci_high"], 3),
                  "color": COLORS[next(iter(r["by_group"]))] if len(r["by_group"]) == 1 else COLORS["MIXED"],
                  "dim": r["verdict"] == "unclear"} for r in summary["streams"]]})

    # 5. per-year medians
    years = list(summary["per_year"])
    dump("05_sharpe_by_year", {
        "type": "groupedbar", "title": "Median Sharpe by year", "subtitle": f"{summary['window']} window",
        "x": years, "valueFormat": "dec2", "zeroLine": True,
        "series": [*({"name": names[g], "color": COLORS[g],
                      "data": [round(summary["per_year"][y][g]["median"], 2) for y in years]} for g in groups),
                   {"name": "Benchmark", "color": "#8B97A7",
                    "data": [round(summary["per_year"][y]["benchmark"], 2) for y in years]}]})


def report(s: dict, groups: dict) -> str:
    b = s["benchmark_sharpe"]
    L = [f"# Analysis — {s['idea_dir']} ({s['window']} window)", "",
         f"Scored {s['period'][0]} → {s['period'][1]}. Benchmark Sharpe **{b:.2f}** "
         f"(annual return {s['benchmark_annual_return']:.0%}, max drawdown {s['benchmark_max_drawdown']:.0%}). "
         f"Unit: {s['unit']}. Largest Sharpe spread between implementations of one idea: "
         f"{s['max_impl_spread']:.3f}.", "",
         f"Comparison with the benchmark: {s['comparison']}.", "",
         "Distinct return streams (ideas that trade identically count once): "
         + ", ".join(f"{g} {n}" for g, n in s["distinct_return_streams"].items()) + ".", "",
         "## Sharpe distribution and verdict vs benchmark (per idea)", "",
         "| | ideas | median Sharpe | IQR | min | max | median Sharpe difference | above | unclear | below |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for g, st in s["sharpe"].items():
        L.append(f"| {g} | {st['n']} | {st['median']:.2f} | {st['q1']:.2f}–{st['q3']:.2f} | {st['min']:.2f} | "
                 f"{st['max']:.2f} | {st['median_delta']:+.2f} | {st['above']}/{st['n']} | {st['unclear']}/{st['n']} | {st['below']}/{st['n']} |")
    L += ["", "## Distinct return streams vs benchmark", "",
          "| stream | ideas in it | Sharpe | Sharpe difference | 95% interval | verdict | title |", "|---|---|---|---|---|---|---|"]
    for r in s["streams"]:
        L.append(f"| {r['lead']} | {', '.join(r['members'])} | {r['sharpe']:.2f} | {r['delta_sharpe']:+.2f} | "
                 f"{r['ci_low']:+.2f} to {r['ci_high']:+.2f} | {r['verdict']} | {r['title']} |")
    L += ["", "Streams by verdict: " + "; ".join(f"{g} " + ", ".join(f"{v} {n}" for v, n in c.items())
                                                for g, c in s["stream_verdicts"].items()) + "."]
    L += ["", "## Return correlation", "",
          "| | mean pairwise corr within model | mean corr to benchmark |", "|---|---|---|"]
    for g in groups:
        w = s["mean_pairwise_corr"][g]
        L.append(f"| {g} | {w:.3f} | {s['mean_pairwise_corr']['to_benchmark'][g]:.3f} |" if w is not None else f"| {g} | – | – |")
    L += ["", f"## Clusters ({s['cluster_rule']})", "",
          "| # | ideas | by model | median Sharpe | with benchmark | mean corr | thesis titles |", "|---|---|---|---|---|---|---|"]
    for c in s["clusters"]:
        med = f"{c['median_sharpe']:.2f}" if c["median_sharpe"] is not None else "–"
        mc = f"{c['mean_corr']:.2f}" if c["mean_corr"] is not None else "–"
        L.append(f"| {c['id']} | {c['size']} | {', '.join(f'{g} {n}' for g, n in c['by_group'].items() if n)} | {med} | "
                 f"{'yes' if c['includes_benchmark'] else ''} | {mc} | {'; '.join(c['titles'])} |")
    L += ["", "## By year: median Sharpe (ideas above benchmark) · median return", "",
          "| year | benchmark | " + " | ".join(groups) + " |", "|---|---|" + "---|" * len(groups)]
    for y, row in s["per_year"].items():
        L.append(f"| {y} | {row['benchmark']:.2f} · {row['benchmark_return']:.0%} | " + " | ".join(
            f"{row[g]['median']:.2f} ({row[g]['above_benchmark']}/{row[g]['n']}) · {row[g]['median_return']:.0%}"
            for g in groups) + " |")
    L += ["", "## Ideas", "", "| label | Sharpe | Sharpe difference | 95% interval | impl spread | ann. return | max DD | exposure | coins held | turnover/wk | fees/yr | title |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i in sorted(s["ideas"], key=lambda i: -i["sharpe"]):
        v = i["vs_benchmark"]
        L.append(f"| {i['label']} | {i['sharpe']:.2f} | {v['delta_sharpe']:+.2f} | {v['ci_low']:+.2f} to {v['ci_high']:+.2f} | "
                 f"{i['impl_spread']:.3f} | {i['annual_return']:.0%} | {i['max_drawdown']:.0%} | {i['exposure']:.0%} | "
                 f"{i['coins_held']:.0f} | {i['turnover_week']:.2f} | {i['fees_per_year']:.1%} | {i['title']} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
