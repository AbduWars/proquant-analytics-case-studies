# 03 · Strategy Research & Backtesting

**Status:** Completed time-ordered test of a curve-state research signal against a mean baseline.

**Summary:** {
  "train_observations": 876,
  "test_observations": 714,
  "train_through": "2023-12-29",
  "test_from": "2024-01-02",
  "oos_mae_bp": 5.1037896212086205,
  "mean_baseline_mae_bp": 5.088772495299489,
  "oos_direction_hit_pct": 50.14005602240896,
  "interpretation": "forecast diagnostic only; not a tradable strategy or realized return"
}

**Method:** Train a one-variable linear diagnostic on 2020–2023 rolling-standardized 10y–2y slope; evaluate five-session forward slope change on 2024–latest. Compare mean absolute error and direction hit rate to a training-mean baseline.

**Source:** https://home.treasury.gov/treasury-daily-interest-rate-xml-feed

**Limitations:**
- The target is a yield-curve change, not instrument P&L.
- No transaction costs, execution, risk-adjusted return or tradability claim.
- No hyperparameter search was performed.
