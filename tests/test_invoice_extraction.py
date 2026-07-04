import pytest

from app.services.invoice_extraction_service import (
    ExtractionError,
    _normalize,
    extract_text,
    heuristic_fields,
)

SAMPLE = """FAKTURA c. 260100019
Dodavatel:
Golf club Rapotin z.s.
IC: 05557887
DIC: CZ05557887
Odberatel:
IC: 87147645
Daniel Medici
Variabilni symbol: 260100019
Datum vystaveni: 30.06.2026
Datum splatnosti: 10.07.2026
Firma neni platce DPH.
Fakturujeme Vam najem dle smlouvy
CELKEM K UHRADE 30 610,00
"""


def test_heuristics_pick_supplier_not_customer():
    f = heuristic_fields(SAMPLE)
    assert f["variable_symbol"] == "260100019"
    assert f["invoice_number"] == "260100019"
    # supplier's IČO/DIČ, not the customer's 87147645
    assert f["counterparty_ico"] == "05557887"
    assert f["counterparty_dic"] == "CZ05557887"
    assert f["invoice_date"] == "2026-06-30"
    assert f["due_date"] == "2026-07-10"
    assert f["unit_price_net"] == "30610.00"
    assert f["vat_rate"] == "0.00"  # "není plátce DPH"
    assert f["direction"] == "RECEIVED"
    assert "Golf" in f["counterparty_name"]


def test_extract_text_rejects_non_pdf():
    with pytest.raises(ExtractionError):
        extract_text(b"plain text", "text/plain", "note.txt")


def test_normalize_cleans_vat_ico_amount():
    out = _normalize(
        {"vat_rate": "21", "counterparty_ico": "CZ 05557887x", "unit_price_net": "1 234,50"}
    )
    assert out["vat_rate"] == "21.00"
    assert out["counterparty_ico"] == "05557887"
    assert out["unit_price_net"] == "1234.50"
