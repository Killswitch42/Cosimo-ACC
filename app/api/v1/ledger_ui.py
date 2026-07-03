"""
Ledger (Účetnictví) viewer — read-only list of posted journal entries with
drill-down to the individual debit/credit lines. Entries are immutable
(Czech §31 retention), so this is view-only; corrections happen via voiding
an invoice, which posts a reversal entry that shows up here too.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.database import async_session_factory
from app.models.journal_entry import JournalEntry
from app.models.user import User
from app.services.auth_service import get_current_user, get_current_user_web

router = APIRouter(tags=["ledger-ui"])
templates = Jinja2Templates(directory="app/templates")

ENTRY_LIMIT = 200


@router.get("/ledger", response_class=HTMLResponse)
async def ledger_page(
    request: Request,
    user: User = Depends(get_current_user_web),
):
    async with async_session_factory() as session:
        result = await session.execute(
            select(JournalEntry)
            .where(JournalEntry.company_id == user.company_id)
            .order_by(JournalEntry.entry_date.desc(), JournalEntry.posting_date.desc())
            .limit(ENTRY_LIMIT)
        )
        entries = list(result.scalars().all())
    return templates.TemplateResponse(
        "ledger.html",
        {"request": request, "user": user, "entries": entries, "limit": ENTRY_LIMIT},
    )


@router.get("/ledger/{entry_id}", response_class=HTMLResponse)
async def ledger_entry_detail(
    entry_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
):
    async with async_session_factory() as session:
        entry = await session.get(JournalEntry, entry_id)
        if not entry or entry.company_id != user.company_id:
            raise HTTPException(status_code=404, detail="Účetní zápis nenalezen.")
        # Touch lines inside the session (selectin already loads them).
        lines = sorted(entry.lines, key=lambda l: l.line_order)
        return templates.TemplateResponse(
            "partials/journal_entry_detail.html",
            {"request": request, "entry": entry, "lines": lines},
        )
