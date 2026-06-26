from datetime import date

from app.services.duzp_service import resolve_vat_period, validate_duzp


def test_vat_period_derived_from_duzp():
    result = validate_duzp(
        duzp=date(2024, 11, 30),
        invoice_date=date(2024, 12, 5),
        direction="ISSUED",
    )
    assert result.vat_period == "2024-11"
    assert result.is_valid


def test_late_invoice_generates_warning():
    result = validate_duzp(
        duzp=date(2024, 3, 1),
        invoice_date=date(2024, 4, 1),
        direction="ISSUED",
    )
    assert result.is_valid
    assert any("15" in warning for warning in result.warnings)


def test_expired_input_vat_generates_error():
    result = validate_duzp(
        duzp=date(2019, 1, 1),
        invoice_date=date(2019, 1, 5),
        direction="RECEIVED",
    )
    assert not result.is_valid
    assert any("3 year" in error or "expired" in error.lower() for error in result.errors)


def test_resolve_vat_period():
    assert resolve_vat_period(date(2024, 3, 15)) == "2024-03"
    assert resolve_vat_period(date(2024, 12, 31)) == "2024-12"
    assert resolve_vat_period(date(2024, 1, 1)) == "2024-01"
