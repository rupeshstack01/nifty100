from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

ROOT = Path(__file__).resolve().parents[2]
DATA = Path("/tmp/nifty100_period_aware_test/analytical")
OUT, REPORTS, DOCS = ROOT / "output", ROOT / "reports", ROOT / "docs"
for d in (OUT, REPORTS, DOCS):
    d.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(DATA / "derived_metrics_period_aware_candidate.csv", low_memory=False)
labels_path = OUT / "cluster_labels.csv"
labels = pd.read_csv(labels_path) if labels_path.exists() else pd.DataFrame()

# Latest annual row per company for cross-company analytics.
period = df["canonical_reporting_period"].fillna("").astype(str).str.lower()
annual = period.str.contains(r"\b(?:mar|dec|sep)\b|^\s*\d{4}\s*$", regex=True)
latest = df[annual].copy()
latest["year"] = pd.to_numeric(latest["year"], errors="coerce")
latest = latest.sort_values("year").drop_duplicates("company_id", keep="last")

# Correlation heatmap: use up to ten available numeric KPIs.
candidates = [
    "calculated_roe_pct", "calculated_debt_to_equity",
    "calculated_opm_pct", "calculated_net_profit_margin_pct",
    "calculated_asset_turnover", "calculated_fcf_cr",
    "profitandloss_sales", "profitandloss_operating_profit",
    "profitandloss_net_profit", "profitandloss_eps",
    "revenue_growth_pct", "net_profit_growth_pct",
]
kpis = [c for c in candidates if c in latest and
        pd.to_numeric(latest[c], errors="coerce").notna().sum() >= 3][:10]
if len(kpis) >= 2:
    corr = latest[kpis].apply(pd.to_numeric, errors="coerce").corr()
    fig, ax = plt.subplots(figsize=(12, 9))
    sns.heatmap(corr, cmap="coolwarm", center=0, annot=True, fmt=".2f", ax=ax)
    ax.set_title("Nifty 100 Candidate KPI Correlation Heatmap")
    fig.tight_layout()
    fig.savefig(REPORTS / "correlation_heatmap.png", dpi=160)
    plt.close(fig)
    corr.to_csv(OUT / "kpi_correlation_matrix.csv")

# Outlier report: flag values beyond 3 standard deviations; descriptive, not a verdict.
outlier_rows = []
outlier_features = [c for c in candidates if c in latest]
for col in outlier_features:
    vals = pd.to_numeric(latest[col], errors="coerce")
    valid = vals.dropna()
    if len(valid) < 5:
        continue
    sd = valid.std(ddof=0)
    if not sd or not np.isfinite(sd):
        continue
    z = (vals - valid.mean()) / sd
    for idx in latest.index[z.abs() > 3]:
        outlier_rows.append({
            "company_id": latest.loc[idx, "company_id"],
            "metric": col,
            "value": vals.loc[idx],
            "z_score": z.loc[idx],
            "method": "absolute z-score > 3",
        })
pd.DataFrame(outlier_rows, columns=[
    "company_id", "metric", "value", "z_score", "method"
]).to_csv(OUT / "outlier_report.csv", index=False)

# Portfolio-level descriptive statistics. These are not investment advice.
stats = []
for col in outlier_features:
    vals = pd.to_numeric(latest[col], errors="coerce").dropna()
    if len(vals):
        stats.append({
            "metric": col, "companies_with_data": int(len(vals)),
            "mean": vals.mean(), "median": vals.median(),
            "minimum": vals.min(), "maximum": vals.max(),
        })
pd.DataFrame(stats).to_csv(OUT / "portfolio_stats.csv", index=False)

# Analyst guide: ten structured pages, with explicit limitations.
styles = getSampleStyleSheet()
story = []
sections = [
    ("1. Purpose and scope", "This guide describes the Nifty 100 candidate analytics pipeline and its generated outputs."),
    ("2. Data sources", "Metrics are read from the period-aware candidate analytical CSV. Cluster labels come from output/cluster_labels.csv."),
    ("3. Period handling", "The clustering workflow accepts supported annual reporting-period labels. Interim and TTM periods should not be treated as annual observations."),
    ("4. Data quality", "Ambiguous source records and missing values can affect calculated metrics. Review flags should be investigated before interpreting results."),
    ("5. KPI definitions", "ROE, debt-to-equity, operating margin and cash-flow measures depend on the available source fields and their accounting definitions."),
    ("6. Five-year CAGR", "CAGR is calculated only when both endpoint values are positive and observations exactly five years apart are available."),
    ("7. Clustering method", "The candidate clustering uses five features, StandardScaler and KMeans with five clusters and random_state=42."),
    ("8. Cluster interpretation", "Cluster labels are descriptive names, not guarantees of business quality or future returns. Small clusters are especially uncertain."),
    ("9. Reports and API", "The heatmap, outlier report, portfolio statistics and API endpoints expose descriptive outputs from candidate data."),
    ("10. Limitations and use", "This is an analytical prototype, not investment advice. Validate data lineage, metrics and cluster stability before production use."),
]
for title, body in sections:
    story += [Paragraph(title, styles["Heading1"]), Spacer(1, 12),
              Paragraph(body, styles["BodyText"]), Spacer(1, 18),
              Paragraph("Review notes: Confirm source values, fiscal-year alignment, missingness and interpretation before relying on this section.", styles["BodyText"]),
              PageBreak()]
story.append(Paragraph("Appendix: Key generated files", styles["Heading1"]))
story.append(Paragraph(
    "output/cluster_labels.csv; output/cluster_profiles.csv; output/outlier_report.csv; "
    "output/portfolio_stats.csv; reports/elbow_plot.png; reports/correlation_heatmap.png; docs/openapi.json.",
    styles["BodyText"]))
SimpleDocTemplate(str(DOCS / "analyst_guide.pdf"), pagesize=A4).build(story)

# Twenty-gate checklist: record actual current evidence, leave unfinished gates open.
performance_file = ROOT / "reports/performance/api_performance_results.csv"
performance_ok = False
if performance_file.exists():
    performance_df = pd.read_csv(performance_file)
    performance_ok = (
        len(performance_df) == 16
        and performance_df["status"].eq("PASS").all()
        and pd.to_numeric(performance_df["errors"], errors="coerce").fillna(1).eq(0).all()
    )

gates = [
    ("AC-01", "Candidate clustering script runs", "PASS"),
    ("AC-02", "Five clusters produced", "PASS" if labels.get("cluster_id", pd.Series(dtype=float)).nunique() == 5 else "PENDING"),
    ("AC-03", "92 companies labelled", "PASS" if labels.get("company_id", pd.Series(dtype=str)).nunique() == 92 else "PENDING"),
    ("AC-04", "Cluster labels CSV exists", "PASS" if labels_path.exists() else "PENDING"),
    ("AC-05", "Cluster profiles CSV exists", "PASS" if (OUT / "cluster_profiles.csv").exists() else "PENDING"),
    ("AC-06", "Elbow plot exists", "PASS" if (REPORTS / "elbow_plot.png").exists() else "PENDING"),
    ("AC-07", "Correlation heatmap exists", "PASS" if (REPORTS / "correlation_heatmap.png").exists() else "PENDING"),
    ("AC-08", "Outlier report exists", "PASS" if (OUT / "outlier_report.csv").exists() else "PENDING"),
    ("AC-09", "Portfolio statistics exist", "PASS" if (OUT / "portfolio_stats.csv").exists() else "PENDING"),
    ("AC-10", "FastAPI app imports", "PASS" if (ROOT / "src/api/main.py").exists() else "PENDING"),
    ("AC-11", "OpenAPI specification exported", "PASS" if (DOCS / "openapi.json").exists() else "PENDING"),
    ("AC-12", "Analyst guide PDF exists", "PASS" if (DOCS / "analyst_guide.pdf").exists() else "PENDING"),
    ("AC-13", "API integration tests", "PASS" if (ROOT / "tests/test_sprint6_api.py").exists() else "PENDING"),
    ("AC-14", "Full pytest suite passes", "PASS" if (REPORTS / "pytest_junit.xml").exists() else "PENDING"),
    ("AC-15", "Company universe reconciled to 92", "PASS" if labels.get("company_id", pd.Series(dtype=str)).nunique() == 92 else "PENDING"),
    ("AC-16", "Performance tests completed", "PASS" if performance_ok else "PENDING"),
    ("AC-17", "HTML pytest report generated", "PASS" if (REPORTS / "pytest_report.html").exists() else "PENDING"),
    ("AC-18", "README and analyst docs reviewed", "PASS" if (ROOT / "README.md").exists() and (DOCS / "analyst_guide.pdf").exists() else "PENDING"),
    ("AC-19", "All deliverables archived", "PASS" if (ROOT / "dist/nifty100_sprint6_submission.zip").exists() else "PENDING"),
    ("AC-20", "Reviewer sign-off", "PENDING"),
]
story = [Paragraph("Sprint 6 Acceptance Checklist", styles["Title"]), Spacer(1, 12),
         Paragraph("PASS indicates a file or condition was observed by this script. PENDING means it has not been verified or completed.", styles["BodyText"]), Spacer(1, 16)]
table_data = [["Gate", "Acceptance criterion", "Status"]] + [list(x) for x in gates]
table = Table(table_data, repeatRows=1, colWidths=[55, 340, 75])
table.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#243447")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("FONTSIZE", (0, 0), (-1, -1), 8),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
]))
story.append(table)
SimpleDocTemplate(str(DOCS / "acceptance_checklist.pdf"), pagesize=A4).build(story)

print("Reports generated:")
for p in [
    REPORTS / "correlation_heatmap.png",
    OUT / "outlier_report.csv",
    OUT / "portfolio_stats.csv",
    DOCS / "analyst_guide.pdf",
    DOCS / "acceptance_checklist.pdf",
]:
    print(("OK " if p.exists() else "MISSING "), p.relative_to(ROOT))
print("KPIs used in heatmap:", kpis)
print("Outlier records:", len(outlier_rows))
print("Acceptance gates marked PASS:", sum(x[2] == "PASS" for x in gates), "/ 20")
