"""Build 12 public-data study packs from official source files in .cache/."""
from __future__ import annotations

import json
import math
import re
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from openpyxl import Workbook
from scipy.optimize import minimize
from scipy.stats import linregress

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache"
OUT = ROOT / "deliverables"
TREASURY_URL = "https://home.treasury.gov/treasury-daily-interest-rate-xml-feed"
SEC_URL = "https://www.sec.gov/edgar/sec-api-documentation"
CFTC_URL = "https://publicreporting.cftc.gov/Commitments-of-Traders/TFF-Futures-Only/gpe5-46if"
CBOE_URL = "https://www.cboe.com/markets/us/equities/regulation/605/bzx"

STUDIES = {
    "01": "Market & Macro Monitor",
    "02": "Quantitative Company Analysis",
    "03": "Strategy Research & Backtesting",
    "04": "Portfolio Construction & Allocation",
    "05": "Positions, Leverage & Carry",
    "06": "Portfolio Risk & What-if Analysis",
    "07": "Execution Costs & Slippage",
    "08": "Performance & Investor Reporting",
    "09": "Model Validation",
    "10": "Derivatives & Pricing",
    "11": "Market Data Platform & Reconciliation",
    "12": "AI-assisted Quantitative Research",
}


def safe_float(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else np.nan
    except (TypeError, ValueError):
        return np.nan


def read_treasury() -> pd.DataFrame:
    ns = {"d": "http://schemas.microsoft.com/ado/2007/08/dataservices"}
    records = []
    for path in sorted(CACHE.glob("treasury-*.xml")):
        root = ET.parse(path).getroot()
        for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
            props = entry.find(".//{http://schemas.microsoft.com/ado/2007/08/dataservices/metadata}properties")
            if props is None:
                continue
            row = {el.tag.split("}")[-1]: el.text for el in props}
            row["date"] = pd.to_datetime(row.pop("NEW_DATE"), errors="coerce")
            records.append(row)
    if not records:
        raise FileNotFoundError("No Treasury XML files in .cache; run scripts/download_public_data.py")
    df = pd.DataFrame(records).drop_duplicates("date").sort_values("date").set_index("date")
    df = df.apply(pd.to_numeric, errors="coerce")
    required = ["BC_2YEAR", "BC_5YEAR", "BC_10YEAR", "BC_30YEAR"]
    missing = [c for c in required if c not in df]
    if missing:
        raise ValueError(f"Treasury fields missing: {missing}")
    df["slope_10y_2y"] = df["BC_10YEAR"] - df["BC_2YEAR"]
    df["slope_5y_2y"] = df["BC_5YEAR"] - df["BC_2YEAR"]
    df["slope_30y_5y"] = df["BC_30YEAR"] - df["BC_5YEAR"]
    return df


TAGS = {
    "revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"),
    "operating_income": ("OperatingIncomeLoss",),
    "net_income": ("NetIncomeLoss",),
    "assets": ("Assets",),
    "liabilities": ("Liabilities",),
    "equity": ("StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
}


def company_facts() -> pd.DataFrame:
    out = []
    for ticker in ("AAPL", "MSFT", "NVDA"):
        path = CACHE / f"{ticker}-companyfacts.json"
        if not path.exists():
            raise FileNotFoundError(f"Missing {path.name}; run scripts/download_public_data.py")
        data = json.loads(path.read_text())
        facts = data.get("facts", {}).get("us-gaap", {})
        by_year = {}
        for metric, alternatives in TAGS.items():
            best_by_year = {}
            for tag_priority, tag in enumerate(alternatives):
                fact = facts.get(tag, {})
                for unit, entries in fact.get("units", {}).items():
                    if unit not in ("USD", "shares"):
                        continue
                    for e in entries:
                        if e.get("form") != "10-K" or e.get("fp") != "FY":
                            continue
                        if metric in {"revenue", "operating_income", "net_income", "operating_cash_flow"}:
                            days = (pd.Timestamp(e["end"]) - pd.Timestamp(e.get("start", e["end"]))).days
                            if not 330 <= days <= 400:
                                continue
                        candidate = (e.get("filed", ""), -tag_priority, e.get("end", ""), e.get("val"))
                        # Use the period's actual end year: SEC `fy` can refer
                        # to the filer fiscal year assigned to the filing, while
                        # end is the date of the financial period being measured.
                        fy = int(str(e.get("end", "0000"))[:4])
                        if fy not in best_by_year or candidate[:2] > best_by_year[fy][:2]:
                            best_by_year[fy] = candidate
            for fy, (filed, _priority, end, value) in best_by_year.items():
                by_year.setdefault(fy, {"ticker": ticker, "issuer": data.get("entityName", ticker), "fiscal_year": fy})
                prior = by_year[fy].get(metric)
                # Prefer the most recently filed annual observation for this fiscal year.
                if prior is None or filed >= by_year[fy].get(metric + "_filed", ""):
                    by_year[fy][metric] = safe_float(value)
                    by_year[fy][metric + "_filed"] = filed
                    by_year[fy][metric + "_end"] = end
        for row in by_year.values():
            out.append(row)
    df = pd.DataFrame(out)
    if df.empty:
        raise ValueError("No annual SEC facts could be extracted")
    df = df[df["fiscal_year"] >= 2020].sort_values(["ticker", "fiscal_year"])
    for metric in ("revenue", "operating_income", "net_income", "assets", "liabilities", "equity", "operating_cash_flow"):
        if metric not in df:
            df[metric] = np.nan
    df["revenue_yoy_pct"] = df.groupby("ticker")["revenue"].pct_change(fill_method=None) * 100
    df["operating_margin_pct"] = df["operating_income"] / df["revenue"] * 100
    df["net_margin_pct"] = df["net_income"] / df["revenue"] * 100
    df["liabilities_to_assets_pct"] = df["liabilities"] / df["assets"] * 100
    return df


def cot_positions() -> pd.DataFrame:
    rows = json.loads((CACHE / "cftc-tff-selected.json").read_text())
    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError("CFTC TFF file is empty")
    df["date"] = pd.to_datetime(df["report_date_as_yyyy_mm_dd"], errors="coerce")
    df = df.rename(
        columns={
            "lev_money_positions_long": "leveraged_money_positions_long",
            "lev_money_positions_short": "leveraged_money_positions_short",
        }
    )
    numeric = ["open_interest_all", "leveraged_money_positions_long", "leveraged_money_positions_short", "asset_mgr_positions_long", "asset_mgr_positions_short"]
    for c in numeric:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["leveraged_money_net"] = df["leveraged_money_positions_long"] - df["leveraged_money_positions_short"]
    df["asset_manager_net"] = df["asset_mgr_positions_long"] - df["asset_mgr_positions_short"]
    df = df[df["contract_market_name"].isin(["UST 10Y NOTE", "UST 2Y NOTE", "UST 5Y NOTE", "UST BOND", "E-MINI S&P 500", "S&P 500 Consolidated"])].copy()
    return df.sort_values(["contract_market_name", "date"])


def save_csv(study: str, name: str, df: pd.DataFrame) -> Path:
    path = OUT / study / name
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, float_format="%.8g")
    return path


def save_json(study: str, name: str, data) -> Path:
    path = OUT / study / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str, allow_nan=False) + "\n")
    return path


def plot_lines(study: str, title: str, df: pd.DataFrame, columns, ylabel: str, name="chart.png"):
    path = OUT / study / name
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 4.8), constrained_layout=True)
    for column, label in columns:
        ax.plot(df["date"], df[column], label=label, linewidth=1.3)
    ax.set_title(title, loc="left", weight="bold")
    ax.set_ylabel(ylabel)
    ax.grid(alpha=.22)
    ax.legend(frameon=False, ncol=min(4, len(columns)))
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


PALETTE = ["#174db7", "#f08a24", "#1a9e77", "#c2410c", "#7c3aed", "#0891b2"]
ABBREV = {"pct": "%", "bp": "(bp)", "oos": "out-of-sample", "mae": "MAE", "rmse": "RMSE", "var": "VaR",
          "es": "ES", "usd": "(USD)", "yoy": "YoY", "10y": "10y", "2y": "2y", "3m": "3-month", "sec": "SEC"}


def label(key: str) -> str:
    """Turn a metrics key into a readable label: oos_mae_bp -> Out-of-sample MAE (bp)."""
    words = [ABBREV.get(w, w) for w in str(key).split("_")]
    text = " ".join(words).replace(" %", " (%)")
    return text[:1].upper() + text[1:]


def fmt(value) -> str:
    """Display a metric value: rounded numbers, thousands separators, Yes/No for flags."""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    if isinstance(value, (float, np.floating)):
        if not math.isfinite(value):
            return "n/a"
        if abs(value) >= 1e9:
            return f"{value / 1e9:,.1f} bn"
        if abs(value) >= 1000:
            return f"{value:,.0f}"
        return f"{value:,.4f}" if abs(value) < 0.01 and value != 0 else f"{value:,.2f}"
    if value is None:
        return "n/a"
    if isinstance(value, list) and all(not isinstance(x, (dict, list)) for x in value):
        return ", ".join(fmt(x) for x in value)
    return str(value)


def flat_rows(summary: dict, prefix: str = "") -> list[tuple[str, str]]:
    """Flatten one level of nested metrics into (label, value) rows; tables of records are skipped."""
    rows = []
    for key, value in summary.items():
        name = f"{prefix}{label(key)}"
        if isinstance(value, dict):
            rows += flat_rows(value, prefix=f"{name} · ")
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            continue
        else:
            rows.append((name, fmt(value)))
    return rows


def record_tables(summary: dict) -> list[tuple[str, pd.DataFrame]]:
    """Lists of records inside the metrics (e.g. grouped medians) shown as their own tables."""
    out = []
    for key, value in summary.items():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            df = pd.DataFrame(value)
            out.append((label(key), df.map(fmt).rename(columns=label)))
    return out


def plot_bars(study: str, title: str, labels, values, ylabel: str, name: str, colors=None, annotate="{:.2f}"):
    path = OUT / study / name
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 4.8), constrained_layout=True)
    bars = ax.bar([str(x) for x in labels], values, color=colors or PALETTE[: len(values)])
    for bar, v in zip(bars, values):
        ax.annotate(annotate.format(v), (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    ha="center", va="bottom", fontsize=10, xytext=(0, 3), textcoords="offset points")
    ax.set_title(title, loc="left", weight="bold")
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=.22)
    ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def returns_metrics(r: pd.Series) -> dict:
    x = r.dropna()
    if not len(x):
        return {"observations": 0, "annualized_return_pct": None, "annualized_volatility_pct": None, "max_drawdown_pct": None}
    growth = (1 + x).cumprod()
    ann = 252 / len(x)
    return {
        "observations": int(len(x)),
        "annualized_return_pct": float((growth.iloc[-1] ** ann - 1) * 100),
        "annualized_volatility_pct": float(x.std(ddof=1) * np.sqrt(252) * 100),
        "max_drawdown_pct": float((growth / growth.cummax() - 1).min() * 100),
    }


def write_study(study: str, status: str, summary: dict, method: str, source: str, caveats: list[str], data_files: list[str], chart: str | None):
    folder = OUT / study
    folder.mkdir(parents=True, exist_ok=True)
    save_json(study, "metrics.json", summary)
    caveat_html = "".join(f"<li>{x}</li>" for x in caveats)
    files_html = "".join(f'<li><a href="{Path(x).name}">{Path(x).name}</a></li>' for x in data_files)
    chart_html = f'<img class="chart" src="{chart}" alt="Study chart">' if chart else ""
    rows = "".join(f"<tr><th>{html_escape(k)}</th><td>{html_escape(v)}</td></tr>" for k, v in flat_rows(summary))
    rows += "".join(f"</table><h3>{html_escape(name)}</h3><div class='scroll'>{df.to_html(index=False, border=0)}</div><table>" for name, df in record_tables(summary))
    doc = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>{study} · {html_escape(STUDIES[study])}</title><style>body{{font:16px/1.6 system-ui,sans-serif;max-width:940px;margin:40px auto;padding:0 22px;color:#14243a;background:#f4f7fb}}article{{background:white;border:1px solid #dce5ef;border-radius:16px;padding:28px}}h1{{font-size:2rem}}.tag{{color:#154ec1;font-weight:700}}.chart{{width:100%;border:1px solid #e3eaf2;border-radius:10px;margin:14px 0}}table{{border-collapse:collapse;width:100%}}th,td{{padding:9px;border-bottom:1px solid #e5ebf2;text-align:left}}.note{{background:#fff4d6;padding:14px;border-radius:9px}}.scroll{{overflow-x:auto}}td{{font-variant-numeric:tabular-nums}}@media(max-width:600px){{body{{margin:16px auto;padding:0 16px}}article{{padding:18px}}}}</style><article><a href="../../index.html">← All studies</a><p class="tag">STUDY {study} · PUBLIC DATA</p><h1>{html_escape(STUDIES[study])}</h1><p>{html_escape(status)}</p><div class="note"><b>Not client work.</b> Public-source analysis with stated hypothetical inputs where applicable. Not investment advice.</div><h2>Observed results</h2><table>{rows}</table>{chart_html}<h2>Method</h2><p>{html_escape(method)}</p><h2>Source</h2><p><a href="{source}">{source}</a></p><h2>Limitations</h2><ul>{caveat_html}</ul><h2>Files</h2><ul>{files_html}</ul><p>Built {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} from local raw inputs under .cache; raw files are excluded from Git.</p></article></html>'''
    (folder / "index.html").write_text(doc)
    table = "| Measure | Value |\n|---|---|\n" + "".join(f"| {k} | {v} |\n" for k, v in flat_rows(summary))
    for name, df in record_tables(summary):
        table += f"\n**{name}**\n\n| " + " | ".join(df.columns) + " |\n|" + "---|" * len(df.columns) + "\n"
        table += "".join("| " + " | ".join(map(str, r)) + " |\n" for r in df.itertuples(index=False))
    md = f"""## Method\n\n{status} {method}\n\n## Results\n\n{table}\n## Source\n\n{source}\n\n## Limitations\n\n""" + "".join(f"- {c}\n" for c in caveats)
    (folder / "METHODOLOGY.md").write_text(md)


def build_all():
    if not CACHE.exists():
        raise FileNotFoundError("Run scripts/download_public_data.py first")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(exist_ok=True)
    rates = read_treasury()
    rates = rates.loc["2020-01-01":].copy()
    rate_out = rates.reset_index()
    # A compact derived panel only; source raw XML remains local.
    derived = rate_out[["date", "BC_1YEAR", "BC_2YEAR", "BC_5YEAR", "BC_10YEAR", "BC_30YEAR", "slope_10y_2y", "slope_5y_2y", "slope_30y_5y"]].copy()
    rates_path = save_csv("01", "yield_curve_derived.csv", derived)
    yields_metrics = {
        "source_rows": int(len(rates)),
        "first_date": str(rates.index.min().date()),
        "last_date": str(rates.index.max().date()),
        "median_10y_2y_slope_pct_points": float(rates["slope_10y_2y"].median()),
        "inverted_curve_observations": int((rates["slope_10y_2y"] < 0).sum()),
        "inverted_curve_share_pct": float((rates["slope_10y_2y"] < 0).mean() * 100),
        "max_10y_2y_slope_pct_points": float(rates["slope_10y_2y"].max()),
        "min_10y_2y_slope_pct_points": float(rates["slope_10y_2y"].min()),
    }
    plot_lines("01", "U.S. Treasury yields and 10y–2y slope", derived, [("BC_2YEAR", "2-year"), ("BC_10YEAR", "10-year")], "Yield (%)", "yield_curve.png")
    write_study("01", "Completed descriptive analysis of official daily yield observations.", yields_metrics, "Parse Treasury XML and calculate daily constant-maturity curve slopes; report distribution, coverage and inversion share.", TREASURY_URL, ["Par yields are indicative curve estimates, not realized bond total returns.", "No macro causal claim or yield forecast is made."], [str(rates_path)], "yield_curve.png")

    companies = company_facts()
    company_path = save_csv("02", "issuer_fundamentals_derived.csv", companies.drop(columns=[c for c in companies if c.endswith("_filed") or c.endswith("_end")], errors="ignore"))
    latest_companies = companies.sort_values("fiscal_year").groupby("ticker", as_index=False).tail(1)
    company_summary = {"issuers": int(companies.ticker.nunique()), "fiscal_years": f"{int(companies.fiscal_year.min())}-{int(companies.fiscal_year.max())}", "latest_revenue_usd": {r.ticker: (None if pd.isna(r.revenue) else float(r.revenue)) for r in latest_companies.itertuples()}, "latest_filed_date": {r.ticker: str(getattr(r, "revenue_filed", "not available")) for r in latest_companies.itertuples()}}
    company_chart = latest_companies[["ticker", "revenue", "operating_margin_pct", "net_margin_pct"]].melt(id_vars="ticker", var_name="metric", value_name="value")
    save_csv("02", "latest_issuer_comparison.csv", company_chart)
    fig, ax = plt.subplots(figsize=(9,4.5),constrained_layout=True)
    for t,g in companies.groupby("ticker"):
        ax.plot(g.fiscal_year,g.revenue/1e9,marker="o",label=t)
    ax.set_title("Reported annual revenue (SEC XBRL)",loc="left",weight="bold");ax.set_ylabel("USD billions");ax.grid(alpha=.2);ax.legend(frameon=False);fig.savefig(OUT/"02"/"revenue.png",dpi=150);plt.close(fig)
    write_study("02", "Completed annual-filing comparison using SEC XBRL facts for three large U.S. issuers.", company_summary, "For each issuer, select duration facts from annual 10-K filings, retain fiscal year and filed date, then calculate revenue growth, margins and liabilities/assets. The extraction code is visible in scripts/build_studies.py.", SEC_URL, ["XBRL tags can differ across issuers and require analyst review.", "This is descriptive company research; no valuation target or recommendation.", "No share prices or market-cap multiples are included."], [str(company_path), "latest_issuer_comparison.csv"], "revenue.png")

    # Term-spread research signal: predict subsequent five-session change in the
    # 10y-2y spread. This deliberately tests a descriptive signal, not P&L.
    s = rates[["slope_10y_2y", "BC_10YEAR"]].copy()
    s["next5_slope_change_bp"] = (s["slope_10y_2y"].shift(-5) - s["slope_10y_2y"]) * 100
    s["slope_z_252"] = (s["slope_10y_2y"] - s["slope_10y_2y"].rolling(252, min_periods=126).mean()) / s["slope_10y_2y"].rolling(252, min_periods=126).std()
    s = s.dropna()
    train = s.loc[:"2023-12-31"]; test = s.loc["2024-01-01":]
    reg = linregress(train["slope_z_252"], train["next5_slope_change_bp"])
    pred = reg.intercept + reg.slope * test["slope_z_252"]
    baseline = np.repeat(train["next5_slope_change_bp"].mean(), len(test))
    mae = float(np.mean(np.abs(test["next5_slope_change_bp"].values-pred)))
    base_mae = float(np.mean(np.abs(test["next5_slope_change_bp"].values-baseline)))
    strategy = s.reset_index()[["date", "slope_10y_2y", "slope_z_252", "next5_slope_change_bp"]]
    path3 = save_csv("03", "signal_test_observations.csv", strategy)
    metrics3 = {"train_observations": int(len(train)), "test_observations": int(len(test)), "train_through": str(train.index.max().date()), "test_from": str(test.index.min().date()), "oos_mae_bp": mae, "mean_baseline_mae_bp": base_mae, "oos_direction_hit_pct": float((np.sign(pred)==np.sign(test["next5_slope_change_bp"])).mean()*100), "interpretation": "forecast diagnostic only; not a tradable strategy or realized return"}
    plot_lines("03", "Signal input: rolling z-score of the 10y–2y slope (train to 2023, test from 2024)", strategy, [("slope_z_252", "Slope z-score (252 sessions)")], "z-score", "signal.png")
    write_study("03", "Completed time-ordered test of a curve-state research signal against a mean baseline.", metrics3, "Train a one-variable linear diagnostic on 2020–2023 rolling-standardized 10y–2y slope; evaluate five-session forward slope change on 2024–latest. Compare mean absolute error and direction hit rate to a training-mean baseline.", TREASURY_URL, ["The target is a yield-curve change, not instrument P&L.", "No transaction costs, execution, risk-adjusted return or tradability claim.", "No hyperparameter search was performed."], [str(path3)], "signal.png")

    # Hypothetical bond duration-only return series from observed yield changes.
    tenors = ["2YEAR", "5YEAR", "10YEAR", "30YEAR"]
    duration = pd.DataFrame(index=rates.index)
    duration["date"] = rates.index
    ycols = [f"BC_{t}" for t in tenors]
    assumed_duration = [2, 5, 10, 20]
    for tenor, duration_years, col in zip([2, 5, 10, 30], assumed_duration, ycols):
        duration[f"bond_{tenor}y_proxy_return"] = -duration_years * rates[col].diff() / 100
    ret_cols = [c for c in duration if c.endswith("proxy_return")]
    returns = duration.set_index("date")[ret_cols].dropna()
    cov = returns.loc[:"2023-12-31"].cov().values
    n = len(ret_cols)
    opt = minimize(lambda w: float(w @ cov @ w), np.repeat(1/n,n), bounds=[(0,1)]*n, constraints={"type":"eq","fun":lambda w: w.sum()-1}, method="SLSQP", options={"ftol": 1e-12, "maxiter": 1000})
    optw = opt.x if opt.success else np.repeat(1/n,n)
    eval_returns = returns.loc["2024-01-01":]
    eq = eval_returns.mean(axis=1)
    minv = eval_returns @ optw
    construction = {"weights":{"equal_weight":{c:1/n for c in ret_cols},"min_variance_train_2020_2023":dict(zip(ret_cols,map(float,optw)))},"equal_weight_oos":returns_metrics(eq),"min_variance_oos":returns_metrics(minv),"optimizer_success":bool(opt.success),"optimizer_message":str(opt.message),"train_end":"2023-12-31","test_start":"2024-01-01","construction":"duration-only zero-coupon proxies"}
    path4=save_csv("04","hypothetical_bond_proxy_returns.csv",eval_returns.reset_index())
    save_csv("04","weight_comparison.csv",pd.DataFrame({"tenor_proxy":ret_cols,"equal_weight":np.repeat(1/n,n),"min_variance_train":optw}))
    plotdf=pd.DataFrame({"date":eval_returns.index,"equal_weight_growth":(1+eq).cumprod(),"min_variance_growth":(1+minv).cumprod()})
    save_csv("04","out_of_sample_growth.csv",plotdf)
    plot_lines("04","Hypothetical duration-only portfolio growth",plotdf,[("equal_weight_growth","Equal weight"),("min_variance_growth","Min variance")],"Growth of 1 (approximation)","portfolio.png")
    write_study("04", "Completed out-of-sample allocation comparison using observed Treasury yield changes and explicit hypothetical duration-only bond proxies.", construction, "Approximate daily return as negative assumed duration times the daily change in corresponding par yield. Optimize long-only minimum variance on 2020–2023, compare with equal weight in 2024–latest.", TREASURY_URL, ["Hypothetical zero-coupon-like exposures; not actual bonds or ETFs.", "Duration-only approximation excludes coupon carry, convexity, roll-down, financing, transaction costs and rebalancing costs.", "Historical test is not a forecast or investment recommendation."], [str(path4),"weight_comparison.csv","out_of_sample_growth.csv"],"portfolio.png")

    cot = cot_positions()
    if cot.empty:
        raise ValueError("CFTC data returned no selected Treasury/S&P futures contracts")
    cot_path=save_csv("05","cftc_tff_position_series.csv",cot[["date","contract_market_name","open_interest_all","leveraged_money_positions_long","leveraged_money_positions_short","leveraged_money_net","asset_mgr_positions_long","asset_mgr_positions_short","asset_manager_net"]])
    cot_summary=cot.groupby("contract_market_name").agg(observations=("date","count"),first_date=("date","min"),last_date=("date","max"),latest_open_interest=("open_interest_all","last"),latest_leveraged_money_net=("leveraged_money_net","last"),latest_asset_manager_net=("asset_manager_net","last")).reset_index()
    save_csv("05","latest_position_summary.csv",cot_summary)
    cottop=cot[cot["contract_market_name"].isin(["UST 10Y NOTE","E-MINI S&P 500"])].copy()
    fig,ax=plt.subplots(figsize=(10,4.8),constrained_layout=True)
    for name,g in cottop.groupby("contract_market_name"):
        ax.plot(g.date,g.leveraged_money_net,label=f"{name} leveraged-money net")
    ax.set_title("Selected CFTC futures-only net positions",loc="left",weight="bold");ax.grid(alpha=.2);ax.legend(frameon=False);fig.savefig(OUT/"05"/"positions.png",dpi=150);plt.close(fig)
    write_study("05", "Completed descriptive positioning analysis of CFTC TFF futures-only aggregates.", {"contracts":int(cot.contract_market_name.nunique()),"latest_report_date":str(cot.date.max().date()),"series_included":sorted(cot.contract_market_name.unique().tolist())}, "Filter futures-only CFTC TFF series to selected U.S. Treasury and E-mini S&P 500 contracts; compute category net positions as long minus short and report open interest and latest observation.", CFTC_URL, ["CFTC categories classify reportable traders; they do not identify individual accounts.", "Open interest and trader net positioning are not portfolio exposures or predictive signals.", "Only public aggregate rows are retained in derived tables."], [str(cot_path),"latest_position_summary.csv"],"positions.png")

    # Hypothetical 10-year-duration portfolio; daily moves and 100 bp shock.
    w = np.array([0.0,0.2,0.6,0.2])
    dr = duration.set_index("date")[ret_cols].dropna()
    portfolio = dr @ w
    var95 = float(np.quantile(portfolio, .05)*100)
    es95 = float(portfolio[portfolio <= np.quantile(portfolio,.05)].mean()*100)
    shock = pd.DataFrame({"tenor_years":[2,5,10,20],"weight":w,"assumed_duration_years":[2,5,10,20]})
    shock["loss_pct_parallel_plus_100bp"] = -shock.weight * shock.assumed_duration_years * .01 * 100
    path6=save_csv("06","daily_hypothetical_portfolio_proxy_returns.csv",pd.DataFrame({"date":portfolio.index,"proxy_return":portfolio.values}))
    save_csv("06","parallel_100bp_shock.csv",shock)
    risk_metrics={"portfolio_weights":dict(zip(ret_cols,map(float,w))),"observations":int(len(portfolio)),"daily_historical_var_95_pct":-var95,"daily_historical_es_95_pct":-es95,"historical_worst_day_pct":float(portfolio.min()*100),"hypothetical_parallel_plus_100bp_loss_pct":float(shock.loss_pct_parallel_plus_100bp.sum()),"assumed_duration_years":dict(zip(ret_cols,[2,5,10,20]))}
    plotdf=pd.DataFrame({"date":portfolio.index,"drawdown_pct":((1+portfolio).cumprod()/(1+portfolio).cumprod().cummax()-1)*100})
    save_csv("06","drawdown.csv",plotdf)
    plot_lines("06","Hypothetical duration-only portfolio drawdown",plotdf,[("drawdown_pct","Drawdown")],"Percent","drawdown.png")
    write_study("06", "Completed historical and hypothetical shock analysis for a clearly specified duration-only portfolio.", risk_metrics, "Compute daily bond proxy returns from Treasury yield changes, use an illustrative 20/60/20 split across 5y/10y/20y durations, calculate historical 95% daily VaR/ES and a +100bp parallel duration shock.", TREASURY_URL, ["Portfolio and duration assumptions are hypothetical.", "Historical VaR/ES from duration proxies omit coupons and convexity and do not estimate client portfolio losses.", "Parallel shock is a first-order sensitivity, not a forecast."], [str(path6),"parallel_100bp_shock.csv","drawdown.csv"],"drawdown.png")

    # Execution quality public OES report: compare medians across report buckets.
    exec_frames=[]
    for month in ("202609","202610"):
        df=pd.read_csv(CACHE/f"cboe-bzx-{month}.csv")
        df["month"]=month
        exec_frames.append(df)
    exe=pd.concat(exec_frames,ignore_index=True)
    for col in ["AvgEffctvSprdPct","AvgPctQuotSprd","WghtdAvgPctPI","WghtdAvgExctnTime","PctExctdAtQuotOrBetter"]:
        exe[col]=pd.to_numeric(exe[col],errors="coerce")
    market_orders=exe[exe["OrderType"].astype(str).str.upper().isin(["M","MARKET"])].copy()
    exec_summary=market_orders.groupby(["month","Sp500"],dropna=False).agg(category_rows=("OrderSize","count"),median_effective_spread_reported=("AvgEffctvSprdPct","median"),median_quoted_spread_reported=("AvgPctQuotSprd","median"),median_weighted_price_improvement_reported=("WghtdAvgPctPI","median"),median_execution_time_reported=("WghtdAvgExctnTime","median"),median_fill_at_quote_or_better=("PctExctdAtQuotOrBetter","median")).reset_index()
    p7s=save_csv("07","monthly_bucket_medians.csv",exec_summary)
    sp_label = lambda v: "S&P 500" if str(v).strip().upper() in {"Y", "1", "TRUE", "S&P500", "YES"} else "Other"
    plot_bars("07", "Median reported effective spread, market orders (%)", [f"{m[:4]}-{m[4:]} · {sp_label(v)}" for m, v in zip(exec_summary.month, exec_summary.Sp500)], exec_summary.median_effective_spread_reported.astype(float).tolist(), "Effective spread (%)", "spreads.png", annotate="{:.3f}")
    write_study("07", "Completed analysis of Cboe BZX Rule 605 summary reports for September and October 2026.", {"report_months":sorted(exe.month.unique().tolist()),"report_bucket_rows":int(len(exe)),"market_order_rows":int(len(market_orders)),"groups":exec_summary.to_dict(orient="records")}, "Compare medians of reported statistics across size and S&P500 classification buckets for market orders. Only grouped medians are published; source rows are not redistributed.", CBOE_URL, ["Cboe states the data are unaudited and may contain errors.", "Two monthly observations are descriptive and not a trend or causal comparison.", "Summary buckets are not order-level client fills and cannot replace a client's best-execution review."], [str(p7s)],"spreads.png")

    # Monthly performance reporting for the same hypothetical proxy book.
    full_month_end = pd.Timestamp.now().normalize().replace(day=1)
    full_month_portfolio = portfolio.loc[portfolio.index < full_month_end]
    monthly=(1+full_month_portfolio).resample("ME").prod()-1
    monthly_df=pd.DataFrame({"month":monthly.index,"proxy_return_pct":monthly.values*100,"growth_of_1":(1+monthly).cumprod().values})
    monthly_df["drawdown_pct"]=(monthly_df.growth_of_1/monthly_df.growth_of_1.cummax()-1)*100
    p8=save_csv("08","hypothetical_monthly_performance.csv",monthly_df)
    metrics8={"months":int(len(monthly_df)),"start_month":str(monthly_df.month.min().date()),"end_month":str(monthly_df.month.max().date()),"cumulative_proxy_return_pct":float((monthly_df.growth_of_1.iloc[-1]-1)*100),"best_month_pct":float(monthly_df.proxy_return_pct.max()),"worst_month_pct":float(monthly_df.proxy_return_pct.min()),"ending_growth_of_1":float(monthly_df.growth_of_1.iloc[-1])}
    plot_lines("08","Hypothetical duration-only monthly performance",monthly_df.rename(columns={"month":"date"}),[("growth_of_1","Growth of 1")],"Index", "growth.png")
    write_study("08", "Completed monthly reporting demonstrator for a hypothetical duration-only portfolio driven by real Treasury yield changes.", metrics8, "Compound daily first-order duration proxy returns to monthly figures, calculate cumulative growth and drawdown, and provide a reproducible monthly table.", TREASURY_URL, ["This is not a real fund, client account or administrator-reconciled NAV series.", "Hypothetical position weights and duration-only return assumptions; no fees or flows.", "The pack illustrates reporting mechanics only."], [str(p8)],"growth.png")

    # Independent forecast validation, with a true chronological holdout.
    test_result={"test_period":metrics3["test_from"]+" to "+str(test.index.max().date()),"test_observations":int(len(test)),"model_mae_bp":mae,"baseline_mae_bp":base_mae,"model_rmse_bp":float(np.sqrt(np.mean((test["next5_slope_change_bp"].values-pred)**2))),"baseline_rmse_bp":float(np.sqrt(np.mean((test["next5_slope_change_bp"].values-baseline)**2))),"model_direction_hit_pct":metrics3["oos_direction_hit_pct"],"baseline_direction_hit_pct":float((np.sign(baseline)==np.sign(test["next5_slope_change_bp"])).mean()*100),"slope_coefficient":float(reg.slope),"r_squared_train":float(reg.rvalue**2)}
    valdf=pd.DataFrame({"date":test.index,"observed_next5_slope_change_bp":test.next5_slope_change_bp.values,"model_prediction_bp":pred,"training_mean_baseline_bp":baseline})
    p9=save_csv("09","out_of_sample_validation.csv",valdf)
    plot_bars("09", "Out-of-sample error: model vs training-mean baseline (bp)", ["Model MAE", "Baseline MAE", "Model RMSE", "Baseline RMSE"], [test_result["model_mae_bp"], test_result["baseline_mae_bp"], test_result["model_rmse_bp"], test_result["baseline_rmse_bp"]], "Basis points", "errors.png", colors=[PALETTE[0], PALETTE[1], PALETTE[0], PALETTE[1]])
    write_study("09", "Completed out-of-sample validation of a simple curve-state forecast, including baseline and error metrics.", test_result, "Freeze a linear model trained through 2023-12-31; validate next-five-session 10y–2y slope change on 2024–latest. Compare out-of-sample errors and direction accuracy to the training-mean baseline.", TREASURY_URL, ["This is an illustrative single-target model validation, not a validation of a client or production model.", "One chronological split and one baseline; results may be unstable across regimes.", "Forecast target is yield-curve slope change, not return or investment performance."], [str(p9)],"errors.png")

    # Black-Scholes-Merton with Treasury 3-month yield; all other terms are fictional.
    from scipy.stats import norm
    latest=rate_out.dropna(subset=["BC_3MONTH"]).iloc[-1]
    r=float(latest["BC_3MONTH"])/100
    S,K,T,q,sigma=100.0,100.0,0.25,0.0,0.25
    d1=(math.log(S/K)+(r-q+sigma*sigma/2)*T)/(sigma*math.sqrt(T));d2=d1-sigma*math.sqrt(T)
    call=S*math.exp(-q*T)*norm.cdf(d1)-K*math.exp(-r*T)*norm.cdf(d2)
    delta=math.exp(-q*T)*norm.cdf(d1);gamma=math.exp(-q*T)*norm.pdf(d1)/(S*sigma*math.sqrt(T));vega=S*math.exp(-q*T)*norm.pdf(d1)*math.sqrt(T)/100
    option={"data_date":str(pd.Timestamp(latest.date).date()),"treasury_3m_rate_pct":r*100,"contract":"hypothetical European call","spot":S,"strike":K,"tenor_years":T,"volatility_pct":sigma*100,"dividend_yield_pct":q*100,"model_price":float(call),"delta":float(delta),"gamma":float(gamma),"vega_per_1vol_point":float(vega),"assumptions_are_hypothetical_except_rate":True}
    p10=save_csv("10","option_scenario.csv",pd.DataFrame([option]))
    rate_scen=[]
    for shock_bp in [-100,-50,0,50,100]:
        rr=r+shock_bp/10000; dd1=(math.log(S/K)+(rr-q+sigma*sigma/2)*T)/(sigma*math.sqrt(T));dd2=dd1-sigma*math.sqrt(T)
        price=S*math.exp(-q*T)*norm.cdf(dd1)-K*math.exp(-rr*T)*norm.cdf(dd2)
        rate_scen.append({"risk_free_rate_shock_bp":shock_bp,"model_price":float(price)})
    p10s=save_csv("10","rate_sensitivity.csv",pd.DataFrame(rate_scen))
    plot_bars("10", "Hypothetical call value under risk-free rate shocks", [f"{x['risk_free_rate_shock_bp']:+d} bp" for x in rate_scen], [x["model_price"] for x in rate_scen], "Model value", "rate_sensitivity.png", colors=[PALETTE[0]] * len(rate_scen))
    write_study("10", "Completed Black–Scholes–Merton scenario using the observed Treasury 3-month par rate and explicitly hypothetical option terms.", option, "Use latest available 3-month Treasury par yield as risk-free rate; calculate European call price and Greeks for a hypothetical at-the-money contract. Reprice over ±100bp rate shocks.", TREASURY_URL, ["Spot, strike, maturity, volatility and dividend yield are illustrative assumptions, not market quotes.", "European exercise only; no bid/ask, discrete dividends, borrow, funding basis or transaction costs.", "Not an executable valuation or recommendation."], [str(p10),str(p10s)],"rate_sensitivity.png")

    # Data platform checks and lineage across the three public datasets.
    cftc_raw=json.loads((CACHE/"cftc-tff-selected.json").read_text())
    qc=[]
    qc.append({"source":"U.S. Treasury","rows":len(rates),"key_duplicates":int(rates.index.duplicated().sum()),"date_min":str(rates.index.min().date()),"date_max":str(rates.index.max().date()),"missing_10y_pct":float(rates.BC_10YEAR.isna().mean()*100)})
    qc.append({"source":"SEC Company Facts","rows":len(companies),"key_duplicates":int(companies.duplicated(["ticker","fiscal_year"]).sum()),"date_min":str(companies.fiscal_year.min()),"date_max":str(companies.fiscal_year.max()),"missing_revenue_pct":float(companies.revenue.isna().mean()*100)})
    qc.append({"source":"CFTC TFF API","rows":len(cftc_raw),"key_duplicates":int(cot.duplicated(["contract_market_name","date"]).sum()),"date_min":str(cot.date.min().date()),"date_max":str(cot.date.max().date()),"missing_open_interest_pct":float(cot.open_interest_all.isna().mean()*100)})
    p11=save_csv("11","source_quality_and_lineage.csv",pd.DataFrame(qc))
    lineage={"source_endpoints":[TREASURY_URL,SEC_URL,CFTC_URL,CBOE_URL],"raw_file_policy":"raw downloads stay local in .cache and are git-ignored","derived_output_count":12,"checks":qc}
    plot_bars("11", "Rows ingested and checked per public source", [q["source"] for q in qc], [q["rows"] for q in qc], "Rows", "sources.png", annotate="{:,.0f}")
    write_study("11", "Completed ingestion, lineage and quality checks across Treasury, SEC and CFTC inputs.", lineage, "Record source endpoints, local retrieval files, date coverage, key duplication and missingness checks before generating the analytical studies.", SEC_URL, ["This run is a local research pipeline, not a production data platform SLA.", "Source systems may revise or extend observations; rerun to refresh.", "Raw source extracts are excluded from the public Git repository."], [str(p11)],"sources.png")

    # Evidence-first summary without an external LLM: source facts plus explicit citations.
    latest_rows=companies.sort_values("fiscal_year").groupby("ticker").tail(1)
    evidence=[]
    for row in latest_rows.itertuples():
        ciks = {"AAPL": "0000320193", "MSFT": "0000789019", "NVDA": "0001045810"}
        filed = getattr(row, "revenue_filed", None)
        evidence.append({"claim":"latest annual revenue in extracted SEC 10-K facts","issuer":row.issuer,"ticker":row.ticker,"fiscal_year":int(row.fiscal_year),"revenue_usd":None if pd.isna(row.revenue) else float(row.revenue),"filed_date":None if filed is None or pd.isna(filed) else str(filed),"source_url":f"https://data.sec.gov/api/xbrl/companyfacts/CIK{ciks[row.ticker]}.json"})
    # Fix a compact auditable evidence ledger with explicit source IDs.
    ledger=pd.DataFrame(evidence)
    p12=save_csv("12","evidence_ledger.csv",ledger)
    brief={"purpose":"Demonstrate deterministic evidence-linked public-market research; no LLM was used.","records":evidence,"review_controls":["source URL retained per issuer","fiscal year and filed date retained","do not infer causality from reported fundamentals","human review required before client use"]}
    save_json("12","evidence_brief.json",brief)
    plot_bars("12", "Evidence ledger: latest reported annual revenue (USD bn, SEC 10-K facts)", [f"{e['ticker']} FY{e['fiscal_year']}" for e in evidence], [(e["revenue_usd"] or 0) / 1e9 for e in evidence], "USD billions", "evidence.png", annotate="{:,.1f}")
    write_study("12", "Completed deterministic, source-linked research demonstrator using official SEC annual facts; no AI-generated claim is presented as verified fact.", {"evidence_rows":len(evidence),"issuer_coverage":sorted(latest_rows.ticker.tolist()),"method":"XBRL extraction, filed-date preservation, calculations, evidence ledger; no LLM generation"}, "Generate a concise issuer evidence ledger from extracted annual SEC facts, retaining ticker, fiscal year, filed date and source endpoint. AI is not called; the demonstrator verifies the no-AI manual fallback and citation structure.", SEC_URL, ["This demonstrates the evidence workflow; it is not independent investment research or advice.", "No external model or AI API was used.", "Statements are limited to the fields and periods explicitly recorded."], [str(p12),"evidence_brief.json"],"evidence.png")

    # Create a single workbook with a concise results sheet plus study data tabs.
    xlsx=OUT/"ProQuant_Public_Studies.xlsx"
    with pd.ExcelWriter(xlsx,engine="openpyxl") as writer:
        pd.DataFrame([{"study":k,"title":v,"report":f"{k}/index.html"} for k,v in STUDIES.items()]).to_excel(writer,sheet_name="Index",index=False)
        for sid, filename in [("01","yield_curve_derived.csv"),("02","issuer_fundamentals_derived.csv"),("03","signal_test_observations.csv"),("04","hypothetical_bond_proxy_returns.csv"),("05","latest_position_summary.csv"),("06","parallel_100bp_shock.csv"),("07","monthly_bucket_medians.csv"),("08","hypothetical_monthly_performance.csv"),("09","out_of_sample_validation.csv"),("10","rate_sensitivity.csv"),("11","source_quality_and_lineage.csv"),("12","evidence_ledger.csv")]:
            df=pd.read_csv(OUT/sid/filename)
            df.to_excel(writer,sheet_name=f"{sid}_{STUDIES[sid][:18]}",index=False)
    # Landing manifest used by the static web gallery.
    manifest={"built_utc":datetime.now(timezone.utc).isoformat(timespec="seconds"),"source_period":"2020 through latest available source observations","studies":[{"id":sid,"title":title,"report":f"deliverables/{sid}/index.html","metrics":f"deliverables/{sid}/metrics.json"} for sid,title in STUDIES.items()],"workbook":"deliverables/ProQuant_Public_Studies.xlsx","raw_source_files_published":False,"client_data_used":False}
    (OUT/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(f"Built 12 study deliverables under {OUT} plus workbook {xlsx.name}")


def html_escape(value):
    import html
    return html.escape(str(value))


if __name__ == "__main__":
    build_all()
