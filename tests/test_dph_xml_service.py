import pytest
from decimal import Decimal

from app.services.dph_xml_service import (
    build_dph_priznani_xml, compute_checksum, validate_against_xsd
)


SAMPLE_DATA = {
    "vat_period": "2024-03",
    "row_01_base": Decimal("50000.00"), "row_01_tax": Decimal("10500.00"),
    "row_02_base": Decimal("10000.00"), "row_02_tax": Decimal("1200.00"),
    "row_40_base": Decimal("20000.00"), "row_40_tax": Decimal("4200.00"),
    "row_41_base": Decimal("5000.00"),  "row_41_tax": Decimal("600.00"),
    "row_63_total_output_tax": Decimal("11700.00"),
    "row_64_total_input_tax": Decimal("4800.00"),
    "row_65_net_vat": Decimal("6900.00"),
    "is_excess_deduction": False,
}

EXCESS_DATA = {
    **SAMPLE_DATA,
    "row_65_net_vat": Decimal("-1000.00"),
    "is_excess_deduction": True,
}


def test_build_dph_xml_returns_bytes():
    xml = build_dph_priznani_xml(
        "CZ12345678", "Medici Analytica s.r.o.", "2024-03", SAMPLE_DATA
    )
    assert isinstance(xml, bytes)


def test_build_dph_xml_has_declaration():
    xml = build_dph_priznani_xml(
        "CZ12345678", "Medici Analytica s.r.o.", "2024-03", SAMPLE_DATA
    )
    assert xml.startswith(b"<?xml")


def test_build_dph_xml_contains_root_element():
    xml = build_dph_priznani_xml(
        "CZ12345678", "Medici Analytica s.r.o.", "2024-03", SAMPLE_DATA
    )
    assert b"Pisemnost" in xml
    assert b"DPHDP3" in xml


def test_build_dph_xml_sets_period_month():
    xml = build_dph_priznani_xml(
        "CZ12345678", "Test s.r.o.", "2024-06", SAMPLE_DATA
    )
    assert b'mesic="06"' in xml
    assert b'rok="2024"' in xml


def test_build_dph_xml_quarterly_sets_quarter():
    data = {**SAMPLE_DATA, "vat_period": "2024-03"}
    xml = build_dph_priznani_xml(
        "CZ12345678", "Test s.r.o.", "2024-03", data, is_quarterly=True
    )
    assert b"ctvrtleti" in xml
    assert b"mesic" not in xml


def test_build_dph_xml_strips_cz_from_dic():
    xml = build_dph_priznani_xml(
        "CZ12345678", "Test s.r.o.", "2024-03", SAMPLE_DATA
    )
    assert b'dic="12345678"' in xml


def test_build_dph_xml_vlastni_danove_povinnosti():
    xml = build_dph_priznani_xml(
        "CZ12345678", "Test s.r.o.", "2024-03", SAMPLE_DATA
    )
    assert b"R65_1" in xml
    assert b"R65_2" not in xml


def test_build_dph_xml_nadmerny_odpocet():
    xml = build_dph_priznani_xml(
        "CZ12345678", "Test s.r.o.", "2024-03", EXCESS_DATA
    )
    assert b"R65_2" in xml
    assert b"R65_1" not in xml


def test_compute_checksum_returns_64_char_hex():
    xml = build_dph_priznani_xml(
        "CZ12345678", "Test s.r.o.", "2024-03", SAMPLE_DATA
    )
    checksum = compute_checksum(xml)
    assert len(checksum) == 64
    assert all(c in "0123456789abcdef" for c in checksum)


def test_compute_checksum_is_deterministic():
    xml = build_dph_priznani_xml(
        "CZ12345678", "Test s.r.o.", "2024-03", SAMPLE_DATA
    )
    assert compute_checksum(xml) == compute_checksum(xml)


def test_validate_against_xsd_missing_file():
    xml = build_dph_priznani_xml(
        "CZ12345678", "Test s.r.o.", "2024-03", SAMPLE_DATA
    )
    valid, errors = validate_against_xsd(xml, "/nonexistent.xsd")
    assert not valid
    assert errors
