# ProQuant Analytics — Public-Data Studies

A reproducible public portfolio of 12 quantitative studies. These are public-data analyses, **not client engagements**. Source data remain in a local `.cache/` folder and are excluded from Git; selected derived results and report files are included.

## Browse and download

- [Interactive study gallery](index.html)
- [Combined results workbook](deliverables/ProQuant_Public_Studies.xlsx)
- [Complete study-pack ZIP](deliverables/ProQuant_Public_Studies.zip)
- [Per-study result pages](deliverables/)
- [Data source rights and caveats](DATA_SOURCES.md)

## Rebuild

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python scripts/download_public_data.py
python scripts/build_studies.py
python scripts/build_gallery.py
pytest -q
```

Raw downloads are saved under `.cache/` and ignored by Git. The generated deliverables are built from the exact source endpoints in each report. Re-running refreshes the source data, so later results may differ.

## Study map

| # | Study | Data and key scope |
|---|---|---|
| 01 | [Market & Macro Monitor](studies/01.md) | Computed from public source data |
| 02 | [Quantitative Company Analysis](studies/02.md) | Computed from public source data |
| 03 | [Strategy Research & Backtesting](studies/03.md) | Computed from public source data |
| 04 | [Portfolio Construction & Allocation](studies/04.md) | Computed with stated hypothetical inputs |
| 05 | [Positions, Leverage & Carry](studies/05.md) | Computed from public source data |
| 06 | [Portfolio Risk & What-if Analysis](studies/06.md) | Computed with stated hypothetical inputs |
| 07 | [Execution Costs & Slippage](studies/07.md) | Computed from public market-center summaries |
| 08 | [Performance & Investor Reporting](studies/08.md) | Computed with stated hypothetical inputs |
| 09 | [Quantitative Model Validation](studies/09.md) | Computed from public source data |
| 10 | [Derivatives & Pricing](studies/10.md) | Computed with stated hypothetical inputs |
| 11 | [Market Data Platform & Reconciliation](studies/11.md) | Computed from public source data |
| 12 | [AI-assisted Quantitative Research](studies/12.md) | Computed evidence workflow; no LLM |

## Source attribution and reuse

- **U.S. Treasury:** [daily yield curve XML feed](https://home.treasury.gov/treasury-daily-interest-rate-xml-feed); outputs are cited derived analyses, not bulk raw copies.
- **SEC:** [EDGAR Company Facts API](https://www.sec.gov/edgar/sec-api-documentation). SEC states information presented on sec.gov may be copied or further distributed with appropriate citation; automated downloads must follow fair-access rules, including the 10 requests/second ceiling and a descriptive User-Agent.
- **CFTC:** [TFF futures-only dataset](https://publicreporting.cftc.gov/Commitments-of-Traders/TFF-Futures-Only/gpe5-46if). CFTC identifies government information on its site as public domain. This study retains selected aggregate contract-category observations only.
- **Cboe:** [BZX Rule 605 reports](https://www.cboe.com/markets/us/equities/regulation/605/bzx). Only grouped medians are published; the source warns that reports are unaudited and may not be directly comparable.

## What the figures mean

Treasury yields are indicative par yields, not bond total returns. Portfolio and option examples use explicitly stated hypothetical inputs. The forecast studies test changes in a yield-curve statistic, not market returns or a trading strategy. The execution study uses a market-center summary, not client order-level fills. No client, private dataset, credential, template source, or internal manual is included.

The figures are research demonstrations, not investment advice, trade instructions, executable quotes, or suitability assessments.
