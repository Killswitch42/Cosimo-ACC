import pytest
from decimal import Decimal

from app.services.pdf_report_service import render_rozvaha_pdf, render_vzz_pdf


ROZVAHA_DATA = {
    "aktiva": {
        "B.I":   Decimal("150000.00"),
        "B.II":  Decimal("500000.00"),
        "B.III": Decimal("0.00"),
        "C.I":   Decimal("30000.00"),
        "C.II":  Decimal("120000.00"),
        "C.III": Decimal("0.00"),
        "C.IV":  Decimal("50000.00"),
    },
    "aktiva_celkem": Decimal("850000.00"),
    "pasiva": {
        "A.I":   Decimal("200000.00"),
        "A.II":  Decimal("0.00"),
        "A.III": Decimal("0.00"),
        "A.IV":  Decimal("300000.00"),
        "A.V":   Decimal("100000.00"),
        "B.I":   Decimal("0.00"),
        "B.II":  Decimal("0.00"),
        "B.III": Decimal("250000.00"),
        "C":     Decimal("0.00"),
    },
    "pasiva_celkem": Decimal("850000.00"),
    "is_balanced": True,
    "difference": Decimal("0.00"),
}

VZZ_DATA = {
    "lines": {
        "I":   Decimal("600000.00"),
        "B":   Decimal("100000.00"),
        "C":   Decimal("80000.00"),
        "D":   Decimal("200000.00"),
        "E":   Decimal("50000.00"),
        "L":   Decimal("36000.00"),
    },
    "total_revenue": Decimal("600000.00"),
    "total_expense_excl_tax": Decimal("430000.00"),
    "profit_before_tax": Decimal("170000.00"),
    "income_tax_current": Decimal("36000.00"),
    "income_tax_deferred": Decimal("0.00"),
    "net_profit_loss": Decimal("134000.00"),
}


def test_render_rozvaha_pdf_returns_bytes():
    pdf = render_rozvaha_pdf("Test s.r.o.", "12345678", "2024", ROZVAHA_DATA)
    assert isinstance(pdf, bytes)
    assert len(pdf) > 1000


def test_render_rozvaha_pdf_is_pdf():
    pdf = render_rozvaha_pdf("Test s.r.o.", "12345678", "2024", ROZVAHA_DATA)
    assert pdf[:4] == b"%PDF"


def test_render_rozvaha_pdf_unbalanced_includes_warning():
    unbalanced = {
        **ROZVAHA_DATA,
        "is_balanced": False,
        "difference": Decimal("100.00"),
        "pasiva_celkem": Decimal("849900.00"),
    }
    pdf = render_rozvaha_pdf("Test s.r.o.", "12345678", "2024", unbalanced)
    assert isinstance(pdf, bytes)
    assert len(pdf) > 1000


def test_render_vzz_pdf_returns_bytes():
    pdf = render_vzz_pdf("Test s.r.o.", "12345678", "2024", VZZ_DATA)
    assert isinstance(pdf, bytes)
    assert len(pdf) > 1000


def test_render_vzz_pdf_is_pdf():
    pdf = render_vzz_pdf("Test s.r.o.", "12345678", "2024", VZZ_DATA)
    assert pdf[:4] == b"%PDF"


def test_render_vzz_pdf_different_periods_differ():
    pdf1 = render_vzz_pdf("Test s.r.o.", "12345678", "2024", VZZ_DATA)
    pdf2 = render_vzz_pdf("Test s.r.o.", "12345678", "2023", VZZ_DATA)
    assert pdf1 != pdf2
