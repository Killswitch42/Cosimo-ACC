import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.invoice import Invoice
from app.schemas.invoice import InvoiceCreate, InvoiceResponse
from app.services.invoice_service import InvoiceError, post_invoice, void_invoice
from app.services.ledger_service import LedgerError, get_default_company_id

router = APIRouter(prefix="/invoices", tags=["invoices"])


async def get_session():
    async with async_session_factory() as session:
        async with session.begin():
            yield session


@router.post("/", response_model=InvoiceResponse)
async def create_invoice(
    data: InvoiceCreate,
    session: AsyncSession = Depends(get_session),
):
    try:
        company_id = await get_default_company_id(session)
        invoice = await post_invoice(session, company_id, data, posted_by="api_user")
        return invoice
    except (InvoiceError, LedgerError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/", response_model=list[InvoiceResponse])
async def list_invoices(
    direction: str | None = Query(None, description="ISSUED or RECEIVED"),
    status: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
):
    company_id = await get_default_company_id(session)
    query = select(Invoice).where(Invoice.company_id == company_id)
    if direction:
        query = query.where(Invoice.direction == direction)
    if status:
        query = query.where(Invoice.status == status)
    query = query.order_by(Invoice.duzp.desc())
    result = await session.execute(query)
    return list(result.scalars().all())


@router.post("/{invoice_id}/void")
async def void_invoice_endpoint(
    invoice_id: uuid.UUID,
    void_reason: str = Query(..., description="Reason for voiding the invoice"),
    session: AsyncSession = Depends(get_session),
):
    try:
        company_id = await get_default_company_id(session)
        invoice = await void_invoice(
            session, invoice_id, company_id, void_reason, posted_by="api_user"
        )
        return {
            "invoice_number": invoice.invoice_number,
            "status": invoice.status,
            "void_reason": invoice.void_reason,
        }
    except (InvoiceError, LedgerError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
