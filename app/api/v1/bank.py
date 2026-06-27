"""
Bank feed integration — STUB ONLY for Phase 06.

Phase 07 will implement:
  - Czech PSD2 bank APIs, MT940/CSV import
  - BankTransaction → Invoice matching engine
  - Auto-reconciliation suggestions via AlertRecord
"""
from fastapi import APIRouter, Depends, HTTPException

from app.models.user import User
from app.services.auth_service import require_role

router = APIRouter(prefix="/bank", tags=["bank"])


@router.post("/import")
async def import_bank_transactions_stub(
    user: User = Depends(require_role("admin", "accountant")),
):
    raise HTTPException(
        status_code=501,
        detail=(
            "Bank feed import is not yet implemented. "
            "This endpoint is a placeholder for Phase 07. "
            "The bank_transactions table and model already exist — "
            "see app/models/bank_transaction.py."
        ),
    )
