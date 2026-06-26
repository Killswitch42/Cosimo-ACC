import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.schemas.journal_entry import (
    JournalEntryCreate,
    JournalEntryResponse,
    ReversalRequest,
)
from app.services.ledger_service import (
    LedgerError,
    get_default_company_id,
    post_journal_entry,
    reverse_journal_entry,
)

router = APIRouter(prefix="/journal-entries", tags=["ledger"])


async def get_session():
    async with async_session_factory() as session:
        async with session.begin():
            yield session


@router.post("/", response_model=JournalEntryResponse)
async def create_journal_entry(
    data: JournalEntryCreate,
    session: AsyncSession = Depends(get_session),
):
    try:
        company_id = await get_default_company_id(session)
        entry = await post_journal_entry(session, company_id, data, posted_by="api_user")
        return entry
    except LedgerError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{entry_id}/reverse", response_model=dict)
async def reverse_entry(
    entry_id: uuid.UUID,
    request: ReversalRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        company_id = await get_default_company_id(session)
        reversal, correction = await reverse_journal_entry(
            session, entry_id, company_id, request, posted_by="api_user"
        )
        return {
            "reversal_entry_number": reversal.entry_number,
            "correction_entry_number": correction.entry_number if correction else None,
        }
    except LedgerError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
