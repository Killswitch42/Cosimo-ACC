from decimal import Decimal

from app.services.vat_service import KH_THRESHOLD_CZK, assign_kh_section


def test_issued_above_threshold_is_a1():
    section, detail = assign_kh_section("ISSUED", Decimal("15000"), True, False, "STANDARD")
    assert section == "A1"
    assert detail is True


def test_issued_below_threshold_is_a2():
    section, detail = assign_kh_section("ISSUED", Decimal("5000"), True, False, "STANDARD")
    assert section == "A2"
    assert detail is False


def test_issued_to_non_vat_payer_is_a3():
    section, detail = assign_kh_section("ISSUED", Decimal("50000"), False, False, "STANDARD")
    assert section == "A3"
    assert detail is False


def test_issued_advance_is_a4():
    section, detail = assign_kh_section("ISSUED", Decimal("20000"), True, False, "ADVANCE")
    assert section == "A4"
    assert detail is False


def test_received_reverse_charge_is_b1():
    section, detail = assign_kh_section("RECEIVED", Decimal("5000"), True, True, "REVERSE_CHARGE")
    assert section == "B1"
    assert detail is True


def test_received_above_threshold_is_b2():
    section, detail = assign_kh_section("RECEIVED", Decimal("10000"), True, False, "STANDARD")
    assert section == "B2"
    assert detail is True


def test_received_below_threshold_is_b3():
    section, detail = assign_kh_section("RECEIVED", Decimal("9999.99"), True, False, "STANDARD")
    assert section == "B3"
    assert detail is False


def test_threshold_boundary_exactly_10000():
    section, detail = assign_kh_section(
        "ISSUED", KH_THRESHOLD_CZK, True, False, "STANDARD"
    )
    assert section == "A1"
    assert detail is True
