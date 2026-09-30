"""Resolve codes/names to FOLIO ids, cached per run."""


class LookupError_(Exception):
    """A code or name could not be found in the tenant."""


def _q(text):
    if '"' in str(text):
        raise ValueError(f"double quote not allowed in {text!r}")
    return '"%s"' % text


class Resolver:
    def __init__(self, client):
        self.client = client
        self._cache = {}

    def _one(self, path, key, query):
        ck = (path, query)
        if ck not in self._cache:
            hits = self.client.folio_get(
                path, key=key, query_params={"query": query, "limit": 5})
            if not hits:
                raise LookupError_(f"not found: {path} {query}")
            self._cache[ck] = hits[0]
        return self._cache[ck]

    def organization(self, code):
        return self._one("/organizations/organizations", "organizations",
                         "code==" + _q(code))["id"]

    def acquisition_method(self, value):
        return self._one("/orders/acquisition-methods", "acquisitionMethods",
                         "value==" + _q(value))["id"]

    def fund(self, code):
        """Return the fund record (id and code)."""
        return self._one("/finance/funds", "funds", "code==" + _q(code))

    def active_budget(self, fund_id):
        """Return the fund's Active budget for the current fiscal year, or None."""
        ck = ("budget", fund_id)
        if ck not in self._cache:
            from folioclient.exceptions import FolioResourceNotFoundError
            try:
                current = self.client.folio_get(
                    "/finance/funds/%s/budget" % fund_id,
                    query_params={"status": "Active"})
                # only the budget record itself lists statusExpenseClasses
                self._cache[ck] = self.client.folio_get(
                    "/finance/budgets/%s" % current["id"])
            except FolioResourceNotFoundError:
                self._cache[ck] = None
        return self._cache[ck]

    def expense_class(self, code):
        return self._one("/finance/expense-classes", "expenseClasses",
                         "code==" + _q(code))["id"]

    def location(self, code):
        return self._one("/locations", "locations", "code==" + _q(code))["id"]

    def material_type(self, name):
        return self._one("/material-types", "mtypes", "name==" + _q(name))["id"]

    def identifier_type(self, name):
        return self._one("/identifier-types", "identifierTypes",
                         "name==" + _q(name))["id"]
