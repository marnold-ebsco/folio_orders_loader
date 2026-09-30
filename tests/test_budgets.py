from folio_orders_loader.budgets import check_budgets


class FakeResolver:
    def __init__(self, budgets):
        self.budgets = budgets  # fund code -> budget dict or None

    def fund(self, code):
        return {"id": "id-" + code, "code": code}

    def active_budget(self, fund_id):
        return self.budgets[fund_id[3:]]

    def expense_class(self, code):
        return "ec-" + code


def line(fund, ec):
    return {"fund_code": fund, "expense_class_code": ec}


def budget(*classes):
    return {"name": "B", "statusExpenseClasses": [
        {"expenseClassId": "ec-" + c, "status": s} for c, s in classes]}


def test_ok_pair_passes():
    r = FakeResolver({"F": budget(("GEN", "Active"))})
    assert check_budgets([line("F", "GEN")], r) == []


def test_no_active_budget():
    errs = check_budgets([line("F", "GEN")], FakeResolver({"F": None}))
    assert "no Active budget" in errs[0]


def test_expense_class_missing_or_inactive():
    r = FakeResolver({"F": budget(("GEN", "Inactive"))})
    assert "not Active" in check_budgets([line("F", "GEN")], r)[0]
    assert "not Active" in check_budgets([line("F", "ACC")], r)[0]


def test_duplicate_pairs_reported_once():
    r = FakeResolver({"F": None})
    assert len(check_budgets([line("F", "GEN"), line("F", "GEN")], r)) == 1
