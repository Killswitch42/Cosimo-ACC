"""
Bank feed — CSV/MT940 import and BankTransaction → Invoice reconciliation.

Mounted under /api/v1. All endpoints require an authenticated admin or
accountant (viewers may read the dashboard but not move money around).
"""
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.bank_transaction import BankTransaction
from app.models.invoice import Invoice
from app.models.user import User
from app.services.auth_service import require_role
from app.services.bank_import_service import (
    BankImportError,
    import_transactions,
    parse_csv,
    parse_mt940,
)
from app.services.bank_matching_service import reconcile, run_auto_match, unmatch
from app.services.ledger_service import LedgerError

router = APIRouter(prefix="/bank", tags=["bank"])


async def get_session():
    async with async_session_factory() as session:
        async with session.begin():
            yield session


class MatchRequest(BaseModel):
    invoice_id: uuid.UUID


def _serialise(tx: BankTransaction) -> dict:
    return {
        "id": str(tx.id),
        "transaction_date": tx.transaction_date.isoformat(),
        "amount_czk": str(tx.amount_czk),
        "direction": tx.direction,
        "variable_symbol": tx.variable_symbol,
        "counterparty_name": tx.counterparty_name,
        "counterparty_account": tx.counterparty_account,
        "description": tx.description,
        "match_status": tx.match_status,
        "is_reconciled": tx.is_reconciled,
        "matched_invoice_id": str(tx.matched_invoice_id) if tx.matched_invoice_id else None,
        "import_source": tx.import_source,
    }


@router.post("/import")
async def import_statement(
    file: UploadFile = File(...),
    format: str = Form(...),
    bank_account_number: str = Form(...),
    user: User = Depends(require_role("admin", "accountant")),
    session: AsyncSession = Depends(get_session),
):
    """Import a bank statement, then auto-match against open invoices."""
    content = await file.read()
    fmt = format.lower()
    try:
        if fmt == "csv":
            rows = parse_csv(content, bank_account_number, import_source="MANUAL_CSV")
        elif fmt == "mt940":
            rows = parse_mt940(content, import_source="MT940")
            for row in rows:
                row.setdefault("bank_account_number", bank_account_number)
                if not row.get("bank_account_number"):
                    row["bank_account_number"] = bank_account_number
        else:
            raise HTTPException(status_code=422, detail="format musí být 'csv' nebo 'mt940'.")
    except BankImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    created = await import_transactions(session, user.company_id, rows, import_source=fmt.upper())
    match_summary = await run_auto_match(session, user.company_id, posted_by=user.email)

    return {
        "imported": len(created),
        "parsed": len(rows),
        "duplicates_skipped": len(rows) - len(created),
        **match_summary,
    }


@router.get("/transactions")
async def list_transactions(
    status: str | None = Query(None, description="UNMATCHED | SUGGESTED | MATCHED | IGNORED"),
    user: User = Depends(require_role("admin", "accountant", "viewer")),
    session: AsyncSession = Depends(get_session),
):
    query = select(BankTransaction).where(BankTransaction.company_id == user.company_id)
    if status:
        query = query.where(BankTransaction.match_status == status.upper())
    query = query.order_by(BankTransaction.transaction_date.desc())
    result = await session.execute(query)
    return [_serialise(tx) for tx in result.scalars().all()]


@router.post("/transactions/{tx_id}/match")
async def match_transaction(
    tx_id: uuid.UUID,
    body: MatchRequest,
    user: User = Depends(require_role("admin", "accountant")),
    session: AsyncSession = Depends(get_session),
):
    tx = await session.get(BankTransaction, tx_id)
    if not tx or tx.company_id != user.company_id:
        raise HTTPException(status_code=404, detail="Transakce nenalezena.")
    invoice = await session.get(Invoice, body.invoice_id)
    if not invoice or invoice.company_id != user.company_id:
        raise HTTPException(status_code=404, detail="Faktura nenalezena.")
    try:
        await reconcile(session, tx, invoice, posted_by=user.email)
    except LedgerError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _serialise(tx)


@router.post("/transactions/{tx_id}/unmatch")
async def unmatch_transaction(
    tx_id: uuid.UUID,
    user: User = Depends(require_role("admin", "accountant")),
    session: AsyncSession = Depends(get_session),
):
    tx = await session.get(BankTransaction, tx_id)
    if not tx or tx.company_id != user.company_id:
        raise HTTPException(status_code=404, detail="Transakce nenalezena.")
    try:
        await unmatch(session, tx, posted_by=user.email)
    except LedgerError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _serialise(tx)


@router.post("/auto-match")
async def auto_match(
    user: User = Depends(require_role("admin", "accountant")),
    session: AsyncSession = Depends(get_session),
):
    return await run_auto_match(session, user.company_id, posted_by=user.email)
