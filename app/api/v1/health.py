from fastapi import APIRouter
from sqlalchemy import text

from app.database import async_session_factory

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Phase 01 health check; confirms DB connectivity and account count."""
    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT COUNT(*) FROM ledger_accounts WHERE is_active = true")
        )
        account_count = result.scalar()
    return {
        "status": "healthy",
        "service": "Medici Analytica Accounting",
        "phase": "01",
        "ledger_accounts_loaded": account_count,
    }
