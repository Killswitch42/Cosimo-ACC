from decimal import Decimal

from pydantic import BaseModel


class AccountBalanceResponse(BaseModel):
    account_number: str
    account_name_cz: str
    opening_balance_czk: Decimal
    period_debit_czk: Decimal
    period_credit_czk: Decimal
    closing_balance_czk: Decimal
    entry_count: int

    model_config = {"from_attributes": True}
