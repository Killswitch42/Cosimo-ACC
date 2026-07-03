"""
PDF rendering of rozvaha and VZZ.
Uses reportlab — pure Python, no system binary dependencies.
"""
import io
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
)


def _fmt_czk(value: Decimal) -> str:
    formatted = f"{abs(value):,.2f}".replace(",", " ").replace(".", ",")
    sign = "-" if value < 0 else ""
    return f"{sign}{formatted} Kč"


_HEADER_STYLE = TableStyle([
    ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
    ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
    ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
    ("ALIGN",       (1, 0), (1, -1), "RIGHT"),
    ("FONTNAME",    (0, -1), (-1, -1), "Helvetica-Bold"),
    ("LINEBELOW",   (0, 0), (-1, 0), 1, colors.black),
    ("LINEABOVE",   (0, -1), (-1, -1), 1, colors.black),
])


def render_rozvaha_pdf(
    company_name: str,
    company_ico: str,
    period_label: str,
    rozvaha_data: dict,
) -> bytes:
    """Render rozvaha as PDF bytes."""
    buffer  = io.BytesIO()
    doc     = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm)
    styles  = getSampleStyleSheet()
    title_s = ParagraphStyle("T", parent=styles["Heading1"], fontSize=14)
    elems   = []

    elems.append(Paragraph(f"Rozvaha — {company_name}", title_s))
    elems.append(Paragraph(f"IČO: {company_ico} | Období: {period_label}", styles["Normal"]))
    elems.append(Spacer(1, 8*mm))

    # AKTIVA
    elems.append(Paragraph("AKTIVA", styles["Heading2"]))
    rows = [["Položka", "Hodnota"]]
    for line, val in rozvaha_data["aktiva"].items():
        rows.append([line, _fmt_czk(val)])
    rows.append(["AKTIVA CELKEM", _fmt_czk(rozvaha_data["aktiva_celkem"])])
    t = Table(rows, colWidths=[310, 140])
    t.setStyle(_HEADER_STYLE)
    elems.append(t)
    elems.append(Spacer(1, 8*mm))

    # PASIVA
    elems.append(Paragraph("PASIVA", styles["Heading2"]))
    rows = [["Položka", "Hodnota"]]
    for line, val in rozvaha_data["pasiva"].items():
        rows.append([line, _fmt_czk(val)])
    rows.append(["PASIVA CELKEM", _fmt_czk(rozvaha_data["pasiva_celkem"])])
    t = Table(rows, colWidths=[310, 140])
    t.setStyle(_HEADER_STYLE)
    elems.append(t)

    if not rozvaha_data["is_balanced"]:
        warn = ParagraphStyle("W", parent=styles["Normal"], textColor=colors.red)
        elems.append(Spacer(1, 4*mm))
        elems.append(Paragraph(
            f"UPOZORNĚNÍ: Rozvaha není vyrovnaná. Rozdíl: {_fmt_czk(rozvaha_data['difference'])}",
            warn,
        ))

    doc.build(elems)
    buffer.seek(0)
    return buffer.read()


def render_dppo_pdf(
    company_name: str,
    company_ico: str,
    period_label: str,
    dppo_data: dict,
) -> bytes:
    """Render the simplified DPPO estimate as PDF bytes."""
    buffer  = io.BytesIO()
    doc     = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm)
    styles  = getSampleStyleSheet()
    title_s = ParagraphStyle("T", parent=styles["Heading1"], fontSize=14)
    elems   = []

    elems.append(Paragraph(f"Daň z příjmů právnických osob — {company_name}", title_s))
    elems.append(Paragraph(f"IČO: {company_ico} | Období: {period_label}", styles["Normal"]))
    elems.append(Spacer(1, 8*mm))

    rows = [["Položka", "Hodnota"]]
    rows.append(["Výsledek hospodaření před zdaněním", _fmt_czk(dppo_data["profit_before_tax"])])
    for adj in dppo_data["adjustments"]:
        rows.append([f"+ Připočitatelná položka ({adj['account']})", _fmt_czk(adj["amount"])])
    rows.append(["Základ daně", _fmt_czk(dppo_data["tax_base"])])
    rows.append(["Základ daně zaokrouhlený (na tisíce dolů)", _fmt_czk(dppo_data["rounded_tax_base"])])
    rows.append([f"Sazba daně", f"{dppo_data['rate']} %"])
    rows.append(["Daň z příjmů", _fmt_czk(dppo_data["tax"])])
    rows.append(["Výsledek hospodaření po zdanění", _fmt_czk(dppo_data["net_profit_after_tax"])])

    style = TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN",       (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME",    (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE",   (0, -1), (-1, -1), 1, colors.black),
    ])
    t = Table(rows, colWidths=[310, 140])
    t.setStyle(style)
    elems.append(t)

    if dppo_data.get("is_simplified"):
        note = ParagraphStyle("N", parent=styles["Normal"], fontSize=8, textColor=colors.grey)
        elems.append(Spacer(1, 6*mm))
        elems.append(Paragraph(
            "Zjednodušený výpočet: zahrnuje pouze rozpoznané neuznatelné náklady "
            "(§ 25 ZDP). Neobsahuje daňovou ztrátu, odčitatelné položky ani zálohy. "
            "Nejedná se o daňové přiznání (DPDPPO).",
            note,
        ))

    doc.build(elems)
    buffer.seek(0)
    return buffer.read()


def render_vzz_pdf(
    company_name: str,
    company_ico: str,
    period_label: str,
    vzz_data: dict,
) -> bytes:
    """Render VZZ (profit and loss statement) as PDF bytes."""
    buffer  = io.BytesIO()
    doc     = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20*mm, bottomMargin=20*mm)
    styles  = getSampleStyleSheet()
    title_s = ParagraphStyle("T", parent=styles["Heading1"], fontSize=14)
    elems   = []

    elems.append(Paragraph(f"Výkaz zisku a ztráty — {company_name}", title_s))
    elems.append(Paragraph(f"IČO: {company_ico} | Období: {period_label}", styles["Normal"]))
    elems.append(Spacer(1, 8*mm))

    rows = [["Řádek", "Hodnota"]]
    for line, val in vzz_data["lines"].items():
        rows.append([line, _fmt_czk(val)])
    rows.append(["Výsledek hospodaření před zdaněním", _fmt_czk(vzz_data["profit_before_tax"])])
    rows.append(["Daň z příjmů splatná",               _fmt_czk(vzz_data["income_tax_current"])])
    rows.append(["Daň z příjmů odložená",              _fmt_czk(vzz_data["income_tax_deferred"])])
    rows.append(["Výsledek hospodaření za účetní období", _fmt_czk(vzz_data["net_profit_loss"])])

    bold_rows = len(rows) - 4  # last four are summary rows

    style = TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR",   (0, 0), (-1, 0), colors.white),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN",       (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME",    (0, bold_rows), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE",   (0, bold_rows), (-1, bold_rows), 1, colors.black),
    ])
    t = Table(rows, colWidths=[310, 140])
    t.setStyle(style)
    elems.append(t)

    doc.build(elems)
    buffer.seek(0)
    return buffer.read()
