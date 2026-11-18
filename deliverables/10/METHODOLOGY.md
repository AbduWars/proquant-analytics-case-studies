# 10 · Derivatives & Pricing

**Status:** Completed Black–Scholes–Merton scenario using the observed Treasury 3-month par rate and explicitly hypothetical option terms.

**Summary:** {
  "data_date": "2026-11-17",
  "treasury_3m_rate_pct": 4.33,
  "contract": "hypothetical European call",
  "spot": 100.0,
  "strike": 100.0,
  "tenor_years": 0.25,
  "volatility_pct": 25.0,
  "dividend_yield_pct": 0.0,
  "model_price": 5.5135874731291565,
  "delta": 0.5592626370546617,
  "gamma": 0.03156259435413999,
  "vega_per_1vol_point": 0.19726621471337494,
  "assumptions_are_hypothetical_except_rate": true
}

**Method:** Use latest available 3-month Treasury par yield as risk-free rate; calculate European call price and Greeks for a hypothetical at-the-money contract. Reprice over ±100bp rate shocks.

**Source:** https://home.treasury.gov/treasury-daily-interest-rate-xml-feed

**Limitations:**
- Spot, strike, maturity, volatility and dividend yield are illustrative assumptions, not market quotes.
- European exercise only; no bid/ask, discrete dividends, borrow, funding basis or transaction costs.
- Not an executable valuation or recommendation.
