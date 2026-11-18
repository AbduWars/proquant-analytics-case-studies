# 02 · Quantitative Company Analysis

**Status:** Completed annual-filing comparison using SEC XBRL facts for three large U.S. issuers.

**Summary:** {
  "issuers": 3,
  "fiscal_years": "2020-2026",
  "latest_revenue_usd": {
    "MSFT": 331839000000.0,
    "AAPL": 478834000000.0,
    "NVDA": 215938000000.0
  },
  "latest_filed_date": {
    "MSFT": "2026-07-29",
    "AAPL": "2026-11-03",
    "NVDA": "2026-02-25"
  }
}

**Method:** For each issuer, select duration facts from annual 10-K filings, retain fiscal year and filed date, then calculate revenue growth, margins and liabilities/assets. The extraction code is visible in scripts/build_studies.py.

**Source:** https://www.sec.gov/edgar/sec-api-documentation

**Limitations:**
- XBRL tags can differ across issuers and require analyst review.
- This is descriptive company research; no valuation target or recommendation.
- No share prices or market-cap multiples are included.
