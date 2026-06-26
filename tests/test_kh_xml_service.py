import pytest
from datetime import date
from decimal import Decimal

from app.services.kh_xml_service import build_kh_xml


def _make_entry(invoice_number: str, vat_rate: Decimal = Decimal("21")) -> dict:
    return {
        "invoice_number": invoice_number,
        "duzp": date(2024, 3, 15),
        "counterparty_dic": "CZ98765432",
        "counterparty_name": "Dodavatel s.r.o.",
        "tax_base_czk": Decimal("50000.00"),
        "tax_amount_czk": Decimal("10500.00"),
        "vat_rate": vat_rate,
    }


KH_DATA_EMPTY = {
    "vat_period": "2024-03",
    "section_a1_detail": [],
    "section_b1_detail": [],
    "section_b2_detail": [],
    "section_a2_aggregate": {"base": Decimal("0.00"), "tax": Decimal("0.00")},
    "section_b3_aggregate": {"base": Decimal("0.00"), "tax": Decimal("0.00")},
}

KH_DATA_WITH_ENTRIES = {
    "vat_period": "2024-03",
    "section_a1_detail": [_make_entry("INV-2024-001")],
    "section_b1_detail": [],
    "section_b2_detail": [_make_entry("FAK-2024-099")],
    "section_a2_aggregate": {"base": Decimal("5000.00"), "tax": Decimal("1050.00")},
    "section_b3_aggregate": {"base": Decimal("3000.00"), "tax": Decimal("630.00")},
}


def test_kh_xml_returns_bytes():
    xml = build_kh_xml("CZ12345678", "Test s.r.o.", "2024-03", KH_DATA_EMPTY)
    assert isinstance(xml, bytes)


def test_kh_xml_has_xml_declaration():
    xml = build_kh_xml("CZ12345678", "Test s.r.o.", "2024-03", KH_DATA_EMPTY)
    assert xml.startswith(b"<?xml")


def test_kh_xml_contains_root_element():
    xml = build_kh_xml("CZ12345678", "Test s.r.o.", "2024-03", KH_DATA_EMPTY)
    assert b"Pisemnost" in xml
    assert b"DPHKH1" in xml


def test_kh_xml_sets_period():
    xml = build_kh_xml("CZ12345678", "Test s.r.o.", "2024-03", KH_DATA_EMPTY)
    assert b'rok="2024"' in xml
    assert b'mesic="03"' in xml


def test_kh_xml_strips_cz_prefix():
    xml = build_kh_xml("CZ12345678", "Test s.r.o.", "2024-03", KH_DATA_EMPTY)
    assert b'dic="12345678"' in xml


def test_kh_xml_includes_a1_entries():
    xml = build_kh_xml("CZ12345678", "Test s.r.o.", "2024-03", KH_DATA_WITH_ENTRIES)
    assert b"VetaA1" in xml
    assert b"INV-2024-001" in xml


def test_kh_xml_includes_b2_entries():
    xml = build_kh_xml("CZ12345678", "Test s.r.o.", "2024-03", KH_DATA_WITH_ENTRIES)
    assert b"VetaB2" in xml
    assert b"FAK-2024-099" in xml


def test_kh_xml_includes_aggregate_sections():
    xml = build_kh_xml("CZ12345678", "Test s.r.o.", "2024-03", KH_DATA_EMPTY)
    assert b"VetaA4" in xml
    assert b"VetaB3" in xml


def test_kh_xml_duzp_format():
    xml = build_kh_xml("CZ12345678", "Test s.r.o.", "2024-03", KH_DATA_WITH_ENTRIES)
    assert b"15032024" in xml  # duzp formatted as ddmmYYYY
