
from pathlib import Path
import re
import pandas as pd

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, KeepTogether
)

ROOT = Path(__file__).resolve().parents[2]
ENGINE_PATH = ROOT / "data/processed/analytical/financial_ratios_engine.csv"
PANEL_PATH = ROOT / "data/processed/analytical/financial_panel.csv"
PROS_PATH = ROOT / "output/pros_cons_generated.csv"
CAPITAL_PATH = ROOT / "output/capital_allocation.csv"
PATTERN_PATH = ROOT / "output/pattern_changes.csv"
CASHFLOW_PATH = ROOT / "output/cashflow_intelligence.xlsx"
RADAR_DIR = ROOT / "reports/radar_charts"

TEARSHEET_DIR = ROOT / "reports/tearsheets"
SECTOR_DIR = ROOT / "reports/sector"
PORTFOLIO_DIR = ROOT / "reports/portfolio"

for directory in [TEARSHEET_DIR, SECTOR_DIR, PORTFOLIO_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="ReportTitle", parent=styles["Title"],
    fontSize=19, leading=23, alignment=TA_CENTER,
    spaceAfter=8
))
styles.add(ParagraphStyle(
    name="SectionHeading", parent=styles["Heading2"],
    fontSize=12, leading=15, spaceBefore=8, spaceAfter=5
))
styles.add(ParagraphStyle(
    name="SmallText", parent=styles["BodyText"],
    fontSize=8, leading=10
))

def safe_name(value):
    return str(value).strip().replace("&", "%26").replace("/", "_").replace(" ", "_")

def fmt(value, suffix="", decimals=2):
    if pd.isna(value):
        return "N/A"
    try:
        return f"{float(value):,.{decimals}f}{suffix}"
    except (ValueError, TypeError):
        return str(value)

def p(text, style="BodyText"):
    return Paragraph(str(text), styles[style])

def make_table(rows, widths=None, font_size=8):
    table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#203864")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("LEADING", (0, 0), (-1, -1), font_size + 2),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C8D0DC")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#F2F5F9")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table

def load_csv(path):
    if not path.exists():
        raise FileNotFoundError(f"Required input is missing: {path}")
    return pd.read_csv(path)

def latest_per_company(df):
    df = df.copy()
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df.dropna(subset=["company_id", "year"])
    return (
        df.sort_values(["company_id", "year"])
          .groupby("company_id", as_index=False)
          .tail(1)
          .copy()
    )

def metric_rows(row):
    fields = [
        ("Sector", row.get("broad_sector", "N/A")),
        ("Latest year", fmt(row.get("year"), decimals=0)),
        ("Net profit margin", fmt(row.get("engine_net_profit_margin_pct"), "%")),
        ("Operating profit margin", fmt(row.get("engine_operating_profit_margin_pct"), "%")),
        ("Return on equity", fmt(row.get("engine_return_on_equity_pct"), "%")),
        ("Return on capital employed", fmt(row.get("engine_roce_pct"), "%")),
        ("Return on assets", fmt(row.get("engine_roa_pct"), "%")),
        ("Debt to equity", fmt(row.get("engine_debt_to_equity"))),
        ("Interest coverage", fmt(row.get("engine_interest_coverage"), "x")),
        ("Asset turnover", fmt(row.get("engine_asset_turnover"), "x")),
        ("Free cash flow", fmt(row.get("free_cash_flow_cr"), " Cr")),
        ("Cash from operations", fmt(row.get("cash_from_operations_cr"), " Cr")),
        ("Capital allocation", row.get("capital_allocation", "N/A")),
        ("Composite quality score", fmt(row.get("composite_quality_score"))),
    ]
    return [["Metric", "Latest available value"]] + [
        [str(k), str(v)] for k, v in fields
    ]

def build_tearsheet(company_id, row, history, findings, patterns):
    review_warnings = []

    record_status = str(row.get("record_status", "")).strip().upper()
    record_count = pd.to_numeric(
        pd.Series([row.get("record_count")]), errors="coerce"
    ).iloc[0]

    if record_status == "VARIANT_REVIEW" or (
        pd.notna(record_count) and record_count > 1
    ):
        review_warnings.append(
            "Latest ratio-engine record has unresolved source variants. "
            "Affected figures must be verified before interpretation."
        )

    if not history.empty:
        latest_history = history.copy()
        latest_history["year"] = pd.to_numeric(
            latest_history["year"], errors="coerce"
        )
        latest_history = latest_history[
            latest_history["year"] == latest_history["year"].max()
        ]

        for flag, label in [
            ("financial_ratios_ambiguous", "financial ratios"),
            ("cashflow_ambiguous", "cash-flow data"),
            ("balancesheet_ambiguous", "balance-sheet data"),
            ("profitandloss_ambiguous", "profit-and-loss data"),
        ]:
            if flag in latest_history.columns:
                ambiguous = (
                    latest_history[flag]
                    .fillna(True)
                    .astype(str)
                    .str.strip()
                    .str.lower()
                    .isin(["true", "1", "yes"])
                )
                if ambiguous.any():
                    review_warnings.append(
                        f"Latest historical panel has unresolved "
                        f"{label} variants."
                    )

    review_warnings = list(dict.fromkeys(review_warnings))
    path = TEARSHEET_DIR / f"{safe_name(company_id)}_tearsheet.pdf"
    doc = SimpleDocTemplate(
        str(path), pagesize=A4,
        rightMargin=15*mm, leftMargin=15*mm,
        topMargin=13*mm, bottomMargin=13*mm
    )
   
    story = [
        p(f"{company_id} — Company Tearsheet", "ReportTitle"),
        p("Financial analytics report | Latest available record", "SmallText"),
        Spacer(1, 5*mm),
    ]

    if review_warnings:
        story.append(
            p(
                "<b>DATA QUALITY WARNING:</b> "
                + " ".join(review_warnings),
                "SmallText",
            )
        )
        story.append(Spacer(1, 2*mm))

    story += [
        p("1. Financial and quality snapshot", "SectionHeading"),
        make_table(metric_rows(row), [58*mm, 105*mm]),
        Spacer(1, 4*mm),
    ]
    radar = RADAR_DIR / f"{company_id}_radar.png"


    
    if radar.exists():
        try:
            img = Image(str(radar), width=85*mm, height=45*mm, kind="proportional")
            story += [p("Existing company radar chart", "SectionHeading"), img]
        except Exception as exc:
            story.append(p(f"Radar chart could not be embedded: {exc}", "SmallText"))
    else:
        story.append(p("No matching radar chart was found.", "SmallText"))

    story += [
        Spacer(1, 3*mm),
        p("2. Rule-based pros and cons", "SectionHeading"),
    ]

    if findings.empty:
        story.append(p("No generated findings were available for this company.", "SmallText"))
    else:
        for kind, label in [("pro", "Pros"), ("con", "Cons")]:
            subset = findings[
    findings["finding_type"].astype(str).str.lower() == kind
].head(3)
            story.append(p(f"<b>{label}</b>", "SmallText"))
            if subset.empty:
                story.append(p("No finding generated under the configured rules.", "SmallText"))
            else:
                for _, f in subset.iterrows():
                    finding = str(f.get("finding", ""))
                    confidence = fmt(f.get("confidence_pct"), "%", 0)
                    story.append(p(
                        f"• {finding} "
                        f"<font color='#666666'>(rule {f.get('rule_id', 'N/A')}; "
                        f"confidence score {confidence})</font>",
                        "SmallText"
                    ))
            story.append(Spacer(1, 2*mm))

    story.append(PageBreak())
    story += [
        p(f"{company_id} — Trends and Observations", "ReportTitle"),
        p("3. Available financial history", "SectionHeading"),
    ]

    if not history.empty:
        columns = [
            ("year", "Year"),
            ("profitandloss_sales", "Revenue"),
            ("profitandloss_net_profit", "Net profit"),
            ("profitandloss_operating_profit", "Operating profit"),
            ("cashflow_operating_activity", "Operating cash flow"),
            ("financial_ratios_free_cash_flow_cr", "Free cash flow"),
            ("balancesheet_borrowings", "Borrowings"),
        ]
        available = [(col, label) for col, label in columns if col in history.columns]
        table_rows = [[label for _, label in available]]
        for _, h in history.sort_values("year").tail(5).iterrows():
            table_rows.append([
                fmt(h.get(col), decimals=0) if col == "year"
                else fmt(h.get(col), decimals=2)
                for col, _ in available
            ])
        story.append(make_table(table_rows, font_size=7))
    else:
        story.append(p("No matching historical records were found.", "SmallText"))

    story += [
        Spacer(1, 4*mm),
        p("4. Latest year-over-year pattern changes", "SectionHeading"),
    ]
    if patterns.empty:
        story.append(p("No pattern-change comparisons were available for this company.", "SmallText"))
    else:
        pattern_rows = [[
            "Metric", "Previous year", "Latest year", "Change", "Direction"
        ]]
        for _, item in patterns.head(5).iterrows():
            pattern_rows.append([
                str(item.get("metric_label", item.get("metric", ""))),
                fmt(item.get("previous_value")),
                fmt(item.get("latest_value")),
                fmt(item.get("absolute_change")),
                str(item.get("direction", "N/A")),
            ])
        story.append(make_table(pattern_rows, font_size=7))

    story += [
        Spacer(1, 5*mm),
        p("Interpretation and limitations", "SectionHeading"),
        p(
            "This tearsheet summarizes the available project dataset and configured "
            "rule-based indicators. Confidence scores are rule scores, not probabilities. "
            "A missing finding does not by itself establish that a company has no risks. "
            "Financial values and reporting years may differ across companies. "
            "This report is analytical information, not investment advice.",
            "SmallText"
        ),
    ]
    doc.build(story)
    return path

def build_sector_report(sector, latest, findings, cashflow):
    path = SECTOR_DIR / f"{safe_name(sector)}_sector_report.pdf"
    doc = SimpleDocTemplate(
        str(path), pagesize=landscape(A4),
        rightMargin=12*mm, leftMargin=12*mm,
        topMargin=12*mm, bottomMargin=12*mm
    )
    companies = latest[latest["broad_sector"].astype(str) == str(sector)].copy()
    story = [
        p(f"{sector} — Sector Report", "ReportTitle"),
        p(f"Companies included: {companies['company_id'].nunique()}", "SmallText"),
        Spacer(1, 5*mm),
    ]

    review_mask = (
        companies["panel_review_required"].fillna(False).astype(bool)
        | companies["engine_review_required"].fillna(False).astype(bool)
    )
    review_companies = sorted(
        companies.loc[review_mask, "company_id"].astype(str).unique()
    )
    if review_companies:
        story.append(p(
            "<b>DATA QUALITY WARNING:</b> Unresolved source variants affect "
            "one or more latest company records in this sector. Verify affected "
            "figures before interpreting sector comparisons. Companies flagged: "
            + ", ".join(review_companies),
            "SmallText",
        ))
        story.append(Spacer(1, 2*mm))

    story.append(p("Latest available company metrics", "SectionHeading"))
    cols = [
        ("company_id", "Company"),
        ("year", "Year"),
        ("engine_net_profit_margin_pct", "Net margin %"),
        ("engine_operating_profit_margin_pct", "Operating margin %"),
        ("engine_return_on_equity_pct", "ROE %"),
        ("engine_debt_to_equity", "Debt/equity"),
        ("engine_interest_coverage", "Interest coverage"),
        ("free_cash_flow_cr", "FCF Cr"),
        ("composite_quality_score", "Quality score"),
    ]
    available = [(c, label) for c, label in cols if c in companies.columns]
    rows = [[label for _, label in available]]
    for _, r in companies.sort_values("company_id").iterrows():
        rows.append([
            str(r.get(c, "")) if c == "company_id"
            else fmt(r.get(c), decimals=2)
            for c, _ in available
        ])
    story.append(make_table(rows, font_size=7))

    sector_findings = findings[
        findings["company_id"].astype(str).isin(companies["company_id"].astype(str))
    ]
    story += [Spacer(1, 4*mm), p("Rule-based finding counts", "SectionHeading")]
    if sector_findings.empty:
        story.append(p("No findings available for this sector.", "SmallText"))
    else:
        counts = sector_findings.groupby("finding_type").size().to_dict()
        story.append(p(
            f"Pros: {counts.get('pro', 0)} | Cons: {counts.get('con', 0)}. "
            "These are rule-trigger counts, not independent measures of company quality.",
            "SmallText"
        ))

    if not cashflow.empty and "sector" in cashflow.columns:
        subset = cashflow[cashflow["sector"].astype(str) == str(sector)]
        if not subset.empty:
            story += [Spacer(1, 3*mm), p("Cash-flow intelligence", "SectionHeading")]
            crows = [["Company", "CFO quality", "Capex intensity", "FCF CAGR", "Distress flag"]]
            for _, r in subset.head(30).iterrows():
                crows.append([
                    str(r.get("company_id", "")),
                    str(r.get("cfo_quality_label", "N/A")),
                    fmt(r.get("capex_intensity_pct"), "%"),
                    fmt(r.get("fcf_cagr_5yr"), "%"),
                    str(r.get("distress_flag", "N/A")),
                ])
            story.append(make_table(crows, font_size=7))

    story += [
        Spacer(1, 4*mm),
        p(
            "Coverage reflects the available ratio-engine universe. The wider financial "
            "panel may contain additional companies not represented in this sector report.",
            "SmallText"
        ),
    ]
    doc.build(story)
    return path

def build_portfolio_report(latest, findings, patterns, cashflow):
    path = PORTFOLIO_DIR / "portfolio_summary.pdf"
    doc = SimpleDocTemplate(
        str(path), pagesize=A4,
        rightMargin=15*mm, leftMargin=15*mm,
        topMargin=14*mm, bottomMargin=14*mm
    )
    story = [
        p("Nifty 100 — Portfolio Analytics Summary", "ReportTitle"),
        p("Project-generated financial analysis | Not investment advice", "SmallText"),
        Spacer(1, 6*mm),
    ]

    review_mask = (
        latest["panel_review_required"].fillna(False).astype(bool)
        | latest["engine_review_required"].fillna(False).astype(bool)
    )
    review_companies = sorted(
        latest.loc[review_mask, "company_id"].astype(str).unique()
    )
    if review_companies:
        story.append(p(
            "<b>DATA QUALITY WARNING:</b> Unresolved financial source variants "
            "affect the latest records for some companies. Portfolio and sector "
            "summaries may include figures that require verification. Do not "
            "interpret affected comparisons as fully reconciled. Companies flagged: "
            + ", ".join(review_companies),
            "SmallText",
        ))
        story.append(Spacer(1, 3*mm))

    story.append(p("1. Coverage and dataset summary", "SectionHeading"))
    summary = [
        ["Measure", "Result"],
        ["Companies in ratio engine", str(latest["company_id"].nunique())],
        ["Sectors represented", str(latest["broad_sector"].nunique())],
        ["Pros/cons findings", str(len(findings))],
        ["Companies with pattern-change records", str(patterns["company_id"].nunique()) if not patterns.empty else "0"],
        ["Pattern-change comparisons", str(len(patterns))],
        ["Companies in cash-flow intelligence", str(cashflow["company_id"].nunique()) if "company_id" in cashflow else "N/A"],
    ]
    story.append(make_table(summary, [85*mm, 65*mm]))

    story += [
        Spacer(1, 5*mm),
        p("2. Sector coverage", "SectionHeading"),
    ]
    sector_rows = [["Sector", "Companies", "Average quality score"]]
    for sector, group in latest.groupby("broad_sector", dropna=False):
        score = pd.to_numeric(group.get("composite_quality_score"), errors="coerce")
        sector_rows.append([
            str(sector),
            str(group["company_id"].nunique()),
            fmt(score.mean() if score is not None else float("nan")),
        ])
    story.append(make_table(sector_rows, [80*mm, 35*mm, 55*mm]))

    story += [
        Spacer(1, 5*mm),
        p("3. Company quality-score distribution", "SectionHeading"),
    ]
    scores = pd.to_numeric(latest["composite_quality_score"], errors="coerce").dropna()
    if not scores.empty:
        score_summary = [
            ["Statistic", "Value"],
            ["Companies with a score", str(len(scores))],
            ["Mean", fmt(scores.mean())],
            ["Median", fmt(scores.median())],
            ["Minimum", fmt(scores.min())],
            ["Maximum", fmt(scores.max())],
        ]
        story.append(make_table(score_summary, [85*mm, 65*mm]))
    else:
        story.append(p("No numeric composite quality scores were available.", "SmallText"))

    story += [
        PageBreak(),
        p("Portfolio Summary — Findings and Methodology", "ReportTitle"),
        p("4. Pros and cons finding distribution", "SectionHeading"),
    ]
    if not findings.empty:
        counts = findings.groupby("finding_type").size().to_dict()
        story.append(make_table([
            ["Finding type", "Count"],
            ["Pros", str(counts.get("pro", 0))],
            ["Cons", str(counts.get("con", 0))],
        ], [85*mm, 65*mm]))
        story.append(Spacer(1, 4*mm))
        story.append(p("Most common triggered rules", "SectionHeading"))
        top_rules = findings.groupby(
            ["finding_type", "rule_id", "finding"], dropna=False
        ).size().reset_index(name="count").sort_values("count", ascending=False).head(15)
        rows = [["Type", "Rule", "Finding", "Count"]]
        for _, r in top_rules.iterrows():
            rows.append([
                str(r["finding_type"]), str(r["rule_id"]),
                p(str(r["finding"]), "SmallText"), str(r["count"])
            ])
        story.append(make_table(rows, font_size=7))
    else:
        story.append(p("No pros/cons findings were available.", "SmallText"))

    story += [
        Spacer(1, 5*mm),
        p("5. Interpretation, coverage, and limitations", "SectionHeading"),
        p(
            "The report uses the latest available ratio-engine record for each company. "
            "Company reporting years can differ. Sector summaries describe the 92-company "
            "ratio-engine universe and should not be interpreted as complete coverage of "
            "every company in the wider financial panel. Rule-based findings depend on "
            "configured thresholds and available data. Confidence scores are not calibrated "
            "probabilities, and absent findings do not establish an absence of risk. "
            "Historical changes are descriptive and do not establish causation. "
            "Validate source data and accounting comparability before using the outputs "
            "for decisions. This report is not investment advice.",
            "SmallText"
        ),
    ]
    doc.build(story)
    return path

def main():
    engine = load_csv(ENGINE_PATH)
    panel = load_csv(PANEL_PATH)
    findings = load_csv(PROS_PATH)
    patterns = load_csv(PATTERN_PATH)
    capital = load_csv(CAPITAL_PATH)

    cashflow = (
        pd.read_excel(CASHFLOW_PATH)
        if CASHFLOW_PATH.exists()
        else pd.DataFrame()
    )

    for df in [engine, panel, findings, patterns, capital]:
        if "company_id" in df.columns:
            df["company_id"] = df["company_id"].astype(str).str.strip()

    latest = latest_per_company(engine)

    # Identify company-years with unresolved financial source variants.
    panel_review = pd.DataFrame()
    required_review_cols = {
        "company_id", "year",
        "financial_ratios_ambiguous",
        "cashflow_ambiguous",
        "balancesheet_ambiguous",
        "profitandloss_ambiguous",
    }
    if required_review_cols.issubset(panel.columns):
        panel_review = panel[
            ["company_id", "year",
             "financial_ratios_ambiguous",
             "cashflow_ambiguous",
             "balancesheet_ambiguous",
             "profitandloss_ambiguous"]
        ].copy()
        panel_review["year"] = pd.to_numeric(
            panel_review["year"], errors="coerce"
        )
        for flag in [
            "financial_ratios_ambiguous",
            "cashflow_ambiguous",
            "balancesheet_ambiguous",
            "profitandloss_ambiguous",
        ]:
            panel_review[flag] = (
                panel_review[flag]
                .fillna(True)
                .astype(str)
                .str.strip()
                .str.lower()
                .isin(["true", "1", "yes"])
            )

        panel_review["panel_review_required"] = panel_review[
            [
                "financial_ratios_ambiguous",
                "cashflow_ambiguous",
                "balancesheet_ambiguous",
                "profitandloss_ambiguous",
            ]
        ].any(axis=1)

        latest_review = (
            panel_review.sort_values(["company_id", "year"])
            .groupby("company_id", as_index=False)
            .tail(1)[["company_id", "year", "panel_review_required"]]
        )
        latest = latest.merge(
            latest_review,
            on=["company_id", "year"],
            how="left",
        )
    else:
        latest["panel_review_required"] = False

    latest["panel_review_required"] = (
        latest["panel_review_required"].fillna(False).astype(bool)
    )
    latest["engine_review_required"] = False
    if "record_status" in latest.columns:
        latest["engine_review_required"] |= (
            latest["record_status"].astype(str).str.upper()
            == "VARIANT_REVIEW"
        )
    if "record_count" in latest.columns:
        counts = pd.to_numeric(latest["record_count"], errors="coerce")
        latest["engine_review_required"] |= counts.gt(1).fillna(False)

    generated = []

    for _, row in latest.iterrows():
        company_id = str(row["company_id"])
        history = panel[panel["company_id"] == company_id].copy()
        company_findings = findings[findings["company_id"] == company_id].copy()
        company_patterns = patterns[patterns["company_id"] == company_id].copy()
        generated.append(build_tearsheet(
            company_id, row, history, company_findings, company_patterns
        ))

    sectors = sorted(latest["broad_sector"].dropna().astype(str).unique())
    for sector in sectors:
        generated.append(build_sector_report(sector, latest, findings, cashflow))

    generated.append(build_portfolio_report(latest, findings, patterns, cashflow))

    tearsheets = sorted(TEARSHEET_DIR.glob("*_tearsheet.pdf"))
    sector_pdfs = sorted(SECTOR_DIR.glob("*_sector_report.pdf"))
    portfolio_pdfs = sorted(PORTFOLIO_DIR.glob("*.pdf"))

    print("\n=== PDF REPORT GENERATION ===")
    print("Companies in ratio engine:", latest["company_id"].nunique())
    print("Actual sectors:", len(sectors), sectors)
    print("Company tearsheets:", len(tearsheets))
    print("Sector reports:", len(sector_pdfs))
    print("Portfolio reports:", len(portfolio_pdfs))

    small_files = []
    for path in tearsheets:
        size = path.stat().st_size
        if size < 30_000:
            small_files.append((path.name, size))

    if small_files:
        print("WARNING: tearsheets smaller than 30 KB:", len(small_files))
        for name, size in small_files[:10]:
            print(f"  {name}: {size:,} bytes")
    else:
        print("All company tearsheets meet the 30 KB size target.")

    print("\nGenerated report directories:")
    print("Company:", TEARSHEET_DIR.relative_to(ROOT))
    print("Sector:", SECTOR_DIR.relative_to(ROOT))
    print("Portfolio:", PORTFOLIO_DIR.relative_to(ROOT))

if __name__ == "__main__":
    main()
