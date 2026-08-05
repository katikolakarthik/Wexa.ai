#!/usr/bin/env python3
"""Generate charts and markdown tables from real benchmark CSV results (Phase 7).

Never fabricates measurements. Charts are produced only from files under results/.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.config import load_benchmark_config

# Distinct, non-purple palette for readability.
DB_COLORS = {
    "cognodb": "#0B6E4F",
    "memgraph": "#1B4F72",
    "falkordb": "#B85C38",
    "arangodb": "#5C4B51",
    "neo4j": "#7D7461",
}

DB_ORDER = ["cognodb", "memgraph", "falkordb", "arangodb", "neo4j"]


def _style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "#F7F5F2",
            "axes.edgecolor": "#333333",
            "axes.grid": True,
            "grid.color": "#D0CBC4",
            "grid.linestyle": "--",
            "grid.alpha": 0.7,
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 10,
        }
    )


def load_ingestion(raw_dir: Path) -> pd.DataFrame:
    rows = []
    for path in sorted(raw_dir.glob("*_ingestion.csv")):
        df = pd.read_csv(path)
        if df.empty:
            continue
        # Keep the latest successful row when multiple loads were appended.
        success = df[df["success"].astype(str).str.lower().isin(["true", "1"])]
        if not success.empty:
            rows.append(success.iloc[-1])
        else:
            rows.append(df.iloc[-1])
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def load_summary(path: Path) -> pd.DataFrame:
    if not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError(f"Missing summary file: {path}")
    return pd.read_csv(path)


def _ordered_dbs(present: list[str]) -> list[str]:
    return [d for d in DB_ORDER if d in present] + [
        d for d in present if d not in DB_ORDER
    ]


def _bar_grouped(
    *,
    categories: list[str],
    series: dict[str, list[float]],
    ylabel: str,
    title: str,
    out_path: Path,
    annotate_missing: str | None = None,
) -> None:
    labels = list(series.keys())
    if not labels:
        return
    x = np.arange(len(categories))
    width = min(0.8 / max(len(labels), 1), 0.22)
    fig, ax = plt.subplots(figsize=(10, 5.5))
    for idx, db in enumerate(labels):
        offsets = x + (idx - (len(labels) - 1) / 2) * width
        values = series[db]
        color = DB_COLORS.get(db, "#444444")
        bars = ax.bar(offsets, values, width=width, label=db, color=color)
        for bar, val in zip(bars, values):
            if np.isfinite(val) and val > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height(),
                    f"{val:.0f}" if val >= 10 else f"{val:.1f}",
                    ha="center",
                    va="bottom",
                    fontsize=7,
                    rotation=0,
                )
    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_ylim(bottom=0)
    ax.legend(frameon=False)
    if annotate_missing:
        ax.text(
            0.99,
            0.98,
            annotate_missing,
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=8,
            color="#666666",
        )
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def chart_ingestion(ing: pd.DataFrame, charts_dir: Path) -> Path | None:
    if ing.empty:
        return None
    ok = ing[ing["success"].astype(str).str.lower().isin(["true", "1"])].copy()
    if ok.empty:
        return None
    dbs = _ordered_dbs(ok["database"].astype(str).tolist())
    ok = ok.set_index("database").loc[dbs]
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(dbs))
    width = 0.35
    nodes = ok["nodes_per_second"].astype(float).tolist()
    rels = ok["relationships_per_second"].astype(float).tolist()
    ax.bar(x - width / 2, nodes, width, label="nodes/s", color="#2F4858")
    ax.bar(x + width / 2, rels, width, label="relationships/s", color="#F26419")
    ax.set_xticks(x)
    ax.set_xticklabels(dbs)
    ax.set_ylabel("Throughput (entities / second)")
    ax.set_title("Ingestion throughput (batch_size=1000)")
    ax.set_ylim(bottom=0)
    ax.legend(frameon=False)
    missing = sorted(set(DB_ORDER) - set(dbs))
    if missing:
        ax.text(
            0.99,
            0.98,
            "Not plotted (failed/missing load): " + ", ".join(missing),
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=8,
            color="#666666",
        )
    fig.tight_layout()
    out = charts_dir / "ingestion_throughput.png"
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out


def chart_workloads(
    summary: pd.DataFrame,
    charts_dir: Path,
    *,
    workloads: list[str],
    metric: str,
    filename: str,
    title: str,
    ylabel: str,
) -> Path | None:
    df = summary[summary["workload"].isin(workloads)].copy()
    if df.empty:
        return None
    dbs = _ordered_dbs(sorted(df["database"].unique().tolist()))
    series: dict[str, list[float]] = {}
    for db in dbs:
        vals = []
        sub = df[df["database"] == db].set_index("workload")
        for wl in workloads:
            vals.append(float(sub.loc[wl, metric]) if wl in sub.index else float("nan"))
        series[db] = vals
    out = charts_dir / filename
    _bar_grouped(
        categories=workloads,
        series=series,
        ylabel=ylabel,
        title=title,
        out_path=out,
        annotate_missing="Neo4j not shown: Aura free 400k relationship limit",
    )
    return out


def chart_mixed_qps(summary: pd.DataFrame, charts_dir: Path) -> Path | None:
    mixed = summary[summary["workload"].str.startswith("mixed_c")].copy()
    if mixed.empty:
        return None
    dbs = _ordered_dbs(sorted(mixed["database"].unique().tolist()))
    levels = sorted({int(c) for c in mixed["concurrency"].dropna().unique()})
    cats = [f"c={c}" for c in levels]
    series: dict[str, list[float]] = {}
    for db in dbs:
        vals = []
        sub = mixed[mixed["database"] == db]
        for c in levels:
            row = sub[sub["concurrency"].astype(int) == c]
            vals.append(float(row.iloc[0]["throughput_qps"]) if not row.empty else float("nan"))
        series[db] = vals
    out = charts_dir / "mixed_workload_qps.png"
    _bar_grouped(
        categories=cats,
        series=series,
        ylabel="Successful operations / second",
        title="Mixed workload throughput (80% read / 20% write)",
        out_path=out,
    )
    return out


def chart_concurrency_scaling(summary: pd.DataFrame, charts_dir: Path) -> Path | None:
    mixed = summary[summary["workload"].str.startswith("mixed_c")].copy()
    if mixed.empty:
        return None
    fig, ax = plt.subplots(figsize=(9, 5.5))
    for db in _ordered_dbs(sorted(mixed["database"].unique().tolist())):
        sub = mixed[mixed["database"] == db].sort_values("concurrency")
        ax.plot(
            sub["concurrency"].astype(int),
            sub["throughput_qps"].astype(float),
            marker="o",
            linewidth=2,
            label=db,
            color=DB_COLORS.get(db, "#444444"),
        )
    ax.set_xlabel("Concurrency (client workers)")
    ax.set_ylabel("Successful operations / second")
    ax.set_title("Concurrency scaling (mixed workload)")
    ax.set_ylim(bottom=0)
    ax.set_xticks([1, 10, 40])
    ax.legend(frameon=False)
    fig.tight_layout()
    out = charts_dir / "concurrency_scaling.png"
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out


def fmt_ms(value: float) -> str:
    if pd.isna(value):
        return "—"
    return f"{float(value):.1f}"


def fmt_qps(value: float) -> str:
    if pd.isna(value):
        return "—"
    return f"{float(value):.2f}"


def build_markdown_tables(summary: pd.DataFrame, ingestion: pd.DataFrame) -> str:
    lines: list[str] = []
    lines.append("# Benchmark result tables (generated)\n")
    lines.append("Source: `results/processed/summary.csv` and `results/raw/*_ingestion.csv`.\n")
    lines.append(
        "Shared prepared graph: deterministic cit-HepPh subsample "
        "(399,000 relationships, seed 42) loaded on all five platforms "
        "to stay under Neo4j Aura free’s 400,000 relationship cap.\n"
    )

    lines.append("\n## Ingestion\n")
    lines.append(
        "| Database | Nodes/s | Rels/s | Node load (ms) | Rel load (ms) | Total (ms) | Verified |\n"
        "|----------|--------:|-------:|---------------:|--------------:|-----------:|----------|\n"
    )
    if not ingestion.empty:
        for _, row in ingestion.iterrows():
            ok = str(row.get("success", "")).lower() in {"true", "1"}
            if ok:
                lines.append(
                    f"| {row['database']} | {float(row['nodes_per_second']):.1f} | "
                    f"{float(row['relationships_per_second']):.1f} | "
                    f"{float(row['node_load_ms']):.1f} | {float(row['relationship_load_ms']):.1f} | "
                    f"{float(row['total_ingestion_ms']):.1f} | "
                    f"{int(row['verified_node_count'])}/{int(row['verified_relationship_count'])} |\n"
                )
            else:
                err = str(row.get("error", "load failed"))
                if "400000" in err or "logical size limit" in err.lower():
                    short = "Aura free 400k relationship limit"
                else:
                    short = (err[:70] + "…") if len(err) > 70 else err
                lines.append(
                    f"| {row['database']} | — | — | — | — | — | FAILED ({short}) |\n"
                )

    def section(title: str, workloads: list[str]) -> None:
        lines.append(f"\n## {title}\n")
        lines.append("| Database | Workload | p50 (ms) | p95 (ms) | p99 (ms) | mean (ms) | QPS | errors |\n")
        lines.append("|----------|----------|---------:|---------:|---------:|----------:|----:|-------:|\n")
        sub = summary[summary["workload"].isin(workloads)].copy()
        sub["database"] = pd.Categorical(sub["database"], categories=DB_ORDER, ordered=True)
        sub["workload"] = pd.Categorical(sub["workload"], categories=workloads, ordered=True)
        sub = sub.sort_values(["workload", "database"])
        for _, row in sub.iterrows():
            lines.append(
                f"| {row['database']} | {row['workload']} | {fmt_ms(row['p50_ms'])} | "
                f"{fmt_ms(row['p95_ms'])} | {fmt_ms(row['p99_ms'])} | {fmt_ms(row['mean_ms'])} | "
                f"{fmt_qps(row['throughput_qps'])} | {int(row['errors'])} |\n"
            )

    section("Traversal", ["one_hop", "two_hop", "three_hop"])
    section("Lookup", ["point_lookup", "filtered_lookup"])
    section("Aggregation", ["aggregation"])
    section("Mixed", ["mixed_c1", "mixed_c10", "mixed_c40"])
    return "".join(lines)


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    cfg = load_benchmark_config()
    raw_dir = PROJECT_ROOT / cfg.get("raw_directory", "results/raw")
    processed_dir = PROJECT_ROOT / cfg.get("processed_directory", "results/processed")
    charts_dir = PROJECT_ROOT / cfg.get("charts_directory", "charts")

    print("Generating report from measured result files...")
    print(f"  raw       : {raw_dir}")
    print(f"  processed : {processed_dir}")
    print(f"  charts    : {charts_dir}")

    try:
        summary = load_summary(processed_dir / "summary.csv")
    except FileNotFoundError as exc:
        print(f"FAILURE: {exc}")
        return 1

    ingestion = load_ingestion(raw_dir)
    _style()

    written: list[Path] = []
    for path in (
        chart_ingestion(ingestion, charts_dir),
        chart_workloads(
            summary,
            charts_dir,
            workloads=["one_hop", "two_hop", "three_hop"],
            metric="p50_ms",
            filename="traversal_p50.png",
            title="Traversal latency p50",
            ylabel="Latency (ms)",
        ),
        chart_workloads(
            summary,
            charts_dir,
            workloads=["one_hop", "two_hop", "three_hop"],
            metric="p95_ms",
            filename="traversal_p95.png",
            title="Traversal latency p95",
            ylabel="Latency (ms)",
        ),
        chart_workloads(
            summary,
            charts_dir,
            workloads=["point_lookup", "filtered_lookup"],
            metric="p50_ms",
            filename="lookup_latency.png",
            title="Lookup latency p50",
            ylabel="Latency (ms)",
        ),
        chart_workloads(
            summary,
            charts_dir,
            workloads=["aggregation"],
            metric="p50_ms",
            filename="aggregation_latency.png",
            title="Aggregation latency p50",
            ylabel="Latency (ms)",
        ),
        chart_mixed_qps(summary, charts_dir),
        chart_concurrency_scaling(summary, charts_dir),
    ):
        if path is not None:
            written.append(path)
            print(f"  wrote {path.relative_to(PROJECT_ROOT)}")

    tables = build_markdown_tables(summary, ingestion)
    tables_path = processed_dir / "report_tables.md"
    tables_path.write_text(tables, encoding="utf-8")
    print(f"  wrote {tables_path.relative_to(PROJECT_ROOT)}")

    # Also write a compact CSV pivot for external use.
    pivot = summary.pivot_table(
        index="database",
        columns="workload",
        values="p50_ms",
        aggfunc="first",
    )
    pivot_path = processed_dir / "p50_pivot.csv"
    pivot.to_csv(pivot_path)
    print(f"  wrote {pivot_path.relative_to(PROJECT_ROOT)}")

    if not written:
        print("FAILURE: No charts generated (missing measured data).")
        return 1

    print(f"SUCCESS: Generated {len(written)} chart(s) and result tables.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
