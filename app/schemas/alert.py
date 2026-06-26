from datetime import date, datetime
import uuid
from pydantic import BaseModel


class AlertResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    severity: str
    category: str
    rule_code: str
    title: str
    detail: str
    suggested_action: str | None
    source_type: str | None
    source_id: uuid.UUID | None
    deadline_date: date | None
    status: str
    resolved_at: datetime | None
    resolved_by: str | None
    resolution_note: str | None
    ai_generated: bool
    ai_confidence: float | None

    model_config = {"from_attributes": True}
