import pytest

from folio_orders_loader.builder import build_order
from folio_orders_loader.loader import load
from folio_orders_loader.records import group_by_po, validate_line


class FakeClient:
    """Answers lookups with ids derived from the query; records POSTs."""

    def __init__(self, existing=()):
        self.existing = set(existing)
        self.posted = []

    def folio_get(self, path, key=None, query_params=None):
        query = query_params["query"]
        value = query.split("==", 1)[1].strip('"')
        if path == "/orders/composite-orders":
            return [{"id": "x"}] if value in self.existing else []
        if path == "/finance/funds":
            return [{"id": "fund-" + value, "code": value}]
        return [{"id": f"{path}:{value}"}]

    def folio_post(self, path, body):
        self.posted.append(body)
        lines = [dict(ln, poLineNumber=f"{body['poNumber']}-{i}")
                 for i, ln in enumerate(body["compositePoLines"], 1)]
        return dict(body, id="new", compositePoLines=lines)


def line(**kw):
    base = {
        "po_number": "P1", "vendor_code": "ebsconet", "title": "T",
        "order_format": "Electronic Resource", "cost": 10.5,
        "currency": "USD", "fund_code": "F", "expense_class_code": "GEN",
        "order_type": "Ongoing", "interval_days": 365,
        "acquisition_method": "Purchase At Vendor System",
        "subscription_to": "2026-12-31",
        "product_ids": [{"value": "1234-5678", "type": "ISSN"}],
    }
    base.update(kw)
    return base


def test_electronic_ongoing_payload():
    from folio_orders_loader.lookups import Resolver
    order = build_order("P1", [line()], Resolver(FakeClient()))
    assert order["workflowStatus"] == "Pending"
    assert order["ongoing"] == {"interval": 365, "isSubscription": True,
                                "manualRenewal": False,
                                "renewalDate": "2026-12-31"}
    pol = order["compositePoLines"][0]
    assert pol["cost"] == {"currency": "USD", "listUnitPriceElectronic": 10.5,
                           "quantityElectronic": 1}
    assert "physical" not in pol
    assert pol["details"]["productIds"][0]["productId"] == "1234-5678"


def test_one_time_has_no_ongoing_block():
    from folio_orders_loader.lookups import Resolver
    order = build_order("P1", [line(order_type="One-Time")],
                        Resolver(FakeClient()))
    assert "ongoing" not in order and order["orderType"] == "One-Time"


def test_physical_needs_material_type_and_sets_quantities():
    assert "material_type required for physical lines" in validate_line(
        line(order_format="Physical Resource"))
    from folio_orders_loader.lookups import Resolver
    pol = build_order("P1", [line(order_format="P/E Mix",
                                  material_type="journal",
                                  location_code="LOC")],
                      Resolver(FakeClient()))["compositePoLines"][0]
    assert pol["cost"]["quantityPhysical"] == 1
    assert pol["cost"]["quantityElectronic"] == 1
    assert pol["locations"][0]["quantityPhysical"] == 1


@pytest.mark.parametrize("po", ["SPIKE-1", "", "A" * 23])
def test_bad_po_number_rejected(po):
    assert any("po_number" in p for p in validate_line(line(po_number=po)))


def test_group_by_po_makes_multiline_and_checks_po_level_fields():
    pos, problems = group_by_po([line(), line(title="U"), line(po_number="P2")])
    assert [len(v) for v in pos.values()] == [2, 1] and not problems
    _, problems = group_by_po([line(), line(interval_days=180)])
    assert "P1" in problems


def test_load_dry_run_then_live_then_rerun_skips():
    client = FakeClient()
    lines = [line(), line(title="U"), line(po_number="P2")]
    assert [r[1] for r in load(client, lines)] == ["dry-run", "dry-run"]
    assert not client.posted
    res = load(client, lines, live=True)
    assert [r[1] for r in res] == ["created", "created"]
    assert res[0][2] == "P1-1,P1-2"
    client.existing = {"P1", "P2"}
    assert [r[1] for r in load(client, lines, live=True)] == ["exists", "exists"]


def test_invalid_po_not_posted():
    client = FakeClient()
    res = load(client, [line(po_number="BAD-1")], live=True)
    assert res[0][1] == "invalid" and not client.posted


def test_description_receipt_status_and_vendor_account():
    from folio_orders_loader.lookups import Resolver
    extra = {"description": "Monthly", "receipt_status": "Receipt Not Required",
             "vendor_account": "12345"}
    pol = build_order("P1", [line(**extra)], Resolver(FakeClient()))["compositePoLines"][0]
    assert pol["poLineDescription"] == "Monthly"
    assert pol["receiptStatus"] == "Receipt Not Required"
    assert pol["vendorDetail"] == {"vendorAccount": "12345"}
    bare = build_order("P1", [line()], Resolver(FakeClient()))["compositePoLines"][0]
    assert not {"poLineDescription", "receiptStatus", "vendorDetail"} & set(bare)


def test_bad_receipt_status_rejected():
    from folio_orders_loader.records import validate_line
    assert any("receipt_status" in p for p in validate_line(line(receipt_status="Done")))


def test_error_message_extracts_folio_errors():
    from folio_orders_loader.loader import error_message
    raw = ('Client error 400\n{"errors": [{"message": "Budget not found", '
           '"code": "budgetExpenseClassNotFound", "parameters": []}]}')
    assert error_message(Exception(raw)) == "Budget not found (budgetExpenseClassNotFound)"
    assert error_message(Exception("boom\n  bad {")) == "boom bad {"


def test_payment_status_and_reference_number():
    from folio_orders_loader.lookups import Resolver
    extra = {"payment_status": "Payment Not Required", "vendor_account": "9",
             "vendor_reference_number": "T-77",
             "vendor_reference_type": "Vendor title number"}
    pol = build_order("P1", [line(**extra)], Resolver(FakeClient()))["compositePoLines"][0]
    assert pol["paymentStatus"] == "Payment Not Required"
    assert pol["vendorDetail"] == {
        "vendorAccount": "9",
        "referenceNumbers": [{"refNumber": "T-77", "refNumberType": "Vendor title number"}]}


def test_bad_payment_status_and_reference_type_rejected():
    assert any("payment_status" in p for p in validate_line(line(payment_status="Paid")))
    assert any("vendor_reference_type" in p
               for p in validate_line(line(vendor_reference_number="1")))
    orphan = line(vendor_reference_type="Vendor title number")
    assert any("without" in p for p in validate_line(orphan))


ADDR = "11111111-2222-4333-8444-555555555555"


def test_po_notes_tags_bill_to_ship_to():
    from folio_orders_loader.lookups import Resolver
    extra = {"notes": "First | Second", "tags": ["migrated", "ebsconet"],
             "bill_to": ADDR, "ship_to": ADDR}
    order = build_order("P1", [line(**extra)], Resolver(FakeClient()))
    assert order["notes"] == ["First", "Second"]
    assert order["tags"] == {"tagList": ["migrated", "ebsconet"]}
    assert order["billTo"] == ADDR and order["shipTo"] == ADDR
    bare = build_order("P1", [line()], Resolver(FakeClient()))
    assert not {"notes", "tags", "billTo", "shipTo"} & set(bare)


def test_bill_to_must_be_uuid_and_po_level_must_agree():
    assert any("bill_to" in p for p in validate_line(line(bill_to="Main Library")))
    _, problems = group_by_po([line(notes="a"), line(notes="b")])
    assert any("notes" in m for m in problems["P1"])
