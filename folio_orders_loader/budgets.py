"""Pre-flight check that each fund / expense class pair has an Active budget."""
from .records import fund_list


def check_budgets(lines, r):
    """Return error strings for fund / expense class pairs FOLIO would reject.

    FOLIO answers budgetExpenseClassNotFound (400) when the fund has no Active
    budget for the current fiscal year, or the budget does not list the expense
    class as Active. Lookup failures are left to build_order to report.
    """
    errors = []
    seen = set()
    pairs = [(f["code"], f["expense_class_code"])
             for ln in lines for f in fund_list(ln)]
    for pair in pairs:
        if pair in seen:
            continue
        seen.add(pair)
        fund = r.fund(pair[0])
        budget = r.active_budget(fund["id"])
        if budget is None:
            errors.append("fund %s has no Active budget for the current fiscal year"
                          % pair[0])
            continue
        ec_id = r.expense_class(pair[1])
        active = {e["expenseClassId"] for e in budget.get("statusExpenseClasses") or []
                  if e.get("status") == "Active"}
        if ec_id not in active:
            errors.append("fund %s: expense class %s is not Active on its budget %s"
                          % (pair[0], pair[1], budget.get("name", "")))
    return errors
