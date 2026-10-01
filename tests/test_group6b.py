import pytest

from folio_orders_loader.builder import build_order
from folio_orders_loader.loader import load
from folio_orders_loader.lookups import LookupError_, Resolver
from folio_orders_loader.records import validate_line

from test_builder import FakeClient, line
from test_funds_locations import pol

UUID = "11111111-2222-3333-4444-555555555555"


def test_receiving_dates():
    p = pol(order_format="P/E Mix", material_type="journal",
            expected_activation="2026-01-02", activation_due=14,
            receipt_due="2026-03-04")
    assert p["eresource"]["expectedActivation"] == "2026-01-02T00:00:00.000+00:00"
    assert p["eresource"]["activationDue"] == 14
    assert p["physical"]["receiptDue"] == "2026-03-04T00:00:00.000+00:00"


def test_activation_due_validated():
    assert any("activation_due" in m for m in validate_line({"activation_due": "x"}))


def test_po_level_keys():
    order = build_order("P1", [line(po_number_prefix="A", po_number_suffix="Z",
                                    manual_po=True, re_encumber=True,
                                    assigned_to=UUID)], Resolver(FakeClient()))
    assert (order["poNumberPrefix"], order["poNumberSuffix"]) == ("A", "Z")
    assert order["manualPo"] is True and order["reEncumber"] is True
    assert order["assignedTo"] == UUID
    assert "manualPo" not in build_order("P1", [line()], Resolver(FakeClient()))


def test_assigned_to_must_be_uuid():
    assert any("assigned_to" in m for m in validate_line({"assigned_to": "bob"}))


class AddressClient(FakeClient):
    def folio_get(self, path, key=None, query_params=None):
        if path == "/settings/entries":
            return [{"id": UUID, "value": {"name": "Main Library", "address": "x"}}]
        return super().folio_get(path, key, query_params)


def test_address_lookup_by_name_and_uuid():
    r = Resolver(AddressClient())
    assert r.address("main library") == UUID
    assert r.address(UUID) == UUID
    with pytest.raises(LookupError_):
        r.address("Nowhere")
    order = build_order("P1", [line(bill_to="Main Library", ship_to=UUID)], r)
    assert order["billTo"] == UUID and order["shipTo"] == UUID


class OpenClient(FakeClient):
    fail_put = False

    def folio_get(self, path, key=None, query_params=None):
        if path == "/orders/composite-orders/new":
            return {"id": "new", "workflowStatus": "Pending"}
        return super().folio_get(path, key, query_params)

    def folio_put(self, path, body):
        if self.fail_put:
            raise RuntimeError('x {"errors":[{"message":"no budget","code":"fundCannotBePaid"}]}')
        self.put = body


def test_open_orders():
    c = OpenClient()
    res = load(c, [line()], live=True, open_orders=True)
    assert res[0][1] == "opened" and c.put["workflowStatus"] == "Open"


def test_open_failure_reported():
    c = OpenClient()
    c.fail_put = True
    res = load(c, [line()], live=True, open_orders=True)
    assert res[0][1] == "open-error" and "no budget" in res[0][2]


def test_no_open_by_default():
    assert load(OpenClient(), [line()], live=True)[0][1] == "created"
