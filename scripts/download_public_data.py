"""Fetch the small set of official public inputs used by the study builder.

Raw inputs are saved under .cache/ and must not be committed.  The builder
publishes only study-specific derived outputs and source citations.
"""
from __future__ import annotations

import json
import ssl
import urllib.parse
import urllib.request
from pathlib import Path

import certifi

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache"
UA = "ProQuant Analytics public-data studies info@proquantanalytics.com"
HEADERS = {"User-Agent": UA}
TLS = ssl.create_default_context(cafile=certifi.where())


def get(url: str) -> bytes:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, context=TLS, timeout=90) as response:
        return response.read()


def main() -> None:
    CACHE.mkdir(exist_ok=True)
    for year in range(2020, 2027):
        url = (
            "https://home.treasury.gov/resource-center/data-chart-center/"
            "interest-rates/pages/xml?data=daily_treasury_yield_curve"
            f"&field_tdr_date_value={year}"
        )
        (CACHE / f"treasury-{year}.xml").write_bytes(get(url))

    for cik, ticker in (
        ("0000320193", "AAPL"),
        ("0000789019", "MSFT"),
        ("0001045810", "NVDA"),
    ):
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        (CACHE / f"{ticker}-companyfacts.json").write_bytes(get(url))

    params = {
        "$select": ",".join(
            (
                "report_date_as_yyyy_mm_dd",
                "market_and_exchange_names",
                "contract_market_name",
                "commodity_name",
                "open_interest_all",
                "lev_money_positions_long",
                "lev_money_positions_short",
                "asset_mgr_positions_long",
                "asset_mgr_positions_short",
                "commodity_subgroup_name",
            )
        ),
        "$order": "report_date_as_yyyy_mm_dd ASC",
        "$limit": "50000",
    }
    url = "https://publicreporting.cftc.gov/resource/gpe5-46if.json?" + urllib.parse.urlencode(params)
    (CACHE / "cftc-tff-selected.json").write_bytes(get(url))

    for month in ("202609", "202610"):
        url = f"https://cdn.cboe.com/resources/us/equities/regulation/605/bzx/summary/BATS{month}.csv"
        (CACHE / f"cboe-bzx-{month}.csv").write_bytes(get(url))

    manifest = {
        "retrieved_utc": "record at runtime in the generated run metadata",
        "raw_inputs_local_only": True,
        "sources": [
            "U.S. Treasury daily par yield curve XML, 2020-2026",
            "SEC Company Facts JSON, AAPL/MSFT/NVDA",
            "CFTC TFF Futures Only API, selected public fields",
            "Cboe BZX Rule 605 OES summary CSV, 2026-09 and 2026-10",
        ],
    }
    (CACHE / "download-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Downloaded official inputs to {CACHE}; raw files are git-ignored.")


if __name__ == "__main__":
    main()
