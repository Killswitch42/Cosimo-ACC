"""
Bank reconciliation UI — server-rendered page + HTMX partials.

Kept separate from the JSON API (app/api/v1/bank.py) so browser flows return
HTML fragments while the API returns JSON. Both call the same services.
"""
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.bank_transaction import BankTransaction
from app.models.invoice import Invoice
from app.models.user import User
from app.services.auth_service import get_current_user, get_current_user_web
from app.services.bank_import_service import (
    BankImportError,
    import_transactions,
    parse_csv,
    parse_mt940,
)
from app.services.bank_matching_service import reconcile, run_auto_match, unmatch
from app.services.ledger_service import LedgerError

router = APIRouter(tags=["bank-ui"])
templates = Jinja2Templates(directory="app/templates")


async def get_session():
    async with async_session_factory() as session:
        async with session.begin():
            yield session


async def _table_context(session: AsyncSession, request: Request, company_id: uuid.UUID) -> dict:
    tx_result = await session.execute(
        select(BankTransaction)
        .where(BankTransaction.company_id == company_id)
        .order_by(BankTransaction.transaction_date.desc())
    )
    transactions = list(tx_result.scalars().all())

    open_result = await session.execute(
        select(Invoice).where(
            Invoice.company_id == company_id,
            Invoice.status == "posted",
            Invoice.payment_date.is_(None),
        )
    )
    open_invoices = list(open_result.scalars().all())
    invoices_by_id = {i.id: i for i in open_invoices}
    return {
        "request": request,
        "transactions": transactions,
        "open_invoices": open_invoices,
        "invoices_by_id": invoices_by_id,
    }


@router.get("/bank", response_class=HTMLResponse)
async def bank_page(
    request: Request,
    user: User = Depends(get_current_user_web),
    session: AsyncSession = Depends(get_session),
):
    context = await _table_context(session, request, user.company_id)
    context["user"] = user
    return templates.TemplateResponse("bank.html", context)


@router.post("/bank/upload", response_class=HTMLResponse)
async def bank_upload(
    request: Request,
    file: UploadFile = File(...),
    format: str = Form(...),
    bank_account_number: str = Form(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    content = await file.read()
    fmt = format.lower()
    try:
        if fmt == "csv":
            rows = parse_csv(content, bank_account_number, import_source="MANUAL_CSV")
        elif fmt == "mt940":
            rows = parse_mt940(content, import_source="MT940")
            for row in rows:
                if not row.get("bank_account_number"):
                    row["bank_account_number"] = bank_account_number
        else:
            raise HTTPException(status_code=422, detail="Neplatný formát.")
        await import_transactions(session, user.company_id, rows, import_source=fmt.upper())
        await run_auto_match(session, user.company_id, posted_by=user.email)
    except BankImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    context = await _table_context(session, request, user.company_id)
    return templates.TemplateResponse("partials/bank_table.html", context)


@router.post("/bank/tx/{tx_id}/confirm", response_class=HTMLResponse)
async def bank_confirm(
    tx_id: uuid.UUID,
    request: Request,
    invoice_id: uuid.UUID = Form(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    tx = await session.get(BankTransaction, tx_id)
    invoice = await session.get(Invoice, invoice_id)
    if not tx or tx.company_id != user.company_id or not invoice:
        raise HTTPException(status_code=404, detail="Nenalezeno.")
    try:
        await reconcile(session, tx, invoice, posted_by=user.email)
    except LedgerError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    context = await _table_context(session, request, user.company_id)
    return templates.TemplateResponse("partials/bank_table.html", context)


@router.post("/bank/tx/{tx_id}/unmatch", response_class=HTMLResponse)
async def bank_unmatch(
    tx_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    tx = await session.get(BankTransaction, tx_id)
    if not tx or tx.company_id != user.company_id:
        raise HTTPException(status_code=404, detail="Nenalezeno.")
    try:
        await unmatch(session, tx, posted_by=user.email)
    except LedgerError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    context = await _table_context(session, request, user.company_id)
    return templates.TemplateResponse("partials/bank_table.html", context)


@router.post("/bank/auto-match", response_class=HTMLResponse)
async def bank_auto_match(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await run_auto_match(session, user.company_id, posted_by=user.email)
    context = await _table_context(session, request, user.company_id)
    return templates.TemplateResponse("partials/bank_table.html", context)
