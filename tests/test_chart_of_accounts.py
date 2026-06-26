from app.seed.chart_of_accounts import get_full_chart


def test_chart_has_all_classes():
    accounts = get_full_chart()
    classes = {a["account_class"] for a in accounts}
    assert classes == {0, 1, 2, 3, 4, 5, 6, 7}


def test_vat_account_343_exists():
    accounts = get_full_chart()
    vat = next((a for a in accounts if a["account_number"] == "343"), None)
    assert vat is not None
    assert vat["is_vat_account"] is True


def test_all_accounts_have_required_fields():
    required = ["account_number", "name_cz", "account_class", "balance_type", "account_type"]
    for account in get_full_chart():
        for field in required:
            assert field in account, f"Missing {field} in {account.get('account_number')}"


def test_balance_types_are_valid():
    for account in get_full_chart():
        assert account["balance_type"] in ("DEBIT", "CREDIT"), (
            f"Invalid balance_type in {account['account_number']}"
        )


def test_expense_accounts_are_debit():
    for account in get_full_chart():
        if account["account_type"] == "EXPENSE":
            assert account["balance_type"] == "DEBIT"


def test_revenue_accounts_are_credit():
    for account in get_full_chart():
        if account["account_type"] == "REVENUE":
            assert account["balance_type"] == "CREDIT"
