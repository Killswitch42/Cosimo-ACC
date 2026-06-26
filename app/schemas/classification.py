import uuid
from decimal import Decimal
from pydantic import BaseModel


class ClassificationRequest(BaseModel):
    description: str
    counterparty: str | None = None
    amount_czk: Decimal | None = None
    direction: str | None = None


class ClassificationResponse(BaseModel):
    classification_id: uuid.UUID
    suggested_debit_account: str | None
    suggested_credit_account: str | None
    suggested_vat_rate: Decimal | None
    suggested_cost_centre: str | None
    reasoning: str | None
    confidence_score: Decimal | None

    model_config = {"from_attributes": True}
