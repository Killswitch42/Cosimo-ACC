import uuid
from datetime import date, datetime
from pydantic import BaseModel


class FilingRecordResponse(BaseModel):
    id: uuid.UUID
    filing_type: str
    period_label: str
    status: str
    reconciliation_passed: bool
    reconciliation_detail: str | None
    file_path: str | None
    file_checksum_sha256: str | None
    deadline_date: date | None
    generated_at: datetime | None
    generated_by: str | None

    model_config = {"from_attributes": True}
