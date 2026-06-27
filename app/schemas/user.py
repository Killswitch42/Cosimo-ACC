import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: str
    full_name: str
    password: str
    role: str = "accountant"


class UserOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}
