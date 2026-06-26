import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.classification_log import ClassificationLog
from app.schemas.classification import ClassificationRequest, ClassificationResponse
from app.services.classifier_service import classify_transaction
from app.services.ledger_service import get_default_company_id

router = APIRouter(prefix="/ai", tags=["ai"])


async def get_session():
    async with async_session_factory() as session:
        async with session.begin():
            yield session


@router.post("/classify", response_model=ClassificationResponse)
async def classify(request: ClassificationRequest, session: AsyncSession = Depends(get_session)):
    company_id = await get_default_company_id(session)
    log = await classify_transaction(
        session=session,
        company_id=company_id,
        description=request.description,
        counterparty=request.counterparty,
        amount_czk=request.amount_czk,
        direction=request.direction,
    )
    return ClassificationResponse(
        classification_id=log.id,
        suggested_debit_account=log.suggested_debit_account,
        suggested_credit_account=log.suggested_credit_account,
        suggested_vat_rate=log.suggested_vat_rate,
        suggested_cost_centre=log.suggested_cost_centre,
        reasoning=log.reasoning,
        confidence_score=log.confidence_score,
    )


@router.post("/{classification_id}/feedback")
async def submit_feedback(
    classification_id: uuid.UUID,
    accepted: bool,
    override_debit_account: str | None = None,
    override_credit_account: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(ClassificationLog).where(ClassificationLog.id == classification_id)
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Classification not found.")
    log.was_accepted = accepted
    log.override_debit_account = override_debit_account
    log.override_credit_account = override_credit_account
    await session.flush()
    return {"status": "feedback_recorded"}
