## Method

Completed ingestion, lineage and quality checks across Treasury, SEC and CFTC inputs. Record source endpoints, local retrieval files, date coverage, key duplication and missingness checks before generating the analytical studies.

## Results

| Measure | Value |
|---|---|
| Source endpoints | https://home.treasury.gov/treasury-daily-interest-rate-xml-feed, https://www.sec.gov/edgar/sec-api-documentation, https://publicreporting.cftc.gov/Commitments-of-Traders/TFF-Futures-Only/gpe5-46if, https://www.cboe.com/markets/us/equities/regulation/605/bzx |
| Raw file policy | raw downloads stay local in .cache and are git-ignored |
| Derived output count | 12 |

**Checks**

| Source | Rows | Key duplicates | Date min | Date max | Missing 10y (%) | Missing revenue (%) | Missing open interest (%) |
|---|---|---|---|---|---|---|---|
| U.S. Treasury | 1,720 | 0 | 2020-01-02 | 2026-11-17 | 0.00 | n/a | n/a |
| SEC Company Facts | 21 | 0 | 2020 | 2026 | n/a | 0.00 | n/a |
| CFTC TFF API | 47,420 | 0 | 2006-06-13 | 2026-11-10 | n/a | n/a | 0.00 |

## Source

https://www.sec.gov/edgar/sec-api-documentation

## Limitations

- This run is a local research pipeline, not a production data platform SLA.
- Source systems may revise or extend observations; rerun to refresh.
- Raw source extracts are excluded from the public Git repository.
