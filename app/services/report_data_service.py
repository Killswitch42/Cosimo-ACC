"""
Report data aggregation service.

Pulls together everything Phase 02–04 produced into the shapes needed
by the rozvaha, VZZ, DPH přiznání, and KH generators.
"""
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.services.vat_service import get_vat_period_totals, get_kh_detail_entries
from app.models.fiscal_period import FiscalPeriod
from app.models.company import Company


class ReportDataError(Exception):
    pass


async def get_period_by_label(
    session: AsyncSession,
    company_id: uuid.UUID,
    period_label: str,
) -> FiscalPeriod:
    result = await session.execute(
        select(FiscalPeriod).where(
            FiscalPeriod.company_id == company_id,
            FiscalPeriod.label == period_label,
        )
    )
    period = result.scalar_one_or_none()
    if not period:
        raise ReportDataError(f"Fiscal period '{period_label}' not found.")
    return period


async def get_company(session: AsyncSession, company_id: uuid.UUID) -> Company:
    result = await session.execute(
        select(Company).where(Company.id == company_id)
    )
    company = result.scalar_one_or_none()
    if not company:
        raise ReportDataError(f"Company {company_id} not found.")
    return company


async def build_dph_priznani_data(
    session: AsyncSession,
    company_id: uuid.UUID,
    vat_period: str,
) -> dict:
    """
    Build the data structure for the DPH přiznání (formulář vzor 25+).

    Covers the standard rows for a Czech s.r.o. with domestic supplies only.
    EU / import / reverse-charge rows flagged as TODO where not yet populated.
    """
    totals = await get_vat_period_totals(session, company_id, vat_period)

    r1_base = totals.get("issued_21", {}).get("base", Decimal("0.00"))
    r1_tax  = totals.get("issued_21", {}).get("tax",  Decimal("0.00"))
    r2_base = totals.get("issued_12", {}).get("base", Decimal("0.00"))
    r2_tax  = totals.get("issued_12", {}).get("tax",  Decimal("0.00"))
    r40_base = totals.get("received_21", {}).get("base", Decimal("0.00"))
    r40_tax  = totals.get("received_21", {}).get("tax",  Decimal("0.00"))
    r41_base = totals.get("received_12", {}).get("base", Decimal("0.00"))
    r41_tax  = totals.get("received_12", {}).get("tax",  Decimal("0.00"))

    total_output_tax = r1_tax + r2_tax
    total_input_tax  = r40_tax + r41_tax
    net_vat = total_output_tax - total_input_tax

    return {
        "vat_period": vat_period,
        "row_01_base": r1_base, "row_01_tax": r1_tax,
        "row_02_base": r2_base, "row_02_tax": r2_tax,
        "row_40_base": r40_base, "row_40_tax": r40_tax,
        "row_41_base": r41_base, "row_41_tax": r41_tax,
        "row_63_total_output_tax": total_output_tax,
        "row_64_total_input_tax": total_input_tax,
        "row_65_net_vat": net_vat,
        "is_excess_deduction": net_vat < Decimal("0.00"),
        "_todo_unhandled_rows": [
            "row_3_4_9: intra-EU acquisitions (§ 16 ZDPH) — not yet populated",
            "row_5: import of goods — not yet populated",
            "row_20_21: intra-EU supplies (§ 64 ZDPH) — see souhrnné hlášení service",
            "row_26: reverse charge domestic (§ 92a) — verify B1 entries reflected",
        ],
    }


async def build_kh_data(
    session: AsyncSession,
    company_id: uuid.UUID,
    vat_period: str,
) -> dict:
    """Build the kontrolní hlášení data structure."""
    a1_entries = await get_kh_detail_entries(session, company_id, vat_period, "A1")
    b1_entries = await get_kh_detail_entries(session, company_id, vat_period, "B1")
    b2_entries = await get_kh_detail_entries(session, company_id, vat_period, "B2")
    totals     = await get_vat_period_totals(session, company_id, vat_period)

    def entry_to_dict(e) -> dict:
        return {
            "invoice_number":   e.invoice_number,
            "duzp":             e.duzp,
            "counterparty_dic": e.counterparty_dic,
            "counterparty_name": e.counterparty_name,
            "tax_base_czk":     e.tax_base_czk,
            "tax_amount_czk":   e.tax_amount_czk,
            "vat_rate":         e.vat_rate,
        }

    return {
        "vat_period": vat_period,
        "section_a1_detail": [entry_to_dict(e) for e in a1_entries],
        "section_b1_detail": [
            {**entry_to_dict(e), "zdph_paragraph": "§92a"} for e in b1_entries
        ],
        "section_b2_detail": [entry_to_dict(e) for e in b2_entries],
        "section_a2_aggregate": {
            "base": (totals.get("issued_21", {}).get("base", Decimal("0.00"))
                     + totals.get("issued_12", {}).get("base", Decimal("0.00"))),
            "tax": (totals.get("issued_21", {}).get("tax", Decimal("0.00"))
                    + totals.get("issued_12", {}).get("tax", Decimal("0.00"))),
        },
        "section_b3_aggregate": {
            "base": (totals.get("received_21", {}).get("base", Decimal("0.00"))
                     + totals.get("received_12", {}).get("base", Decimal("0.00"))),
            "tax": (totals.get("received_21", {}).get("tax", Decimal("0.00"))
                    + totals.get("received_12", {}).get("tax", Decimal("0.00"))),
        },
    }
