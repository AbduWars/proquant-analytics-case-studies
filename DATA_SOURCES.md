# Data sources, rights, and caveats

The downloadable pack contains analytical outputs, not client records. Raw source downloads are kept only in local `.cache/`, which is excluded from Git.

| Source | Use in this portfolio | Reuse / handling |
|---|---|---|
| [U.S. Treasury daily rates feed](https://home.treasury.gov/treasury-daily-interest-rate-xml-feed) | Curve monitoring, rate-shock calculations, duration proxies, and the risk-free input to one hypothetical option example | Official public feed and Treasury open-data program. Cite Treasury. Raw XML is not in the repository; outputs are analytical transformations. Par yields are not bond total returns. |
| [SEC EDGAR Company Facts](https://www.sec.gov/edgar/sec-api-documentation) | Annual reported-fundamental comparisons and the evidence ledger | SEC says information presented on sec.gov may be copied or further distributed with citation. Follow SEC fair-access limits and use a descriptive User-Agent. Issuer XBRL tags and periods require review. |
| [CFTC TFF Futures Only](https://publicreporting.cftc.gov/Commitments-of-Traders/TFF-Futures-Only/gpe5-46if) | Aggregate futures positioning for selected Treasury and E-mini S&P 500 contracts | CFTC identifies government information on its website as public domain. Categories are aggregate trader classifications, not individual accounts. |
| [Cboe BZX Rule 605](https://www.cboe.com/markets/us/equities/regulation/605/bzx) | September and October 2026 grouped market-order summary statistics | Only calculated group medians are published; source rows are not redistributed. Cboe states reports are unaudited and may contain errors or lack comparability. |

All results are dated and linked to the source. Re-running the downloader may yield updated observations and changed results. The public pack is not investment advice or a substitute for source, accounting, market-data entitlement, or client-specific review.
