from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.services.ledger_service import get_default_company_id
from app.services.vat_service import get_kh_detail_entries, get_vat_period_totals

router = APIRouter(prefix="/vat-register", tags=["vat"])


async def get_session():
    async with async_session_factory() as session:
        yield session


@router.get("/period-totals")
async def vat_period_totals(
    vat_period: str = Query(..., description="Format: YYYY-MM e.g. 2024-03"),
    session: AsyncSession = Depends(get_session),
):
    company_id = await get_default_company_id(session)
    totals = await get_vat_period_totals(session, company_id, vat_period)
    return {"vat_period": vat_period, "totals": totals}


@router.get("/kh-detail")
async def kh_detail(
    vat_period: str = Query(..., description="Format: YYYY-MM"),
    kh_section: str = Query(..., description="A1, B1, or B2"),
    session: AsyncSession = Depends(get_session),
):
    company_id = await get_default_company_id(session)
    entries = await get_kh_detail_entries(session, company_id, vat_period, kh_section)
    return {
        "vat_period": vat_period,
        "kh_section": kh_section,
        "entries": [
            {
                "invoice_number": entry.invoice_number,
                "duzp": str(entry.duzp),
                "counterparty_dic": entry.counterparty_dic,
                "counterparty_name": entry.counterparty_name,
                "vat_rate": str(entry.vat_rate),
                "tax_base_czk": str(entry.tax_base_czk),
                "tax_amount_czk": str(entry.tax_amount_czk),
                "kh_detail_required": entry.kh_detail_required,
            }
            for entry in entries
        ],
        "count": len(entries),
    }
