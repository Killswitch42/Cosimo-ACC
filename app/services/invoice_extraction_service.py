"""
Invoice extraction — read an uploaded invoice/receipt and pull out the fields
needed to pre-fill the entry form.

Two layers, so it degrades gracefully:
  1. Deterministic heuristics over the PDF's text layer (labels that are
     standard on Czech invoices: Variabilní symbol, IČ/IČO, DIČ, dates,
     CELKEM…). Works offline, no API credits.
  2. Grok (xAI) refinement on top — used automatically when credits are
     available; skipped cleanly (falls back to heuristics) when not.

Photos / scanned PDFs without a text layer need OCR (not available yet); the
caller surfaces a "fill manually" message in that case.
"""
from __future__ import annotations

import io
import json
import re
from datetime import datetime

from app.services.ai_client import AIClientError, call_claude

ALLOWED_VAT = {"0", "0.0", "0.00", "12", "12.0", "12.00", "21", "21.0", "21.00"}
_DATE_RE = r"(\d{1,2}\.\s?\d{1,2}\.\s?\d{4})"


class ExtractionError(Exception):
    pass


def extract_text(content: bytes, content_type: str | None, filename: str | None) -> str:
    name = (filename or "").lower()
    is_pdf = (
        (content_type or "").lower() == "application/pdf"
        or name.endswith(".pdf")
        or content[:5] == b"%PDF-"
    )
    if not is_pdf:
        raise ExtractionError(
            "Automatické čtení zatím podporuje pouze PDF s textovou vrstvou. "
            "U fotek a skenů vyplňte údaje ručně."
        )

    text = ""
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(content)) as pdf:
            text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    except Exception:
        text = ""

    if not text.strip():
        try:
            import pypdf

            reader = pypdf.PdfReader(io.BytesIO(content))
            text = "\n".join((pg.extract_text() or "") for pg in reader.pages)
        except Exception:
            text = ""

    if not text.strip():
        raise ExtractionError(
            "PDF neobsahuje textovou vrstvu (patrně sken). Vyplňte údaje ručně."
        )
    return text


def _to_iso(cz_date: str) -> str | None:
    cz = cz_date.replace(" ", "")
    try:
        return datetime.strptime(cz, "%d.%m.%Y").date().isoformat()
    except ValueError:
        return None


def _amount(s: str) -> str | None:
    s = s.replace("\xa0", "").replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    m = re.search(r"-?\d+(?:\.\d{1,2})?", s)
    return m.group(0) if m else None


def heuristic_fields(text: str) -> dict:
    f: dict = {"direction": "RECEIVED"}

    m = re.search(r"Variabiln[íi]\s*symbol[:\s]*([0-9]{1,10})", text, re.I)
    if m:
        f["variable_symbol"] = m.group(1)

    m = re.search(r"FAKTURA\s*(?:č\.?|číslo)?\s*:?\s*([0-9][0-9/\-]{3,})", text, re.I)
    if m:
        f["invoice_number"] = m.group(1).strip()
    elif f.get("variable_symbol"):
        f["invoice_number"] = f["variable_symbol"]

    # Supplier (Dodavatel) IČO/DIČ appear before the "Odběratel" block.
    head = text
    om = re.search(r"Odb[ěe]ratel", text, re.I)
    if om:
        head = text[: om.start()]
    mi = re.search(r"I[ČC]O?[:\s]*([0-9]{8})", head)
    if mi:
        f["counterparty_ico"] = mi.group(1)
    md = re.search(r"DI[ČC][:\s]*([A-Z]{2}[0-9]+)", head)
    if md:
        f["counterparty_dic"] = md.group(1)

    mv = re.search(r"vystaven[íi][:\s]*" + _DATE_RE, text, re.I)
    if mv and _to_iso(mv.group(1)):
        f["invoice_date"] = _to_iso(mv.group(1))
    ms = re.search(r"splatnost[i]?[:\s]*" + _DATE_RE, text, re.I)
    if ms and _to_iso(ms.group(1)):
        f["due_date"] = _to_iso(ms.group(1))
    mu = re.search(r"(?:DUZP|zdaniteln[ée]ho pln[ěe]n[íi])[:\s]*" + _DATE_RE, text, re.I)
    if mu and _to_iso(mu.group(1)):
        f["duzp"] = _to_iso(mu.group(1))

    dm = re.search(r"Dodavatel[:\s]*\n+\s*([^\n]+)", text, re.I)
    if dm:
        f["counterparty_name"] = dm.group(1).strip()

    tm = re.search(r"CELKEM\s*K\s*[ÚU]HRAD[ĚE][:\s]*([0-9 \xa0.,]+)", text, re.I)
    if not tm:
        tm = re.search(r"Sou[čc]et\s*polo[žz]ek[:\s]*([0-9 \xa0.,]+)", text, re.I)
    if tm:
        amt = _amount(tm.group(1))
        if amt:
            f["unit_price_net"] = amt

    if re.search(r"nen[íi]\s*pl[áa]tce\s*DPH", text, re.I):
        f["vat_rate"] = "0.00"

    fm = re.search(r"Fakturujeme[^\n]*", text, re.I)
    if fm:
        f["line_description"] = fm.group(0).strip()[:200]

    return f


_GROK_SYSTEM = (
    "Jsi extraktor dat z českých faktur. Z textu faktury vrať POUZE JSON "
    "(žádný markdown, žádný komentář) s klíči: "
    'direction ("RECEIVED" pro přijatou fakturu/účtenku, jinak "ISSUED"), '
    "invoice_number, variable_symbol, invoice_date, duzp, due_date (vše YYYY-MM-DD), "
    "counterparty_name (název DODAVATELE), counterparty_ico (8 číslic, IČO dodavatele), "
    "counterparty_dic, unit_price_net (celková částka bez DPH jako číslo), "
    'vat_rate ("21.00", "12.00" nebo "0.00"), line_description (stručný popis plnění). '
    "Chybějící údaje vynech. Vrať pouze JSON."
)


async def grok_fields(text: str) -> dict | None:
    reply, _ = await call_claude(_GROK_SYSTEM, text[:6000], max_tokens=800)
    m = re.search(r"\{.*\}", reply.strip(), re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return {k: v for k, v in data.items() if v not in (None, "", "null")}


def _normalize(f: dict) -> dict:
    out = dict(f)

    if "counterparty_ico" in out:
        digits = "".join(ch for ch in str(out["counterparty_ico"]) if ch.isdigit())
        out["counterparty_ico"] = digits[:8] if len(digits) >= 8 else digits

    if "unit_price_net" in out:
        amt = _amount(str(out["unit_price_net"]))
        if amt:
            out["unit_price_net"] = amt

    if "vat_rate" in out:
        vr = str(out["vat_rate"]).replace("%", "").strip()
        if vr in ALLOWED_VAT:
            out["vat_rate"] = f"{float(vr):.2f}"
        else:
            out.pop("vat_rate", None)

    for key in ("invoice_date", "duzp", "due_date"):
        if key in out and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(out[key])):
            iso = _to_iso(str(out[key]))
            if iso:
                out[key] = iso
            else:
                out.pop(key, None)

    if out.get("direction") not in ("RECEIVED", "ISSUED"):
        out["direction"] = "RECEIVED"
    return out


async def extract_invoice(
    content: bytes, content_type: str | None, filename: str | None
) -> tuple[dict, str]:
    """Return (fields, source_note). Never raises for AI issues — only for
    files it genuinely cannot read (raises ExtractionError)."""
    text = extract_text(content, content_type, filename)
    fields = heuristic_fields(text)
    source = "textová vrstva PDF (heuristika)"
    try:
        ai = await grok_fields(text)
        if ai:
            fields = {**fields, **ai}  # AI values take precedence
            source = "Grok AI + heuristika"
    except AIClientError:
        source = "heuristika — AI nedostupná (zkontrolujte kredit xAI)"
    except Exception:
        pass
    return _normalize(fields), source
