"""Build the public landing page and study-note index from computed outputs."""
from __future__ import annotations

import html
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "deliverables"
STUDY_ROOT = ROOT / "studies"

TITLES = {
    "01": "Market & Macro Monitor",
    "02": "Quantitative Company Analysis",
    "03": "Strategy Research & Backtesting",
    "04": "Portfolio Construction & Allocation",
    "05": "Positions, Leverage & Carry",
    "06": "Portfolio Risk & What-if Analysis",
    "07": "Execution Costs & Slippage",
    "08": "Performance & Investor Reporting",
    "09": "Quantitative Model Validation",
    "10": "Derivatives & Pricing",
    "11": "Market Data Platform & Reconciliation",
    "12": "AI-assisted Quantitative Research",
}
SOURCES = {
    "01": ("U.S. Treasury daily yield curve", "https://home.treasury.gov/treasury-daily-interest-rate-xml-feed"),
    "02": ("SEC Company Facts / EDGAR", "https://www.sec.gov/edgar/sec-api-documentation"),
    "03": ("U.S. Treasury daily yield curve", "https://home.treasury.gov/treasury-daily-interest-rate-xml-feed"),
    "04": ("U.S. Treasury daily yield curve", "https://home.treasury.gov/treasury-daily-interest-rate-xml-feed"),
    "05": ("CFTC Traders in Financial Futures", "https://publicreporting.cftc.gov/Commitments-of-Traders/TFF-Futures-Only/gpe5-46if"),
    "06": ("U.S. Treasury daily yield curve", "https://home.treasury.gov/treasury-daily-interest-rate-xml-feed"),
    "07": ("Cboe BZX Rule 605 monthly OES reports", "https://www.cboe.com/markets/us/equities/regulation/605/bzx"),
    "08": ("U.S. Treasury daily yield curve", "https://home.treasury.gov/treasury-daily-interest-rate-xml-feed"),
    "09": ("U.S. Treasury daily yield curve", "https://home.treasury.gov/treasury-daily-interest-rate-xml-feed"),
    "10": ("U.S. Treasury daily 3-month par yield", "https://home.treasury.gov/treasury-daily-interest-rate-xml-feed"),
    "11": ("Treasury, SEC and CFTC public feeds", "https://www.sec.gov/about/developer-resources"),
    "12": ("SEC Company Facts / EDGAR", "https://www.sec.gov/edgar/sec-api-documentation"),
}


def money_bn(value):
    return f"${float(value) / 1e9:,.1f}bn" if value is not None else "not available"


def highlight(sid: str, m: dict) -> str:
    if sid == "01":
        return f"{m['source_rows']:,} daily observations; the 10y–2y curve was inverted on {m['inverted_curve_share_pct']:.1f}% of observed days."
    if sid == "02":
        rev = m["latest_revenue_usd"]
        return f"SEC annual facts for 3 issuers, FY 2020–2026; latest revenues: AAPL {money_bn(rev['AAPL'])}, MSFT {money_bn(rev['MSFT'])}, NVDA {money_bn(rev['NVDA'])}."
    if sid == "03":
        return f"Out-of-sample 5-session curve-change MAE: {m['oos_mae_bp']:.2f} bp vs {m['mean_baseline_mae_bp']:.2f} bp baseline; the signal did not improve MAE."
    if sid == "04":
        w = m["weights"]["min_variance_train_2020_2023"]
        return f"Training-period minimum variance selected {w['bond_2y_proxy_return']:.0%} 2y proxy; out-of-sample proxy volatility {m['min_variance_oos']['annualized_volatility_pct']:.2f}% vs {m['equal_weight_oos']['annualized_volatility_pct']:.2f}% equal-weight."
    if sid == "05":
        return f"CFTC TFF futures-only records across {m['contracts']} selected Treasury and S&P futures contracts; latest report {m['latest_report_date']}."
    if sid == "06":
        return f"Illustrative duration proxy: historical one-day 95% VaR {m['daily_historical_var_95_pct']:.2f}%; hypothetical +100bp parallel shock {m['hypothetical_parallel_plus_100bp_loss_pct']:.1f}%."
    if sid == "07":
        return f"Grouped Cboe BZX Rule 605 reports for {', '.join(m['report_months'])}: {m['market_order_rows']} market-order buckets analysed."
    if sid == "08":
        return f"Hypothetical duration-only portfolio: {m['months']} full months; proxy cumulative change {m['cumulative_proxy_return_pct']:.1f}% through {m['end_month']}. Not fund performance."
    if sid == "09":
        return f"Out-of-sample MAE {m['model_mae_bp']:.2f} bp vs baseline {m['baseline_mae_bp']:.2f} bp; direction hit rate {m['model_direction_hit_pct']:.1f}%."
    if sid == "10":
        return f"Hypothetical European call value {m['model_price']:.2f} at observed 3-month Treasury rate {m['treasury_3m_rate_pct']:.2f}%; other contract inputs are assumed."
    if sid == "11":
        checks = m["checks"]
        return f"Lineage and coverage checks across {len(checks)} sources; duplicate primary keys: {sum(x['key_duplicates'] for x in checks)}."
    return f"Evidence ledger contains {m['evidence_rows']} issuer records; deterministic extraction only, with no external LLM call."


def chart_of(sid: str) -> str | None:
    pngs = sorted((OUT / sid).glob("*.png"))
    return pngs[0].name if pngs else None


def title_status(sid: str) -> str:
    if sid in {"04", "06", "08", "10"}:
        return "Computed with stated hypothetical inputs"
    if sid == "07":
        return "Computed from public market-center summaries"
    if sid == "12":
        return "Computed evidence workflow; no LLM"
    return "Computed from public source data"


def make_page() -> str:
    cards = []
    for sid, title in TITLES.items():
        m = json.loads((OUT / sid / "metrics.json").read_text())
        source, url = SOURCES[sid]
        cards.append('<article class="card">' +
            (f'<a href="deliverables/{sid}/index.html"><img class="thumb" loading="lazy" src="deliverables/{sid}/{chart_of(sid)}" alt="{html.escape(title)} chart"></a>' if chart_of(sid) else "") + f'''<div class="row"><span class="num">{sid}</span><span class="pill">{html.escape(title_status(sid))}</span></div><h2>{html.escape(title)}</h2><p class="source">Source: <a href="{url}">{html.escape(source)}</a></p><p>{html.escape(highlight(sid,m))}</p><a class="open" href="deliverables/{sid}/index.html">Open study, methodology and downloads ↗</a></article>'''
        )
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ProQuant Analytics | Public Data Studies</title><style>
:root{--ink:#102039;--muted:#5c6c82;--bg:#f3f6fa;--blue:#174db7;--line:#dbe3ed}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 system-ui,-apple-system,Segoe UI,sans-serif}.hero{background:linear-gradient(120deg,#0c1b32,#12396b);color:white;padding:58px max(calc((100vw - 1120px)/2),24px) 50px}.eyebrow{text-transform:uppercase;letter-spacing:.12em;color:#a7caff;font-size:.78rem;font-weight:750}.hero h1{font-size:clamp(2rem,5vw,3.45rem);line-height:1.08;max-width:860px;margin:.7rem 0}.hero p{max-width:760px;color:#d9e6f6}.wrap{max-width:1120px;margin:0 auto;padding:14px 24px 54px}.banner{background:#fff4d6;border:1px solid #edcf7b;color:#553c00;border-radius:12px;padding:16px 18px;margin-bottom:18px}.downloads{display:flex;gap:12px;flex-wrap:wrap;margin:15px 0 24px}.button{display:inline-block;padding:10px 15px;border-radius:9px;background:var(--blue);color:white;text-decoration:none;font-weight:700}.button.secondary{background:white;color:var(--blue);border:1px solid var(--line)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(310px,100%),1fr));gap:18px}.card{background:white;border:1px solid var(--line);border-radius:15px;padding:22px;box-shadow:0 6px 20px #172b4610;min-width:0}.thumb{display:block;width:100%;aspect-ratio:2/1;object-fit:cover;object-position:left top;border:1px solid #e3eaf2;border-radius:10px;margin-bottom:12px;background:#fff}.row{display:flex;align-items:center;justify-content:space-between;gap:10px}.num{font-size:.8rem;color:var(--blue);font-weight:800;letter-spacing:.08em}.pill{font-size:.68rem;border:1px solid #d8e5fb;background:#f1f6ff;color:#17428f;border-radius:20px;padding:4px 8px}.card h2{font-size:1.22rem;line-height:1.3;margin:.65rem 0}.source{font-size:.9rem;color:var(--muted)}.card p{font-size:.93rem}.open{display:inline-block;margin-top:9px;color:var(--blue);font-weight:750;text-decoration:none}.foot{border-top:1px solid var(--line);padding:22px 0;color:var(--muted);font-size:.9rem}@media(max-width:600px){.hero{padding:40px 22px}.wrap{padding-inline:16px}}</style></head><body><header class="hero"><div class="eyebrow">ProQuant Analytics · Public research</div><h1>Quantitative studies built from public evidence</h1><p>Twelve studies, with real public observations where available, computed outputs, sources and limitations. No case is presented as client work.</p></header><main class="wrap"><div class="banner"><b>Read the scope:</b> This is a public-data analytical portfolio, not twelve customer engagements. Studies 04, 06, 08 and 10 use explicitly hypothetical portfolio or contract assumptions alongside observed data. Study 03/09 test a curve-change signal, not strategy returns. See each methodology before interpreting the figures. No investment advice.</div><div class="downloads"><a class="button" href="deliverables/ProQuant_Public_Studies.xlsx">Download results workbook</a><a class="button secondary" href="deliverables/ProQuant_Public_Studies.zip">Download complete study pack</a><a class="button secondary" href="https://github.com/AbduWars/proquant-analytics-case-studies">Browse source and reproducibility scripts</a></div><div class="grid">''' + "".join(cards) + '''</div><div class="foot"><p><b>Source rights and attribution:</b> SEC website information may be copied with citation; its data APIs require fair-access controls. CFTC government information is public domain. Treasury public feed and Cboe monthly report links are cited; raw inputs remain local and are not included in this repository. Cboe warns that Rule 605 data are unaudited and may not be directly comparable.</p><p><a href="https://www.sec.gov/about/privacy-information">SEC redistribution note</a> · <a href="https://www.sec.gov/about/developer-resources">SEC API rules</a> · <a href="https://www.cftc.gov/data">CFTC open data</a> · <a href="https://home.treasury.gov/treasury-daily-interest-rate-xml-feed">Treasury rates</a> · <a href="https://www.cboe.com/markets/us/equities/regulation/605/bzx">Cboe Rule 605</a></p><p>All calculations are reproducible from the scripts and published endpoints, subject to source updates. Built from public data retrieved 18 November 2026.</p></div></main></body></html>'''


def write_root_notes() -> None:
    for sid, title in TITLES.items():
        m = json.loads((OUT / sid / "metrics.json").read_text())
        source, url = SOURCES[sid]
        report = f"../deliverables/{sid}/index.html"
        methodology = (OUT / sid / "METHODOLOGY.md").read_text()
        (STUDY_ROOT / f"{sid}.md").write_text(
            f"# {sid} · {title}\n\n**Status:** {title_status(sid)} · **Source:** [{source}]({url}) · [Open the full study page]({report})\n\n> {highlight(sid, m)}\n\n" + (f"![{title} chart](../deliverables/{sid}/{chart_of(sid)})\n\n" if chart_of(sid) else "") + f"{methodology}\n\nThis is a public-data study, not a client engagement. Not investment advice.\n"
        )


def write_readme() -> None:
    lines = [
        "# ProQuant Analytics — Public-Data Studies",
        "",
        "A reproducible public portfolio of 12 quantitative studies. These are public-data analyses, **not client engagements**. Source data remain in a local `.cache/` folder and are excluded from Git; selected derived results and report files are included.",
        "",
        "## Browse and download",
        "",
        "- [Interactive study gallery](index.html)",
        "- [Combined results workbook](deliverables/ProQuant_Public_Studies.xlsx)",
        "- [Complete study-pack ZIP](deliverables/ProQuant_Public_Studies.zip)",
        "- [Per-study result pages](deliverables/)",
        "- [Data source rights and caveats](DATA_SOURCES.md)",
        "",
        "## Rebuild",
        "",
        "```bash",
        "python -m venv .venv && . .venv/bin/activate",
        "pip install -r requirements.txt",
        "python scripts/download_public_data.py",
        "python scripts/build_studies.py",
        "python scripts/build_gallery.py",
        "pytest -q",
        "```",
        "",
        "Raw downloads are saved under `.cache/` and ignored by Git. The generated deliverables are built from the exact source endpoints in each report. Re-running refreshes the source data, so later results may differ.",
        "",
        "## Study map",
        "",
        "| # | Study | Data and key scope |",
        "|---|---|---|",
    ]
    for sid, title in TITLES.items():
        lines.append(f"| {sid} | [{title}](studies/{sid}.md) | {title_status(sid)} |")
    lines.extend(
        [
            "",
            "## Source attribution and reuse",
            "",
            "- **U.S. Treasury:** [daily yield curve XML feed](https://home.treasury.gov/treasury-daily-interest-rate-xml-feed); outputs are cited derived analyses, not bulk raw copies.",
            "- **SEC:** [EDGAR Company Facts API](https://www.sec.gov/edgar/sec-api-documentation). SEC states information presented on sec.gov may be copied or further distributed with appropriate citation; automated downloads must follow fair-access rules, including the 10 requests/second ceiling and a descriptive User-Agent.",
            "- **CFTC:** [TFF futures-only dataset](https://publicreporting.cftc.gov/Commitments-of-Traders/TFF-Futures-Only/gpe5-46if). CFTC identifies government information on its site as public domain. This study retains selected aggregate contract-category observations only.",
            "- **Cboe:** [BZX Rule 605 reports](https://www.cboe.com/markets/us/equities/regulation/605/bzx). Only grouped medians are published; the source warns that reports are unaudited and may not be directly comparable.",
            "",
            "## What the figures mean",
            "",
            "Treasury yields are indicative par yields, not bond total returns. Portfolio and option examples use explicitly stated hypothetical inputs. The forecast studies test changes in a yield-curve statistic, not market returns or a trading strategy. The execution study uses a market-center summary, not client order-level fills. No client, private dataset, credential, template source, or internal manual is included.",
            "",
            "The figures are research demonstrations, not investment advice, trade instructions, executable quotes, or suitability assessments.",
            "",
        ]
    )
    (ROOT / "README.md").write_text("\n".join(lines))


def make_archive() -> None:
    zip_path = OUT / "ProQuant_Public_Studies.zip"
    shutil.copy2(ROOT / "DATA_SOURCES.md", OUT / "DATA_SOURCES.md")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=8) as zf:
        for p in OUT.rglob("*"):
            if p.is_file() and p != zip_path:
                zf.write(p, p.relative_to(OUT))


def main() -> None:
    if not (OUT / "manifest.json").exists():
        raise SystemExit("Run scripts/build_studies.py first")
    (ROOT / "index.html").write_text(make_page())
    write_root_notes()
    write_readme()
    make_archive()
    print("Updated landing page, 12 study notes, README, and downloadable ZIP.")


if __name__ == "__main__":
    main()
