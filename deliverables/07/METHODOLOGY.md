# 07 · Execution Costs & Slippage

**Status:** Completed analysis of Cboe BZX Rule 605 summary reports for September and October 2026.

**Summary:** {
  "report_months": [
    "202609",
    "202610"
  ],
  "report_bucket_rows": 72,
  "market_order_rows": 36,
  "groups": [
    {
      "month": "202609",
      "Sp500": "N",
      "category_rows": 9,
      "median_effective_spread_reported": 0.012785,
      "median_quoted_spread_reported": 0.006929,
      "median_weighted_price_improvement_reported": 0.001382,
      "median_execution_time_reported": 4674.067707,
      "median_fill_at_quote_or_better": 0.678364
    },
    {
      "month": "202609",
      "Sp500": "Y",
      "category_rows": 9,
      "median_effective_spread_reported": 0.004864,
      "median_quoted_spread_reported": 0.008295,
      "median_weighted_price_improvement_reported": 0.002508,
      "median_execution_time_reported": 5.360686,
      "median_fill_at_quote_or_better": 0.625
    },
    {
      "month": "202610",
      "Sp500": "N",
      "category_rows": 9,
      "median_effective_spread_reported": 0.003325,
      "median_quoted_spread_reported": 0.004081,
      "median_weighted_price_improvement_reported": 0.000736,
      "median_execution_time_reported": 1733.567128,
      "median_fill_at_quote_or_better": 0.760871
    },
    {
      "month": "202610",
      "Sp500": "Y",
      "category_rows": 9,
      "median_effective_spread_reported": -0.000378,
      "median_quoted_spread_reported": 0.005682,
      "median_weighted_price_improvement_reported": 0.001908,
      "median_execution_time_reported": 4.932621,
      "median_fill_at_quote_or_better": 0.832411
    }
  ]
}

**Method:** Compare medians of reported statistics across size and S&P500 classification buckets for market orders. Only grouped medians are published; source rows are not redistributed.

**Source:** https://www.cboe.com/markets/us/equities/regulation/605/bzx

**Limitations:**
- Cboe states the data are unaudited and may contain errors.
- Two monthly observations are descriptive and not a trend or causal comparison.
- Summary buckets are not order-level client fills and cannot replace a client's best-execution review.
