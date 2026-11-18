# 09 · Model Validation

**Status:** Completed out-of-sample validation of a simple curve-state forecast, including baseline and error metrics.

**Summary:** {
  "test_period": "2024-01-02 to 2026-11-09",
  "test_observations": 714,
  "model_mae_bp": 5.1037896212086205,
  "baseline_mae_bp": 5.088772495299489,
  "model_rmse_bp": 6.489391076700602,
  "baseline_rmse_bp": 6.495311593406789,
  "model_direction_hit_pct": 50.14005602240896,
  "baseline_direction_hit_pct": 48.59943977591036,
  "slope_coefficient": 0.583691315358355,
  "r_squared_train": 0.008154504891912986
}

**Method:** Freeze a linear model trained through 2023-12-31; validate next-five-session 10y–2y slope change on 2024–latest. Compare out-of-sample errors and direction accuracy to the training-mean baseline.

**Source:** https://home.treasury.gov/treasury-daily-interest-rate-xml-feed

**Limitations:**
- This is an illustrative single-target model validation, not a validation of a client or production model.
- One chronological split and one baseline; results may be unstable across regimes.
- Forecast target is yield-curve slope change, not return or investment performance.
