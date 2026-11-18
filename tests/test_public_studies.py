import json
import math
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DELIVERABLES = ROOT / "deliverables"


def read_metrics(study_id):
    path = DELIVERABLES / study_id / "metrics.json"
    assert path.is_file(), f"Missing computed metrics for study {study_id}"

    def reject_constant(value):
        raise ValueError(f"Invalid JSON numeric constant: {value}")

    return json.loads(path.read_text(), parse_constant=reject_constant)


def test_all_twelve_studies_have_html_method_metrics_and_data():
    for study_id in (f"{n:02d}" for n in range(1, 13)):
        folder = DELIVERABLES / study_id
        assert (folder / "index.html").is_file()
        assert (folder / "METHODOLOGY.md").is_file()
        assert read_metrics(study_id)
        assert any(p.suffix.lower() in {".csv", ".png", ".json"} for p in folder.iterdir())


def test_model_test_is_time_ordered_and_reports_baseline():
    signal = read_metrics("03")
    validation = read_metrics("09")
    assert signal["train_through"] < signal["test_from"]
    assert signal["test_observations"] > 500
    assert validation["model_mae_bp"] > 0
    assert validation["baseline_mae_bp"] > 0
    assert 0 <= validation["model_direction_hit_pct"] <= 100


def test_hypothetical_inputs_are_explicit_in_metrics():
    assert read_metrics("06")["assumed_duration_years"]
    assert read_metrics("10")["assumptions_are_hypothetical_except_rate"] is True
    assert "hypothetical" in (DELIVERABLES / "08" / "METHODOLOGY.md").read_text().lower()


def test_sec_company_facts_coverage_and_results_are_present():
    summary = read_metrics("02")
    assert summary["issuers"] == 3
    assert all(summary["latest_revenue_usd"][ticker] for ticker in ("AAPL", "MSFT", "NVDA"))


def test_data_quality_has_no_duplicate_keys_and_no_missing_required_values():
    checks = read_metrics("11")["checks"]
    assert len(checks) == 3
    assert all(item["key_duplicates"] == 0 for item in checks)
    assert all(math.isfinite(item["missing_10y_pct"] if item["source"] == "U.S. Treasury" else item["missing_revenue_pct"] if item["source"] == "SEC Company Facts" else item["missing_open_interest_pct"]) for item in checks)


def test_public_bundles_exclude_raw_cache_and_contain_workbook_and_zip():
    assert (ROOT / "index.html").is_file()
    assert (DELIVERABLES / "ProQuant_Public_Studies.xlsx").is_file()
    archive = DELIVERABLES / "ProQuant_Public_Studies.zip"
    assert archive.is_file()
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
        assert "01/index.html" in names
        assert "ProQuant_Public_Studies.xlsx" in names
        assert not any("treasury-202" in name or "companyfacts" in name or "cftc-tff-selected" in name for name in names)


def test_gallery_discloses_public_study_not_client_work():
    page = (ROOT / "index.html").read_text()
    assert "not twelve customer engagements" in page
    assert "Open study, methodology and downloads" in page
    assert "hypothetical" in page.lower()
