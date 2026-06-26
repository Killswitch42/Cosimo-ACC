import pytest
from datetime import date
from app.services.deadline_service import build_deadline_calendar, _severity_for_days


def test_deadline_calendar_has_dph_entries():
    deadlines = build_deadline_calendar(date(2024, 3, 1))
    codes = [item["code"] for item in deadlines]
    assert "DPH_MONTHLY" in codes


def test_deadline_calendar_has_dppo():
    deadlines = build_deadline_calendar(date(2024, 3, 1))
    codes = [item["code"] for item in deadlines]
    assert "DPPO_ANNUAL" in codes


def test_deadline_calendar_has_zaverka():
    deadlines = build_deadline_calendar(date(2024, 3, 1))
    codes = [item["code"] for item in deadlines]
    assert "UCETNI_ZAVERKA" in codes


def test_dppo_with_advisor_is_july():
    deadlines = build_deadline_calendar(date(2024, 3, 1), has_tax_advisor=True)
    dppo = next(item for item in deadlines if item["code"] == "DPPO_ANNUAL")
    assert dppo["deadline_date"].month == 7


def test_dppo_without_advisor_is_april():
    deadlines = build_deadline_calendar(date(2024, 3, 1), has_tax_advisor=False)
    dppo = next(item for item in deadlines if item["code"] == "DPPO_ANNUAL")
    assert dppo["deadline_date"].month == 4


def test_severity_escalation():
    assert _severity_for_days(-1) == "BLOCKER"
    assert _severity_for_days(10) == "INFO"


@pytest.mark.asyncio
async def test_deadline_api_returns_calendar(client):
    response = await client.get("/api/v1/compliance/deadlines")
    assert response.status_code == 200
    data = response.json()
    assert "deadlines" in data
    assert "days_until" in data["deadlines"][0]


@pytest.mark.asyncio
async def test_compliance_scan_endpoint(client):
    response = await client.post("/api/v1/compliance/scan?vat_period=2024-06")
    assert response.status_code == 200
    data = response.json()
    assert "total_alerts" in data
